#!/usr/bin/env python3
"""County-level replication of the political orientation/social-distancing claim.

The transportation extract supplies trip counts by distance bin rather than the
paper's proprietary mobility index.  This script reconstructs average trip
distance from bin midpoints and defines social distancing as the percent
reduction from March 2--8 to March 19--28, 2020.  The first window is the
pre-COVID reference week specified only generally in the supplied materials.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/replication_mplconfig")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf


DATA_DIR = Path("task_input") / "replication_data"
OUTPUT_DIR = Path("results")
TRANSPORT = DATA_DIR / "transportation.csv"
COUNTIES = DATA_DIR / "county_variables.csv"

# Representative miles for the supplied distance intervals. The final,
# unbounded bin is assigned 625 miles (the midpoint of 500--750 miles).
DISTANCE_COLUMNS = {
    "trips_under_1": 0.5, "trips_1_3": 2.0, "trips_3_5": 4.0,
    "trips_5_10": 7.5, "trips_10_25": 17.5, "trips_25_50": 37.5,
    "trips_50_100": 75.0, "trips_100_250": 175.0,
    "trips_250_500": 375.0, "trips_over_500": 625.0,
}
BASELINE_START, BASELINE_END = "2020-03-02", "2020-03-08"
STUDY_START, STUDY_END = "2020-03-19", "2020-03-28"


def make_mobility_outcome() -> pd.DataFrame:
    """Stream the large daily file and calculate county-window mean distances."""
    sums: dict[tuple[str, str], list[float]] = {}
    usecols = ["fips", "date", "num_trips", *DISTANCE_COLUMNS]
    for chunk in pd.read_csv(TRANSPORT, usecols=usecols, dtype={"fips": "string"}, chunksize=100_000):
        chunk["date"] = pd.to_datetime(chunk["date"], errors="coerce")
        window = np.select(
            [
                chunk["date"].between(BASELINE_START, BASELINE_END),
                chunk["date"].between(STUDY_START, STUDY_END),
            ],
            ["baseline", "study"], default="",
        )
        chunk["window"] = window
        chunk = chunk.loc[chunk["window"] != ""].copy()
        if chunk.empty:
            continue
        trip_counts = chunk[list(DISTANCE_COLUMNS)].apply(pd.to_numeric, errors="coerce").fillna(0.0)
        chunk["distance_sum"] = trip_counts.mul(pd.Series(DISTANCE_COLUMNS)).sum(axis=1)
        chunk["num_trips"] = pd.to_numeric(chunk["num_trips"], errors="coerce")
        chunk = chunk.dropna(subset=["fips", "num_trips"])
        grouped = chunk.groupby(["fips", "window"], observed=True)[["distance_sum", "num_trips"]].sum()
        for (fips, period), values in grouped.iterrows():
            key = (str(fips), str(period))
            old = sums.setdefault(key, [0.0, 0.0])
            old[0] += float(values["distance_sum"])
            old[1] += float(values["num_trips"])

    rows = []
    for fips in sorted({key[0] for key in sums}):
        baseline = sums.get((fips, "baseline"), [np.nan, np.nan])
        study = sums.get((fips, "study"), [np.nan, np.nan])
        if baseline[1] > 0 and study[1] > 0:
            baseline_distance = baseline[0] / baseline[1]
            study_distance = study[0] / study[1]
            rows.append({"fips": fips, "baseline_mean_distance": baseline_distance,
                         "study_mean_distance": study_distance,
                         "social_distancing": 100 * (baseline_distance - study_distance) / baseline_distance})
    return pd.DataFrame(rows)


def main() -> None:
    if not TRANSPORT.exists() or not COUNTIES.exists():
        raise FileNotFoundError("Expected input CSV files under task_input/replication_data/")
    OUTPUT_DIR.mkdir(exist_ok=True)

    mobility = make_mobility_outcome()
    county = pd.read_csv(COUNTIES, dtype={"fips": "string"})
    numeric_controls = [
        "trump_share", "income_per_capita", "percent_college", "percent_male",
        "percent_black", "percent_hispanic", "percent_14_under", "percent_15_24",
        "percent_25_34", "percent_35_44", "percent_45_54", "percent_55_64",
        "percent_65_74", "percent_75_over", "percent_rural", "percent_retail",
        "percent_transportation", "percent_hes",
    ]
    for column in numeric_controls:
        county[column] = pd.to_numeric(county[column], errors="coerce")
    data = county.merge(mobility, on="fips", how="inner")
    data = data.dropna(subset=["state_po", "social_distancing", *numeric_controls]).copy()
    if len(data) < 100:
        raise RuntimeError("Fewer than 100 complete county observations remain.")
    data.to_csv(OUTPUT_DIR / "analysis_dataset.csv", index=False)

    controls = " + ".join(numeric_controls[1:])
    formula = f"social_distancing ~ trump_share + {controls} + C(state_po)"
    model = smf.ols(formula, data=data).fit(cov_type="HC1")
    beta = float(model.params["trump_share"])
    ci = model.conf_int().loc["trump_share"].astype(float)
    p_value = float(model.pvalues["trump_share"])
    iqr = float(data["trump_share"].quantile(0.75) - data["trump_share"].quantile(0.25))
    effect_pp = beta * iqr
    lower_pp, upper_pp = float(ci.iloc[0] * iqr), float(ci.iloc[1] * iqr)
    supported = bool(beta < 0 and p_value < 0.05)

    coefficient_table = pd.DataFrame({
        "term": model.params.index,
        "estimate": model.params.values,
        "std_error_HC1": model.bse.values,
        "p_value": model.pvalues.values,
        "ci_lower_95": model.conf_int().iloc[:, 0].values,
        "ci_upper_95": model.conf_int().iloc[:, 1].values,
    })
    coefficient_table.to_csv(OUTPUT_DIR / "regression_coefficients.csv", index=False)
    pd.DataFrame([{
        "n_counties": int(model.nobs), "r_squared": float(model.rsquared),
        "trump_share_iqr": iqr, "coefficient_per_unit_trump_share": beta,
        "iqr_effect_percentage_points": effect_pp,
        "iqr_effect_ci_lower_95": lower_pp, "iqr_effect_ci_upper_95": upper_pp,
        "p_value": p_value, "hypothesis_supported": supported,
    }]).to_csv(OUTPUT_DIR / "primary_result.csv", index=False)

    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.scatter(data["trump_share"] * 100, data["social_distancing"], s=8, alpha=0.25, color="#377eb8")
    line_x = np.linspace(data["trump_share"].min(), data["trump_share"].max(), 100)
    # Show the adjusted slope at the observed mean of other covariates.
    adjusted_y = data["social_distancing"].mean() + beta * (line_x - data["trump_share"].mean())
    ax.plot(line_x * 100, adjusted_y, color="#e41a1c", linewidth=2, label="Adjusted Trump-share slope")
    ax.set(xlabel="Trump vote share, 2016 (%)", ylabel="Social distancing (reduction in mean trip distance, %)")
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "trump_share_social_distancing.png", dpi=180)
    plt.close(fig)

    result = {
        "hypothesis": "County Trump support is negatively associated with social distancing.",
        "outcome_definition": "Percent reduction in trip-count-weighted mean trip distance from 2020-03-02 through 2020-03-08 to 2020-03-19 through 2020-03-28.",
        "interpretive_choice": "The supplied materials identify a pre-COVID reference week but not its dates; March 2-8, 2020 was selected as the immediately preceding complete pre-COVID week.",
        "model": "OLS with state fixed effects and HC1 robust standard errors; controls are supplied demographic, education, rurality, and essential-worker composition variables.",
        "n_counties": int(model.nobs), "trump_share_iqr": iqr,
        "trump_share_coefficient": beta, "iqr_effect_percentage_points": effect_pp,
        "iqr_effect_95_ci": [lower_pp, upper_pp], "p_value": p_value,
        "hypothesis_supported": supported,
    }
    (OUTPUT_DIR / "results.json").write_text(json.dumps(result, indent=2) + "\n")
    print(f"Replication completed: n={int(model.nobs)}, Trump-share IQR={iqr:.4f}; "
          f"effect={effect_pp:.3f} pp (95% CI {lower_pp:.3f}, {upper_pp:.3f}), p={p_value:.4g}; "
          f"hypothesis supported={supported}.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Replication failed: {exc}", file=sys.stderr)
        raise
