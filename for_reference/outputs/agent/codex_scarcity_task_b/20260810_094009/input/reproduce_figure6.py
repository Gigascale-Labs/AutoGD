#!/usr/bin/env python3
"""Reproduce Figure 6 of the supplied paper's static scarcity-of-labor model.

Run from the workspace root:
    python reproduce_figure6.py

The script uses no data files.  It writes results/figure6_results.csv,
results/figure6_parameters.json, and results/figure6_reproduction.svg.
"""

from __future__ import annotations

import csv
import json
import math
import sys
from pathlib import Path


# Figure 6 parameters, kept separate from the equilibrium calculations.
PARAMETER_CASES = {
    "equal_endowments": {"K": 1.0, "L": 1.0, "sigma": 0.5, "A": 1.0},
    "abundant_capital": {"K": 10.0, "L": 1.0, "sigma": 0.2, "A": 1.0},
}
N_AUTOMATION_POINTS = 1001


def region_one(phi: float, K: float, L: float, sigma: float, A: float) -> tuple[float, float, float]:
    """Equations (4), (6), and (7), for 0 < phi < K/(K+L)."""
    power = (sigma - 1.0) / sigma
    ces_sum = K**power * phi ** (1.0 / sigma) + L**power * (1.0 - phi) ** (1.0 / sigma)
    output = A * ces_sum ** (sigma / (sigma - 1.0))
    # Equations (6)-(7): A is raised to (sigma-1)/sigma.
    # This also follows by differentiating equation (4).
    productivity_term = A ** ((sigma - 1.0) / sigma) * output ** (1.0 / sigma)
    capital_return = productivity_term * K ** (-1.0 / sigma) * phi ** (1.0 / sigma)
    wage = productivity_term * L ** (-1.0 / sigma) * (1.0 - phi) ** (1.0 / sigma)
    return output, wage, capital_return


def equilibrium(phi: float, parameters: dict[str, float]) -> dict[str, float | str]:
    """Static equilibrium from Lemma 1, including endpoint limits at phi=0."""
    K, L, sigma, A = (parameters[key] for key in ("K", "L", "sigma", "A"))
    threshold = K / (K + L)  # Equation (3), expressed in phi = Phi(I).

    if phi == 0.0:
        # Limit of equations (4), (6), and (7): no task is capital-automatable.
        output, wage, capital_return, regime = A * L, A, 0.0, "region_1_labor_scarce"
    elif phi < threshold:
        output, wage, capital_return = region_one(phi, K, L, sigma, A)
        regime = "region_1_labor_scarce"
    else:
        # Equation (5): w = R = A in Region 2.
        output, wage, capital_return, regime = A * (K + L), A, A, "region_2_labor_not_scarce"

    wage_bill = wage * L
    capital_income = capital_return * K
    return {
        "phi": phi,
        "output": output,
        "wage": wage,
        "capital_return": capital_return,
        "wage_bill": wage_bill,
        "capital_income": capital_income,
        "regime": regime,
        "threshold_phi": threshold,
    }


def validate(case_name: str, rows: list[dict[str, float | str]], parameters: dict[str, float]) -> dict[str, float | str]:
    """Fail loudly if model identities or Figure 6 qualitative implications fail."""
    K, L, sigma, A = (parameters[key] for key in ("K", "L", "sigma", "A"))
    threshold = K / (K + L)
    accounting_error = max(abs(float(row["output"]) - float(row["wage_bill"]) - float(row["capital_income"])) for row in rows)
    if accounting_error > 1e-9:
        raise ValueError(f"{case_name}: factor-income accounting error {accounting_error}")

    below = region_one(math.nextafter(threshold, 0.0), K, L, sigma, A)
    region_two_output = A * (K + L)
    continuity_error = max(abs(value - A) for value in below[1:])
    continuity_error = max(continuity_error, abs(below[0] - region_two_output))
    if continuity_error > 1e-6:
        raise ValueError(f"{case_name}: threshold continuity error {continuity_error}")

    outputs = [float(row["output"]) for row in rows]
    if min(current - previous for previous, current in zip(outputs, outputs[1:])) < -1e-10:
        raise ValueError(f"{case_name}: output is not weakly increasing over automation")
    if abs(float(rows[0]["output"]) - A * L) > 1e-12 or abs(float(rows[-1]["output"]) - A * (K + L)) > 1e-12:
        raise ValueError(f"{case_name}: endpoint output identity failed")

    return {
        "case": case_name,
        "threshold_phi": threshold,
        "max_accounting_error": accounting_error,
        "threshold_continuity_error": continuity_error,
        "initial_output": float(rows[0]["output"]),
        "full_automation_output": float(rows[-1]["output"]),
        "output_monotonic": "passed",
    }


