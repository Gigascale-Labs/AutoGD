#!/usr/bin/env python3
"""Replicate the supplied gender difference in COVID-19 concern data.

The source R script identifies mh_anxiety_1 as the focal outcome, excludes the
third/unknown gender code, and uses a pooled two-sample t test.  This script
implements that specified focal test and also reports the top-two-box
(responses 4 or 5) percentages used by the textual claim.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pandas as pd
from scipy import stats


DATA_PATH = Path("task_input/replication_data/data_gerhold.csv")
OUTPUT_DIR = Path("replication_results")
FOCAL_OUTCOME = "mh_anxiety_1"
AGREEMENT_CODES = {4, 5}


def finite_float(value: float) -> float:
    """Convert NumPy scalar values to JSON-safe Python floats."""
    return float(value) if math.isfinite(float(value)) else None


def two_sided_f_test(x: pd.Series, y: pd.Series) -> tuple[float, float]:
    """Return the variance ratio and two-sided Fisher F-test p-value."""
    var_x = x.var(ddof=1)
    var_y = y.var(ddof=1)
    ratio = var_x / var_y
    df1, df2 = len(x) - 1, len(y) - 1
    p_value = min(1.0, 2.0 * min(stats.f.cdf(ratio, df1, df2), stats.f.sf(ratio, df1, df2)))
    return ratio, p_value


def main() -> None:
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Required data file not found: {DATA_PATH}")

    data = pd.read_csv(DATA_PATH)
    required = {"gender", "female", FOCAL_OUTCOME}
    missing = required.difference(data.columns)
    if missing:
        raise ValueError(f"Dataset is missing required columns: {sorted(missing)}")

    # This exactly follows the supplied R code's exclusion of gender code 3.
    data = data.loc[data["gender"].isin([1, 2])].copy()
    data = data.dropna(subset=["female", FOCAL_OUTCOME])
    data["female"] = data["female"].astype(int)
    data[FOCAL_OUTCOME] = pd.to_numeric(data[FOCAL_OUTCOME], errors="raise")
    if not set(data["female"].unique()).issubset({0, 1}):
        raise ValueError("The female indicator must contain only 0 (men) and 1 (women).")

    women = data.loc[data["female"] == 1, FOCAL_OUTCOME]
    men = data.loc[data["female"] == 0, FOCAL_OUTCOME]
    if len(women) < 2 or len(men) < 2:
        raise ValueError("At least two observations per gender group are required.")

    # The original supplied R script specifies var.equal=TRUE for its focal test.
    t_test = stats.ttest_ind(women, men, equal_var=True, alternative="two-sided")
    variance_ratio, f_p_value = two_sided_f_test(women, men)
    pooled_sd = math.sqrt(
        ((len(women) - 1) * women.var(ddof=1) + (len(men) - 1) * men.var(ddof=1))
        / (len(women) + len(men) - 2)
    )
    cohens_d = (women.mean() - men.mean()) / pooled_sd

    agreement = data[FOCAL_OUTCOME].isin(AGREEMENT_CODES)
    agreement_women = agreement.loc[data["female"] == 1]
    agreement_men = agreement.loc[data["female"] == 0]
    p_women, p_men = agreement_women.mean(), agreement_men.mean()
    pooled_p = agreement.mean()
    z_statistic = (p_women - p_men) / math.sqrt(
        pooled_p * (1 - pooled_p) * (1 / len(women) + 1 / len(men))
    )
    agreement_p_value = 2 * stats.norm.sf(abs(z_statistic))

    table = pd.DataFrame(
        [
            {
                "group": "Women",
                "n": len(women),
                "mean_mh_anxiety_1": women.mean(),
                "sd_mh_anxiety_1": women.std(ddof=1),
                "top_two_box_n": int(agreement_women.sum()),
                "top_two_box_proportion": p_women,
            },
            {
                "group": "Men",
                "n": len(men),
                "mean_mh_anxiety_1": men.mean(),
                "sd_mh_anxiety_1": men.std(ddof=1),
                "top_two_box_n": int(agreement_men.sum()),
                "top_two_box_proportion": p_men,
            },
            {
                "group": "All eligible respondents",
                "n": len(data),
                "mean_mh_anxiety_1": data[FOCAL_OUTCOME].mean(),
                "sd_mh_anxiety_1": data[FOCAL_OUTCOME].std(ddof=1),
                "top_two_box_n": int(agreement.sum()),
                "top_two_box_proportion": agreement.mean(),
            },
        ]
    )

    result = {
        "dataset": str(DATA_PATH),
        "analysis_sample_n": int(len(data)),
        "exclusion": "Removed 121 rows with gender code 3, as in the supplied R script.",
        "focal_outcome": FOCAL_OUTCOME,
        "focal_test": {
            "method": "Two-sided pooled-variance independent-samples t-test (women minus men)",
            "women_mean": finite_float(women.mean()),
            "men_mean": finite_float(men.mean()),
            "mean_difference": finite_float(women.mean() - men.mean()),
            "t_statistic": finite_float(t_test.statistic),
            "degrees_of_freedom": int(len(women) + len(men) - 2),
            "p_value_two_sided": finite_float(t_test.pvalue),
            "cohens_d": finite_float(cohens_d),
            "variance_ratio_women_over_men": finite_float(variance_ratio),
            "f_test_p_value_two_sided": finite_float(f_p_value),
            "decision_alpha_0_05": "supported" if t_test.pvalue < 0.05 and women.mean() > men.mean() else "not supported",
        },
        "textual_claim_top_two_box_check": {
            "coding": "Responses 4 or 5, interpreting the upper end of the 1--5 scale as agree/strongly agree. This direction is consistent with the supplied R script's interpretation that a higher focal mean indicates more concern.",
            "overall_proportion": finite_float(agreement.mean()),
            "women_proportion": finite_float(p_women),
            "men_proportion": finite_float(p_men),
            "women_minus_men": finite_float(p_women - p_men),
            "two_proportion_z": finite_float(z_statistic),
            "p_value_two_sided": finite_float(agreement_p_value),
            "comparison_to_reported_claim": "The supplied data's unweighted top-two-box percentages do not reproduce the reported 62.1% overall, 68.2% women, and 55.7% men figures.",
        },
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    table.to_csv(OUTPUT_DIR / "descriptive_statistics.csv", index=False)
    with (OUTPUT_DIR / "focal_test_results.json").open("w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2)
        handle.write("\n")

    print(
        "Replication completed: "
        f"N={len(data)}; women mean={women.mean():.3f}; men mean={men.mean():.3f}; "
        f"t({len(data) - 2})={t_test.statistic:.3f}, p={t_test.pvalue:.3g}; "
        f"top-two-box women={p_women:.1%}, men={p_men:.1%}."
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"Replication failed: {error}", file=sys.stderr)
        sys.exit(1)
