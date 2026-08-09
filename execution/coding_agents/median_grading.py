#!/usr/bin/env python3
"""Run evaluate-execute / evaluate-interpret one or more times per study and report median scores.

Both graders are LLM judges and evaluate-execute in particular is a multi-turn ReAct agent, not a
single deterministic call, repeated runs on identical input can and do produce different scores.
This script runs the grader N times per study (default 1, just reads whatever's already there),
archives every run instead of letting the tool overwrite it, and reports the median across
whatever runs exist on disk, old and new.

Usage:
    python3 median_grading.py                       # read existing scores only, no new API calls
    python3 median_grading.py --repeats 3            # run 3 fresh repeats per study, then report
    python3 median_grading.py --repeats 2 --studies 3 13 18 20 --stage execute
    python3 median_grading.py --save for_reference/outputs/EMPIRICAL_20_STUDY_SCORES.md
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RB_ROOT = REPO_ROOT / "replicatoragent" / "replicatorbench"
AGENT_OUT = REPO_ROOT / "for_reference" / "outputs" / "agent"

# study_id -> snapshot dir relative to AGENT_OUT. Studies 3, 16 are known genuine execution
# failures (Docker/dependency errors); study 19 has no execution_results.json at all (hit the
# execute-stage turn limit before writing one) and is intentionally excluded.
STUDIES = {
    1: "study_1_regrade/20260808_222120/input",
    2: "study_2_regrade/20260808_222321/input",
    3: "study_3/20260728_223505",
    4: "study_4/20260728_225042",
    5: "study_5/20260728_225410",
    6: "study_6/20260728_230022",
    7: "study_7/20260728_230521",
    8: "study_8/20260728_231014",
    9: "study_9/20260728_231721",
    10: "study_10/20260728_224552",
    11: "study_11/20260728_232325",
    12: "study_12/20260728_232639",
    13: "study_13/20260728_233113",
    14: "study_14/20260728_233347",
    15: "study_15/20260728_233646",
    16: "study_16/20260728_234218",
    17: "study_17/20260728_234857",
    18: "study_18/20260728_235124",
    20: "study_20/20260728_214830",
}


def study_path(study_id: int) -> Path:
    return AGENT_OUT / STUDIES[study_id]


def gt_report_path(study_id: int) -> Path | None:
    gt_dir = RB_ROOT / "data" / "original" / str(study_id) / "gt"
    matches = sorted(gt_dir.glob("human_report.*"))
    return matches[0] if matches else None


def run_cli(args: list[str]) -> None:
    env = dict(os.environ)
    env["PYTHONPATH"] = "."
    subprocess.run(["python3", "-m", *args], cwd=RB_ROOT, env=env,
                    capture_output=True, text=True)


def archive_run(canonical: Path) -> None:
    """Copy the just-produced eval file to a numbered archive so the next run doesn't clobber it."""
    if not canonical.is_file():
        return
    i = 1
    while True:
        dest = canonical.with_name(f"{canonical.stem}.run{i}{canonical.suffix}")
        if not dest.exists():
            dest.write_text(canonical.read_text())
            return
        i += 1


def score_fields(data: dict) -> list[float]:
    scores: list[float] = []

    def collect(value):
        if isinstance(value, dict):
            if isinstance(value.get("score"), (int, float)):
                scores.append(value["score"])
            else:
                for child in value.values():
                    collect(child)

    collect(data)
    return scores


def all_run_scores(canonical: Path) -> list[tuple[int, int]]:
    """Return (sum, count) for every archived + canonical run of this eval file found on disk."""
    results = []
    candidates = [canonical] if canonical.is_file() else []
    candidates += sorted(canonical.parent.glob(f"{canonical.stem}.run*{canonical.suffix}"))
    for path in candidates:
        try:
            scores = score_fields(json.loads(path.read_text()))
        except (json.JSONDecodeError, OSError):
            continue
        if scores:
            results.append((int(sum(scores)), len(scores)))
    return results


def grade_execute(study_id: int, repeats: int) -> None:
    sp = study_path(study_id)
    canonical = sp / "evals" / "gpt-4o" / "execute_llm_eval.json"
    for _ in range(repeats):
        run_cli(["validator.cli.evaluate_execute_cli",
                  "--study_path", str(sp), "--evaluator_model", "gpt-4o"])
        archive_run(canonical)


