#!/usr/bin/env python3
"""Replicate the county-level Trump-support/social-distancing analysis.

Inputs are the two CSV files supplied in task_input/replication_data.  Outputs
are written to results/ and are deliberately regenerated on every run.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", str(Path(__file__).resolve().parent / "results" / ".matplotlib"))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "task_input" / "replication_data"
OUT = ROOT / "results"
RANDOM_SEED = 2982
SAMPLE_FRACTION = 0.05
PERIODS = {
    "reference": (pd.Timestamp("2020-02-16"), pd.Timestamp("2020-02-29")),
    "march": (pd.Timestamp("2020-03-19"), pd.Timestamp("2020-04-01")),
    "august": (pd.Timestamp("2020-08-16"), pd.Timestamp("2020-08-29")),
}


def read_period_means() -> pd.DataFrame:
    """Read only needed transportation columns in chunks and average by period."""
    pieces: list[pd.DataFrame] = []
    columns = ["fips", "state", "date", "pop_home", "pop_not_home"]
    for chunk in pd.read_csv(DATA / "transportation.csv", usecols=columns, chunksize=200_000):
        chunk["date"] = pd.to_datetime(chunk["date"], errors="coerce")
        chunk = chunk[(chunk["pop_home"] + chunk["pop_not_home"]) > 0].copy()
        chunk["period"] = pd.NA
        for period, (start, end) in PERIODS.items():
            chunk.loc[chunk["date"].between(start, end), "period"] = period
        chunk = chunk.dropna(subset=["period", "pop_home"])
        if not chunk.empty:
            chunk["prop_home"] = chunk["pop_home"] / (chunk["pop_home"] + chunk["pop_not_home"])
            pieces.append(chunk.groupby(["fips", "state", "period"], as_index=False)["prop_home"].agg(["sum", "count"]).reset_index())
    if not pieces:
        raise ValueError("No transportation records were found in the specified periods.")
    summed = pd.concat(pieces, ignore_index=True).groupby(["fips", "state", "period"], as_index=False)[["sum", "count"]].sum()
    summed["prop_home"] = summed["sum"] / summed["count"]
    wide = summed.pivot(index=["fips", "state"], columns="period", values="prop_home").reset_index()
    required = set(PERIODS)
    if not required.issubset(wide.columns):
        raise ValueError(f"Transportation data lack required periods: {sorted(required - set(wide.columns))}")
    for period in ("march", "august"):
        wide[f"prop_home_change_{period}"] = 100 * (wide[period] / wide["reference"] - 1)
    return wide


def prepare_analysis_data() -> tuple[pd.DataFrame, float]:
    county = pd.read_csv(DATA / "county_variables.csv")
    sample = county.sample(frac=SAMPLE_FRACTION, random_state=RANDOM_SEED).copy()
    mobility = read_period_means()
    df = sample.merge(mobility, on="fips", how="left")
    # The transportation file's state code identifies state fixed effects.

    # The supplied data use a finer age coding than the labels in the supplied R
    # script.  Retain those available categories, omitting under-five as the
    # reference category, rather than inventing unobserved 10-year age bins.
    controls = [
        "income_per_capita", "percent_male", "percent_black", "percent_hispanic",
        "percent_college", "percent_retail", "percent_transportation", "percent_hes",
        "percent_rural", "percent_5_9", "percent_10_14", "percent_15_19",
        "percent_20_24", "percent_25_34", "percent_35_44", "percent_45_54",
        "percent_55_59", "percent_60_64", "percent_65_74", "percent_75_84",
        "percent_85_over",
    ]
    needed = ["fips", "state", "trump_share", "prop_home_change_march", "prop_home_change_august", *controls]
    absent = set(needed) - set(df.columns)
    if absent:
        raise ValueError(f"Required analysis columns are absent: {sorted(absent)}")
    df = df[needed].dropna().copy()
    if len(df) < 30:
        raise ValueError(f"Only {len(df)} complete counties remain; insufficient for the specified model.")
    # County percentages are stored as percentage points except rurality, which
    # is stored as a proportion.  Scaling rurality makes all percent controls
    # comparable and does not alter fit or the focal Trump coefficient.
    df["percent_rural"] *= 100
    df["income_per_capita"] /= 1000
    trump_iqr = float(sample["trump_share"].dropna().quantile(.75) - sample["trump_share"].dropna().quantile(.25))
    return df, trump_iqr


def fit_outcome(df: pd.DataFrame, outcome: str, trump_iqr: float) -> dict:
    predictors = [col for col in df.columns if col not in {"fips", "state", "prop_home_change_march", "prop_home_change_august"}]
    formula = f"{outcome} ~ {' + '.join(predictors)} + C(state)"
    model = smf.ols(formula, data=df).fit()
    coef = float(model.params["trump_share"])
    ci_low, ci_high = model.conf_int().loc["trump_share"].astype(float)
    p_value = float(model.pvalues["trump_share"])
    return {
        "outcome": outcome,
        "n": int(model.nobs),
        "r_squared": float(model.rsquared),
        "trump_share_coefficient_per_unit": coef,
        "trump_share_95ci_per_unit": [float(ci_low), float(ci_high)],
        "trump_share_p_value": p_value,
        "trump_share_iqr": trump_iqr,
        "effect_per_iqr_percentage_points": coef * trump_iqr,
        "effect_95ci_per_iqr_percentage_points": [float(ci_low * trump_iqr), float(ci_high * trump_iqr)],
        "supports_preregistered_direction_and_p_lt_0_05": bool(coef < 0 and p_value < .05),
        "model_summary": model.summary().as_text(),
    }


def save_outputs(results: list[dict], df: pd.DataFrame) -> None:
    OUT.mkdir(exist_ok=True)
    rows = []
    for result in results:
        (OUT / f"{result['outcome']}_model.txt").write_text(result.pop("model_summary"))
        rows.append(result)
    pd.DataFrame(rows).to_csv(OUT / "trump_support_effects.csv", index=False)
    with (OUT / "results.json").open("w") as handle:
        json.dump({"analysis_sample_n": len(df), "models": rows}, handle, indent=2)

    fig, ax = plt.subplots(figsize=(7, 4))
    labels = ["Mar. 19–Apr. 1", "Aug. 16–29"]
    effects = [r["effect_per_iqr_percentage_points"] for r in rows]
    low = [r["effect_95ci_per_iqr_percentage_points"][0] for r in rows]
    high = [r["effect_95ci_per_iqr_percentage_points"][1] for r in rows]
    x = np.arange(len(rows))
    ax.errorbar(x, effects, yerr=[np.array(effects)-np.array(low), np.array(high)-np.array(effects)], fmt="o", capsize=4, color="#1f4e79")
    ax.axhline(0, color="black", linewidth=.8)
    ax.set_xticks(x, labels)
    ax.set_ylabel("Change in stay-at-home behavior (percentage points)")
    ax.set_title("Effect of an IQR increase in Trump vote share")
    fig.tight_layout()
    fig.savefig(OUT / "trump_support_effects.png", dpi=180)
    plt.close(fig)


def main() -> None:
    df, trump_iqr = prepare_analysis_data()
    results = [fit_outcome(df, "prop_home_change_march", trump_iqr), fit_outcome(df, "prop_home_change_august", trump_iqr)]
    save_outputs(results, df)
    march = results[0]
    print(f"Replication completed: {len(df)} complete counties; Trump-share IQR={trump_iqr:.4f}.")
    print("March IQR effect: "
          f"{march['effect_per_iqr_percentage_points']:.3f} pp "
          f"(95% CI {march['effect_95ci_per_iqr_percentage_points'][0]:.3f}, "
          f"{march['effect_95ci_per_iqr_percentage_points'][1]:.3f}; p={march['trump_share_p_value']:.4g}).")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Replication failed: {exc}", file=sys.stderr)
        sys.exit(1)
