#!/usr/bin/env python3
"""Replicate the country-level COVID-19 infection-growth analysis.

This script translates the supplied Stata workflow (Analysis_script_v2.do).
It estimates a log cumulative-case growth slope for each country over its first
30 days above one cumulative case per million, then tests the preregistered
tightness-by-government-efficiency interaction in an OLS model.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.api as sm


EXCLUDED_COUNTRIES = {
    "Belgium", "France", "New Zealand", "Norway", "Pakistan", "Venezuela"
}
CONTROLS = ["gdp", "gini", "median_age", "efficiency", "tightness"]
PREDICTORS = ["efficiency_x_tightness", *CONTROLS]


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise RuntimeError(message)


def country_growth_data(data: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Apply the supplied Stata data preparation and estimate country slopes."""
    work = data.loc[~data["country"].isin(EXCLUDED_COUNTRIES)].copy()
    work["date"] = pd.to_datetime(work["date"], format="%Y-%m-%d", errors="raise")
    country_rows = []
    slopes = []

    for country, country_data in work.groupby("country", sort=True):
        country_data = country_data.sort_values("date").set_index("date")
        daily_index = pd.date_range(country_data.index.min(), country_data.index.max(), freq="D")

        # Equivalent to tsfill followed by forward filling cumulative cases and GDP.
        # Static covariates are taken from an observed row, as they are constant
        # within country and inserted tsfill rows do not carry their values.
        daily = country_data.reindex(daily_index)
        daily["total_covid_per_million"] = daily["total_covid_per_million"].ffill()
        daily["gdp"] = daily["gdp"].ffill()
        observed_covariates = country_data.iloc[0].copy()

        daily = daily.loc[daily["total_covid_per_million"] > 1].copy()
        daily["time"] = np.arange(1, len(daily) + 1)
        daily = daily.loc[daily["time"] <= 30].copy()
        if len(daily) != 30:
            fail(f"{country} has {len(daily)} eligible days; expected 30.")

        daily["log_total_cases_per_million"] = np.log(daily["total_covid_per_million"])
        slope_fit = sm.OLS(
            daily["log_total_cases_per_million"], sm.add_constant(daily["time"], has_constant="add")
        ).fit()
        slopes.append({"country": country, "infection_growth_slope": float(slope_fit.params["time"]),
                       "slope_standard_error": float(slope_fit.bse["time"]), "days_used": int(len(daily))})

        row = {"country": country}
        for name in ["tightness", "efficiency", "gdp", "gini_val", "alternative_gini", "median_age"]:
            row[name] = observed_covariates[name]
        country_rows.append(row)

    country_table = pd.DataFrame(country_rows)
    country_table["gini"] = country_table["gini_val"].combine_first(country_table["alternative_gini"])
    country_table["efficiency_x_tightness"] = country_table["efficiency"] * country_table["tightness"]
    return country_table, pd.DataFrame(slopes)


def write_plot(model_data: pd.DataFrame, model: sm.regression.linear_model.RegressionResultsWrapper,
               output_path: Path) -> None:
    """Plot model-implied growth slopes across tightness at low/high efficiency."""
    x_values = np.linspace(model_data["tightness"].min(), model_data["tightness"].max(), 100)
    efficiency_mean = model_data["efficiency"].mean()
    efficiency_sd = model_data["efficiency"].std(ddof=1)
    baseline = {name: model_data[name].mean() for name in ["gdp", "gini", "median_age"]}
    plt.figure(figsize=(7, 4.5))
    for label, efficiency, color in [
        ("Low efficiency (mean - 1 SD)", efficiency_mean - efficiency_sd, "#b2182b"),
        ("High efficiency (mean + 1 SD)", efficiency_mean + efficiency_sd, "#2166ac"),
    ]:
        prediction_data = pd.DataFrame({
            "const": 1.0,
            "efficiency_x_tightness": efficiency * x_values,
            "gdp": baseline["gdp"], "gini": baseline["gini"],
            "median_age": baseline["median_age"], "efficiency": efficiency,
            "tightness": x_values,
        })
        plt.plot(x_values, model.predict(prediction_data), label=label, color=color, linewidth=2)
    plt.xlabel("Cultural tightness")
    plt.ylabel("Predicted log infection-growth slope")
    plt.title("Model-implied tightness × efficiency association")
    plt.legend(frameon=False)
    plt.tight_layout()
    plt.savefig(output_path, dpi=200)
    plt.close()


