"""Run the static Figure 6 model and write numerical and graphical outputs."""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt

from model import automation_threshold, evaluate


ROOT = Path(__file__).resolve().parent
PARAMETER_PATH = ROOT / "parameters.json"
OUTPUT_DIRECTORY = ROOT / "outputs"
ACCOUNTING_TOLERANCE = 1e-10


def _load_parameters() -> dict[str, Any]:
    with PARAMETER_PATH.open("r", encoding="utf-8") as handle:
        parameters = json.load(handle)
    grid = parameters["automation_grid"]
    if grid["points"] < 2 or grid["minimum"] != 0.0 or grid["maximum"] != 1.0:
        raise ValueError("the Figure 6 automation grid must span [0, 1] with at least two points")
    if set(parameters["cases"]) != {"left", "right"}:
        raise ValueError("parameters.json must contain exactly the left and right Figure 6 cases")
    return parameters


def _grid(grid_parameters: dict[str, Any]) -> list[float]:
    lower = float(grid_parameters["minimum"])
    upper = float(grid_parameters["maximum"])
    count = int(grid_parameters["points"])
    step = (upper - lower) / (count - 1)
    return [lower + step * index for index in range(count)]


def _validate_case(case: str, parameters: dict[str, float], threshold: float, results: list[dict[str, float | int]]) -> None:
    if not math.isclose(threshold, parameters["K"] / (parameters["K"] + parameters["L"]), rel_tol=0.0, abs_tol=1e-15):
        raise ArithmeticError(f"{case}: threshold check failed")
    if results[0]["phi"] != 0.0 or results[-1]["phi"] != 1.0:
        raise ArithmeticError(f"{case}: automation grid does not include both endpoints")
    for result in results:
        values = [result[key] for key in ("phi", "Y", "w", "R", "wage_bill", "capital_income", "accounting_error")]
        if not all(math.isfinite(float(value)) for value in values):
            raise ArithmeticError(f"{case}: non-finite numerical result")
        if abs(float(result["accounting_error"])) > ACCOUNTING_TOLERANCE:
            raise ArithmeticError(f"{case}: Y != wage_bill + capital_income at Phi={result['phi']}")
        expected_region = 1 if float(result["phi"]) < threshold else 2
        if result["region"] != expected_region:
            raise ArithmeticError(f"{case}: incorrect scarcity regime at Phi={result['phi']}")
        if result["region"] == 2:
            if not math.isclose(float(result["Y"]), parameters["A"] * (parameters["K"] + parameters["L"]), abs_tol=ACCOUNTING_TOLERANCE):
                raise ArithmeticError(f"{case}: region 2 output check failed")
            if not (math.isclose(float(result["w"]), parameters["A"], abs_tol=ACCOUNTING_TOLERANCE) and math.isclose(float(result["R"]), parameters["A"], abs_tol=ACCOUNTING_TOLERANCE)):
                raise ArithmeticError(f"{case}: region 2 factor-price check failed")


def _write_results(case: str, parameters: dict[str, float], threshold: float, results: list[dict[str, float | int]]) -> None:
    payload = {"case": case, "parameters": parameters, "threshold": threshold, "results": results}
    destination = OUTPUT_DIRECTORY / f"{case}_results.json"
    with destination.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, allow_nan=False)
        handle.write("\n")


def _plot(case_results: dict[str, list[dict[str, float | int]]]) -> None:
    figure, axes = plt.subplots(1, 2, figsize=(12, 4.8), sharex=True)
    titles = {"left": "(a) Equal factor endowments", "right": "(b) Abundant effective capital"}
    for axis, case in zip(axes, ("left", "right")):
        results = case_results[case]
        phi = [float(row["phi"]) for row in results]
        output = [float(row["Y"]) for row in results]
        wage_bill = [float(row["wage_bill"]) for row in results]
        capital_income = [float(row["capital_income"]) for row in results]
        axis.plot(phi, output, color="blue", linewidth=2, label="Output $Y$")
        axis.fill_between(phi, wage_bill, color="#a9d9a5", alpha=0.65, label="Wage bill $wL$")
        axis.fill_between(phi, wage_bill, output, color="#f5a3a3", alpha=0.65, label="Return on capital $RK$")
        axis.set_title(titles[case])
        axis.set_xlabel("Fraction $\\Phi(I)$ of automated tasks")
        axis.set_ylabel("Output and factor payments")
        axis.set_xlim(0.0, 1.0)
        axis.grid(alpha=0.35)
        axis.legend(loc="best")
    figure.suptitle("Figure 6: Static equilibria under rising automation")
    figure.tight_layout()
    figure.savefig(OUTPUT_DIRECTORY / "figure6.png", dpi=180)
    plt.close(figure)


def main() -> int:
    try:
        configuration = _load_parameters()
        OUTPUT_DIRECTORY.mkdir(exist_ok=True)
        phi_grid = _grid(configuration["automation_grid"])
        case_results: dict[str, list[dict[str, float | int]]] = {}
        for case in ("left", "right"):
            case_parameters = {key: float(value) for key, value in configuration["cases"][case].items()}
            threshold = automation_threshold(case_parameters)
            results = [evaluate(phi, case_parameters) for phi in phi_grid]
            _validate_case(case, case_parameters, threshold, results)
            _write_results(case, case_parameters, threshold, results)
            case_results[case] = results
        _plot(case_results)
    except Exception as error:
        print(f"model run failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
