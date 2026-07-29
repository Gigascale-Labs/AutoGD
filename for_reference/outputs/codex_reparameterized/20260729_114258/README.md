# Codex scarcity-of-labour reparameterisation

This folder records the successful bullet 4 reparameterisation run.

## What was tested

Codex received a frozen, already-validated scarcity-of-labour implementation and a new parameter set:

- A = 1.2
- K = 4.0
- L = 2.0
- sigma = 0.35

Codex created a separate execution wrapper and re-ran the model without modifying `model.py`.

## Result

The reparameterised implementation passed validation against the independent reference model.

- 1,001 Phi values evaluated from 0 to 1
- threshold = 0.6666666666666666
- maximum accounting error = 5.33e-15
- maximum numerical difference from the reference = 7.11e-15
- sign mismatches = 0
- frozen model unchanged = true

These differences are floating-point noise.

## Main evidence

- `validation_summary.json` — machine-readable validation metadata
- `events.jsonl` — Codex execution trace and token usage
- `final_message.txt` — Codex completion report
- `model.py.before` — frozen model snapshot used for the integrity check

Generated artifacts:

- `agent_workspace/reparameterized/reparameterized_parameters.json`
- `agent_workspace/reparameterized/run_reparameterized.py`
- `agent_workspace/reparameterized/outputs/reparameterized_results.json`
- `agent_workspace/reparameterized/outputs/reparameterized_figure.png`