def main() -> None:
    root = Path(__file__).resolve().parent
    input_path = root / "task_input" / "replication_data" / "gelfand_replication_data.csv"
    output_dir = root / "replication_results"
    output_dir.mkdir(exist_ok=True)
    if not input_path.exists():
        fail(f"Input dataset not found: {input_path.relative_to(root)}")

    data = pd.read_csv(input_path, na_values=["NA"])
    required = {"country", "date", "total_covid_per_million", "tightness", "efficiency", "gdp",
                "gini_val", "alternative_gini", "median_age"}
    missing = required.difference(data.columns)
    if missing:
        fail(f"Input is missing required columns: {sorted(missing)}")

    country_table, slopes = country_growth_data(data)
    analysis_data = country_table.merge(slopes, on="country", validate="one_to_one")
    complete = analysis_data.dropna(subset=["infection_growth_slope", *PREDICTORS]).copy()
    if len(complete) < len(PREDICTORS) + 2:
        fail("Too few complete country observations for the planned OLS model.")

    design = sm.add_constant(complete[PREDICTORS], has_constant="add")
    model = sm.OLS(complete["infection_growth_slope"], design).fit()
    focal = "efficiency_x_tightness"
    coefficient_table = pd.DataFrame({
        "term": model.params.index,
        "estimate": model.params.values,
        "standard_error": model.bse.values,
        "t_statistic": model.tvalues.values,
        "p_value_two_sided": model.pvalues.values,
        "ci_95_lower": model.conf_int().iloc[:, 0].values,
        "ci_95_upper": model.conf_int().iloc[:, 1].values,
    })

    analysis_data.sort_values("country").to_csv(output_dir / "country_growth_rates.csv", index=False)
    coefficient_table.to_csv(output_dir / "regression_coefficients.csv", index=False)
    write_plot(complete, model, output_dir / "interaction_effect.png")

    focal_result = coefficient_table.loc[coefficient_table["term"] == focal].iloc[0]
    results = {
        "analysis": "Country-level OLS replication of supplied Analysis_script_v2.do",
        "input_dataset": str(input_path.relative_to(root)),
        "countries_in_file": int(data["country"].nunique()),
        "countries_after_prespecified_exclusion": int(country_table.shape[0]),
        "countries_in_regression": int(complete.shape[0]),
        "excluded_countries": sorted(EXCLUDED_COUNTRIES),
        "outcome": "30-day log cumulative COVID-19 cases-per-million growth slope",
        "focal_term": focal,
        "estimate": float(focal_result["estimate"]),
        "standard_error": float(focal_result["standard_error"]),
        "t_statistic": float(focal_result["t_statistic"]),
        "degrees_of_freedom": float(model.df_resid),
        "p_value_two_sided": float(focal_result["p_value_two_sided"]),
        "confidence_interval_95": [float(focal_result["ci_95_lower"]), float(focal_result["ci_95_upper"])],
        "r_squared": float(model.rsquared),
        "supports_directional_hypothesis_at_0_05": bool(
            focal_result["estimate"] < 0 and focal_result["p_value_two_sided"] < 0.05
        ),
        "missing_data_rule": "Listwise deletion in the final regression; two countries lack efficiency.",
    }
    with (output_dir / "results.json").open("w", encoding="utf-8") as handle:
        json.dump(results, handle, indent=2)

    print("Replication analysis completed successfully.")
    print(f"Countries: {results['countries_in_regression']} of {results['countries_after_prespecified_exclusion']} eligible")
    print("Interaction (efficiency × tightness): "
          f"b={results['estimate']:.6f}, SE={results['standard_error']:.6f}, "
          f"t({results['degrees_of_freedom']:.0f})={results['t_statistic']:.3f}, "
          f"p={results['p_value_two_sided']:.4f}")
    print(f"Directional hypothesis supported at alpha=.05: {results['supports_directional_hypothesis_at_0_05']}")
    print(f"Results written to: {output_dir.relative_to(root)}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Analysis failed: {exc}", file=sys.stderr)
        sys.exit(1)