def grade_interpret(study_id: int, repeats: int) -> None:
    sp = study_path(study_id)
    gt = gt_report_path(study_id)
    if gt is None:
        return
    canonical = sp / "evals" / "gpt-4o" / "interpret_llm_eval.json"
    for _ in range(repeats):
        run_cli(["validator.cli.evaluate_interpret_cli",
                  "--study_path", str(sp), "--reference_report_path", str(gt),
                  "--evaluator_model", "gpt-4o"])
        archive_run(canonical)


def fmt_row(study_id: int, canonical_name: str, max_per_field: int) -> tuple[str, str, int, float | None]:
    """Returns (display string, observed runs string, n, median ratio 0-1 or None).

    max_per_field is the max score a single rubric field can get: 1 for evaluate-execute
    (binary criteria), 3 for evaluate-interpret (0-3 semantic-match scale). `c` from
    all_run_scores is the number of gradable fields, not the max score, so the true max
    for a run is c * max_per_field.
    """
    sp = study_path(study_id)
    canonical = sp / "evals" / "gpt-4o" / canonical_name
    runs = all_run_scores(canonical)
    if not runs:
        return ("-", "-", 0, None)
    ratios = [s / (c * max_per_field) for s, c in runs]
    med_ratio = statistics.median(ratios)
    # report against the most commonly seen field count for readability
    field_count = statistics.mode([c for _, c in runs])
    denom = field_count * max_per_field
    observed = ", ".join(f"{s}/{c * max_per_field}" for s, c in runs)
    return (f"{med_ratio * denom:.1f}/{denom}", observed, len(runs), med_ratio)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=0,
                         help="Fresh repeats to run per study before reporting (default 0: read existing only)")
    parser.add_argument("--stage", choices=["execute", "interpret", "both"], default="both")
    parser.add_argument("--studies", type=int, nargs="*", default=sorted(STUDIES),
                         help="Study IDs to include (default: all)")
    parser.add_argument("--save", type=Path, default=None, help="Also write the table to this markdown file")
    args = parser.parse_args()

    for sid in args.studies:
        if sid not in STUDIES:
            continue
        if args.repeats and args.stage in ("execute", "both"):
            grade_execute(sid, args.repeats)
        if args.repeats and args.stage in ("interpret", "both"):
            grade_interpret(sid, args.repeats)

    lines = ["| Study | Execute median | Execute runs (n) | Interpret median | Interpret runs (n) |",
             "|---|---|---|---|---|"]
    ex_ratios: list[float] = []
    it_ratios: list[float] = []
    for sid in args.studies:
        if sid not in STUDIES:
            continue
        ex_med, ex_obs, ex_n, ex_ratio = fmt_row(sid, "execute_llm_eval.json", max_per_field=1)
        it_med, it_obs, it_n, it_ratio = fmt_row(sid, "interpret_llm_eval.json", max_per_field=3)
        if ex_ratio is not None:
            ex_ratios.append(ex_ratio)
        if it_ratio is not None:
            it_ratios.append(it_ratio)
        lines.append(f"| {sid} | {ex_med} | {ex_obs} ({ex_n}) | {it_med} | {it_obs} ({it_n}) |")

    table = "\n".join(lines)
    print(table)

    summary_lines = ["", "## Across-studies summary (median of each study's representative score)", ""]
    if ex_ratios:
        summary_lines.append(
            f"- evaluate-execute: median {statistics.median(ex_ratios) * 10:.1f}/10 "
            f"across {len(ex_ratios)} studies (mean {statistics.mean(ex_ratios) * 10:.1f}/10)"
        )
    if it_ratios:
        summary_lines.append(
            f"- evaluate-interpret: median {statistics.median(it_ratios) * 100:.1f}% "
            f"across {len(it_ratios)} studies (mean {statistics.mean(it_ratios) * 100:.1f}%)"
        )
    summary = "\n".join(summary_lines)
    print(summary)

    if args.save:
        args.save.write_text(f"# Median grading scores\n\n{table}\n{summary}\n")
        print(f"\nSaved to {args.save}")


if __name__ == "__main__":
    main()
