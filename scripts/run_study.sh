#!/usr/bin/env bash
# Run a ReplicatorBench make target against a study, then snapshot the study
# directory's outputs into <study_root>/runs/<timestamp>/ so the next run's
# overwrite (replication_info.json, execution_results.json, artifacts/, etc.
# are all written in-place by the pipeline) doesn't destroy prior results.
#
# Usage: scripts/run_study.sh <make-target> STUDY=<path> [MODEL=...] [ARGS...]
# Example: scripts/run_study.sh execute-easy STUDY=$(pwd)/our_models/scarcity_of_labor/input MODEL=gpt-5.4-mini
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
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

echo "==> make $TARGET STUDY=$STUDY_PATH ${EXTRA_ARGS[*]}"
set +e
( cd "$PROJECT_DIR" && uv run --project "$REPO_ROOT" make "$TARGET" "STUDY=$STUDY_PATH" "${EXTRA_ARGS[@]}" )
STATUS=$?
set -e

if [[ $STATUS -ne 0 ]]; then
  echo "==> make $TARGET exited with status $STATUS; snapshotting anyway"
fi

STUDY_ROOT="$(dirname "$STUDY_PATH")"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
SNAPSHOT_DIR="$STUDY_ROOT/runs/$TIMESTAMP"
mkdir -p "$SNAPSHOT_DIR/input"
rsync -a --exclude='*.pdf' "$STUDY_PATH/" "$SNAPSHOT_DIR/input/"
echo "==> snapshot saved to $SNAPSHOT_DIR/input"

exit $STATUS
