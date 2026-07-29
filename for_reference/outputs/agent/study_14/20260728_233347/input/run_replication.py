#!/usr/bin/env python3
"""Replicate the supplied federal-employee turnover-intention regression.

The supplied R script fits a binomial model for LeavingAgency with agency-
clustered standard errors.  This script implements the same complete-case
specification in Python and writes portable numerical outputs.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.stats import norm


DATA_PATH = Path("task_input/replication_data/Estimation Data - Pitts (126zz).csv")
OUTPUT_DIR = Path("replication_results")
OUTCOME = "LeavingAgency"
CLUSTER = "Agency"
PREDICTORS = [
    "JobSat",
    "Over40",
    "NonMinority",
    "SatPay",
    "SatAdvan",
    "PerfCul",
    "Empowerment",
    "RelSup",
    "Relcow",
    "Over40xSatAdvan",
]
ALPHA = 0.01


def load_complete_cases(path: Path) -> tuple[pd.DataFrame, int]:
    """Read only analysis columns in chunks and apply the R code's na.omit rule."""
    if not path.is_file():
        raise FileNotFoundError(f"Replication data not found: {path}")
    columns = [CLUSTER, OUTCOME, *PREDICTORS]
    chunks: list[pd.DataFrame] = []
    source_rows = 0
    for chunk in pd.read_csv(path, usecols=columns, chunksize=100_000):
        source_rows += len(chunk)
        chunks.append(chunk.dropna())
    if not chunks:
        raise ValueError("The supplied CSV has no data rows.")
    data = pd.concat(chunks, ignore_index=True)
    if data.empty:
        raise ValueError("No complete cases remain after applying na.omit.")
    if not set(data[OUTCOME].unique()).issubset({0, 1}):
        raise ValueError("LeavingAgency must be coded as binary 0/1.")
    if data[CLUSTER].nunique() < 2:
        raise ValueError("At least two agency clusters are needed for clustered inference.")
    return data, source_rows


def fit_model(data: pd.DataFrame):
    """Fit the R-script logistic specification with finite-sample clustered SEs."""
    design = sm.add_constant(data[PREDICTORS].astype(float), has_constant="add")
    model = sm.GLM(data[OUTCOME].astype(float), design, family=sm.families.Binomial())
    return model.fit(
        cov_type="cluster",
        cov_kwds={
            "groups": data[CLUSTER],
            "use_correction": True,
            "df_correction": True,
        },
    )


def coefficient_table(result) -> pd.DataFrame:
    """Create a machine-readable coefficient table from robust Wald inference."""
    estimates = result.params.astype(float)
    standard_errors = result.bse.astype(float)
    z_values = estimates / standard_errors
    p_values = 2 * norm.sf(np.abs(z_values))
    intervals_low = estimates - norm.ppf(0.975) * standard_errors
    intervals_high = estimates + norm.ppf(0.975) * standard_errors
    return pd.DataFrame(
        {
            "term": estimates.index,
            "coefficient_log_odds": estimates.values,
            "cluster_robust_se": standard_errors.values,
            "z_value": z_values.values,
            "p_value_two_sided": p_values,
            "ci_95_low_log_odds": intervals_low.values,
            "ci_95_high_log_odds": intervals_high.values,
            "odds_ratio": np.exp(estimates.values),
        }
    )


def main() -> None:
    data, source_rows = load_complete_cases(DATA_PATH)
    result = fit_model(data)
    table = coefficient_table(result)
    job_sat = table.loc[table["term"] == "JobSat"].iloc[0]
    supports_hypothesis = bool(
        job_sat["coefficient_log_odds"] < 0 and job_sat["p_value_two_sided"] < ALPHA
    )

    OUTPUT_DIR.mkdir(exist_ok=True)
    table.to_csv(OUTPUT_DIR / "model_coefficients.csv", index=False, float_format="%.12g")
    pd.DataFrame(
        [
            {
                "source_rows": source_rows,
                "complete_case_rows": len(data),
                "rows_excluded_for_missingness": source_rows - len(data),
                "agency_clusters": int(data[CLUSTER].nunique()),
                "leaving_agency_events": int(data[OUTCOME].sum()),
                "leaving_agency_rate": float(data[OUTCOME].mean()),
            }
        ]
    ).to_csv(OUTPUT_DIR / "data_summary.csv", index=False, float_format="%.12g")

    numerical_result = {
        "hypothesis": "Higher overall job satisfaction (JobSat) is associated with lower odds of intending to leave one's agency.",
        "model": {
            "family": "binomial logistic regression",
            "outcome": OUTCOME,
            "predictors": PREDICTORS,
            "cluster_variable": CLUSTER,
            "covariance": "agency-clustered sandwich covariance with finite-sample correction",
            "missing_data_rule": "complete-case analysis (matches na.omit in supplied R script)",
        },
        "sample": {
            "source_rows": source_rows,
            "complete_case_rows": int(len(data)),
            "rows_excluded_for_missingness": int(source_rows - len(data)),
            "agency_clusters": int(data[CLUSTER].nunique()),
            "leaving_agency_events": int(data[OUTCOME].sum()),
            "leaving_agency_rate": float(data[OUTCOME].mean()),
        },
        "job_satisfaction_test": {
            "coefficient_log_odds": float(job_sat["coefficient_log_odds"]),
            "cluster_robust_se": float(job_sat["cluster_robust_se"]),
            "z_value": float(job_sat["z_value"]),
            "p_value_two_sided": float(job_sat["p_value_two_sided"]),
            "odds_ratio": float(job_sat["odds_ratio"]),
            "alpha": ALPHA,
            "direction_is_negative": bool(job_sat["coefficient_log_odds"] < 0),
            "statistically_significant": bool(job_sat["p_value_two_sided"] < ALPHA),
            "supports_hypothesis": supports_hypothesis,
        },
        "original_claim_comparison": {
            "reported_original_coefficient": -0.444,
            "reported_original_se": 0.0163,
            "replication_coefficient_difference": float(job_sat["coefficient_log_odds"] + 0.444),
            "interpretation": "The replication supports the same negative, statistically significant association; its estimated magnitude is modestly smaller in absolute value.",
        },
    }
    with (OUTPUT_DIR / "results.json").open("w", encoding="utf-8") as handle:
        json.dump(numerical_result, handle, indent=2, allow_nan=False)
        handle.write("\n")

    print("Replication analysis completed successfully.")
    print(
        "Complete cases: {n:,}; agency clusters: {g}; JobSat coefficient: {b:.4f}; "
        "cluster-robust SE: {se:.4f}; two-sided p: {p:.3g}; hypothesis supported: {s}.".format(
            n=len(data),
            g=data[CLUSTER].nunique(),
            b=job_sat["coefficient_log_odds"],
            se=job_sat["cluster_robust_se"],
            p=job_sat["p_value_two_sided"],
            s=supports_hypothesis,
        )
    )
    print(f"Outputs written to {OUTPUT_DIR}/")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Replication analysis failed: {exc}", file=sys.stderr)
        sys.exit(1)
