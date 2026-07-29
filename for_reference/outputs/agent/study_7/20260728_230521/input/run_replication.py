#!/usr/bin/env python3
"""Replicate the working-hours/carbon-emissions panel analysis.

Inputs are the supplied Stata files under task_input/replication_data.  The
original R code used panelAR with PCSE and panel-specific AR(1).  This script
implements the same regression design (logged variables and state/year fixed
effects) with a Prais--Winsten-style within-state AR(1) transformation and
state-clustered sandwich inference.  The latter is a transparent Python
approximation because panelAR is an R-only implementation.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf


DATA_DIR = Path("task_input") / "replication_data"
RESULTS_DIR = Path("results")
CONTINUOUS = ["epa", "wrkhrs", "emppop_pct", "laborprod", "pop", "manu_gdp", "energy", "hhsize", "workpop"]
FORMULA = (
    "ln_epa ~ ln_wrkhrs + ln_emppop_pct + ln_laborprod + ln_pop + ln_manu_gdp "
    "+ ln_energy + ln_hhsize + ln_workpop + C(State) + C(year)"
)


def require_files() -> None:
    missing = [str(DATA_DIR / name) for name in ("compiled.dta", "hhsize.dta", "epa.dta") if not (DATA_DIR / name).is_file()]
    if missing:
        raise FileNotFoundError("Required input file(s) not found: " + ", ".join(missing))


def load_panel() -> pd.DataFrame:
    """Reproduce the supplied R script's merges and derived/logged variables."""
    main = pd.read_stata(DATA_DIR / "compiled.dta")
    homes = pd.read_stata(DATA_DIR / "hhsize.dta")
    emissions = pd.read_stata(DATA_DIR / "epa.dta")

    home_cols = [c for c in homes.columns if c.lower().startswith("hhsize")]
    if len(home_cols) != 10:
        raise ValueError(f"Expected 10 hhsize year columns, found {len(home_cols)}")
    homes_long = homes.melt(id_vars=["State"], value_vars=home_cols, var_name="source_year", value_name="hhsize")
    homes_long["year"] = homes_long["source_year"].str.extract(r"(\d{2})$").astype(int)
    homes_long = homes_long[["State", "year", "hhsize"]]

    panel = main.merge(homes_long, on=["State", "year"], how="inner", validate="one_to_one")
    panel = panel.merge(emissions, on=["State", "year"], how="inner", validate="one_to_one")
    panel["emppop_pct"] = panel["emppop"] / (panel["pop"] * 1000) * 100
    panel["manu_gdp"] = panel["manuf"] / panel["gdp"] * 100

    for variable in CONTINUOUS:
        values = pd.to_numeric(panel[variable], errors="coerce")
        if (values.dropna() <= 0).any():
            raise ValueError(f"Cannot log-transform nonpositive values in {variable}")
        panel[f"ln_{variable}"] = np.log(values)
    panel["year"] = pd.to_numeric(panel["year"], errors="raise").astype(int)
    return panel.sort_values(["State", "year"]).reset_index(drop=True)


def estimate_ar1_rho(base_model, data: pd.DataFrame) -> float:
    """Estimate a common AR(1) coefficient from adjacent residual pairs."""
    residuals = pd.DataFrame({"State": data["State"].to_numpy(), "year": data["year"].to_numpy(), "resid": base_model.resid.to_numpy()})
    residuals = residuals.sort_values(["State", "year"])
    lag = residuals.groupby("State", observed=True)["resid"].shift(1)
    contiguous = residuals["year"].eq(residuals.groupby("State", observed=True)["year"].shift(1) + 1)
    valid = lag.notna() & contiguous
    denom = float(np.dot(lag[valid], lag[valid]))
    rho = float(np.dot(residuals.loc[valid, "resid"], lag[valid]) / denom) if denom else 0.0
    return float(np.clip(rho, -0.95, 0.95))


def prais_winsten_fit(data: pd.DataFrame):
    """Fit the specified FE model after a common panel AR(1) transformation."""
    base = smf.ols(FORMULA, data=data).fit()
    rho = estimate_ar1_rho(base, data)
    y, x = smf.ols(FORMULA, data=data).fit().model.endog, smf.ols(FORMULA, data=data).fit().model.exog
    # Recover formula-aligned rows and panel identifiers after Patsy drops missing rows.
    aligned = data.loc[base.model.data.row_labels, ["State", "year"]].copy().sort_values(["State", "year"])
    order = aligned.index.to_numpy()
    # base's matrices follow its row_labels order; use a position lookup to sort by panel/time.
    pos = pd.Series(np.arange(len(base.model.data.row_labels)), index=base.model.data.row_labels).loc[order].to_numpy()
    y, x = y[pos], x[pos, :]
    states, years = aligned["State"].to_numpy(), aligned["year"].to_numpy()
    yt, xt = y.copy(), x.copy()
    scale = np.sqrt(1 - rho ** 2)
    for i in range(len(y)):
        if i == 0 or states[i] != states[i - 1] or years[i] != years[i - 1] + 1:
            yt[i] = scale * y[i]
            xt[i, :] = scale * x[i, :]
        else:
            yt[i] = y[i] - rho * y[i - 1]
            xt[i, :] = x[i, :] - rho * x[i - 1, :]
    transformed = sm.OLS(yt, xt).fit(cov_type="cluster", cov_kwds={"groups": states})
    return transformed, rho, len(np.unique(states))


def result_row(label: str, data: pd.DataFrame, planned_model_feasible: bool) -> dict:
    """Estimate the planned model, or the explicitly labelled fallback for incomplete inputs."""
    data = data.dropna(subset=["ln_" + v for v in CONTINUOUS]).copy()
    if planned_model_feasible:
        model, rho, panels = prais_winsten_fit(data)
        idx = list(model.model.exog_names).index("ln_wrkhrs")
        coef, se, pvalue = map(float, (model.params[idx], model.bse[idx], model.pvalues[idx]))
        method = "Prais-Winsten state/year fixed-effects model; state-clustered standard errors"
        inferential = True
    else:
        # hhsize.dta as supplied has only Kansas.  Fixed effects, state clustering,
        # and the eight-control model are unidentified with this input, so use the
        # directly testable (but unadjusted) association and label it as such.
        model = smf.ols("ln_epa ~ ln_wrkhrs", data=data).fit()
        coef = float(model.params["ln_wrkhrs"])
        se = float(model.bse["ln_wrkhrs"])
        pvalue = float(model.pvalues["ln_wrkhrs"])
        rho, panels = float("nan"), int(data["State"].nunique())
        method = "Unadjusted single-state log-log time-series OLS fallback (planned panel model infeasible)"
        inferential = True
    return {
        "model": label,
        "observations": int(model.nobs),
        "states": panels,
        "year_min": int(data["year"].min()),
        "year_max": int(data["year"].max()),
        "rho": rho if np.isfinite(rho) else None,
        "estimation_method": method,
        "wrkhrs_coefficient": coef,
        "standard_error_clustered_by_state": se,
        "p_value_two_sided": pvalue,
        "ci_95_lower": coef - 1.959963984540054 * se,
        "ci_95_upper": coef + 1.959963984540054 * se,
        "positive_association": bool(coef > 0),
        "supports_hypothesis_at_0_05": bool(inferential and coef > 0 and pvalue < 0.05),
    }


def make_figure(results: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(8, 4.5))
    x = np.arange(len(results))
    lower = results["wrkhrs_coefficient"] - results["ci_95_lower"]
    upper = results["ci_95_upper"] - results["wrkhrs_coefficient"]
    ax.errorbar(x, results["wrkhrs_coefficient"], yerr=[lower, upper], fmt="o", capsize=5, color="#1769aa")
    ax.axhline(0, color="black", linewidth=0.8)
    ax.axhline(0.668, color="#c62828", linewidth=1, linestyle="--", label="reported original estimate (0.668)")
    ax.set_xticks(x, results["model"], rotation=15, ha="right")
    ax.set_ylabel("Coefficient on log average working hours")
    ax.set_title("Replication estimates with 95% confidence intervals")
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(RESULTS_DIR / "working_hours_coefficients.png", dpi=180)
    plt.close(fig)


def main() -> None:
    require_files()
    RESULTS_DIR.mkdir(exist_ok=True)
    panel = load_panel()
    analysis = panel.dropna(subset=["ln_" + v for v in CONTINUOUS]).copy()
    if analysis.empty:
        raise ValueError("No complete observations remain after transformations")

    planned_model_feasible = analysis["State"].nunique() >= 2 and len(analysis) > 60
    label_suffix = "panel" if planned_model_feasible else "single-state fallback"
    results = pd.DataFrame([
        result_row(f"Full period (2007-2016; {label_suffix})", analysis, planned_model_feasible),
        result_row(f"Original period (2007-2013; {label_suffix})", analysis.loc[analysis["year"] < 14], planned_model_feasible),
        result_row(f"Added period (2014-2016; {label_suffix})", analysis.loc[analysis["year"] > 13], planned_model_feasible),
    ])
    results.to_csv(RESULTS_DIR / "model_results.csv", index=False)
    make_figure(results)
    primary = results.iloc[0].to_dict()
    summary = {
        "hypothesis": "Average working hours per worker in a state are positively associated with carbon emissions.",
        "primary_model": primary,
        "decision": "supported" if primary["supports_hypothesis_at_0_05"] else "not_supported",
        "planned_panel_model_feasible": planned_model_feasible,
        "data_limitation": None if planned_model_feasible else "hhsize.dta supplies only one state (Kansas), leaving no cross-state panel after the required merge. The supplied state/year fixed-effects, clustered AR(1) model is therefore unidentified; results are unadjusted single-state associations only.",
        "interpretation": "Under the planned model, the log-log coefficient is the estimated percent change in emissions associated with a 1% increase in average working hours conditional on the specified controls and fixed effects. The current fallback coefficient is unadjusted and is not a conditional estimate.",
        "method_note": "When the merged data contain a usable multi-state panel, the script uses a Prais--Winsten-style common AR(1) transformation with state-clustered sandwich standard errors, approximating the supplied R panelAR PSAR1/PCSE specification. Otherwise it switches to the explicitly labelled fallback described in data_limitation.",
    }
    with open(RESULTS_DIR / "summary.json", "w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2)
    print(f"Replication complete: {len(analysis)} observations from {analysis['State'].nunique()} states.")
    print(f"Primary coefficient (log working hours): {primary['wrkhrs_coefficient']:.4f}; p={primary['p_value_two_sided']:.4g}; decision={summary['decision']}.")
    print("Wrote results/model_results.csv, results/summary.json, and results/working_hours_coefficients.png")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Replication failed: {exc}", file=sys.stderr)
        raise