def write_csv(path: Path, results: dict[str, list[dict[str, float | str]]]) -> None:
    fields = ["case", "phi", "output", "wage", "capital_return", "wage_bill", "capital_income", "regime", "threshold_phi"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for case_name, rows in results.items():
            for row in rows:
                writer.writerow({"case": case_name, **row})


def make_figure(path: Path, results: dict[str, list[dict[str, float | str]]]) -> None:
    """Write a portable SVG plot using only Python's standard library."""
    width, height, top, bottom, panel_width, gap = 1200, 540, 70, 105, 480, 85
    plot_height, lefts = height - top - bottom, (100, 100 + panel_width + gap)
    series = (("output", "Total output", "#222222"), ("wage_bill", "Wage bill", "#1f77b4"), ("capital_income", "Capital returns", "#d62728"))
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">', '<rect width="100%" height="100%" fill="white"/>', '<style>text{font-family:Arial,sans-serif;fill:#222}.tick{font-size:13px}.label{font-size:15px}.title{font-size:18px;font-weight:bold}</style>']
    svg.append(f'<text x="25" y="{top + plot_height / 2}" class="label" transform="rotate(-90 25 {top + plot_height / 2})">Output or factor earnings (A = 1)</text>')
    for left, (case_name, rows) in zip(lefts, results.items()):
        y_limit = max(float(row[key]) for row in rows for key, _, _ in series) * 1.08
        title = "Equal factor endowments" if case_name == "equal_endowments" else "Abundant effective capital"
        p = PARAMETER_CASES[case_name]
        svg += [f'<text x="{left + panel_width / 2}" y="32" text-anchor="middle" class="title">{title}</text>', f'<text x="{left + 8}" y="54" class="tick">K={p["K"]:g}, L={p["L"]:g}, σ={p["sigma"]:g}</text>']
        for tick in range(5):
            value, y = y_limit * tick / 4, top + plot_height * (1 - tick / 4)
            svg += [f'<line x1="{left}" y1="{y:.2f}" x2="{left + panel_width}" y2="{y:.2f}" stroke="#dddddd"/>', f'<text x="{left - 8}" y="{y + 4:.2f}" text-anchor="end" class="tick">{value:.2g}</text>']
        for tick in range(6):
            x = left + panel_width * tick / 5
            svg += [f'<line x1="{x:.2f}" y1="{top + plot_height}" x2="{x:.2f}" y2="{top + plot_height + 5}" stroke="#222"/>', f'<text x="{x:.2f}" y="{top + plot_height + 23}" text-anchor="middle" class="tick">{tick / 5:.1f}</text>']
        svg += [f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_height}" stroke="#222"/>', f'<line x1="{left}" y1="{top + plot_height}" x2="{left + panel_width}" y2="{top + plot_height}" stroke="#222"/>']
        threshold_x = left + panel_width * float(rows[0]["threshold_phi"])
        svg.append(f'<line x1="{threshold_x:.2f}" y1="{top}" x2="{threshold_x:.2f}" y2="{top + plot_height}" stroke="#666" stroke-dasharray="5 4"/>')
        for key, _, color in series:
            points = " ".join(f'{left + panel_width * float(row["phi"]):.2f},{top + plot_height * (1 - float(row[key]) / y_limit):.2f}' for row in rows)
            svg.append(f'<polyline fill="none" stroke="{color}" stroke-width="2.2" points="{points}"/>')
        svg.append(f'<text x="{left + panel_width / 2}" y="{height - 34}" text-anchor="middle" class="label">Fraction of automated tasks, Φ(I)</text>')
        if case_name == "abundant_capital":
            for index, (_, label, color) in enumerate(series):
                y = top + 16 + index * 21
                svg += [f'<line x1="{left + 17}" y1="{y}" x2="{left + 41}" y2="{y}" stroke="{color}" stroke-width="2.2"/>', f'<text x="{left + 47}" y="{y + 5}" class="tick">{label}</text>']
            svg += [f'<line x1="{left + 17}" y1="{top + 79}" x2="{left + 41}" y2="{top + 79}" stroke="#666" stroke-dasharray="5 4"/>', f'<text x="{left + 47}" y="{top + 84}" class="tick">Region threshold</text>']
    path.write_text("\n".join(svg + ['</svg>']), encoding="utf-8")


def main() -> int:
    output_dir = Path("results")
    output_dir.mkdir(exist_ok=True)
    phi_grid = [point / (N_AUTOMATION_POINTS - 1) for point in range(N_AUTOMATION_POINTS)]
    results = {case: [equilibrium(float(phi), parameters) for phi in phi_grid] for case, parameters in PARAMETER_CASES.items()}
    validations = [validate(case, rows, PARAMETER_CASES[case]) for case, rows in results.items()]

    write_csv(output_dir / "figure6_results.csv", results)
    with (output_dir / "figure6_parameters.json").open("w", encoding="utf-8") as handle:
        json.dump({"parameters": PARAMETER_CASES, "automation_grid_points": N_AUTOMATION_POINTS, "validations": validations}, handle, indent=2)
    make_figure(output_dir / "figure6_reproduction.svg", results)

    print("Figure 6 static scarcity-of-labor replication completed.")
    for item in validations:
        print(f"{item['case']}: threshold Phi={item['threshold_phi']:.9g}; accounting error={item['max_accounting_error']:.3e}; monotonic output={item['output_monotonic']}")
    print("Wrote results/figure6_results.csv, results/figure6_parameters.json, and results/figure6_reproduction.svg")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
