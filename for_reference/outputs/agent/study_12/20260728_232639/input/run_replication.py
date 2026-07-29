#!/usr/bin/env python3
"""Reproduce the supplied Anderson (2011) replication-code regressions.

Run from the study workspace with ``python run_replication.py``.  The script
uses only the supplied Stata data and writes all generated artifacts below
``output/``.  The confirmatory analysis follows the uncommented "final
analysis" block in the supplied .do file.  In Stata, variables in
``stcode##caste`` without an ``i.`` prefix are continuous; therefore this is
estimated here as state code, caste code, and their numeric interaction.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf


DATA_PATH = Path("task_input/replication_data/analysis_data.dta")
OUTPUT_DIR = Path("output")
REQUIRED_COLUMNS = {
    "raw_inc_per_acre", "net_inc_per_acre", "literate_hh", "land_owned",
    "locaste_land_v", "stcode", "caste", "vill_id",
}
FORMULA_TAIL = "literate_hh + land_owned + locaste_land_v + stcode * caste"


def fit_model(data: pd.DataFrame, outcome: str, analysis_name: str) -> tuple[dict, list[dict]]:
    """Fit OLS with Stata-style cluster-robust inference by village."""
    variables = [outcome, "literate_hh", "land_owned", "locaste_land_v", "stcode", "caste", "vill_id"]
    used = data.dropna(subset=variables).copy()
    if used.empty:
        raise ValueError(f"{analysis_name}: no complete observations")
    clusters = int(used["vill_id"].nunique())
    if clusters < 2:
        raise ValueError(f"{analysis_name}: fewer than two village clusters")

    model = smf.ols(f"{outcome} ~ {FORMULA_TAIL}", data=used).fit(
        cov_type="cluster",
        cov_kwds={"groups": used["vill_id"], "use_correction": True, "df_correction": True},
        use_t=True,
    )
    ci = model.conf_int(alpha=0.05)
    rows = []
    for term in model.params.index:
        rows.append({
            "analysis": analysis_name,
            "outcome": outcome,
            "term": term,
            "coefficient": float(model.params[term]),
            "robust_se_clustered_by_village": float(model.bse[term]),
            "t_statistic": float(model.tvalues[term]),
            "p_value": float(model.pvalues[term]),
            "ci_95_lower": float(ci.loc[term, 0]),
            "ci_95_upper": float(ci.loc[term, 1]),
            "n_observations": int(model.nobs),
            "n_village_clusters": clusters,
        })
    focal = next(row for row in rows if row["term"] == "locaste_land_v")
    fit = {
        "analysis": analysis_name,
        "outcome": outcome,
        "n_observations": int(model.nobs),
        "n_village_clusters": clusters,
        "r_squared": float(model.rsquared),
        "adjusted_r_squared": float(model.rsquared_adj),
        "aic": float(model.aic),
        "bic": float(model.bic),
        "log_likelihood": float(model.llf),
        "focal_result": focal,
    }
    return fit, rows


def main() -> None:
    if not DATA_PATH.is_file():
        raise FileNotFoundError(f"Required data file not found: {DATA_PATH}")
    data = pd.read_stata(DATA_PATH, convert_categoricals=False)
    missing = sorted(REQUIRED_COLUMNS.difference(data.columns))
    if missing:
        raise ValueError(f"Data are missing required columns: {', '.join(missing)}")

    analyses = [
        ("confirmatory_raw_income_all_states", data, "raw_inc_per_acre"),
        ("exploratory_net_income_all_states", data, "net_inc_per_acre"),
        ("sensitivity_raw_income_states_2_15", data.loc[data["stcode"].isin([2, 15])], "raw_inc_per_acre"),
    ]
    fit_rows, coefficient_rows = [], []
    for name, subset, outcome in analyses:
        fit, rows = fit_model(subset, outcome, name)
        fit_rows.append(fit)
        coefficient_rows.extend(rows)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(coefficient_rows).to_csv(OUTPUT_DIR / "regression_coefficients.csv", index=False)
    pd.DataFrame([{k: v for k, v in row.items() if k != "focal_result"} for row in fit_rows]).to_csv(
        OUTPUT_DIR / "model_fit_statistics.csv", index=False
    )
    confirmatory = fit_rows[0]["focal_result"]
    conclusion = (
        "supported" if confirmatory["coefficient"] > 0 and confirmatory["p_value"] < 0.01
        else "not_supported"
    )
    results = {
        "data_file": str(DATA_PATH),
        "input_rows": int(len(data)),
        "model_specification": "OLS with village-clustered robust standard errors; "
                               "raw_inc_per_acre ~ literate_hh + land_owned + locaste_land_v + stcode + caste + stcode:caste.",
        "interpretive_choice": "The supplied .do file writes stcode##caste without i. prefixes. "
                                "This script treats both as continuous numeric variables, matching Stata factor-variable syntax.",
        "confirmatory_hypothesis_test": {
            "term": "locaste_land_v",
            "null_hypothesis": "coefficient <= 0",
            "alternative_hypothesis": "coefficient > 0",
            "decision_rule": "Positive coefficient and two-sided cluster-robust p < 0.01, matching the stated original claim.",
            "result": confirmatory,
            "conclusion": conclusion,
        },
        "all_models": fit_rows,
    }
    with (OUTPUT_DIR / "replication_results.json").open("w", encoding="utf-8") as handle:
        json.dump(results, handle, indent=2, allow_nan=False)

    print("Replication analysis completed successfully.")
    print(f"Input rows: {len(data)}; confirmatory complete cases: {confirmatory['n_observations']}; village clusters: {confirmatory['n_village_clusters']}")
    print("locaste_land_v: "
          f"b={confirmatory['coefficient']:.3f}, SE={confirmatory['robust_se_clustered_by_village']:.3f}, "
          f"t={confirmatory['t_statistic']:.3f}, p={confirmatory['p_value']:.4f}")
    print(f"Hypothesis conclusion: {conclusion}")
    print(f"Results written to: {OUTPUT_DIR}")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"Replication analysis failed: {error}", file=sys.stderr)
        sys.exit(1)
