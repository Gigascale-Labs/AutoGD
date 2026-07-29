#!/usr/bin/env python3
"""Replicate the supplied Cohen et al. (2015) ACT-subsidy analysis.

This is a Python translation of the supplied Stata do-file.  The data contain
post-baseline illness episodes; the estimating sample is the CHW-test subset.
Because the do-file constructs a unique household ID for each observation, the
survey variance is calculated as a stratum-centred linearized sandwich with one
PSU per retained row (the same operational assumption documented in the do-file).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy.stats import t as student_t


DATA_PATH = Path("task_input/replication_data/ReplicationData_Cohen_AmEcoRev_2015_2lb5.dta")
OUTPUT_DIR = Path("replication_results")
ALPHA = 0.01


def stata_strpos(series: pd.Series, needle: str) -> pd.Series:
    """Return Stata's 1-based strpos result, retaining missing values."""
    result = series.astype("string").str.find(needle).add(1).astype(float)
    return result.where(series.notna())


def indicator(series: pd.Series, value: float) -> pd.Series:
    """Stata-style binary indicator that is missing when its source is missing."""
    return pd.Series(np.where(series.notna(), (series == value).astype(float), np.nan), index=series.index)


def survey_linearized_covariance(model, strata: pd.Series) -> tuple[np.ndarray, int, int]:
    """Calculate a Taylor-linearized, stratum-centred covariance matrix.

    The supplied code invokes `svyset hh_id [pweight=weight], strata(cu_code)`.
    Its generated `hh_id` is unique, so every fitted row is a singleton PSU.
    """
    x = np.asarray(model.model.exog, dtype=float)
    weights = np.asarray(model.model.weights, dtype=float)
    residuals = np.asarray(model.resid, dtype=float)
    stratum = np.asarray(strata)
    bread = np.linalg.inv(x.T @ (weights[:, None] * x))
    scores = x * (weights * residuals)[:, None]
    meat = np.zeros((x.shape[1], x.shape[1]))
    non_singleton_strata = 0

    for label in np.unique(stratum):
        score = scores[stratum == label]
        n_psu = len(score)
        if n_psu < 2:
            continue
        non_singleton_strata += 1
        centered = score - score.mean(axis=0)
        meat += (n_psu / (n_psu - 1)) * centered.T @ centered

    covariance = bread @ meat @ bread
    design_df = len(residuals) - non_singleton_strata
    return covariance, design_df, non_singleton_strata


