#!/usr/bin/env python3
"""Replicate the supplied country-year entrepreneurship regression.

The supplied Stata program specifies a weighted OLS regression of the country-year
entrepreneurship rate on median age and year fixed effects, with standard errors
clustered by country.  This script implements that specification and writes compact,
machine-readable results beneath ``results/``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy.stats import norm


DATA_PATH = Path("task_input/replication_data/replication_data_mkk9.csv")
OUTPUT_DIR = Path("results")
REQUIRED_COLUMNS = {
    "year", "entrepreneurship", "cy_cell", "country", "median_age"
}
CLAIM_SD_YEARS = 3.5
CLAIM_EFFECT = 0.025
ALPHA = 0.05


def finite_float(value: float) -> float:
    """Convert NumPy scalars to JSON-safe native floats."""
    return float(value)


def main() -> None:
    if not DATA_PATH.is_file():
        raise FileNotFoundError(f"Required data file not found: {DATA_PATH}")

    data = pd.read_csv(DATA_PATH)
    missing_columns = REQUIRED_COLUMNS.difference(data.columns)
    if missing_columns:
        raise ValueError(f"Data file is missing required columns: {sorted(missing_columns)}")

    # This follows `drop if median_age == "NA"` in the supplied Stata code.
    for column in ("entrepreneurship", "cy_cell", "median_age"):
        data[column] = pd.to_numeric(data[column], errors="coerce")
    invalid_weights = data["cy_cell"].isna() | (data["cy_cell"] <= 0)
    if invalid_weights.any():
        raise ValueError("cy_cell must contain positive, non-missing analytic weights")

    analysis_data = data.dropna(
        subset=["entrepreneurship", "median_age", "country", "year", "cy_cell"]
    ).copy()
    if analysis_data.empty:
        raise ValueError("No complete observations remain for estimation")
    if analysis_data["country"].nunique() < 2:
        raise ValueError("At least two country clusters are required")

    # Matches: reg entrepreneurship median_age i.year [aw=cy_cell], cluster(country)
    model = smf.wls(
        "entrepreneurship ~ median_age + C(year)",
        data=analysis_data,
        weights=analysis_data["cy_cell"],
    )
    fit = model.fit(
        cov_type="cluster",
        cov_kwds={"groups": analysis_data["country"], "use_correction": True},
    )

    coefficient = finite_float(fit.params["median_age"])
    standard_error = finite_float(fit.bse["median_age"])
    z_statistic = coefficient / standard_error
    p_two_sided = finite_float(2 * norm.sf(abs(z_statistic)))
    p_one_sided_negative = finite_float(norm.cdf(z_statistic))
    ci_low = coefficient - norm.ppf(1 - ALPHA / 2) * standard_error
    ci_high = coefficient + norm.ppf(1 - ALPHA / 2) * standard_error

    # A decrease in age is represented by -3.5, so its rate change is -3.5 * beta.
    sd_decrease_effect = -CLAIM_SD_YEARS * coefficient
    sd_decrease_se = CLAIM_SD_YEARS * standard_error
    effect_ci_low = sd_decrease_effect - norm.ppf(1 - ALPHA / 2) * sd_decrease_se
    effect_ci_high = sd_decrease_effect + norm.ppf(1 - ALPHA / 2) * sd_decrease_se
    year_2010 = analysis_data.loc[analysis_data["year"] == 2010, "entrepreneurship"]
    mean_2010 = finite_float(year_2010.mean()) if not year_2010.empty else None
    percent_of_2010_mean = (
        finite_float(100 * sd_decrease_effect / mean_2010) if mean_2010 else None
    )

    OUTPUT_DIR.mkdir(exist_ok=True)
    coefficient_table = pd.DataFrame(
        [
            {
                "term": "median_age",
                "estimate": coefficient,
                "clustered_standard_error": standard_error,
                "z_statistic": finite_float(z_statistic),
                "p_value_two_sided": p_two_sided,
                "ci_95_low": finite_float(ci_low),
                "ci_95_high": finite_float(ci_high),
            },
            {
                "term": "effect_of_3.5_year_age_decrease",
                "estimate": finite_float(sd_decrease_effect),
                "clustered_standard_error": finite_float(sd_decrease_se),
                "z_statistic": np.nan,
                "p_value_two_sided": np.nan,
                "ci_95_low": finite_float(effect_ci_low),
                "ci_95_high": finite_float(effect_ci_high),
            },
        ]
    )
    coefficient_table.to_csv(OUTPUT_DIR / "regression_results.csv", index=False)

    results = {
        "analysis": {
            "dataset": str(DATA_PATH),
            "model": "Weighted least squares: entrepreneurship ~ median_age + year fixed effects",
            "weights": "cy_cell analytic weights",
            "inference": "Country-clustered robust covariance, small-sample correction",
            "missing_data_rule": "Listwise deletion for model variables; three rows missing median_age were excluded",
            "observations_input": int(len(data)),
            "observations_analyzed": int(len(analysis_data)),
            "countries_analyzed": int(analysis_data["country"].nunique()),
            "years_analyzed": sorted(int(x) for x in analysis_data["year"].unique()),
        },
        "median_age_association": {
            "coefficient": coefficient,
            "clustered_standard_error": standard_error,
            "z_statistic": finite_float(z_statistic),
            "p_value_two_sided": p_two_sided,
            "p_value_one_sided_negative": p_one_sided_negative,
            "ci_95": [finite_float(ci_low), finite_float(ci_high)],
            "supports_negative_association_at_alpha_0_05": bool(
                coefficient < 0 and p_one_sided_negative < ALPHA
            ),
        },
        "claim_scale_effect": {
            "age_decrease_years": CLAIM_SD_YEARS,
            "estimated_entrepreneurship_rate_increase": finite_float(sd_decrease_effect),
            "ci_95": [finite_float(effect_ci_low), finite_float(effect_ci_high)],
            "original_claim_benchmark_effect": CLAIM_EFFECT,
            "difference_from_benchmark": finite_float(sd_decrease_effect - CLAIM_EFFECT),
            "mean_entrepreneurship_rate_2010_in_replication": mean_2010,
            "percent_of_replication_2010_mean": percent_of_2010_mean,
        },
    }
    with (OUTPUT_DIR / "results.json").open("w", encoding="utf-8") as handle:
        json.dump(results, handle, indent=2, allow_nan=False)
        handle.write("\n")

    print(
        "Replication completed: "
        f"N={len(analysis_data)}, countries={analysis_data['country'].nunique()}, "
        f"median-age coefficient={coefficient:.6f}, "
        f"clustered SE={standard_error:.6f}, p(two-sided)={p_two_sided:.3g}; "
        f"estimated 3.5-year decrease effect={sd_decrease_effect:.4f}."
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Replication analysis failed: {exc}", file=sys.stderr)
        raise
