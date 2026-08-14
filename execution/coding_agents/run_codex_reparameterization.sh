#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SOURCE_WORKSPACE="$REPO_ROOT/agent_workspace/paper_only"
WORKSPACE="$REPO_ROOT/agent_workspace/reparameterized"
INPUT_SOURCE="$REPO_ROOT/execution/our_models/scarcity_of_labor/input"
PROMPT_FILE="$REPO_ROOT/execution/coding_agents/prompts/reparameterize_model.md"
RUN_ID="$(date +%Y%m%d_%H%M%S)"
RUN_DIR="$REPO_ROOT/for_reference/outputs/codex_reparameterized/$RUN_ID"

CODEX_HOME_DIR="${CODEX_HOME_DIR:-$HOME/.codex-api}"
CODEX_MODEL="${CODEX_MODEL:-gpt-5.6-terra}"

rm -rf "$WORKSPACE"
mkdir -p "$WORKSPACE/task_input" "$RUN_DIR"

cp "$SOURCE_WORKSPACE/model.py" "$WORKSPACE/"
cp "$SOURCE_WORKSPACE/run_model.py" "$WORKSPACE/"
cp "$SOURCE_WORKSPACE/parameters.json" "$WORKSPACE/"
cp "$SOURCE_WORKSPACE/requirements.txt" "$WORKSPACE/"
cp "$SOURCE_WORKSPACE/README.md" "$WORKSPACE/"
cp -R "$SOURCE_WORKSPACE/outputs" "$WORKSPACE/"
cp "$INPUT_SOURCE/new_parameters.json" "$WORKSPACE/task_input/"

cp "$WORKSPACE/model.py" "$RUN_DIR/model.py.before"

CODEX_HOME="$CODEX_HOME_DIR" codex exec \
  --ignore-user-config \
  --model "$CODEX_MODEL" \
  -C "$WORKSPACE" \
  --sandbox workspace-write \
  --json \
  --output-last-message "$RUN_DIR/final_message.txt" \
  - < "$PROMPT_FILE" | tee "$RUN_DIR/events.jsonl"

cmp -s "$RUN_DIR/model.py.before" "$WORKSPACE/model.py" || {
  echo "ERROR: model.py changed during reparameterisation" >&2
  exit 1
}

echo "Codex run saved to: $RUN_DIR"
echo "Reparameterised workspace saved to: $WORKSPACE"
