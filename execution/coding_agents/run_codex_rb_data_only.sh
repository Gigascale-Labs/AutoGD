#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RB_ROOT="$REPO_ROOT/replicatoragent/replicatorbench"
PROMPT_FILE="$REPO_ROOT/execution/coding_agents/prompts/replicatorbench_data_only.md"
RB_TEMPLATE="$RB_ROOT/templates/pre_registration_schema_python.json"
RB_INPUT_BUILDER="$REPO_ROOT/execution/coding_agents/build_rb_input.py"
RB_RUNNER="$REPO_ROOT/execution/scripts/run_study.sh"
RB_EVALUATOR_PATCH="$REPO_ROOT/execution/coding_agents/benchmark_agent/rb_evaluator_action_parser.patch"
RB_EXECUTE_TURN_LIMIT_PATCH="$REPO_ROOT/execution/coding_agents/benchmark_agent/rb_execute_turn_limit.patch"

RB_EXECUTE_PATCH_APPLIED=false
RB_EVALUATOR_PATCH_APPLIED=false

cleanup_rb_patches() {
  if [[ "$RB_EVALUATOR_PATCH_APPLIED" == true ]]; then
    git -C "$REPO_ROOT/replicatoragent" apply --reverse "$RB_EVALUATOR_PATCH" >/dev/null 2>&1 || true
  fi
  if [[ "$RB_EXECUTE_PATCH_APPLIED" == true ]]; then
    git -C "$REPO_ROOT/replicatoragent" apply --reverse "$RB_EXECUTE_TURN_LIMIT_PATCH" >/dev/null 2>&1 || true
  fi
}

trap cleanup_rb_patches EXIT
CODEX_HOME_DIR="${CODEX_HOME_DIR:-$HOME/.codex-api}"
CODEX_MODEL="${CODEX_MODEL:-gpt-5.6-terra}"
RB_EVAL_MODEL="${RB_EVAL_MODEL:-gpt-4o}"
RB_CONDA_ENV="${RB_CONDA_ENV:-replicatorbench-poc}"

usage() {
  echo "Usage: $0 --study STUDY_ID [--prepare-only] [--rb-only]"
}

STUDY_ID=""
PREPARE_ONLY=false
RB_ONLY=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --study)
      STUDY_ID="${2:-}"
      shift 2
      ;;
    --prepare-only)
      PREPARE_ONLY=true
      shift
      ;;
    --rb-only)
      RB_ONLY=true
      shift
      ;;
    *)
      usage
      exit 2
      ;;
  esac
done

if [[ -z "$STUDY_ID" ]]; then
  usage
  exit 2
fi

STUDY_INPUT="$RB_ROOT/data/original/$STUDY_ID/input"
WORKSPACE="$REPO_ROOT/agent_workspace/replicatorbench_data_only/study_$STUDY_ID"
TASK_INPUT="$WORKSPACE/task_input"
RUN_ID="$(date +%Y%m%d_%H%M%S)"
RUN_DIR="$REPO_ROOT/for_reference/outputs/codex/study_$STUDY_ID/$RUN_ID"

for required in \
  "$STUDY_INPUT/initial_details.txt" \
  "$STUDY_INPUT/original_paper.pdf" \
  "$STUDY_INPUT/replication_data" \
  "$RB_TEMPLATE" \
  "$RB_INPUT_BUILDER" \
  "$RB_RUNNER" \
  "$PROMPT_FILE"
do
  if [[ ! -e "$required" ]]; then
    echo "Missing required input: $required" >&2
    exit 1
  fi
done

if [[ "$RB_ONLY" == false ]]; then
  rm -rf "$WORKSPACE"
  mkdir -p "$TASK_INPUT/replication_data" "$RUN_DIR"

  cp "$STUDY_INPUT/initial_details.txt" "$TASK_INPUT/"
  cp "$STUDY_INPUT/original_paper.pdf" "$TASK_INPUT/"
  if [[ -f "$STUDY_INPUT/post_registration.json" ]]; then
    cp "$STUDY_INPUT/post_registration.json" "$TASK_INPUT/"
  fi
  cp "$RB_TEMPLATE" "$TASK_INPUT/pre_registration_template.json"

  find "$STUDY_INPUT/replication_data" -maxdepth 1 -type f \
    -exec cp {} "$TASK_INPUT/replication_data/" \;

  cat > "$RUN_DIR/run_metadata.json" <<JSON
{
  "study_id": "$STUDY_ID",
  "mode": "data_only",
  "model": "$CODEX_MODEL",
  "codex_home": "$CODEX_HOME_DIR",
  "workspace": "$WORKSPACE",
  "status": "prepared"
}
JSON

  echo "Prepared isolated workspace: $WORKSPACE"
  echo "Copied inputs:"
  find "$TASK_INPUT" -maxdepth 2 -type f -print | sort
else
  if [[ ! -d "$WORKSPACE" ]]; then
    echo "Existing workspace not found for --rb-only: $WORKSPACE" >&2
    exit 1
  fi

  mkdir -p "$RUN_DIR"

  cat > "$RUN_DIR/run_metadata.json" <<JSON
{
  "study_id": "$STUDY_ID",
  "mode": "data_only_rb_only",
  "model": "$CODEX_MODEL",
  "workspace": "$WORKSPACE",
  "status": "prepared",
  "codex_exit_code": 0,
  "codex_reused": true
}
JSON

  CODEX_EXIT=0
