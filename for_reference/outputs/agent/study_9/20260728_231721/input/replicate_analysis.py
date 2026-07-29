#!/usr/bin/env python3
"""Replication of the Andrews & Money economic-dispersion analysis.

The implementation follows task_input/replication_data/Andrews-Money_Replication.do.
It uses all available supplied observations, as directed by that program.
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.stats import t as student_t
from sklearn.decomposition import PCA


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "task_input" / "replication_data"
OUTPUT_DIR = ROOT / "results"
PCA_COLUMNS = [
    "per303", "per401", "per402", "per403", "per404", "per407",
    "per412", "per413", "per414", "per504", "per505", "per701",
]


def log_positive(values: pd.Series) -> pd.Series:
    """Match Stata's missing result for log of zero or a negative value."""
    result = pd.Series(np.nan, index=values.index, dtype=float)
    positive = values > 0
    result.loc[positive] = np.log(values.loc[positive])
    return result


def main() -> None:
    cmp_path = DATA_DIR / "CMP_final.dta"
    cpds_path = DATA_DIR / "CPDS_final.dta"
    if not cmp_path.exists() or not cpds_path.exists():
        raise FileNotFoundError("Expected CMP_final.dta and CPDS_final.dta in task_input/replication_data")

    cmp_data = pd.read_stata(cmp_path, convert_categoricals=False).drop_duplicates()
    cpds_data = pd.read_stata(cpds_path, convert_categoricals=False).drop_duplicates()
    input_cmp_rows, input_cpds_rows = len(cmp_data), len(cpds_data)

    cmp_data = cmp_data.rename(columns={"countryname": "country"})
    cmp_data["year"] = pd.to_datetime(cmp_data["edate"]).dt.year.astype(str)
    cpds_data["year"] = cpds_data["year"].astype(str)
    data = cmp_data.merge(
        cpds_data[["country", "year", "prop"]],
        on=["country", "year"], how="inner", validate="many_to_one",
    )
    merged_rows = len(data)

    # The Stata do-file creates an ordered, within-country election identifier.
    elections = data[["country", "edate"]].drop_duplicates().sort_values(["country", "edate"]).copy()
    elections["election"] = elections.groupby("country").cumcount() + 1
    data = data.merge(elections, on=["country", "edate"], how="left", validate="many_to_one")

    # Faithful implementation of the supplied program's two successive screening steps.
    data = data.sort_values(["party", "election"]).copy()
    data["relative_seat"] = data["absseat"] / data["totseats"]
    data["relative_seat_t_1"] = data.groupby("party")["relative_seat"].shift(-1)
    has_two = ((data["relative_seat"] > 0.01) & (data["relative_seat_t_1"] > 0.01)).groupby(data["party"]).transform("max")
    data = data.loc[has_two].copy()
    data["relative_seat_t_1"] = data.groupby("party")["relative_seat"].shift(-1)
    data["relative_seat_t_2"] = data.groupby("party")["relative_seat"].shift(-2)
    has_three = (
        (data["relative_seat"] > 0.01)
        & (data["relative_seat_t_1"] > 0.01)
        & (data["relative_seat_t_2"] > 0.01)
    ).groupby(data["party"]).transform("max")
    data = data.loc[has_three].copy()
    screened_rows = len(data)

    data["count_parties"] = data.groupby(["country", "election"])["party"].transform("size")
    data["log_count_parties"] = np.log(data["count_parties"])

    # Stata pca uses the covariance matrix by default. Scores are estimated for
    # complete cases; incomplete party records retain missing scores.
    complete_pca = data[PCA_COLUMNS].notna().all(axis=1)
    pca = PCA(n_components=1, svd_solver="full")
    pca.fit(data.loc[complete_pca, PCA_COLUMNS])
    data["economic_policy"] = np.nan
    data.loc[complete_pca, "economic_policy"] = pca.transform(data.loc[complete_pca, PCA_COLUMNS])[:, 0]
    extrema = data.groupby(["country", "election"])["economic_policy"]
    data["dispersion"] = extrema.transform("max") - extrema.transform("min")
    data["log_dispersion"] = log_positive(data["dispersion"])
    data["single_member"] = np.where(data["prop"].isna(), np.nan, (data["prop"] == 0).astype(float))

    # One record per party system, then Stata-style panel lag (only election t-1).
    systems = data[
        ["log_dispersion", "log_count_parties", "country", "edate", "single_member", "year", "election", "data_sample"]
    ].drop_duplicates().copy()
    systems["id_country"] = pd.factorize(systems["country"], sort=True)[0] + 1
    previous = systems[["id_country", "election", "log_dispersion"]].copy()
    previous["election"] += 1
    previous = previous.rename(columns={"log_dispersion": "lagged_dispersion"})
    systems = systems.merge(previous, on=["id_country", "election"], how="left", validate="one_to_one")
    model_data = systems.replace([np.inf, -np.inf], np.nan).dropna(
        subset=["log_dispersion", "log_count_parties", "single_member", "lagged_dispersion"]
    ).copy()
    if model_data.empty:
        raise RuntimeError("No complete party-system observations remain for the regression")

    x = sm.add_constant(model_data[["log_count_parties", "single_member", "lagged_dispersion"]], has_constant="add")
    model = sm.OLS(model_data["log_dispersion"], x).fit(
        cov_type="cluster",
        cov_kwds={"groups": model_data["id_country"], "use_correction": True, "df_correction": True},
    )
    clusters = int(model_data["id_country"].nunique())
    critical = float(student_t.ppf(0.975, clusters - 1))
    coefficients = pd.DataFrame({
        "term": model.params.index,
        "estimate": model.params.values,
        "cluster_robust_se": model.bse.values,
        "z_statistic": model.tvalues.values,
        "normal_approx_p_value": model.pvalues.values,
    })
    coefficients["ci_95_lower_cluster_t"] = coefficients["estimate"] - critical * coefficients["cluster_robust_se"]
    coefficients["ci_95_upper_cluster_t"] = coefficients["estimate"] + critical * coefficients["cluster_robust_se"]

    focal = coefficients.loc[coefficients["term"] == "log_count_parties"].iloc[0]
    conclusion = bool(focal["estimate"] > 0 and focal["ci_95_lower_cluster_t"] > 0)
    OUTPUT_DIR.mkdir(exist_ok=True)
    coefficients.to_csv(OUTPUT_DIR / "model_coefficients.csv", index=False)
    pd.DataFrame([{
        "input_cmp_rows_after_deduplication": input_cmp_rows,
        "input_cpds_rows_after_deduplication": input_cpds_rows,
        "rows_after_merge": merged_rows,
        "party_records_after_system_screen": screened_rows,
        "party_systems_before_model": len(systems),
        "regression_observations": int(model.nobs),
        "countries_clustered": clusters,
        "pca_complete_party_records": int(complete_pca.sum()),
        "r_squared": float(model.rsquared),
    }]).to_csv(OUTPUT_DIR / "analysis_sample_summary.csv", index=False)
    result = {
        "hypothesis": "On the economic policy dimension, the number of parties in the party system is positively associated with policy dispersion.",
        "outcome": "log dispersion between the most economically extreme parties in a country-election",
        "focal_predictor": "log count of qualifying parties in the country-election party system",
        "estimator": "OLS with country-clustered robust covariance; 95% intervals use t critical value with clusters - 1 degrees of freedom",
        "focal_result": {
            "estimate": float(focal["estimate"]),
            "cluster_robust_se": float(focal["cluster_robust_se"]),
            "ci_95": [float(focal["ci_95_lower_cluster_t"]), float(focal["ci_95_upper_cluster_t"])],
            "normal_approx_p_value": float(focal["normal_approx_p_value"]),
            "supports_hypothesis": conclusion,
        },
        "sample": {"observations": int(model.nobs), "country_clusters": clusters, "party_systems_before_model": len(systems)},
        "interpretive_choice": "The supplied do-file says to use all available observations; this includes its post-1999 and additional-country records.",
    }
    with (OUTPUT_DIR / "replication_results.json").open("w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2)

    print(
        "Replication completed: "
        f"N={int(model.nobs)}, clusters={clusters}, beta_log_party_count={focal['estimate']:.3f}, "
        f"clustered_SE={focal['cluster_robust_se']:.3f}, "
        f"95%_CI=[{focal['ci_95_lower_cluster_t']:.3f}, {focal['ci_95_upper_cluster_t']:.3f}], "
        f"supports_hypothesis={conclusion}. Results: {OUTPUT_DIR.relative_to(ROOT)}"
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Replication failed: {exc}", file=sys.stderr)
        raise
