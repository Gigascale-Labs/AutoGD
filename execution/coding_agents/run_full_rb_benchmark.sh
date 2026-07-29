#!/usr/bin/env bash
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RUNNER="${RUNNER:-$REPO_ROOT/execution/coding_agents/run_codex_rb_data_only.sh}"
SUMMARY_DIR="$REPO_ROOT/for_reference/outputs/full_benchmark"
SUMMARY_CSV="$SUMMARY_DIR/batch_status.csv"

mkdir -p "$SUMMARY_DIR"

printf "study,status,exit_code\n" > "$SUMMARY_CSV"

STUDIES="${STUDIES:-$(seq 1 20)}"

for study in $STUDIES; do
  echo
  echo "=================================================="
  echo "Starting study $study"
  echo "=================================================="

  if "$RUNNER" --study "$study"; then
    printf "%s,completed,0\n" "$study" >> "$SUMMARY_CSV"
    echo "Study $study completed."
  else
    exit_code=$?
    printf "%s,failed,%s\n" "$study" "$exit_code" >> "$SUMMARY_CSV"
    echo "Study $study failed with exit code $exit_code. Continuing."
  fi
done

echo
echo "Full benchmark loop finished."
echo "Summary: $SUMMARY_CSV"