fi

if [[ "$PREPARE_ONLY" == true ]]; then
  echo "Prepare-only mode: Codex was not invoked."
  exit 0
fi

if [[ "$RB_ONLY" == false ]]; then
  START_SECONDS="$(date +%s)"

  set +e
  CODEX_HOME="$CODEX_HOME_DIR" codex exec \
    --ignore-user-config \
    --model "$CODEX_MODEL" \
    -C "$WORKSPACE" \
    --sandbox workspace-write \
    --json \
    --output-last-message "$RUN_DIR/final_message.txt" \
    - < "$PROMPT_FILE" | tee "$RUN_DIR/events.jsonl"

  CODEX_EXIT="${PIPESTATUS[0]}"
  set -e

  END_SECONDS="$(date +%s)"
  DURATION_SECONDS="$((END_SECONDS - START_SECONDS))"

  python3 - \
    "$RUN_DIR/run_metadata.json" \
    "$RUN_DIR/events.jsonl" \
    "$CODEX_EXIT" \
    "$DURATION_SECONDS" <<'PY'
import json
import sys
from pathlib import Path

metadata_path = Path(sys.argv[1])
events_path = Path(sys.argv[2])
exit_code = int(sys.argv[3])
duration = int(sys.argv[4])

usage = {
    "input_tokens": None,
    "cached_input_tokens": None,
    "output_tokens": None,
    "reasoning_output_tokens": None,
}

if events_path.exists():
    for line in events_path.read_text(errors="replace").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue

        candidate = event.get("usage")
        if not isinstance(candidate, dict):
            candidate = event.get("token_usage")

        if isinstance(candidate, dict):
            for key in usage:
                if candidate.get(key) is not None:
                    usage[key] = candidate[key]

metadata = json.loads(metadata_path.read_text())
metadata.update(
    {
        "status": "completed" if exit_code == 0 else "failed",
        "codex_exit_code": exit_code,
        "duration_seconds": duration,
        "token_usage": usage,
    }
)
metadata_path.write_text(json.dumps(metadata, indent=2) + "\n")
PY

fi

if [[ "$CODEX_EXIT" -ne 0 ]]; then
  echo "Codex failed; RB input and execution were skipped." >&2
  echo "Codex run artifacts: $RUN_DIR"
  exit "$CODEX_EXIT"
fi

RB_INPUT="$WORKSPACE/rb_input"

python3 "$RB_INPUT_BUILDER" \
  --workspace "$WORKSPACE" \
  --template "$RB_TEMPLATE" \
  --output "$RB_INPUT"

echo "Codex run artifacts: $RUN_DIR"
echo "Generated implementation: $WORKSPACE"
echo "Prepared RB input: $RB_INPUT"

RB_LOG="$RUN_DIR/rb_execute.log"

if [[ -f "$RB_EXECUTE_TURN_LIMIT_PATCH" ]]; then
  if git -C "$REPO_ROOT/replicatoragent" apply --check "$RB_EXECUTE_TURN_LIMIT_PATCH" >/dev/null 2>&1; then
    git -C "$REPO_ROOT/replicatoragent" apply "$RB_EXECUTE_TURN_LIMIT_PATCH"
    RB_EXECUTE_PATCH_APPLIED=true
  elif git -C "$REPO_ROOT/replicatoragent" apply --reverse --check "$RB_EXECUTE_TURN_LIMIT_PATCH" >/dev/null 2>&1; then
    echo "RB execution turn-limit patch already applied."
  else
    echo "RB execution turn-limit patch could not be applied cleanly." >&2
    exit 1
  fi
fi

RB_START_SECONDS="$(date +%s)"

set +e
"$RB_RUNNER" execute-easy "STUDY=$RB_INPUT" \
  2>&1 | tee "$RB_LOG"
RB_EXIT="${PIPESTATUS[0]}"
set -e

RB_END_SECONDS="$(date +%s)"
RB_DURATION_SECONDS="$((RB_END_SECONDS - RB_START_SECONDS))"

RB_SNAPSHOT_PATH="$(
  sed -n 's/^==> snapshot saved to //p' "$RB_LOG" | tail -n 1
)"

python3 - \
  "$RUN_DIR/run_metadata.json" \
  "$RB_EXIT" \
  "$RB_DURATION_SECONDS" \
  "$RB_LOG" \
  "$RB_INPUT" \
  "$RB_SNAPSHOT_PATH" <<'PYMETA'
import json
import sys
from pathlib import Path

metadata_path = Path(sys.argv[1])
rb_exit_code = int(sys.argv[2])
rb_duration = int(sys.argv[3])
rb_log = Path(sys.argv[4])
rb_input = Path(sys.argv[5])
rb_snapshot = sys.argv[6].strip() or None

metadata = json.loads(metadata_path.read_text())