def main() -> None:
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Required data file not found: {DATA_PATH}")
    OUTPUT_DIR.mkdir(exist_ok=True)

    data = pd.read_stata(DATA_PATH, convert_categoricals=False)
    required = {
        "drugs_taken_AL", "maltest_chw_voucher_given", "maltest_where", "wave",
        "weight", "cu_code", "ses_hh_items", "ses_toilet_type", "ses_wall_material",
        "ses_no_sheep",
    }
    missing = sorted(required.difference(data.columns))
    if missing:
        raise ValueError(f"Dataset is missing required variables: {', '.join(missing)}")

    data["took_ACT"] = data["drugs_taken_AL"]
    data["act_subsidy"] = np.where(
        data["maltest_chw_voucher_given"].eq(98),
        np.nan,
        data["maltest_chw_voucher_given"].eq(1).astype(float),
    )
    # These reproduce the transformations in the supplied do-file exactly.
    data["refrigerator"] = stata_strpos(data["ses_hh_items"], "3")
    data["mobile"] = stata_strpos(data["ses_hh_items"], "5")
    data["vip_toilet"] = indicator(data["ses_toilet_type"], 2)
    data["composting_toilet"] = indicator(data["ses_toilet_type"], 5)
    data["other_toilet"] = indicator(data["ses_toilet_type"], 8)
    data["stone_wall"] = indicator(data["ses_wall_material"], 1)
    data["cement_wall"] = indicator(data["ses_wall_material"], 7)
    data["num_sheep"] = data["ses_no_sheep"]

    subset = data.loc[(data["maltest_where"] == 1) & (data["wave"] != 0)].copy()
    formula = (
        "took_ACT ~ act_subsidy + C(cu_code) + refrigerator + mobile + vip_toilet + "
        "composting_toilet + other_toilet + cement_wall + num_sheep"
    )
    model = smf.wls(formula, data=subset, weights=subset["weight"], missing="drop").fit()
    retained_index = model.model.data.row_labels
    retained = subset.loc[retained_index]
    covariance, design_df, n_strata = survey_linearized_covariance(model, retained["cu_code"])

    term_names = model.model.exog_names
    standard_errors = np.sqrt(np.diag(covariance))
    estimates = np.asarray(model.params)
    statistics = estimates / standard_errors
    p_values = 2 * student_t.sf(np.abs(statistics), df=design_df)
    table = pd.DataFrame({
        "term": term_names,
        "estimate": estimates,
        "standard_error": standard_errors,
        "t_statistic": statistics,
        "p_value": p_values,
        "ci_95_lower": estimates - student_t.ppf(0.975, design_df) * standard_errors,
        "ci_95_upper": estimates + student_t.ppf(0.975, design_df) * standard_errors,
    })
    table.to_csv(OUTPUT_DIR / "model_coefficients.csv", index=False)

    focal = table.loc[table["term"] == "act_subsidy"].iloc[0]
    group_summary = retained.groupby("act_subsidy", dropna=False).agg(
        observations=("took_ACT", "size"),
        weighted_act_uptake=("took_ACT", lambda y: np.average(y, weights=retained.loc[y.index, "weight"])),
    ).reset_index()
    group_summary.to_csv(OUTPUT_DIR / "estimation_sample_summary.csv", index=False)

    result = {
        "analysis": "Weighted linear probability model translated from supplied Stata do-file",
        "dataset": str(DATA_PATH),
        "input_rows": int(len(data)),
        "chw_postbaseline_rows_before_listwise_deletion": int(len(subset)),
        "estimation_rows": int(model.nobs),
        "strata_with_at_least_two_psus": int(n_strata),
        "design_degrees_of_freedom": int(design_df),
        "outcome": "took_ACT (drugs_taken_AL)",
        "treatment": "act_subsidy (maltest_chw_voucher_given == 1; 98 set missing)",
        "omitted_collinear_control": "stone_wall; it is identical to vip_toilet in the listwise-complete estimation sample and is omitted, as Stata would omit a collinear regressor.",
        "estimate": float(focal["estimate"]),
        "standard_error": float(focal["standard_error"]),
        "t_statistic": float(focal["t_statistic"]),
        "p_value": float(focal["p_value"]),
        "confidence_interval_95": [float(focal["ci_95_lower"]), float(focal["ci_95_upper"])],
        "alpha": ALPHA,
        "hypothesis_supported": bool((focal["estimate"] > 0) and (focal["p_value"] < ALPHA)),
        "interpretation": "The ACT-subsidy coefficient is positive and statistically significant at the 1% level." if (focal["estimate"] > 0 and focal["p_value"] < ALPHA) else "The preregistered directional 1% criterion is not met.",
        "note": "The supplied Stata script's operationalization produces an estimate that should be compared with its stated model, not assumed to equal the paper claim's reported 0.187 without further reconciliation of samples/specifications.",
    }
    with (OUTPUT_DIR / "results.json").open("w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2)

    print(
        "Replication completed: "
        f"N={int(model.nobs)}, ACT subsidy coefficient={focal['estimate']:.3f}, "
        f"SE={focal['standard_error']:.3f}, p={focal['p_value']:.3g}, "
        f"hypothesis_supported={result['hypothesis_supported']}"
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Replication failed: {exc}", file=sys.stderr)
        sys.exit(1)
