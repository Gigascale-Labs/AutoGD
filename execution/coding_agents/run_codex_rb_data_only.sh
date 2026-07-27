#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RB_ROOT="$REPO_ROOT/replicatoragent/replicatorbench"
PROMPT_FILE="$REPO_ROOT/execution/coding_agents/prompts/replicatorbench_data_only.md"
CODEX_HOME_DIR="${CODEX_HOME_DIR:-$HOME/.codex-api}"
CODEX_MODEL="${CODEX_MODEL:-gpt-5.6-terra}"

usage() {
  echo "Usage: $0 --study STUDY_ID [--prepare-only]"
}

STUDY_ID=""
PREPARE_ONLY=false

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
  "$STUDY_INPUT/post_registration.json" \
  "$STUDY_INPUT/replication_data" \
  "$RB_ROOT/templates/pre_registration_schema_python.json" \
  "$PROMPT_FILE"
do
  if [[ ! -e "$required" ]]; then
    echo "Missing required input: $required" >&2
    exit 1
  fi
done

rm -rf "$WORKSPACE"
mkdir -p "$TASK_INPUT/replication_data" "$RUN_DIR"

cp "$STUDY_INPUT/initial_details.txt" "$TASK_INPUT/"
cp "$STUDY_INPUT/original_paper.pdf" "$TASK_INPUT/"
cp "$STUDY_INPUT/post_registration.json" "$TASK_INPUT/"
cp "$RB_ROOT/templates/pre_registration_schema_python.json" \
  "$TASK_INPUT/pre_registration_template.json"

find "$STUDY_INPUT/replication_data" -maxdepth 1 -type f \
  ! -name '*.py' \
  ! -name '*.R' \
  ! -name '*.r' \
  ! -name '*.sh' \
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

if [[ "$PREPARE_ONLY" == true ]]; then
  echo "Prepare-only mode: Codex was not invoked."
  exit 0
fi

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

python - "$RUN_DIR/run_metadata.json" "$RUN_DIR/events.jsonl" "$CODEX_EXIT" "$DURATION_SECONDS" <<'PY'
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

echo "Codex run artifacts: $RUN_DIR"
echo "Generated implementation: $WORKSPACE"

exit "$CODEX_EXIT"
