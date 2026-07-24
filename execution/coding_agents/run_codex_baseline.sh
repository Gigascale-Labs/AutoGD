#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WORKSPACE="$REPO_ROOT/agent_workspace/baseline"
INPUT_SOURCE="$REPO_ROOT/execution/our_models/scarcity_of_labor/input"
PROMPT_FILE="$REPO_ROOT/execution/coding_agents/prompts/implement_model.md"
RUN_ID="$(date +%Y%m%d_%H%M%S)"
RUN_DIR="$REPO_ROOT/for_reference/outputs/codex/$RUN_ID"

rm -rf "$WORKSPACE/task_input"
mkdir -p "$WORKSPACE/task_input" "$RUN_DIR"

cp "$INPUT_SOURCE/initial_details.txt" "$WORKSPACE/task_input/"
cp "$INPUT_SOURCE/model_specification.pdf" "$WORKSPACE/task_input/"
cp "$INPUT_SOURCE/original_paper.pdf" "$WORKSPACE/task_input/"

codex exec \
  -C "$WORKSPACE" \
  --sandbox workspace-write \
  --json \
  --output-last-message "$RUN_DIR/final_message.txt" \
  - < "$PROMPT_FILE" | tee "$RUN_DIR/events.jsonl"

echo "Codex run saved to: $RUN_DIR"
echo "Generated implementation saved to: $WORKSPACE"
