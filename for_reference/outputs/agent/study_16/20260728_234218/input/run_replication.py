#!/usr/bin/env python3
"""Replicate the association between COVID-19 lockdowns and transit mobility.

Run from the workspace (or any directory): ``python run_replication.py``.
The script reads the supplied CSV relative to its own location and writes
machine-readable estimates, a coefficient table, and a diagnostic figure to
``results/``.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

# Keep matplotlib's cache writable without creating an analysis artifact.
ROOT = Path(__file__).resolve().parent
os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "replication_matplotlib"))

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf


DATA_PATH = ROOT / "task_input" / "replication_data" / "replicationDataset_Malik2020_with.year.csv"
OUTPUT_DIR = ROOT / "results"
REQUIRED_COLUMNS = {"city", "date", "CMRT_transit", "lockdown"}


def main() -> None:
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Required dataset not found: {DATA_PATH}")

    data = pd.read_csv(DATA_PATH)
    missing_columns = REQUIRED_COLUMNS.difference(data.columns)
    if missing_columns:
        raise ValueError(f"Dataset is missing required columns: {sorted(missing_columns)}")

    data["date_parsed"] = pd.to_datetime(data["date"], format="%m/%d/%Y", errors="coerce")
    for column in ("CMRT_transit", "lockdown"):
        data[column] = pd.to_numeric(data[column], errors="coerce")
    analysis_data = data.dropna(subset=["city", "date_parsed", "CMRT_transit", "lockdown"]).copy()
    if analysis_data.empty:
        raise ValueError("No complete observations remain for the focal model.")
    if not analysis_data["lockdown"].isin([0, 1]).all():
        raise ValueError("The lockdown variable must be coded 0/1 for this replication.")

    # Centered calendar time is numerically stable and leaves the time and
    # lockdown coefficients unchanged from Stata's uncentered date variable.
    first_date = analysis_data["date_parsed"].min()
    analysis_data["day_index"] = (analysis_data["date_parsed"] - first_date).dt.days

    # Corresponds to: xtmixed CMRT_transit date2 lockdown || city:, var
    # Stata's default estimation method for xtmixed is REML.
    model = smf.mixedlm(
        "CMRT_transit ~ day_index + lockdown",
        analysis_data,
        groups=analysis_data["city"],
        re_formula="1",
    )
    fit = model.fit(reml=True, method="lbfgs", maxiter=500, disp=False)
    if not fit.converged:
        raise RuntimeError("Mixed-effects model did not converge.")

    confidence_intervals = fit.conf_int(alpha=0.05)
    fixed_effects = ["Intercept", "day_index", "lockdown"]
    coefficient_table = pd.DataFrame(
        {
            "term": fixed_effects,
            "estimate": [float(fit.params[term]) for term in fixed_effects],
            "standard_error": [float(fit.bse[term]) for term in fixed_effects],
            "z_statistic": [float(fit.tvalues[term]) for term in fixed_effects],
            "p_value": [float(fit.pvalues[term]) for term in fixed_effects],
            "ci_95_lower": [float(confidence_intervals.loc[term, 0]) for term in fixed_effects],
            "ci_95_upper": [float(confidence_intervals.loc[term, 1]) for term in fixed_effects],
        }
    )
    lockdown_row = coefficient_table.loc[coefficient_table["term"] == "lockdown"].iloc[0]
    magnitude_ci = sorted([-float(lockdown_row["ci_95_upper"]), -float(lockdown_row["ci_95_lower"])])
    original_magnitude_ci = [20.0, 27.0]
    overlaps_original_ci = max(magnitude_ci[0], original_magnitude_ci[0]) <= min(
        magnitude_ci[1], original_magnitude_ci[1]
    )
    supports_hypothesis = bool(lockdown_row["estimate"] < 0 and lockdown_row["p_value"] < 0.05)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    coefficient_table.to_csv(OUTPUT_DIR / "coefficient_table.csv", index=False)

    daily = analysis_data.groupby(["day_index", "lockdown"], as_index=False)["CMRT_transit"].mean()
    fig, ax = plt.subplots(figsize=(8, 5))
    labels = {0: "No lockdown", 1: "Lockdown"}
    colors = {0: "#4C78A8", 1: "#E45756"}
    for status in (0, 1):
        subset = daily.loc[daily["lockdown"] == status]
        ax.plot(subset["day_index"], subset["CMRT_transit"], marker="o", linewidth=1.8,
                label=labels[status], color=colors[status])
    ax.set_xlabel(f"Days since {first_date.date().isoformat()}")
    ax.set_ylabel("Transit mobility change from baseline (%)")
    ax.set_title("Observed mean transit mobility by lockdown status")
    ax.legend(frameon=False)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "transit_mobility_by_lockdown.png", dpi=180)
    plt.close(fig)

    results = {
        "analysis": "Random-intercept linear mixed model (REML): CMRT_transit ~ day_index + lockdown + (1 | city)",
        "dataset": {
            "path": str(DATA_PATH.relative_to(ROOT)),
            "n_observations": int(len(analysis_data)),
            "n_cities": int(analysis_data["city"].nunique()),
            "date_start": first_date.date().isoformat(),
            "date_end": analysis_data["date_parsed"].max().date().isoformat(),
        },
        "lockdown_effect": {
            "estimate_percentage_points": float(lockdown_row["estimate"]),
            "ci_95_percentage_points": [float(lockdown_row["ci_95_lower"]), float(lockdown_row["ci_95_upper"])],
            "p_value": float(lockdown_row["p_value"]),
            "estimate_decrease_magnitude_percentage_points": -float(lockdown_row["estimate"]),
            "ci_95_decrease_magnitude_percentage_points": magnitude_ci,
        },
        "hypothesis_test": {
            "null": "The adjusted lockdown coefficient is zero or positive.",
            "alternative": "The adjusted lockdown coefficient is negative.",
            "alpha": 0.05,
            "decision": "supported" if supports_hypothesis else "not_supported",
        },
        "comparison_with_original_claim": {
            "original_claim_decrease_magnitude_percentage_points": 23.0,
            "original_claim_ci_95_magnitude_percentage_points": original_magnitude_ci,
            "replication_ci_overlaps_original_ci": overlaps_original_ci,
        },
        "interpretive_choice": (
            "The supplied Stata file requests an unseeded 5% random sample. The primary analysis uses all "
            "available complete observations because an unseeded draw cannot be reproduced and discarding 95% "
            "of the supplied replication data is not needed for the specified mixed model."
        ),
    }
    with (OUTPUT_DIR / "replication_results.json").open("w", encoding="utf-8") as handle:
        json.dump(results, handle, indent=2)
        handle.write("\n")

    print(
        "Replication completed: "
        f"n={len(analysis_data)}, cities={analysis_data['city'].nunique()}, "
        f"lockdown effect={lockdown_row['estimate']:.2f} percentage points "
        f"(95% CI {lockdown_row['ci_95_lower']:.2f}, {lockdown_row['ci_95_upper']:.2f}; "
        f"p={lockdown_row['p_value']:.3g}); decision={results['hypothesis_test']['decision']}."
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"Replication failed: {error}", file=sys.stderr)
        raise
