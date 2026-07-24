# Codex Baseline Workflow

This experiment tests whether Codex can independently implement the scarcity-of-labor model from the provided task package.

## Inputs given to Codex

Codex receives only:

- `initial_details.txt`
- `model_specification.pdf`
- `original_paper.pdf`
- `prompts/implement_model.md`

The hidden reference implementation and validation artifacts are not exposed to Codex.

## Run the experiment

From the repository root:

```bash
./execution/coding_agents/run_codex_baseline.sh
