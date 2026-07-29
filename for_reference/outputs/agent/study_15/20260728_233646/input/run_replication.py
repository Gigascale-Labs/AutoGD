#!/usr/bin/env python3
"""Reproduce the focal quadratic violence--election-fraud analysis.

Inputs are the supplied Stata data and Stata replication workflow.  Results are
written to ``results/``; no input files are modified.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

# Avoid writing matplotlib's cache in a user's home directory in containers.
os.environ.setdefault("MPLCONFIGDIR", tempfile.gettempdir())

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.stats import t as student_t


ROOT = Path(__file__).resolve().parent
DATA_FILE = ROOT / "task_input" / "replication_data" / "Afghanistan_Election_Violence_2014.dta"
OUTPUT_DIR = ROOT / "results"
REQUIRED = ["fraud", "sigact_5r", "pcx", "electric", "pcexpend", "dist", "elevation", "regcom"]
CONTROLS = ["pcx", "electric", "pcexpend", "dist", "elevation"]


def main() -> None:
    if not DATA_FILE.is_file():
        raise FileNotFoundError(f"Required input not found: {DATA_FILE.relative_to(ROOT)}")

    OUTPUT_DIR.mkdir(exist_ok=True)
    data = pd.read_stata(DATA_FILE, convert_categoricals=False)
    missing = sorted(set(REQUIRED) - set(data.columns))
    if missing:
        raise ValueError(f"Data lack required variables: {missing}")

    # Stata's logit omits incomplete observations by default; match that rule.
    model_data = data.loc[:, REQUIRED].dropna().copy()
    model_data["violence_squared"] = model_data["sigact_5r"] ** 2
    x_columns = ["sigact_5r", "violence_squared", *CONTROLS]
    design = sm.add_constant(model_data[x_columns], has_constant="add")
    fit = sm.Logit(model_data["fraud"], design).fit(
        disp=False,
        cov_type="cluster",
        cov_kwds={"groups": model_data["regcom"], "use_correction": True},
    )

    n_clusters = int(model_data["regcom"].nunique())
    cluster_df = n_clusters - 1
    estimates = pd.DataFrame(
        {
            "term": fit.params.index,
            "coefficient": fit.params.values,
            "cluster_robust_se": fit.bse.values,
        }
    )
    estimates["wald_t"] = estimates["coefficient"] / estimates["cluster_robust_se"]
    # Stata uses a cluster-count-minus-one reference distribution for clustered tests.
    estimates["p_value_two_sided_t_df_clusters_minus_1"] = (
        2 * student_t.sf(np.abs(estimates["wald_t"]), df=cluster_df)
    )
    estimates["p_value_one_sided_negative_t_df_clusters_minus_1"] = np.where(
        estimates["coefficient"] < 0,
        student_t.cdf(estimates["wald_t"], df=cluster_df),
        student_t.sf(estimates["wald_t"], df=cluster_df),
    )
    estimates.to_csv(OUTPUT_DIR / "model_coefficients.csv", index=False)

    summary = data[["fraud", "pcx", "sigact_5r", "sigact_60r", "pcexpend", "electric", "dist", "elevation"]].describe().T
    summary.index.name = "variable"
    summary.to_csv(OUTPUT_DIR / "descriptive_statistics.csv")

    # Mirrors Stata margins: set violence for every estimation observation and
    # average predicted probabilities, retaining each observation's controls.
    grid = np.arange(0.0, 0.400001, 0.01)
    prediction_rows = []
    for value in grid:
        counterfactual = design.copy()
        counterfactual["sigact_5r"] = value
        counterfactual["violence_squared"] = value**2
        probability = fit.predict(counterfactual)
        prediction_rows.append(
            {"violence_election": value, "mean_predicted_fraud_probability": float(probability.mean())}
        )
    predictions = pd.DataFrame(prediction_rows)
    predictions.to_csv(OUTPUT_DIR / "marginal_predictions.csv", index=False)

    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.plot(predictions["violence_election"], predictions["mean_predicted_fraud_probability"], color="#1f4e79", linewidth=2)
    ax.set(xlabel="Violence during five-day election window", ylabel="Average predicted probability of fraud")
    ax.set_ylim(bottom=0)
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "marginal_predictions.png", dpi=180)
    plt.close(fig)

    focal = estimates.loc[estimates["term"] == "violence_squared"].iloc[0]
    turning_point = float(-fit.params["sigact_5r"] / (2 * fit.params["violence_squared"]))
    result = {
        "analysis": "Logit fraud ~ violence_5_day + violence_5_day_squared + pcx + electric + pcexpend + dist + elevation",
        "input_file": str(DATA_FILE.relative_to(ROOT)),
        "n_input_rows": int(len(data)),
        "n_estimation_rows": int(len(model_data)),
        "n_clusters_regional_command": n_clusters,
        "cluster_reference_degrees_of_freedom": cluster_df,
        "focal_term": "violence_squared",
        "coefficient": float(focal["coefficient"]),
        "cluster_robust_se": float(focal["cluster_robust_se"]),
        "wald_t": float(focal["wald_t"]),
        "p_value_two_sided_t_df_clusters_minus_1": float(focal["p_value_two_sided_t_df_clusters_minus_1"]),
        "p_value_one_sided_negative_t_df_clusters_minus_1": float(focal["p_value_one_sided_negative_t_df_clusters_minus_1"]),
        "linear_violence_coefficient": float(fit.params["sigact_5r"]),
        "turning_point_violence": turning_point,
        "directional_hypothesis_supported_at_one_sided_0_05": bool(
            focal["coefficient"] < 0 and focal["p_value_one_sided_negative_t_df_clusters_minus_1"] < 0.05
        ),
        "two_sided_significance_at_0_05": bool(focal["p_value_two_sided_t_df_clusters_minus_1"] < 0.05),
        "interpretation": (
            "The quadratic coefficient is negative. It meets a directional one-sided 0.05 test, "
            "but not a two-sided 0.05 test when inference uses five cluster degrees of freedom."
        ),
    }
    with (OUTPUT_DIR / "replication_results.json").open("w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2)

    print(
        "Replication completed: "
        f"N={result['n_estimation_rows']}, clusters={n_clusters}, "
        f"quadratic coefficient={result['coefficient']:.3f}, "
        f"cluster SE={result['cluster_robust_se']:.3f}, "
        f"one-sided p={result['p_value_one_sided_negative_t_df_clusters_minus_1']:.4f}."
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Replication failed: {exc}", file=sys.stderr)
        sys.exit(1)
