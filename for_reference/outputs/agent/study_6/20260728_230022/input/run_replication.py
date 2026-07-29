#!/usr/bin/env python3
"""Replicate the post-secular versus traditional evolution comparison.

This script uses only the supplied GSSreplication.dta file.  It implements the
cleaning rules in OBrienReplication_OSF_Axxe_20201012.do, restricts the focal
replication to the independent 2012--2018 GSS waves, fits a weighted
three-class categorical latent-class model, and performs the specified pooled,
two-sided t test on the binary evolution item.
"""

from __future__ import annotations

import csv
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/replication_matplotlib")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.special import logsumexp
from scipy.stats import ttest_ind


ROOT = Path(__file__).resolve().parent
DATA_PATH = ROOT / "task_input" / "replication_data" / "GSSreplication.dta"
OUTPUT_DIR = ROOT / "results"
RNG_SEED = 12345
N_STARTS = 30
N_CLASSES = 3

ITEMS = [
    "HOTCORE", "RADIOACT", "BOYORGRL", "LASERS", "ELECTRON", "VIRUSES",
    "EARTHSUN", "CONDRIFT", "BIGBANG", "EVOLVED", "EXPDESGN", "ODDS1",
    "ODDS2", "SCISTUDY", "NEXTGEN", "TOOFAST", "ADVFRONT", "SCIBNFTS",
    "BIBLE", "RELITEN",
]
BINARY = ITEMS[:13]
TRUE_RESPONSE = {"HOTCORE", "BOYORGRL", "ELECTRON", "EARTHSUN", "CONDRIFT", "BIGBANG", "EVOLVED", "ODDS2"}


def read_supplied_stata(path: Path) -> dict[str, np.ndarray]:
    """Read the supplied Stata 110 file without requiring external Stata.

    The file was written by R in legacy Stata layout.  Its descriptors identify
    23 variables and a fixed 123-byte record.  Data start is located by finding
    the first valid GSS year followed by a complete run of fixed-width records;
    this avoids relying on nonstandard legacy descriptor padding.
    """
    raw = path.read_bytes()
    names = [
        "YEAR", "WTSS", "HOTCORE", "RADIOACT", "BOYORGRL", "LASERS", "ELECTRON",
        "VIRUSES", "EARTHSUN", "CONDRIFT", "BIGBANG", "EVOLVED", "EXPDESGN",
        "ODDS1", "ODDS2", "SCISTUDY", "NEXTGEN", "TOOFAST", "ADVFRONT",
        "SCIBNFTS", "BIBLE", "RELITEN", "sample_choice",
    ]
    dtype = np.dtype(list(zip(names, ["<f8", "<f8"] + ["<i4"] * 20 + ["S27"])))
    nobs = int.from_bytes(raw[6:10], byteorder="little")
    year_bytes = np.asarray([2006.0], dtype="<f8").tobytes()
    start = -1
    offset = raw.find(year_bytes)
    while offset >= 0:
        if offset + dtype.itemsize * 4 <= len(raw):
            probe = np.frombuffer(raw, dtype=dtype, count=4, offset=offset)
            if np.all(np.isin(probe["YEAR"], [2006., 2008., 2010., 2012., 2014., 2016., 2018.])):
                start = offset
                break
        offset = raw.find(year_bytes, offset + 1)
    if start < 0 or start + nobs * dtype.itemsize > len(raw):
        raise ValueError("Could not locate the supplied Stata data records safely.")
    records = np.frombuffer(raw, dtype=dtype, count=nobs, offset=start)
    return {name: records[name].astype(float) for name in names[:-1]}


