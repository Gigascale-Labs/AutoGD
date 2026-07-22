#!/usr/bin/env bash
# Run a ReplicatorBench make target against a study, then snapshot the study
# directory's outputs into for_reference/outputs/agent/<study_name>/<timestamp>/
# (matching the for_reference/outputs/reference/ convention used by
# reference_model/plots.py) so the next run's in-place overwrite
# (replication_info.json, execution_results.json, artifacts/, etc.) doesn't
# destroy prior results.
#
# Usage: execution/scripts/run_study.sh <make-target> STUDY=<path> [MODEL=...] [ARGS...]
# Example: execution/scripts/run_study.sh execute-easy STUDY=$(pwd)/execution/our_models/scarcity_of_labor/input MODEL=gpt-5.4-mini
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PROJECT_DIR="$REPO_ROOT/replicatoragent/replicatorbench"

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <make-target> STUDY=<path> [MODEL=...] [ARGS...]" >&2
  exit 1
fi

TARGET="$1"
shift

STUDY_PATH=""
EXTRA_ARGS=()
for arg in "$@"; do
  if [[ "$arg" == STUDY=* ]]; then
    STUDY_PATH="${arg#STUDY=}"
  else
    EXTRA_ARGS+=("$arg")
  fi
done

if [[ -z "$STUDY_PATH" ]]; then
  echo "ERROR: STUDY=<path> is required" >&2
  exit 1
fi

STUDY_PATH="$(cd "$STUDY_PATH" && pwd)"

# Auto-approve ReplicatorBench's human-confirmation prompts (core/tools.py,
# generator/execute_tools.py) so headless runs never block on stdin. This is a
# root-level shim (execution/scripts/autoapprove/sitecustomize.py), not a submodule edit.
export PYTHONPATH="$SCRIPT_DIR/autoapprove${PYTHONPATH:+:$PYTHONPATH}"

echo "==> make $TARGET STUDY=$STUDY_PATH ${EXTRA_ARGS[*]}"
set +e
( cd "$PROJECT_DIR" && uv run --project "$REPO_ROOT" make "$TARGET" "STUDY=$STUDY_PATH" "${EXTRA_ARGS[@]}" )
STATUS=$?
set -e

if [[ $STATUS -ne 0 ]]; then
  echo "==> make $TARGET exited with status $STATUS; snapshotting anyway"
fi

STUDY_ROOT="$(dirname "$STUDY_PATH")"
STUDY_NAME="$(basename "$STUDY_ROOT")"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
if [[ $STATUS -ne 0 ]]; then
  TIMESTAMP="${TIMESTAMP}_FAILED"
fi
SNAPSHOT_DIR="$REPO_ROOT/for_reference/outputs/agent/$STUDY_NAME/$TIMESTAMP"
mkdir -p "$SNAPSHOT_DIR/input"
rsync -a --exclude='*.pdf' "$STUDY_PATH/" "$SNAPSHOT_DIR/input/"
echo "==> snapshot saved to $SNAPSHOT_DIR/input"

exit $STATUS
