# RB rubric fields that don't map cleanly to this study

`scarcity_of_labor` is a custom, hand-authored model-spec task (theoretical, dataless), not one of
ReplicatorBench's native SCORE studies. Its `replication_info.json` was hand-authored to skip
`extract-stage1`/`design-easy`, and its execution was produced by Codex standalone rather than by
RB's own `execute-easy`. Both grading stages (`interpret-easy`, `evaluate-execute`) ran successfully
against it, but several rubric fields either don't apply or are checked more loosely than they would
be for a native study.

## Missing inputs native SCORE studies normally have

- **`post_registration.json`** — normally produced by `extract-stage1`, which this study never ran.
  `interpret-easy` and `evaluate-execute` both reference it as an "agent_files" context item; both
  handled its absence gracefully (a logged file-not-found, not a hard failure), but neither stage's
  judgment is informed by it here.
- **`replication_data/`** — this model has no input dataset by design (stated explicitly in
  `initial_details.txt`). Rubric criteria that assume a dataset (`evaluate_design.file_system.1.3.3`,
  "data mounting path") were scored as trivially satisfied ("theoretical model used, so data mounting
  path is not relevant") rather than genuinely evaluated — those criteria aren't really being tested
  for this kind of study, just auto-passed.

## Rubric criteria that check field presence, not real behavior, for this workflow

- **`docker_specs` (base image, packages)** — these fields in `replication_info.json` describe the
  *original RB-native design run's* intended environment. Because bullet 2 deliberately skips RB's
  own `execute-easy` (to avoid RB's agent re-executing or potentially rewriting Codex's code), no
  Docker container was actually built or verified for Codex's implementation. The evaluator's pass
  on `evaluate_design.environment.1.1.1` ("docker_specs.base_image exists") confirms the field is
  present, not that Codex's `model.py`/`run_model.py` actually run inside that declared environment.
- **`evaluate_design.file_system.1.3.1`** ("hard-coded paths were detected and fixed") — scored a
  pass with the explanation "no specific mentions of hard-coded paths in the log." There is no
  execute-easy log for this run (Codex's original run predates any RB integration), so this is an
  absence-of-evidence pass, not a genuine check.

## Output schema mismatch

- RB's native `execute_schema.json` expects empirical-style results (`findings_summary` entries with
  `standard_error`, `confidence_interval`, `p_value`, `statistical_significance`, `direction`) — none
  of which apply to a deterministic closed-form model evaluated over a parameter grid. Rather than
  force-fit Codex's `Y`/`w`/`R`-over-Phi output into that schema, a minimal custom `execution_results.json`
  (`execution_summary` + `code_executed`) was written instead. `interpret-easy` handled this fine (it
  falls back to inspecting raw output files when the summary is thin), but this means the study's
  `execution_results.json` isn't schema-conformant with what a native SCORE study produces.

## Infrastructure incompatibility found and fixed

- `evaluate-execute`'s file-reading tool internally appends `/input` to whatever `STUDY=` path is
  passed (`core/validator/evaluate_execute.py`), unlike `interpret-easy`/`execute-easy`/`design-easy`,
  which expect `STUDY=` to point directly at the content folder. `STUDY=` must be the *parent* of the
  study's `input/` directory for `evaluate-execute` specifically — passing the `input/` folder itself
  causes silent "file access" failures (every rubric criterion scores 0 with "unable to verify due to
  access issues", not an explicit error). This cost one failed run before being caught; documenting it
  here so it isn't rediscovered the same way on the next custom study.

## Tooling gap

- `build_rb_input.py`/`normalize_rb_replication_info.py` (built for the RB-native studies pipeline)
  weren't used here — both hard-require `post_registration.json` and a `replication_data/` directory
  to exist, neither of which apply to this study. The RB input folder for this study was assembled by
  hand instead. It follows the same downstream execution/grading stages, but not the same input-
  packaging tooling, as the automated RB-studies pipeline.
- `aggregate_full_benchmark.py` (the 20-study benchmark's scoring rollup) expects studies named
  `study_<N>` under `for_reference/outputs/codex/study_<N>/`. This study's outputs live under
  `execution/our_models/scarcity_of_labor_codex/` and `for_reference/outputs/agent/scarcity_of_labor_codex/`,
  so it would not be picked up by that script without modification.