def clean_data(data: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    cleaned = {key: value.copy() for key, value in data.items()}
    for item in BINARY:
        raw = data[item]
        result = np.full(raw.shape, np.nan)
        valid = ~np.isin(raw, [1, 5])
        correct_code = 2 if item in TRUE_RESPONSE else 3
        result[valid] = (raw[valid] == correct_code).astype(float)
        cleaned[item] = result
    cleaned["SCISTUDY"] = np.where(np.isin(data["SCISTUDY"], [2, 3, 4]), data["SCISTUDY"], np.nan)
    for item in ["NEXTGEN", "TOOFAST", "ADVFRONT"]:
        cleaned[item] = np.where(np.isin(data[item], [2, 3, 4, 5]), data[item] - 1, np.nan)
    cleaned["TOOFAST"] = np.where(np.isnan(cleaned["TOOFAST"]), np.nan, 5 - cleaned["TOOFAST"])
    cleaned["SCIBNFTS"] = np.select([data["SCIBNFTS"] == 2, data["SCIBNFTS"] == 3, data["SCIBNFTS"] == 4], [4., 2., 0.], default=np.nan)
    cleaned["BIBLE"] = np.select([data["BIBLE"] == 2, data["BIBLE"] == 3, data["BIBLE"] == 4], [1., 2., 3.], default=np.nan)
    cleaned["RELITEN"] = np.select([data["RELITEN"] == 2, data["RELITEN"] == 3, data["RELITEN"] == 4, data["RELITEN"] == 5], [4., 3., 2., 1.], default=np.nan)
    return cleaned


def fit_lca(x: np.ndarray, weights: np.ndarray, levels: list[int], seed: int) -> tuple[float, np.ndarray, list[np.ndarray], int]:
    """EM estimation of a locally independent categorical LCA."""
    rng = np.random.default_rng(seed)
    n, p = x.shape
    posterior = rng.dirichlet(np.ones(N_CLASSES), size=n)
    previous_ll = -np.inf
    for iteration in range(1, 1001):
        weighted_post = posterior * weights[:, None]
        proportions = weighted_post.sum(axis=0)
        proportions /= proportions.sum()
        probabilities: list[np.ndarray] = []
        for column, n_levels in enumerate(levels):
            counts = np.full((N_CLASSES, n_levels), 1e-3)
            np.add.at(counts, (np.arange(N_CLASSES)[:, None], x[:, column][None, :]), weighted_post.T)
            probabilities.append(counts / counts.sum(axis=1, keepdims=True))
        log_prob = np.broadcast_to(np.log(proportions), (n, N_CLASSES)).copy()
        for column in range(p):
            log_prob += np.log(probabilities[column][:, x[:, column]].T)
        log_denominator = logsumexp(log_prob, axis=1)
        posterior = np.exp(log_prob - log_denominator[:, None])
        log_likelihood = float(np.sum(weights * log_denominator))
        if abs(log_likelihood - previous_ll) < 1e-7:
            return log_likelihood, posterior, probabilities, iteration
        previous_ll = log_likelihood
    return log_likelihood, posterior, probabilities, iteration


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Required data file not found: {DATA_PATH}")
    OUTPUT_DIR.mkdir(exist_ok=True)
    data = clean_data(read_supplied_stata(DATA_PATH))
    complete = np.logical_and.reduce([~np.isnan(data[item]) for item in ITEMS])
    focal = (data["YEAR"] > 2010) & complete
    x_original = np.column_stack([data[item][focal].astype(int) for item in ITEMS])
    weights = data["WTSS"][focal]
    years = data["YEAR"][focal].astype(int)
    if len(x_original) == 0 or np.any(weights <= 0):
        raise ValueError("The focal complete-case sample is empty or has invalid weights.")

    x = np.empty_like(x_original)
    levels: list[int] = []
    original_levels: list[np.ndarray] = []
    for column in range(x_original.shape[1]):
        values = np.unique(x_original[:, column])
        x[:, column] = np.searchsorted(values, x_original[:, column])
        levels.append(len(values))
        original_levels.append(values)

    fits = [fit_lca(x, weights, levels, RNG_SEED + start) for start in range(N_STARTS)]
    log_likelihood, posterior, probabilities, iterations = max(fits, key=lambda fit: fit[0])
    assigned = posterior.argmax(axis=1)

    # The original workflow labels classes after inspecting profiles.  To make
    # that step reproducible without using the focal evolution outcome: label
    # post-secular as the class with the strongest religious profile (higher
    # RELITEN and lower BIBLE); call the lower non-evolution science-knowledge
    # class among the two remaining classes traditional; the other is modern.
    item_index = {item: index for index, item in enumerate(ITEMS)}
    profile_means = np.array([[x_original[assigned == cls, col].mean() for col in range(len(ITEMS))] for cls in range(N_CLASSES)])
    religiosity = profile_means[:, item_index["RELITEN"]] / 4 + (4 - profile_means[:, item_index["BIBLE"]]) / 3
    post_class = int(np.argmax(religiosity))
    remaining = [cls for cls in range(N_CLASSES) if cls != post_class]
    non_evolution_science = [item_index[item] for item in BINARY if item != "EVOLVED"]
    traditional_class = min(remaining, key=lambda cls: float(profile_means[cls, non_evolution_science].mean()))
    modern_class = next(cls for cls in remaining if cls != traditional_class)
    labels = {traditional_class: "traditional", modern_class: "modern", post_class: "post_secular"}

    evolved = x_original[:, item_index["EVOLVED"]].astype(float)
    post_values = evolved[assigned == post_class]
    traditional_values = evolved[assigned == traditional_class]
    test = ttest_ind(post_values, traditional_values, equal_var=True)
    difference = float(post_values.mean() - traditional_values.mean())
    pooled_sd = np.sqrt((((len(post_values) - 1) * post_values.var(ddof=1)) + ((len(traditional_values) - 1) * traditional_values.var(ddof=1))) / (len(post_values) + len(traditional_values) - 2))

    n_parameters = (N_CLASSES - 1) + N_CLASSES * sum(level - 1 for level in levels)
    bic = -2 * log_likelihood + n_parameters * np.log(len(x))
    class_rows = []
    for cls in range(N_CLASSES):
        class_rows.append({
            "latent_class": cls + 1, "assigned_label": labels[cls], "n_hard_assigned": int((assigned == cls).sum()),
            "weighted_class_proportion": float(np.mean(posterior[:, cls] * weights) / np.mean(weights)),
            "evolution_endorsement_rate": float(evolved[assigned == cls].mean()),
            "religiosity_label_score": float(religiosity[cls]),
            "non_evolution_science_score": float(profile_means[cls, non_evolution_science].mean()),
        })
    write_csv(OUTPUT_DIR / "class_summary.csv", class_rows)
    item_rows = []
    for cls in range(N_CLASSES):
        for column, item in enumerate(ITEMS):
            item_rows.append({"latent_class": cls + 1, "assigned_label": labels[cls], "item": item, "hard_assignment_mean": float(profile_means[cls, column])})
    write_csv(OUTPUT_DIR / "class_item_means.csv", item_rows)
    comparison_row = {
        "comparison": "post_secular_minus_traditional", "post_secular_n": len(post_values), "traditional_n": len(traditional_values),
        "post_secular_evolution_rate": float(post_values.mean()), "traditional_evolution_rate": float(traditional_values.mean()),
        "difference_in_rates": difference, "t_statistic": float(test.statistic), "degrees_of_freedom": len(post_values) + len(traditional_values) - 2,
        "two_sided_p_value": float(test.pvalue), "cohens_d": float(difference / pooled_sd),
    }
    write_csv(OUTPUT_DIR / "evolution_comparison.csv", [comparison_row])
    write_csv(OUTPUT_DIR / "model_fit.csv", [{"classes": N_CLASSES, "weighted_log_likelihood": log_likelihood, "bic": float(bic), "n_parameters": n_parameters, "em_iterations_best_start": iterations, "random_starts": N_STARTS}])

    ordered = [traditional_class, modern_class, post_class]
    plt.figure(figsize=(7, 4.5))
    bars = plt.bar([labels[cls].replace("_", "-") for cls in ordered], [evolved[assigned == cls].mean() for cls in ordered], color=["#6c757d", "#4c78a8", "#d95f02"])
    plt.ylim(0, 1)
    plt.ylabel("Proportion endorsing human evolution")
    plt.title("Evolution endorsement by latent class (GSS 2012–2018)")
    for bar in bars:
        plt.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + .02, f"{bar.get_height():.3f}", ha="center")
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "evolution_by_class.png", dpi=160)
    plt.close()

    result = {
        "dataset": "GSSreplication.dta", "analysis_waves": [2012, 2014, 2016, 2018], "complete_case_n": int(len(x)),
        "complete_cases_by_year": {str(year): int((years == year).sum()) for year in np.unique(years)},
        "lca": {"classes": N_CLASSES, "weighted_log_likelihood": log_likelihood, "bic": float(bic), "random_starts": N_STARTS, "seed": RNG_SEED},
        "class_mapping": {labels[cls]: int(cls + 1) for cls in range(N_CLASSES)},
        "hypothesis_test": comparison_row,
        "conclusion": "supported" if difference < 0 and test.pvalue < .05 else "not_supported",
        "interpretive_note": "Classes were labeled from religious-profile and non-evolution science-item profiles before the focal evolution comparison; latent-class numeric identifiers themselves are arbitrary.",
    }
    (OUTPUT_DIR / "replication_results.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"Replication completed: {len(x)} complete cases from GSS 2012–2018.")
    print(f"Post-secular evolution endorsement={post_values.mean():.3f}; traditional={traditional_values.mean():.3f}; difference={difference:.3f}.")
    print(f"Pooled two-sided t({comparison_row['degrees_of_freedom']})={test.statistic:.3f}, p={test.pvalue:.3g}; conclusion={result['conclusion']}.")
    print(f"Results written to {OUTPUT_DIR.relative_to(ROOT)}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Replication failed: {exc}", file=sys.stderr)
        sys.exit(1)
