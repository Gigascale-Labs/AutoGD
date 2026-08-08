#!/usr/bin/env python3
"""Replication of county-level Trump support and stay-at-home behavior.

Uses the supplied county and transportation files only.  The supplied R/Python
scripts specify a seeded 5% county sample, reference (Feb. 16--29), March
(Mar. 19--Apr. 1), and August (Aug. 16--29) periods, and OLS with state fixed
effects.  This implementation corrects variable names to the delivered schema.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Some minimal containers have no writable home directory.  Configure this
# before importing matplotlib so figure generation remains non-interactive.
os.environ.setdefault("MPLCONFIGDIR", "/tmp/replication_matplotlib")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.stats import iqr


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "task_input" / "replication_data"
OUTPUT = ROOT / "results"
COUNTY_PATH = DATA / "county_variables.csv"
TRANSPORT_PATH = DATA / "transportation.csv"
SEED = 2982
SAMPLE_FRACTION = 0.05

PERIODS = {
    "reference": ("2020-02-16", "2020-02-29"),
    "march": ("2020-03-19", "2020-04-01"),
    "august": ("2020-08-16", "2020-08-29"),
}
AGE_CONTROLS = [
    "percent_10_14", "percent_15_19", "percent_20_24", "percent_25_34",
    "percent_35_44", "percent_45_54", "percent_55_59", "percent_60_64",
    "percent_65_74", "percent_75_84", "percent_85_over",
]
BASE_CONTROLS = [
    "income_per_capita", "percent_male", "percent_black", "percent_hispanic",
    "percent_college", "percent_retail", "percent_transportation", "percent_hes",
    "percent_rural",
]


def load_period_means() -> pd.DataFrame:
    """Read transportation data in chunks and calculate daily-ratio means."""
    parts: list[pd.DataFrame] = []
    usecols = ["fips", "state", "date", "pop_home", "pop_not_home"]
    for chunk in pd.read_csv(TRANSPORT_PATH, usecols=usecols, chunksize=200_000):
        date = pd.to_datetime(chunk["date"], errors="coerce")
        labels = np.select(
            [
                date.between(*PERIODS["reference"]),
                date.between(*PERIODS["march"]),
                date.between(*PERIODS["august"]),
            ],
            ["reference", "march", "august"],
            default="",
        )
        keep = (labels != "") & chunk["pop_home"].notna()
        if not keep.any():
            continue
        selected = chunk.loc[keep, ["fips", "state", "pop_home", "pop_not_home"]].copy()
        selected["period"] = labels[keep]
        denominator = selected["pop_home"] + selected["pop_not_home"]
        selected["prop_home"] = selected["pop_home"] / denominator
        selected = selected.replace([np.inf, -np.inf], np.nan).dropna(subset=["prop_home"])
        parts.append(selected[["fips", "state", "period", "prop_home"]])
    if not parts:
        raise RuntimeError("No transportation records were found in the specified periods.")
    daily = pd.concat(parts, ignore_index=True)
    averaged = daily.groupby(["fips", "state", "period"], as_index=False)["prop_home"].mean()
    wide = averaged.pivot(index=["fips", "state"], columns="period", values="prop_home")
    required = {"reference", "march", "august"}
    if not required.issubset(wide.columns):
        raise RuntimeError(f"Missing period averages: {sorted(required - set(wide.columns))}")
    for period in ("march", "august"):
        wide[f"prop_home_change_{period}"] = 100 * (wide[period] / wide["reference"] - 1)
    return wide.reset_index()[['fips', 'state', 'prop_home_change_march', 'prop_home_change_august']]


def prepare_data() -> tuple[pd.DataFrame, float]:
    counties = pd.read_csv(COUNTY_PATH)
    sampled = counties.sample(frac=SAMPLE_FRACTION, random_state=SEED).copy()
    period_data = load_period_means()
    merged = sampled.merge(period_data, on="fips", how="left", validate="one_to_one")
    # The county data stores rurality as a proportion; the other demographic
    # controls are percentage points.  Scale rurality to percentage points.
    merged["percent_rural"] = merged["percent_rural"] * 100
    merged["income_per_capita"] = merged["income_per_capita"] / 1000
    needed = ["trump_share", "state"] + BASE_CONTROLS + AGE_CONTROLS + [
        "prop_home_change_march", "prop_home_change_august"
    ]
    analysis = merged[needed].dropna().copy()
    if analysis.empty:
        raise RuntimeError("Listwise deletion left no complete observations.")
    return analysis, float(iqr(sampled["trump_share"].dropna()))


def fit_model(data: pd.DataFrame, outcome: str):
    predictors = ["trump_share"] + BASE_CONTROLS + AGE_CONTROLS
    x = data[predictors].copy()
    states = pd.get_dummies(data["state"], prefix="state", drop_first=True, dtype=float)
    x = pd.concat([x, states], axis=1)
    x = sm.add_constant(x, has_constant="add").astype(float)
    return sm.OLS(data[outcome].astype(float), x).fit()


def effect_record(model, outcome: str, trump_iqr: float) -> dict:
    coefficient = float(model.params["trump_share"])
    se = float(model.bse["trump_share"])
    ci = model.conf_int().loc["trump_share"]
    iqr_effect = coefficient * trump_iqr
    iqr_ci = [float(ci.iloc[0] * trump_iqr), float(ci.iloc[1] * trump_iqr)]
    return {
        "outcome": outcome,
        "n": int(model.nobs),
        "r_squared": float(model.rsquared),
        "trump_share_coefficient_per_unit": coefficient,
        "trump_share_standard_error_per_unit": se,
        "trump_share_p_value": float(model.pvalues["trump_share"]),
        "trump_share_95ci_per_unit": [float(ci.iloc[0]), float(ci.iloc[1])],
        "trump_share_iqr": trump_iqr,
        "effect_of_iqr_percentage_points": iqr_effect,
        "effect_of_iqr_95ci_percentage_points": iqr_ci,
        "supports_negative_association_at_0_05": bool(coefficient < 0 and model.pvalues["trump_share"] < 0.05),
    }


def write_outputs(data: pd.DataFrame, models: dict, trump_iqr: float) -> dict:
    OUTPUT.mkdir(exist_ok=True)
    records = [effect_record(models[key], key, trump_iqr) for key in ("march", "august")]
    result = {
        "hypothesis": "County Trump vote share is negatively associated with the percentage-point increase in staying home.",
        "design": {"county_sample_fraction": SAMPLE_FRACTION, "random_seed": SEED, "state_fixed_effects": True},
        "interpretive_note": "March is the primary comparison to the original claim; August is the supplied code's later-period replication outcome.",
        "models": records,
    }
    (OUTPUT / "results.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    table = pd.DataFrame(records)
    table.to_csv(OUTPUT / "model_results.csv", index=False)
    coefficients = []
    for label, model in models.items():
        ci = model.conf_int().loc["trump_share"]
        coefficients.append({
            "period": label, "coefficient": model.params["trump_share"],
            "ci_lower": ci.iloc[0], "ci_upper": ci.iloc[1], "p_value": model.pvalues["trump_share"],
        })
        (OUTPUT / f"ols_{label}_summary.txt").write_text(model.summary().as_text() + "\n", encoding="utf-8")
    pd.DataFrame(coefficients).to_csv(OUTPUT / "trump_share_coefficients.csv", index=False)
    fig, ax = plt.subplots(figsize=(6, 3.5))
    plot = pd.DataFrame(coefficients)
    y = np.arange(len(plot))
    ax.errorbar(plot["coefficient"], y, xerr=[plot["coefficient"] - plot["ci_lower"], plot["ci_upper"] - plot["coefficient"]], fmt="o", color="#1f4e79", capsize=4)
    ax.axvline(0, color="black", linewidth=0.8)
    ax.set_yticks(y, ["March 19–April 1", "August 16–29"])
    ax.set_xlabel("OLS coefficient for Trump vote share\n(outcome: percentage-point increase in staying home)")
    ax.set_title("Association of Trump support with stay-at-home behavior")
    fig.tight_layout()
    fig.savefig(OUTPUT / "trump_share_coefficients.png", dpi=160)
    plt.close(fig)
    return result


def main() -> None:
    for required in (COUNTY_PATH, TRANSPORT_PATH):
        if not required.exists():
            raise FileNotFoundError(f"Required input is missing: {required}")
    data, trump_iqr = prepare_data()
    models = {
        "march": fit_model(data, "prop_home_change_march"),
        "august": fit_model(data, "prop_home_change_august"),
    }
    result = write_outputs(data, models, trump_iqr)
    march = result["models"][0]
    print(
        f"Replication completed: N={march['n']}; Trump-share IQR={march['trump_share_iqr']:.4f}; "
        f"March IQR effect={march['effect_of_iqr_percentage_points']:.3f} percentage points "
        f"(95% CI {march['effect_of_iqr_95ci_percentage_points'][0]:.3f}, "
        f"{march['effect_of_iqr_95ci_percentage_points'][1]:.3f}; p={march['trump_share_p_value']:.4g})."
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Replication failed: {exc}", file=sys.stderr)
        raise
