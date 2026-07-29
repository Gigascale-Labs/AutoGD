#!/usr/bin/env python3
"""Replicate the focal Imports-from-the-South panel-model test.

Run from the workspace root: python3 replication_analysis.py
Inputs are supplied under task_input/; outputs are written to results/.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "task_input" / "replication_data" / "processed_data.csv"
OUT = ROOT / "results"


def prepare_data() -> tuple[pd.DataFrame, list[str]]:
    """Load supplied processed panel and form valid calendar-year lags."""
    required = {"year", "countrynum", "NAff", "IMS", "EXS", "unemp"}
    if not DATA.exists():
        raise FileNotFoundError(f"Required input is absent: {DATA}")
    df = pd.read_csv(DATA)
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"Input lacks required columns: {sorted(missing)}")
    if df[list(required)].isna().any().any():
        raise ValueError("Processed input unexpectedly contains missing model variables")
    if df.duplicated(["countrynum", "year"]).any():
        raise ValueError("Panel identifier/year combinations must be unique")

    df = df.sort_values(["countrynum", "year"]).reset_index(drop=True)
    year_gap = df.groupby("countrynum")["year"].diff()
    # Stata's L. operator is missing unless the preceding calendar year exists.
    for variable in ("IMS", "EXS", "unemp"):
        lag = df.groupby("countrynum")[variable].shift(1)
        df[f"L_{variable}"] = lag.where(year_gap.eq(1))
    time_dummies = [c for c in df.columns if c.startswith("DUM")]
    if not time_dummies:
        raise ValueError("No supplied five-year time-dummy columns were found")
    model = df.dropna(subset=["L_IMS", "L_EXS", "L_unemp"]).copy()
    # Segments identify consecutive observations for AR(1) transformations.
    model["segment"] = (
        model.groupby("countrynum")["year"].diff().ne(1).groupby(model["countrynum"]).cumsum()
    )
    return model, time_dummies


def make_design(df: pd.DataFrame, time_dummies: list[str]) -> tuple[np.ndarray, list[str]]:
    country = pd.get_dummies(df["countrynum"].astype(str), prefix="country", drop_first=True, dtype=float)
    names = ["Intercept", "L_IMS", "L_EXS", "L_unemp", *time_dummies, *country.columns.tolist()]
    x = np.column_stack((np.ones(len(df)), df[["L_IMS", "L_EXS", "L_unemp", *time_dummies]].to_numpy(float), country.to_numpy(float)))
    return x, names


def fit_panel_fgls(y: np.ndarray, x: np.ndarray, groups: np.ndarray, segments: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, int]:
    """Iterated Prais--Winsten FGLS with panel-specific AR(1) and variances.

    This is a transparent Python implementation of the supplied Stata command's
    panels(hetero) corr(psar1) structure.  Standard errors are conventional FGLS
    standard errors based on the final transformed design matrix.
    """
    beta = np.linalg.lstsq(x, y, rcond=None)[0]
    unique_groups = np.unique(groups)
    rhos = np.zeros(len(unique_groups))
    scales = np.ones(len(unique_groups))
    for iteration in range(1, 201):
        residual = y - x @ beta
        transformed_x, transformed_y = [], []
        for pos, group in enumerate(unique_groups):
            idx = np.flatnonzero(groups == group)
            e, seg = residual[idx], segments[idx]
            adjacent = seg[1:] == seg[:-1]
            numerator = np.dot(e[1:][adjacent], e[:-1][adjacent])
            denominator = np.dot(e[:-1][adjacent], e[:-1][adjacent])
            rho = 0.0 if denominator <= 0 else float(np.clip(numerator / denominator, -0.98, 0.98))
            rhos[pos] = rho
            xi, yi = x[idx], y[idx]
            first = np.r_[True, ~adjacent]
            weight_first = np.sqrt(1.0 - rho**2)
            tx = xi.copy()
            ty = yi.copy()
            tx[first] *= weight_first
            ty[first] *= weight_first
            follow = ~first
            tx[follow] = xi[follow] - rho * xi[np.flatnonzero(follow) - 1]
            ty[follow] = yi[follow] - rho * yi[np.flatnonzero(follow) - 1]
            transformed_residual = ty - tx @ beta
            scale = float(np.sqrt(np.mean(transformed_residual**2)))
            scales[pos] = max(scale, 1e-12)
            transformed_x.append(tx / scales[pos])
            transformed_y.append(ty / scales[pos])
        tx_all, ty_all = np.vstack(transformed_x), np.concatenate(transformed_y)
        updated = np.linalg.lstsq(tx_all, ty_all, rcond=None)[0]
        if np.max(np.abs(updated - beta)) < 1e-8:
            beta = updated
            break
        beta = updated
    covariance = np.linalg.inv(tx_all.T @ tx_all)
    return beta, np.sqrt(np.diag(covariance)), rhos, scales, iteration


def main() -> None:
    OUT.mkdir(exist_ok=True)
    df, time_dummies = prepare_data()
    x, names = make_design(df, time_dummies)
    y = df["NAff"].to_numpy(float)
    beta, se, rhos, scales, iterations = fit_panel_fgls(
        y, x, df["countrynum"].to_numpy(), df["segment"].to_numpy()
    )
    z = beta / se
    p = 2 * norm.sf(np.abs(z))
    ci_low, ci_high = beta - 1.96 * se, beta + 1.96 * se
    table = pd.DataFrame({
        "term": names, "estimate": beta, "std_error": se, "z": z,
        "p_value_two_sided": p, "ci_95_low": ci_low, "ci_95_high": ci_high,
    })
    table.to_csv(OUT / "coefficient_table.csv", index=False)
    focal = table.loc[table.term == "L_IMS"].iloc[0]
    supported = bool(focal.estimate > 0 and focal.p_value_two_sided < 0.05)
    result = {
        "focal_claim": "Imports from the South will be positively associated with national affluence.",
        "estimator": "Iterated panel FGLS (Prais-Winsten), country-specific AR(1) and heteroskedastic panel variances",
        "dependent_variable": "NAff (GDP / population)",
        "focal_predictor": "L_IMS (one-calendar-year lag of Imports from the South)",
        "n_observations": int(len(df)), "n_countries": int(df.countrynum.nunique()),
        "year_range_model": [int(df.year.min()), int(df.year.max())],
        "focal_estimate": float(focal.estimate), "focal_standard_error": float(focal.std_error),
        "focal_z": float(focal.z), "focal_p_value_two_sided": float(focal.p_value_two_sided),
        "focal_ci_95": [float(focal.ci_95_low), float(focal.ci_95_high)],
        "hypothesis_supported": supported,
        "original_reported_coefficient": 0.910,
        "original_reported_standard_error": 0.104,
        "interpretive_note": "The supplied extension uses unstandardized NAff and IMS units, so coefficient magnitude is not directly comparable to the reported b=.910; direction and statistical significance are the focal comparison.",
        "implementation_note": "processed_data.csv is used because it supplies the variables and time indicators prepared by the supplied KMYR.do. Calendar-year gaps are treated as missing lags/AR breaks.",
        "fgls_iterations": int(iterations),
        "panel_ar1_rho_summary": {"min": float(rhos.min()), "mean": float(rhos.mean()), "max": float(rhos.max())},
        "panel_scale_summary": {"min": float(scales.min()), "mean": float(scales.mean()), "max": float(scales.max())},
    }
    (OUT / "replication_results.json").write_text(json.dumps(result, indent=2) + "\n")
    (OUT / "model_summary.txt").write_text(
        "Replication focal test\n"
        f"N={result['n_observations']}; countries={result['n_countries']}; years={result['year_range_model']}\n"
        f"L_IMS estimate={focal.estimate:.6g}, SE={focal.std_error:.6g}, z={focal.z:.4f}, p={focal.p_value_two_sided:.4g}\n"
        f"Positive and p<.05: {supported}\n"
    )
    print(f"Replication complete: N={len(df)}, countries={df.countrynum.nunique()}; "
          f"L_IMS={focal.estimate:.6g}, SE={focal.std_error:.6g}, p={focal.p_value_two_sided:.4g}; "
          f"hypothesis_supported={supported}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Replication failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise
