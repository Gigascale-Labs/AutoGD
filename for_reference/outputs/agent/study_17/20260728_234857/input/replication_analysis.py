#!/usr/bin/env python3
"""Replicate the strong-democracy long model from the supplied study materials.

The script uses only paths relative to this file.  It estimates the supplied
R specification on countries with Polity IV democracy scores >= 9, using
listwise deletion and Stata/R-compatible HC1 heteroscedasticity-robust
standard errors.  The primary result excludes wave 7, as in the first real
data run in the supplied ``analyze.R``; retaining wave 7 is reported as a
prespecified sensitivity analysis.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import numpy as np
from scipy import stats


ROOT = Path(__file__).resolve().parent
DATA_PATH = ROOT / "task_input" / "replication_data" / "data.csv"
OUTPUT_DIR = ROOT / "results"

OUTCOME = "gov_consumption"
FOCAL = "sd_gov"
PREDICTORS = [
    "sd_gov", "mean_gov", "africa", "laam", "asiae", "col_uka", "col_espa",
    "col_otha", "federal", "oecd", "log_gdp_per_capita", "trade_share",
    "age_15_64", "age_65_plus",
]
REQUIRED_COLUMNS = ["country", "democ", "wave", OUTCOME, *PREDICTORS]


def read_data() -> list[dict[str, str]]:
    """Read and validate the supplied country-level CSV."""
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Required dataset not found: {DATA_PATH}")
    with DATA_PATH.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError("Dataset has no header row.")
        missing = sorted(set(REQUIRED_COLUMNS) - set(reader.fieldnames))
        if missing:
            raise ValueError(f"Dataset is missing required columns: {missing}")
        rows = list(reader)
    if not rows:
        raise ValueError("Dataset has no observations.")
    return rows


def usable_rows(rows: list[dict[str, str]], exclude_wave_7: bool) -> tuple[list[dict[str, str]], int]:
    """Select strong democracies, optionally exclude wave 7, then delete missing rows."""
    selected = []
    for row in rows:
        try:
            is_strong_democracy = float(row["democ"]) >= 9
            is_wave_7 = float(row["wave"]) == 7
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid democracy or wave value for {row.get('country', 'unknown')}") from exc
        if is_strong_democracy and not (exclude_wave_7 and is_wave_7):
            selected.append(row)

    complete = []
    for row in selected:
        try:
            values = [float(row[column]) for column in [OUTCOME, *PREDICTORS]]
        except (TypeError, ValueError):
            continue
        if all(np.isfinite(values)):
            complete.append(row)
    return complete, len(selected) - len(complete)


def fit_hc1(rows: list[dict[str, str]], model_name: str, excluded_missing: int) -> tuple[list[dict[str, object]], dict[str, object]]:
    """Fit OLS and calculate HC1 robust covariance, matching R sandwich::vcovHC(type='HC1')."""
    n = len(rows)
    x = np.column_stack((np.ones(n), *([np.array([float(row[p]) for row in rows]) for p in PREDICTORS])))
    y = np.array([float(row[OUTCOME]) for row in rows])
    k = x.shape[1]
    if n <= k:
        raise ValueError(f"{model_name}: {n} complete observations are insufficient for {k} parameters.")
    beta, _, rank, _ = np.linalg.lstsq(x, y, rcond=None)
    if rank < k:
        raise ValueError(f"{model_name}: design matrix is rank deficient (rank {rank} of {k}).")

    residuals = y - x @ beta
    df_resid = n - k
    xtx_inverse = np.linalg.inv(x.T @ x)
    meat = x.T @ ((residuals ** 2)[:, None] * x)
    covariance = (n / df_resid) * xtx_inverse @ meat @ xtx_inverse
    standard_errors = np.sqrt(np.diag(covariance))
    t_values = beta / standard_errors
    p_values = 2 * stats.t.sf(np.abs(t_values), df=df_resid)
    names = ["const", *PREDICTORS]
    coefficients = [
        {
            "model": model_name,
            "term": term,
            "coefficient": float(coef),
            "robust_se_hc1": float(se),
            "t_value": float(t_stat),
            "p_value": float(p),
            "n": n,
            "df_resid": df_resid,
        }
        for term, coef, se, t_stat, p in zip(names, beta, standard_errors, t_values, p_values)
    ]
    r_squared = 1 - float(np.sum(residuals ** 2) / np.sum((y - y.mean()) ** 2))
    focal = coefficients[names.index(FOCAL)]
    summary = {
        "model": model_name,
        "n": n,
        "parameters": k,
        "df_resid": df_resid,
        "dropped_for_missingness": excluded_missing,
        "r_squared": r_squared,
        "focal_term": FOCAL,
        "focal_coefficient": focal["coefficient"],
        "focal_robust_se_hc1": focal["robust_se_hc1"],
        "focal_t_value": focal["t_value"],
        "focal_p_value": focal["p_value"],
    }
    return coefficients, summary


def write_csv(rows: list[dict[str, object]], path: Path) -> None:
    if not rows:
        raise ValueError("No result rows to write.")
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    all_rows = read_data()
    OUTPUT_DIR.mkdir(exist_ok=True)

    primary_rows, primary_missing = usable_rows(all_rows, exclude_wave_7=True)
    sensitivity_rows, sensitivity_missing = usable_rows(all_rows, exclude_wave_7=False)
    primary_coefficients, primary = fit_hc1(primary_rows, "primary_drop_wave_7", primary_missing)
    sensitivity_coefficients, sensitivity = fit_hc1(sensitivity_rows, "sensitivity_keep_wave_7", sensitivity_missing)

    primary_supports_hypothesis = (
        primary["focal_coefficient"] < 0 and primary["focal_p_value"] < 0.05
    )
    results = {
        "analysis": "OLS long specification with HC1 heteroscedasticity-robust standard errors",
        "dataset": str(DATA_PATH.relative_to(ROOT)),
        "strong_democracy_threshold": 9,
        "input_rows": len(all_rows),
        "strong_democracy_rows": sum(float(row["democ"]) >= 9 for row in all_rows),
        "primary_model": primary,
        "sensitivity_model": sensitivity,
        "hypothesis_test": {
            "criterion": "support requires a negative sd_gov coefficient and two-sided HC1 p < 0.05",
            "supported": primary_supports_hypothesis,
        },
        "interpretive_note": (
            "The supplied data already contain only Polity IV scores 9 or 10. "
            "The supplied R file runs both wave-7 exclusions; this analysis treats its first real-data run "
            "(excluding wave 7) as primary and reports the other as sensitivity."
        ),
    }
    write_csv(primary_coefficients + sensitivity_coefficients, OUTPUT_DIR / "regression_coefficients.csv")
    (OUTPUT_DIR / "results.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")

    print(
        "Replication complete: "
        f"primary N={primary['n']}, beta_sd_gov={primary['focal_coefficient']:.4f}, "
        f"HC1 SE={primary['focal_robust_se_hc1']:.4f}, p={primary['focal_p_value']:.4g}; "
        f"hypothesis supported={primary_supports_hypothesis}."
    )
    print(f"Results written to {OUTPUT_DIR.relative_to(ROOT)}/results.json and regression_coefficients.csv")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Replication analysis failed: {exc}", file=sys.stderr)
        sys.exit(1)
