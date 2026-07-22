import json
from dataclasses import dataclass, asdict
from pathlib import Path

import csv
import numpy as np


BASE_DIR = Path(__file__).resolve().parent
ARTIFACT_DIR = BASE_DIR / "artifacts"
ARTIFACT_DIR.mkdir(exist_ok=True)


@dataclass
class ModelParams:
    K: float
    L: float
    sigma: float
    A: float = 1.0


def threshold(K: float, L: float) -> float:
    ratio = K / L
    return ratio / (1.0 + ratio)


def region1_condition(phi: float, K: float, L: float) -> bool:
    return (K / L) > (phi / (1.0 - phi)) if phi < 1.0 else False


def compute_values(phi: float, params: ModelParams):
    K, L, sigma, A = params.K, params.L, params.sigma, params.A
    th = threshold(K, L)
    if phi < 1.0 and region1_condition(phi, K, L):
        y = A * ((K ** ((sigma - 1.0) / sigma)) * (phi ** (1.0 / sigma)) + (L ** ((sigma - 1.0) / sigma)) * ((1.0 - phi) ** (1.0 / sigma))) ** (sigma / (sigma - 1.0))
        w = A * ((sigma - 1.0) / sigma) * (y ** (1.0 / sigma)) * (L ** (-1.0 / sigma)) * ((1.0 - phi) ** (1.0 / sigma))
        r = A * ((sigma - 1.0) / sigma) * (y ** (1.0 / sigma)) * (K ** (-1.0 / sigma)) * (phi ** (1.0 / sigma))
        region = 1
    else:
        y = A * (K + L)
        w = A
        r = A
        region = 2
    wage_bill = w * L
    capital_income = r * K
    return {
        "phi": phi,
        "threshold": th,
        "region": region,
        "Y": y,
        "w": w,
        "R": r,
        "wage_bill": wage_bill,
        "capital_income": capital_income,
        "identity_gap": y - (wage_bill + capital_income),
    }


def run_case(name: str, params: ModelParams):
    phis = np.linspace(0.0, 1.0, 501)
    rows = []
    for phi in phis:
        if phi == 1.0:
            phi_eval = np.nextafter(1.0, 0.0)
        else:
            phi_eval = phi
        rows.append(compute_values(phi_eval, params))
    return rows


def save_outputs(case_name: str, params: ModelParams, rows):
    csv_path = ARTIFACT_DIR / f"{case_name}_results.csv"
    json_path = ARTIFACT_DIR / f"{case_name}_results.json"

    with csv_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    with json_path.open("w") as f:
        json.dump({"params": asdict(params), "results": rows}, f, indent=2)

    return {"csv": str(csv_path), "json": str(json_path)}


def main():
    cases = {
        "left": ModelParams(K=1, L=1, sigma=0.5, A=1.0),
        "right": ModelParams(K=10, L=1, sigma=0.2, A=1.0),
    }
    summary = {}
    for name, params in cases.items():
        rows = run_case(name, params)
        summary[name] = save_outputs(name, params, rows)
    with (ARTIFACT_DIR / "execution_summary.json").open("w") as f:
        json.dump(summary, f, indent=2)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
