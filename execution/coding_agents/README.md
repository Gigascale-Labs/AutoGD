# Codex paper-only workflow

This experiment tests whether Codex can independently implement the scarcity-of-labor model from the source paper and minimal task instructions.

## Inputs given to Codex

Codex receives only:

- `initial_details.txt`
- `original_paper.pdf`
- `prompts/implement_model.md`

The independent reference implementation and validation artifacts are not exposed to Codex.

## Run the experiment

From the repository root:

```bash
./execution/coding_agents/run_codex_paper_only.sh
