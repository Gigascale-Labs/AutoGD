#!/usr/bin/env python3
"""Replicate the Kim & Radoias under-diagnosis analysis from supplied IFLS data."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/replication_analysis_mpl")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.api as sm


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "task_input" / "replication_data" / "replication_data.dta"
OUT = ROOT / "results"


def clean_when(frame: pd.DataFrame, column: str, flag: str, values: tuple[int, ...]) -> pd.Series:
    """Apply the supplied do-file's item-specific don't-know recodes."""
    x = frame[column].copy()
    x.loc[frame[flag].isin(values)] = np.nan
    return x


def row_total(frame: pd.DataFrame, columns: list[str]) -> pd.Series:
    # Stata's chained addition is missing if any component is missing.
    return frame[columns].sum(axis=1, min_count=len(columns))


def build_variables(d: pd.DataFrame) -> pd.DataFrame:
    x = pd.DataFrame(index=d.index)
    systolic = (d.us07b1 + d.us07c1) / 2
    diastolic = (d.us07b2 + d.us07c2) / 2
    hypertension = ((systolic > 140) | (diastolic > 90)).astype(float)
    hypertension.loc[d[["us07b1", "us07c1", "us07b2", "us07c2"]].isna().any(axis=1)] = np.nan
    x["under_diag"] = ((hypertension == 1) & (d.cd05 == 3)).astype(float)
    x.loc[hypertension.isna() | d.cd05.isna() | (d.cd05 == 8), "under_diag"] = np.nan

    school = pd.Series(np.nan, index=d.index)
    school.loc[d.dl04 == 3] = 0
    grade = d.dl07.mask(d.dl07 == 98).copy()
    replacements = {2: (6, 0), 11: (1, 0), 72: (6, 0), 3: (3, 6), 4: (3, 6),
                    12: (4, 1), 73: (3, 6), 5: (3, 9), 6: (4, 9), 15: (3, 5),
                    74: (3, 9), 60: (3, 12), 61: (4, 12), 62: (3, 16),
                    63: (5, 16), 13: (6, 12)}
    for level, (completed, offset) in replacements.items():
        g = grade.mask((d.dl06 == level) & (grade == 7), completed)
        school.loc[d.dl06 == level] = (g + offset).loc[d.dl06 == level]
    school.loc[d.dl06 == 90] = 0
    school.loc[d.dl06.isin([14, 98, 99])] = np.nan
    x["yrs_school"] = school

    x["age"] = d.ar09.mask(d.ar09 == 998)
    x["agesqrt"] = (d.ar09 ** 2).mask(d.ar09 == 998)
    def risk(q1, q2, q3, q4, q5):
        z = pd.Series(np.nan, index=d.index); base = (d[q1] == 1) | (d[q2] == 2)
        z.loc[base & (d[q3] == 1) & (d[q4] == 1)] = 4; z.loc[base & (d[q3] == 1) & (d[q4] == 2)] = 3
        z.loc[base & (d[q3] == 2) & (d[q5] == 1)] = 2; z.loc[base & (d[q3] == 2) & (d[q5] == 2)] = 1
        z.loc[d[[q1,q2,q3,q4,q5]].eq(8).any(axis=1)] = np.nan; return z
    def time(q1, q2, q3, q4, q5):
        z = pd.Series(np.nan, index=d.index); base = (d[q1] == 1) | (d[q5] == 3)
        z.loc[base & (d[q2] == 1) & (d[q3] == 1)] = 4; z.loc[base & (d[q2] == 1) & (d[q3] == 2)] = 3
        z.loc[base & (d[q2] == 2) & (d[q4] == 1)] = 2; z.loc[base & (d[q2] == 2) & (d[q4] == 2)] = 1
        z.loc[d[[q1,q2,q3,q4,q5]].eq(9).any(axis=1)] = np.nan; return z
    x["risk_preference"] = np.floor((risk("si01","si02","si03","si04","si05") + risk("si11","si12","si13","si14","si15")) / 2 + .5)
    x["time_preference"] = np.floor((time("si21a","si21b","si21c","si21d","si21e") + time("si22a","si22b","si22c","si22d","si22e")) / 2 + .5)
    x["distance"] = d.rj11.mask(d.rj11x == 8)
    x["female"] = (d.ar07 == 3).astype(float).mask(d.ar07.isna())

    weekly_groups = [(list("ABCDE"), {"B": (7, 8)}), (list("FGH"), {}), (list("IJ"), {}),
                     (list("KLMN"), {}), (["OA", "OB"], {}), (["P", "Q"], {"Q": (5, 8)}),
                     (list("RSTUVWXY"), {}), (["Z", "AA", "BA", "CA", "DA", "EA", "FA", "GA", "HA", "IA", "IB"], {"IA": (5, 8), "IB": (5, 8)})]
    weekly = []
    for labels, exceptional in weekly_groups:
        cols = []
        for lab in labels:
            col, flag = f"ks02_ks1type_{lab}", f"ks02x_ks1type_{lab}"
            vals = exceptional.get(lab, (8,))
            x[col] = clean_when(d, col, flag, vals); cols.append(col)
        weekly.append(row_total(x, cols))
    monthly_labels = ["A1", "A2", "A3", "A4", "B", "C", "C1", "D", "E", "F1", "F2"]
    monthly = []
    for lab in monthly_labels:
        col, flag = f"ks06_ks2type_{lab}", f"ks06x_ks2type_{lab}"
        x[col] = clean_when(d, col, flag, (8,)); monthly.append(x[col])
    annual_labels = ["A", "B", "C", "D", "E", "F"]
    annual = []
    for lab in annual_labels:
        col, flag = f"ks08_ks3type_{lab}", f"ks08x_ks3type_{lab}"
        vals = (7, 8) if lab in ["C", "D"] else ((6, 8) if lab == "E" else (8,))
        x[col] = clean_when(d, col, flag, vals); annual.append(x[col])
    # The Stata source has a likely typo in the water recode; use its intended item-specific recode.
    spending = 4.34524 * sum(weekly) + sum(monthly) + sum(annual) / 12
    x["log_PCE"] = np.log(spending.where(spending > 0) / d.hh_size)
    x["poor_health"] = d.kk01.isin([3, 4]).astype(float).mask(d.kk01.isna())
    return x


def fit_model(x: pd.DataFrame, variables: list[str], label: str) -> tuple[dict, pd.DataFrame]:
    sample = x.loc[x.poor_health == 1, ["under_diag"] + variables].dropna()
    model = sm.Probit(sample.under_diag, sm.add_constant(sample[variables], has_constant="add")).fit(disp=False)
    me = model.get_margeff(at="mean", method="dydx").summary_frame()
    education = me.loc["yrs_school"]
    result = {"specification": label, "n": int(model.nobs), "events": int(sample.under_diag.sum()),
              "pseudo_r2": float(model.prsquared), "education_marginal_effect": float(education["dy/dx"]),
              "education_se": float(education["Std. Err."]), "education_z": float(education["z"]),
              "education_p_value": float(education["Pr(>|z|)"])}
    table = me.reset_index().rename(columns={"index": "variable"}); table.insert(0, "specification", label)
    return result, table


def main() -> None:
    if not DATA.exists(): raise FileNotFoundError(f"Required dataset not found: {DATA}")
    OUT.mkdir(exist_ok=True)
    raw = pd.read_stata(DATA, convert_categoricals=False)
    x = build_variables(raw)
    base = ["yrs_school", "log_PCE", "risk_preference", "time_preference", "female", "age", "agesqrt"]
    results, tables = [], []
    for label, vars_ in [("without_distance", base), ("with_distance", base[:4] + ["distance"] + base[4:])]:
        r, t = fit_model(x, vars_, label); results.append(r); tables.append(t)
    primary = results[0]
    primary["hypothesis_supported"] = bool(primary["education_marginal_effect"] < 0 and primary["education_p_value"] < .05)
    pd.concat(tables, ignore_index=True).to_csv(OUT / "marginal_effects.csv", index=False)
    pd.DataFrame(results).to_csv(OUT / "model_summary.csv", index=False)
    with (OUT / "results.json").open("w") as f: json.dump({"dataset_rows": int(len(raw)), "primary_specification": primary, "all_specifications": results, "interpretation": "Primary specification excludes distance, because the supplied do-file presents it as the less selected alternative; effects are average marginal effects at covariate means (Stata mfx convention)."}, f, indent=2)
    fig, ax = plt.subplots(figsize=(6, 4))
    plot = pd.DataFrame(results); ax.errorbar(plot.specification, plot.education_marginal_effect, yerr=1.96*plot.education_se, fmt="o", capsize=4)
    ax.axhline(0, color="black", lw=.8); ax.set_ylabel("Marginal effect of years of education"); ax.set_title("Under-diagnosis probit: poor-health sample")
    fig.tight_layout(); fig.savefig(OUT / "education_marginal_effect.png", dpi=180); plt.close(fig)
    print(f"Replication completed: {len(raw)} records read; primary N={primary['n']}; education AME={primary['education_marginal_effect']:.5f}, SE={primary['education_se']:.5f}, p={primary['education_p_value']:.4g}; hypothesis_supported={primary['hypothesis_supported']}.")


if __name__ == "__main__":
    try: main()
    except Exception as exc:
        print(f"Replication failed: {exc}", file=sys.stderr); sys.exit(1)
