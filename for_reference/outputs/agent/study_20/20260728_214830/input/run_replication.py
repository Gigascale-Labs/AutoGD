#!/usr/bin/env python3
"""Replicate the focal longitudinal threat--negative-affect association.

The cleaning rules and outcome scoring follow replication_data/Analysis_updated.Rmd.
Outputs are written to replication_results.json, regression_table.csv, and
coefficient_plot.png in the current working directory.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

# Keep matplotlib's cache in a writable location in minimal containers.
os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.api as sm


DATA_PATH = Path("task_input/replication_data/Kachanoff_Survey_deidentify.csv")
RESULT_JSON = Path("replication_results.json")
TABLE_PATH = Path("regression_table.csv")
FIGURE_PATH = Path("coefficient_plot.png")
EMPTY_ID_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
START_TIME = pd.Timestamp("2021-01-18 15:39:38")
DUPLICATE_SESSIONS = {
    "yzjrqRlxP9w2VGfCc8oH8Ksx1Yy0dbIVzyYISA9cWO7usiklW1LN5cTrMUQ24ULh",
    "iz1H-cKfL9nNaOhPcG48r6qpur0ONIdF0I5de4DIqxE2zsJnB74YBh9zxgM_P7Ob",
    "EZZPS01lPHHFhMBsAb2VO037TFobEwTVd6W78z03LgW3OlznQ4dr8eXZZC03F1be",
    "sAetiZs9o7qBrRB057nP0BaGuKAT0Q6eNCUl3zQWBXCAsZP7gngqMvAtJ1GrNh7a",
    "d-a0BOe7-Z6nrW12Bsq2PhEzo9jIbc_3Ep5AQkLK5po-Bvy6b6fAIFOoEkyP7XBd",
}
ID_CORRECTIONS = {
    "DJQanruwarJ2PKjrPE3nNdEypUcXDt6nP5ih-QoBBDjzlULNWQUYx9UjTIkIefan": "5785878a7736990fc77e00a986691b585d99f8f4bb54f23c956d4b9308f5560c",
    "dZSb1dXIBV-n7L4y8G_agKJaaPT7f5mH0C2Hhd6NLmSRnY6blJGdB88V319-JxH9": "0673437a2ed308f0bbaf10316ef2e82982bf81af157d29d204fa23adf672f08c",
    "0AabsQl0emQ1Tm8S5JRuTdiZHK40Bnp_D2W_6O6Qdrc4tAOolxyOBSDGNoxiUjjY": "1de48a76898337ed94716e3fa5801a92e97b8380ecfc3ad3e807003e7b9a807d",
    "MWTXvlIJ_5s95rGPBU9DDy_EwnUridHqNTsTuOMuSSofk3lC5HQ3BbwvhlQfEiFC": "43c6eae02afe28045ffaf8c840681f371ce90bf77b4fd3d598cbdd5f758b3227",
    "V0qB0HT3nzxege3w_uhiyvMLvFFd1s59bqthHXkV3RsSpAQ2WqnqELiqU_W6UanK": "f6a67bb87a9848674bd1658b16984e900539913682cd57098418da6433ea9f9e",
    "1sj37XZOM60G_V_a_pJBmlqy8I3kg0ckBn0G4gnf0ECTLH076MiPODA6VTgchKoz": "8d5a6ff56773cd89287b6fef08426805239bdad1ed4cfafda46b07196e66f197",
    "spasGfBDHDZ99_09r0zGti0DG6m17WMRFTtXINRP_5itwscUd817DquL6YZy8GvM": "607670bd19da0c3aedab99a7c23e64561d23a02d0c174ad74afa23967410b869",
    "Jx26YD6h6_9Ti0Bvc16bijyiZDNaIt2dacAISjc_sO5ZaFme1S9FedDgBlGROPIL": "19bbdee77a0ef89a217fcb888c9fba4f745aed34444178f62f184ae795ca26a0",
    "WIlUb9O7dhPIZmYs2YzHGOEZPb6u4MxWRN3C6atXVtGNo9wDLTs04ofolIwcLGmY": "c433b2f1a8aa00b25ce09874bbd852c0643b73a54953f63c0294bebb94c73f0a",
}


def scalar(value: object) -> object:
    """Convert NumPy/Pandas scalars to JSON-compatible Python values."""
    if pd.isna(value):
        return None
    if isinstance(value, (np.integer, np.floating)):
        return value.item()
    return value


def main() -> None:
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Required data file not found: {DATA_PATH}")

    df = pd.read_csv(DATA_PATH)
    audit = {"raw_rows": int(len(df))}
    df["created"] = pd.to_datetime(df["created"], errors="coerce")
    if df["created"].isna().any():
        raise ValueError("Some created timestamps could not be parsed.")

    df = df.loc[df["created"] > START_TIME].copy()
    audit["after_start_time_exclusion"] = int(len(df))
    df = df.loc[~df["session"].isin(DUPLICATE_SESSIONS)].copy()
    audit["after_documented_duplicate_session_exclusions"] = int(len(df))
    df.loc[df["session"].isin(ID_CORRECTIONS), "participant_id"] = df["session"].map(ID_CORRECTIONS)
    df = df.loc[df["participant_id"] != EMPTY_ID_SHA256].copy()
    audit["after_unmatched_blank_id_exclusion"] = int(len(df))

    # The notebook recodes BAI and attention_check1 before attention screening.
    bai_and_check = [c for c in df.columns if c.startswith("bai") or c == "attention_check1"]
    df[bai_and_check] = df[bai_and_check].apply(pd.to_numeric, errors="coerce") - 1
    check2 = pd.to_numeric(df["attention_check2"], errors="coerce")
    check3 = pd.to_numeric(df["attention_check3"], errors="coerce")
    check4 = pd.to_numeric(df["attention_check4"], errors="coerce")
    dog_pattern = re.compile(r"dog|bark|bork|woof|bowwow|bow wow|ruff|roof|arf|wolf|whoof|woo|whoops|roo|boof")
    dog_correct = df["attention_check5"].fillna("").astype(str).str.lower().str.contains(dog_pattern)
    attention_total = (
        (df["attention_check1"] == 2).astype(int)
        + (check2 == 50).astype(int)
        + ((check3 < check2) & (check3.mod(5) == 0)).astype(int)
        + (check4 < check3).astype(int)
        + dog_correct.astype(int)
    )
    df = df.loc[attention_total >= 4].copy()
    audit["after_attention_check_exclusion"] = int(len(df))

    # Composites follow the notebook: threat scores are item means; PANAS is summed.
    real_items = [f"covid_real{i}" for i in range(1, 6)]
    symbolic_items = [f"covid_symbolic{i}" for i in range(1, 6)]
    negative_items = [f"negative{i}" for i in range(1, 11)]
    for columns in (real_items, symbolic_items, negative_items):
        if not set(columns).issubset(df.columns):
            raise ValueError(f"Expected scale items missing: {sorted(set(columns) - set(df.columns))}")
        df[columns] = df[columns].apply(pd.to_numeric, errors="coerce")
    df["realistic_t1"] = df[real_items].mean(axis=1, skipna=True)
    df["symbolic_t1"] = df[symbolic_items].mean(axis=1, skipna=True)
    df["negative_affect"] = df[negative_items].sum(axis=1, min_count=1)

    # The analysis notebook requires first/second responses. Reject extra visits rather
    # than silently creating a many-to-many merge as would happen with a naive merge.
    df = df.sort_values(["participant_id", "created"], kind="mergesort").copy()
    counts = df.groupby("participant_id").size()
    if (counts > 2).any():
        raise ValueError("More than two retained visits for at least one participant.")
    paired_ids = counts.index[counts == 2]
    paired = df.loc[df["participant_id"].isin(paired_ids)].copy()
    paired["visit"] = paired.groupby("participant_id").cumcount() + 1
    wide = paired.pivot(index="participant_id", columns="visit", values=["realistic_t1", "symbolic_t1", "negative_affect", "created"])
    wide.columns = [f"{measure}_t{visit}" for measure, visit in wide.columns]
    wide = wide.reset_index()
    analysis = wide[["negative_affect_t2", "realistic_t1_t1", "symbolic_t1_t1"]].dropna().copy()
    analysis.columns = ["negative_affect_t2", "realistic_threat_t1", "symbolic_threat_t1"]
    # Pivoting alongside timestamps can leave these columns as object dtype.
    analysis = analysis.apply(pd.to_numeric, errors="raise")
    if len(analysis) < 10:
        raise ValueError("Fewer than 10 complete longitudinal pairs are available.")
    audit["participants_with_two_retained_visits"] = int(len(wide))
    audit["complete_cases_in_focal_model"] = int(len(analysis))

    x = sm.add_constant(analysis[["realistic_threat_t1", "symbolic_threat_t1"]])
    fit = sm.OLS(analysis["negative_affect_t2"], x).fit()
    conf = fit.conf_int(alpha=0.05)
    table = pd.DataFrame({
        "term": fit.params.index,
        "estimate": fit.params.values,
        "std_error": fit.bse.values,
        "t_value": fit.tvalues.values,
        "p_value": fit.pvalues.values,
        "ci_95_lower": conf.iloc[:, 0].values,
        "ci_95_upper": conf.iloc[:, 1].values,
    })
    table.to_csv(TABLE_PATH, index=False)

    focal = table.loc[table["term"] == "realistic_threat_t1"].iloc[0]
    decision = bool(focal["estimate"] > 0 and focal["p_value"] < 0.05)
    result = {
        "hypothesis": "Higher T1 realistic COVID-19 threat predicts higher T2 negative affect, controlling for T1 symbolic threat.",
        "model": "OLS: T2 PANAS negative-affect sum ~ T1 realistic-threat mean + T1 symbolic-threat mean",
        "data_file": str(DATA_PATH),
        "cleaning_and_pairing": {
            "source_notebook": "task_input/replication_data/Analysis_updated.Rmd",
            "audit": audit,
            "interpretive_choice": "The documented preprocessing exclusions and attention screen were applied before pairing. Participants with one retained visit were excluded; retained pairs use the chronologically first response as T1 and second as T2.",
        },
        "focal_result": {
            "term": "realistic_threat_t1",
            "estimate": scalar(focal["estimate"]),
            "std_error": scalar(focal["std_error"]),
            "t_value": scalar(focal["t_value"]),
            "p_value": scalar(focal["p_value"]),
            "ci_95": [scalar(focal["ci_95_lower"]), scalar(focal["ci_95_upper"])],
            "direction": "positive" if focal["estimate"] > 0 else "negative",
            "supports_hypothesis_at_alpha_0_05": decision,
        },
        "model_fit": {"r_squared": scalar(fit.rsquared), "adjusted_r_squared": scalar(fit.rsquared_adj), "residual_df": scalar(fit.df_resid)},
        "outputs": {"regression_table": str(TABLE_PATH), "coefficient_figure": str(FIGURE_PATH)},
    }
    RESULT_JSON.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")

    plotted = table.loc[table["term"].isin(["realistic_threat_t1", "symbolic_threat_t1"])].copy()
    labels = ["Realistic threat (T1)", "Symbolic threat (T1)"]
    errors = np.vstack([plotted["estimate"] - plotted["ci_95_lower"], plotted["ci_95_upper"] - plotted["estimate"]])
    fig, ax = plt.subplots(figsize=(6.5, 3.5))
    ax.errorbar(plotted["estimate"], np.arange(len(plotted)), xerr=errors, fmt="o", color="#1f5a94", capsize=4)
    ax.axvline(0, color="black", linewidth=0.8)
    ax.set_yticks(np.arange(len(plotted)), labels)
    ax.set_xlabel("OLS coefficient (95% CI), outcome: T2 negative affect")
    ax.set_title("Longitudinal threat predictors")
    fig.tight_layout()
    fig.savefig(FIGURE_PATH, dpi=200)
    plt.close(fig)

    print(
        "Replication completed: "
        f"n={audit['complete_cases_in_focal_model']}, "
        f"b_realistic={focal['estimate']:.3f}, p={focal['p_value']:.4g}, "
        f"supports_positive_hypothesis={decision}."
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Replication failed: {exc}", file=sys.stderr)
        sys.exit(1)
