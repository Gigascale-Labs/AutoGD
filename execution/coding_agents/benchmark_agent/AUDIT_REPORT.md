# Study 2 supervised preflight audit

Date: 2026-07-28

## Scope

This audit is limited to Study 2. No Codex, ReplicatorBench, Docker, grading, or paid API command was executed.

## Eligibility

Study 2 is eligible for the existing data-only runner. Eligibility is operationally represented by the complete input layout expected by `run_codex_rb_data_only.sh` under `replicatoragent/replicatorbench/data/original/2/input/`:

- `initial_details.txt`
- `original_paper.pdf`
- `post_registration.json`
- non-empty `replication_data/`

The runner has no separate eligibility manifest or allowlist. Study 2 satisfies every input check implemented by the runner. Its post-registration and runner template parse as JSON. The paper is a materialized PDF, and the replication inputs are a materialized R script and a 15,853,385-byte RDS file. None of these Study 2 paths is configured for Git LFS, and no file contains an LFS pointer in place of content.

Required shared inputs are also present:

- `replicatoragent/replicatorbench/templates/pre_registration_schema_python.json`
- `execution/coding_agents/build_rb_input.py`
- `execution/scripts/run_study.sh`
- `execution/coding_agents/prompts/replicatorbench_data_only.md`

## Intended command

```bash
execution/coding_agents/run_codex_rb_data_only.sh --study 2
```

The command selects exactly one study. The script has no batch mode, automatic retry, resume, completed-study skip, or budget-limit implementation.

## Expected artifacts

- Isolated workspace and generated implementation: `agent_workspace/replicatorbench_data_only/study_2/`
- Prepared RB input: `agent_workspace/replicatorbench_data_only/study_2/rb_input/`
- Timestamped Codex/run metadata: `for_reference/outputs/codex/study_2/<YYYYMMDD_HHMMSS>/`
- RB snapshot: `for_reference/outputs/agent/study_2/<YYYYMMDD_HHMMSS>/input/`
- Grading input/results beneath the timestamped Codex run directory, including `grading/evals/gpt-4o/execute_llm_eval.json`
- Benchmark summaries, maintained by the supervising agent: `for_reference/outputs/full_benchmark/benchmark_summary.csv` and `.json`

## Recording behavior

The runner records Codex exit status, Codex runtime, available Codex token fields, RB exit status/runtime/log/snapshot, and grading exit status/runtime/result in `run_metadata.json`. It does not calculate cost, enforce a budget, write the requested full-benchmark summaries, record UTC start/end timestamps, or distinguish Codex output tokens from reasoning tokens beyond fields present in the event stream. Cost must remain unavailable unless an explicit pricing configuration is supplied.

## Budget and pricing

No explicit benchmark budget or pricing configuration was found. The only variable named in `.env` is `OPENAI_API_KEY`; its value was not read or printed. The paid command therefore requires Juan's explicit approval.

## Git baseline

Before this report was written:

- Parent: `benchmark/full-rb-data-only...origin/main`, with untracked `execution/coding_agents/benchmark_agent/`.
- Submodule: detached `HEAD` at `fb6a804fd710764f3ad3c8b84e1323c2804c4776`, clean.

## Blocking infrastructure defect and risks

The preflight is not ready to run. `run_codex_rb_data_only.sh` uses `$CONDA_BIN` in the grading command while running with `set -u`, but does not define `CONDA_BIN`; it is also unset in the current environment. The command would therefore fail predictably at grading after paid Codex and RB work. `/opt/anaconda3/bin/conda` exists, but changing the command or runner requires explicit direction because the requested execution command is exact and production scripts may not be modified during this audit.

Other risks:

- Codex generation and `gpt-4o` grading are paid API operations.
- The runner deletes/recreates the Study 2 isolated workspace and timestamped grading workspace; it does not modify benchmark source inputs by design.
- Scientific/model failures must be retained as benchmark results.
- Token metadata may be absent from emitted events, and no configured pricing exists for cost estimation.

The maximum permitted attempts are two: one initial attempt and, only after explicit approval, at most one retry caused by a documented shared-infrastructure failure and associated fix. This supervised request authorizes only the initial attempt at present.

## Minimal implementation plan

Before execution, explicitly configure `CONDA_BIN` without exposing credentials, or approve a minimal runner fix that defines a safe default. No benchmark input or scientific implementation should change. After a successful preflight and explicit paid-run approval, run only Study 2 once, classify the outcome, and write the CSV/JSON summary records. Do not proceed to another study.

Potential file requiring an infrastructure change, only with approval:

- `execution/coding_agents/run_codex_rb_data_only.sh`

## Proposed supervised test

Run Study 2 only. A second supervised study is outside this task and should be considered only after reviewing Study 2's artifacts, resource use, and infrastructure behavior.
