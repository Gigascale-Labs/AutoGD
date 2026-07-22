#!/usr/bin/env bash
set -euo pipefail

EXPECTED_COMMIT="fb6a804fd710764f3ad3c8b84e1323c2804c4776"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${REPLICATORBENCH_REPO:-$SCRIPT_DIR/../replicatoragent}"
PROJECT_DIR="$REPO_ROOT/replicatorbench"

if [[ ! -e "$REPO_ROOT/.git" ]]; then
  echo "ERROR: ReplicatorBench repository not found at $REPO_ROOT"
  exit 1
fi

ACTUAL_COMMIT="$(git -C "$REPO_ROOT" rev-parse HEAD)"

if [[ "$ACTUAL_COMMIT" != "$EXPECTED_COMMIT" ]]; then
  echo "ERROR: Wrong ReplicatorBench commit"
  echo "Expected: $EXPECTED_COMMIT"
  echo "Actual:   $ACTUAL_COMMIT"
  exit 1
fi

if [[ ! -f "$PROJECT_DIR/Makefile" ]]; then
  echo "ERROR: ReplicatorBench project folder is incomplete"
  exit 1
fi

if [[ -n "$(git -C "$REPO_ROOT" status --porcelain)" ]]; then
  echo "WARNING: ReplicatorBench working tree has local changes"
else
  echo "ReplicatorBench working tree: clean"
fi

echo "ReplicatorBench path: $PROJECT_DIR"
echo "Pinned commit verified: $ACTUAL_COMMIT"
docker info >/dev/null
echo "Docker: OK"
python --version