metadata["rb_execution"] = {
    "status": "completed" if rb_exit_code == 0 else "failed",
    "exit_code": rb_exit_code,
    "duration_seconds": rb_duration,
    "input_path": str(rb_input),
    "log_path": str(rb_log),
    "snapshot_path": rb_snapshot,
}

metadata["status"] = (
    "completed"
    if metadata.get("codex_exit_code") == 0 and rb_exit_code == 0
    else "failed"
)

metadata_path.write_text(json.dumps(metadata, indent=2) + "\n")
PYMETA

echo "RB execution log: $RB_LOG"
echo "RB duration: ${RB_DURATION_SECONDS}s"
echo "RB exit code: $RB_EXIT"

if [[ -n "$RB_SNAPSHOT_PATH" ]]; then
  echo "RB snapshot: $RB_SNAPSHOT_PATH"
fi

if [[ "$RB_EXIT" -ne 0 || -z "$RB_SNAPSHOT_PATH" ]]; then
  echo "RB execution failed or produced no snapshot; grading was skipped." >&2
  exit "$RB_EXIT"
fi

GRADE_ROOT="$RUN_DIR/grading"
GRADE_INPUT="$GRADE_ROOT/input"
GRADE_LOG="$RUN_DIR/rb_evaluate_execute.log"
GRADE_RESULT="$GRADE_ROOT/evals/$RB_EVAL_MODEL/execute_llm_eval.json"

rm -rf "$GRADE_ROOT"
mkdir -p "$GRADE_INPUT"
cp -R "$RB_SNAPSHOT_PATH"/. "$GRADE_INPUT/"

# Preserve the original study inputs for evaluator inspection.
mkdir -p "$GRADE_INPUT/task_input"
cp -R "$WORKSPACE/task_input"/. "$GRADE_INPUT/task_input/"

GRADE_START_SECONDS="$(date +%s)"

if [[ -f "$RB_EVALUATOR_PATCH" ]]; then
  if git -C "$REPO_ROOT/replicatoragent" apply --check "$RB_EVALUATOR_PATCH" >/dev/null 2>&1; then
    git -C "$REPO_ROOT/replicatoragent" apply "$RB_EVALUATOR_PATCH"
    RB_EVALUATOR_PATCH_APPLIED=true
  elif git -C "$REPO_ROOT/replicatoragent" apply --reverse --check "$RB_EVALUATOR_PATCH" >/dev/null 2>&1; then
    echo "RB evaluator compatibility patch already applied."
  else
    echo "RB evaluator compatibility patch could not be applied cleanly." >&2
    exit 1
  fi
fi

set +e
(
  cd "$RB_ROOT"
  "$CONDA_BIN" run -n "$RB_CONDA_ENV"     python -m validator.cli.evaluate_execute_cli     --study_path "$GRADE_ROOT"     --evaluator_model "$RB_EVAL_MODEL"
) 2>&1 | tee "$GRADE_LOG"
GRADE_EXIT="${PIPESTATUS[0]}"
set -e

GRADE_END_SECONDS="$(date +%s)"
GRADE_DURATION_SECONDS="$((GRADE_END_SECONDS - GRADE_START_SECONDS))"

python3 -   "$RUN_DIR/run_metadata.json"   "$GRADE_EXIT"   "$GRADE_DURATION_SECONDS"   "$GRADE_LOG"   "$GRADE_RESULT"   "$RB_EVAL_MODEL" <<'PYGRADE'
import json
import sys
from pathlib import Path

metadata_path = Path(sys.argv[1])
grade_exit = int(sys.argv[2])
grade_duration = int(sys.argv[3])
grade_log = Path(sys.argv[4])
grade_result = Path(sys.argv[5])
grade_model = sys.argv[6]

passed = None
total = None

if grade_result.is_file():
    result = json.loads(grade_result.read_text())
    scores = []

    def collect(value):
        if isinstance(value, dict):
            if isinstance(value.get("score"), (int, float)):
                scores.append(value["score"])
            else:
                for child in value.values():
                    collect(child)

    collect(result)
    if scores:
        passed = sum(1 for score in scores if score == 1)
        total = len(scores)

metadata = json.loads(metadata_path.read_text())
metadata["rb_evaluation"] = {
    "status": "completed" if grade_exit == 0 and grade_result.is_file() else "failed",
    "exit_code": grade_exit,
    "duration_seconds": grade_duration,
    "model": grade_model,
    "log_path": str(grade_log),
    "result_path": str(grade_result),
    "passed_checks": passed,
    "total_checks": total,
}

metadata["status"] = (
    "completed"
    if metadata.get("codex_exit_code") == 0
    and metadata.get("rb_execution", {}).get("exit_code") == 0
    and grade_exit == 0
    and grade_result.is_file()
    else "failed"
)

metadata_path.write_text(json.dumps(metadata, indent=2) + "\n")
PYGRADE

echo "RB grading log: $GRADE_LOG"
echo "RB grading duration: ${GRADE_DURATION_SECONDS}s"
echo "RB grading exit code: $GRADE_EXIT"

if [[ -f "$GRADE_RESULT" ]]; then
  echo "RB grading result: $GRADE_RESULT"
fi

exit "$GRADE_EXIT"
