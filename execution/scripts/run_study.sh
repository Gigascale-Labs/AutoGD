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
#
# Passed as a `make` command-line variable (not just exported) because
# replicatorbench/Makefile does `export PYTHONPATH := .` unconditionally at its
# top; a plain shell-exported PYTHONPATH gets clobbered by that before the
# generator subprocess ever sees it. A command-line variable assignment beats
# a makefile `:=` assignment (short of an `override` directive, which this
# Makefile doesn't use), so this survives. The trailing `:.` preserves the
# Makefile's own "." entry, which the generator needs to import its local
# packages.
AUTOAPPROVE_PYTHONPATH="$SCRIPT_DIR/autoapprove:."

# Purge the target stage's own prior-run output so the agent can't find
# "already succeeded" evidence (e.g. execution_result.json's run-analysis:
# ok:true) and short-circuit straight to summarizing stale results instead of
# actually re-running. Safe because the previous run's full state was already
# preserved by this script's own post-run snapshot below before this ever
# runs again. Only clears outputs owned by the stage(s) TARGET invokes, not
# every stage's outputs (interpret-easy still needs execute-easy's results).
STALE_OUTPUTS=()
case "$TARGET" in
  design-easy)
    STALE_OUTPUTS=(replication_info.json)
    ;;
  execute-easy)
    STALE_OUTPUTS=(execution_result.json 'execution_results*.json' artifacts _artifacts _runtime)
    ;;
  interpret-easy)
    STALE_OUTPUTS=(interpret_results.json)
    ;;
  generate)
    STALE_OUTPUTS=(replication_info.json execution_result.json 'execution_results*.json' artifacts _artifacts _runtime)
    ;;
  pipeline-easy)
    STALE_OUTPUTS=(replication_info.json execution_result.json 'execution_results*.json' artifacts _artifacts _runtime interpret_results.json)
    ;;
esac

if [[ ${#STALE_OUTPUTS[@]} -gt 0 ]]; then
  echo "==> clearing stale $TARGET output from $STUDY_PATH: ${STALE_OUTPUTS[*]}"
  shopt -s nullglob
  for pattern in "${STALE_OUTPUTS[@]}"; do
    for match in "$STUDY_PATH"/$pattern; do
      rm -rf "$match"
    done
  done
  shopt -u nullglob
fi

if [[ ${#EXTRA_ARGS[@]} -gt 0 ]]; then
  echo "==> make $TARGET STUDY=$STUDY_PATH ${EXTRA_ARGS[*]}"
else
  echo "==> make $TARGET STUDY=$STUDY_PATH"
fi

set +e
if [[ ${#EXTRA_ARGS[@]} -gt 0 ]]; then
  (
    cd "$PROJECT_DIR"
    uv run --project "$REPO_ROOT" make "$TARGET" \
      "STUDY=$STUDY_PATH" \
      "PYTHONPATH=$AUTOAPPROVE_PYTHONPATH" \
      "${EXTRA_ARGS[@]}"
  )
else
  (
    cd "$PROJECT_DIR"
    uv run --project "$REPO_ROOT" make "$TARGET" \
      "STUDY=$STUDY_PATH" \
      "PYTHONPATH=$AUTOAPPROVE_PYTHONPATH"
  )
fi
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

rsync -a \
  --exclude='*.pdf' \
  --exclude='replication_data/' \
  --exclude='task_input/replication_data/' \
  "$STUDY_PATH/" "$SNAPSHOT_DIR/input/"
echo "==> snapshot saved to $SNAPSHOT_DIR/input"

exit $STATUS
