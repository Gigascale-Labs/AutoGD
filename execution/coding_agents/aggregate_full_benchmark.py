#!/usr/bin/env python3

import csv
import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
CODEX_ROOT = REPO_ROOT / "for_reference" / "outputs" / "codex"
OUTPUT_DIR = REPO_ROOT / "for_reference" / "outputs" / "full_benchmark"
CSV_PATH = OUTPUT_DIR / "benchmark_results.csv"
JSON_PATH = OUTPUT_DIR / "benchmark_results.json"


def read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def collect_scores(value: Any, path: str = "") -> tuple[list[float], list[dict[str, str]]]:
    scores: list[float] = []
    failures: list[dict[str, str]] = []

    if isinstance(value, dict):
        score = value.get("score")
        if isinstance(score, (int, float)):
            scores.append(score)
            if score == 0:
                failures.append(
                    {
                        "check": path,
                        "explanation": str(value.get("explanation", "")),
                    }
                )

        for key, child in value.items():
            child_path = f"{path}.{key}" if path else key
            child_scores, child_failures = collect_scores(child, child_path)
            scores.extend(child_scores)
            failures.extend(child_failures)

    elif isinstance(value, list):
        for index, child in enumerate(value):
            child_scores, child_failures = collect_scores(
                child, f"{path}[{index}]"
            )
            scores.extend(child_scores)
            failures.extend(child_failures)

    return scores, failures


def timestamped_runs(study_dir: Path) -> list[Path]:
    return sorted(
        (
            path
            for path in study_dir.iterdir()
            if path.is_dir() and path.name[:8].isdigit()
        ),
        key=lambda path: path.name,
    )


def find_latest_graded_run(runs: list[Path]) -> tuple[Path | None, Path | None]:
    for run in reversed(runs):
        results = sorted(run.glob("grading/evals/*/execute_llm_eval.json"))
        if results:
            return run, results[-1]
    return None, None


def find_latest_codex_metadata(runs: list[Path], before_or_at: Path) -> dict[str, Any]:
    eligible = [run for run in runs if run.name <= before_or_at.name]

    for run in reversed(eligible):
        metadata = read_json(run / "run_metadata.json")
        if metadata.get("mode") == "data_only" and "token_usage" in metadata:
            return metadata

    return {}


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []

    for study_id in range(1, 21):
        study_dir = CODEX_ROOT / f"study_{study_id}"

        if not study_dir.is_dir():
            rows.append(
                {
                    "study_id": study_id,
                    "status": "missing",
                    "score": "",
                    "passed_checks": "",
                    "total_checks": "",
                    "codex_duration_seconds": "",
                    "rb_execution_duration_seconds": "",
                    "grading_duration_seconds": "",
                    "total_duration_seconds": "",
                    "input_tokens": "",
                    "cached_input_tokens": "",
                    "output_tokens": "",
                    "reasoning_output_tokens": "",
                    "failed_checks": "",
                    "graded_run": "",
                }
            )
            continue

        runs = timestamped_runs(study_dir)
        graded_run, grading_path = find_latest_graded_run(runs)

        if graded_run is None or grading_path is None:
            rows.append(
                {
                    "study_id": study_id,
                    "status": "not_graded",
                    "score": "",
                    "passed_checks": "",
                    "total_checks": "",
                    "codex_duration_seconds": "",
                    "rb_execution_duration_seconds": "",
                    "grading_duration_seconds": "",
                    "total_duration_seconds": "",
                    "input_tokens": "",
                    "cached_input_tokens": "",
                    "output_tokens": "",
                    "reasoning_output_tokens": "",
                    "failed_checks": "",
                    "graded_run": "",
                }
            )
            continue

        metadata = read_json(graded_run / "run_metadata.json")
        grading_data = read_json(grading_path)
        scores, failures = collect_scores(grading_data)

        passed = sum(1 for score in scores if score == 1)
        total = len(scores)

        codex_metadata = metadata
        if "token_usage" not in codex_metadata:
            codex_metadata = find_latest_codex_metadata(runs, graded_run)

        token_usage = codex_metadata.get("token_usage", {})
        rb_execution = metadata.get("rb_execution", {})
        rb_evaluation = metadata.get("rb_evaluation", {})

        codex_duration = codex_metadata.get("duration_seconds", "")
        rb_duration = rb_execution.get("duration_seconds", "")
        grading_duration = rb_evaluation.get("duration_seconds", "")

        durations = [
            value
            for value in (codex_duration, rb_duration, grading_duration)
            if isinstance(value, (int, float))
        ]

        failed_text = " | ".join(
            f"{failure['check']}: {failure['explanation']}"
            for failure in failures
        )

        execution_status = rb_execution.get("status", "")
        execution_result = read_json(
            graded_run / "grading" / "input" / "execution_result.json"
        )
        analysis_executed = execution_result.get("ok")

        if total:
            if analysis_executed is False:
                status = "graded_execution_failure"
            elif execution_status not in ("", "completed"):
                status = "graded_execution_failure"
            else:
                status = "completed"
        else:
            status = "grading_result_unreadable"

        rows.append(
            {
                "study_id": study_id,
                "status": status,
                "score": passed,
                "passed_checks": passed,
                "total_checks": total,
                "codex_duration_seconds": codex_duration,
                "rb_execution_duration_seconds": rb_duration,
                "grading_duration_seconds": grading_duration,
                "total_duration_seconds": sum(durations) if durations else "",
                "input_tokens": token_usage.get("input_tokens", ""),
                "cached_input_tokens": token_usage.get("cached_input_tokens", ""),
                "output_tokens": token_usage.get("output_tokens", ""),
                "reasoning_output_tokens": token_usage.get(
                    "reasoning_output_tokens", ""
                ),
                "failed_checks": failed_text,
                "graded_run": str(graded_run.relative_to(REPO_ROOT)),
            }
        )

    fieldnames = [
        "study_id",
        "status",
        "score",
        "passed_checks",
        "total_checks",
        "codex_duration_seconds",
        "rb_execution_duration_seconds",
        "grading_duration_seconds",
        "total_duration_seconds",
        "input_tokens",
        "cached_input_tokens",
        "output_tokens",
        "reasoning_output_tokens",
        "failed_checks",
        "graded_run",
    ]

    with CSV_PATH.open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    JSON_PATH.write_text(json.dumps(rows, indent=2) + "\n")

    print(f"Wrote: {CSV_PATH}")
    print(f"Wrote: {JSON_PATH}")
    print()
    print("Study scores:")
    for row in rows:
        score = (
            f"{row['passed_checks']}/{row['total_checks']}"
            if row["total_checks"] != ""
            else "N/A"
        )
        print(f"  Study {row['study_id']:>2}: {score} — {row['status']}")


if __name__ == "__main__":
    main()
