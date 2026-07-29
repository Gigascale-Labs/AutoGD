"""Run the frozen static model with the separate reparameterised inputs."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt

from model import automation_threshold, evaluate
from run_model import _grid, _validate_case


ROOT = Path(__file__).resolve().parent
PARAMETER_PATH = ROOT / "reparameterized_parameters.json"
OUTPUT_DIRECTORY = ROOT / "outputs"
RESULT_PATH = OUTPUT_DIRECTORY / "reparameterized_results.json"
FIGURE_PATH = OUTPUT_DIRECTORY / "reparameterized_figure.png"


def _load_configuration() -> tuple[dict[str, Any], dict[str, float]]:
    with PARAMETER_PATH.open("r", encoding="utf-8") as handle:
        configuration = json.load(handle)
    grid = configuration["automation_grid"]
    if grid["points"] < 2 or grid["minimum"] != 0.0 or grid["maximum"] != 1.0:
        raise ValueError("the automation grid must span [0, 1] with at least two points")
    parameters = {key: float(value) for key, value in configuration["case"].items()}
    if set(parameters) != {"A", "K", "L", "sigma"}:
        raise ValueError("the reparameterised case must contain exactly A, K, L, and sigma")
    return grid, parameters


def _write_results(parameters: dict[str, float], threshold: float, results: list[dict[str, float | int]]) -> None:
    payload = {
        "case": "reparameterized",
        "parameters": parameters,
        "threshold": threshold,
        "results": results,
    }
    with RESULT_PATH.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, allow_nan=False)
        handle.write("\n")


def _plot(results: list[dict[str, float | int]]) -> None:
    phi = [float(row["phi"]) for row in results]
    output = [float(row["Y"]) for row in results]
    wage_bill = [float(row["wage_bill"]) for row in results]
    capital_income = [float(row["capital_income"]) for row in results]
    figure, axis = plt.subplots(figsize=(7, 4.8))
    axis.plot(phi, output, color="blue", linewidth=2, label="Output $Y$")
    axis.fill_between(phi, wage_bill, color="#a9d9a5", alpha=0.65, label="Wage bill $wL$")
    axis.fill_between(phi, wage_bill, output, color="#f5a3a3", alpha=0.65, label="Return on capital $RK$")
    axis.set_title("Static equilibrium under rising automation")
    axis.set_xlabel("Fraction $\\Phi(I)$ of automated tasks")
    axis.set_ylabel("Output and factor payments")
    axis.set_xlim(0.0, 1.0)
    axis.grid(alpha=0.35)
    axis.legend(loc="best")
    figure.tight_layout()
    figure.savefig(FIGURE_PATH, dpi=180)
    plt.close(figure)


def main() -> int:
    try:
        grid_parameters, parameters = _load_configuration()
        OUTPUT_DIRECTORY.mkdir(exist_ok=True)
        phi_grid = _grid(grid_parameters)
        threshold = automation_threshold(parameters)
        results = [evaluate(phi, parameters) for phi in phi_grid]
        _validate_case("reparameterized", parameters, threshold, results)
        _write_results(parameters, threshold, results)
        _plot(results)
    except Exception as error:
        print(f"reparameterized model run failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
