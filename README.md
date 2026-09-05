# SysRisk agentic modelling experiments

This repository contains experiments testing whether coding agents can implement, execute, evaluate, and reparameterise social-science models while preserving scientific correctness.

The project contains two main experiment families:

- **Empirical benchmark:** runs the agentic pipeline across 20 ReplicatorBench studies to test whether the workflow can complete on existing empirical replication tasks. Results are under `for_reference/outputs/full_benchmark/` and `for_reference/outputs/EMPIRICAL_20_STUDY_SCORES.md`.
- **Controlled scarcity-of-labour experiment:** uses the model from Korinek & Suh as a known-ground-truth case for testing implementation correctness, evaluator reliability, and reparameterisation.

For the controlled experiment:

- `execution/our_models/scarcity_of_labor_ra_hard/` contains the ReplicatorAgent condition and its evaluations.
- `agent_workspace/paper_only/` contains the Codex paper-only implementation.
- `for_reference/reference_model/` contains the independent human-written reference implementation used for numerical validation.
- `agent_workspace/reparameterized/` contains the reparameterised Codex run.
- `for_reference/outputs/codex_reparameterized/` contains saved reparameterisation artifacts and validation results.
- `for_reference/outputs/interpret_eval_runs/` contains repeated evaluator runs used to test evaluator reliability.

A key distinction in this repository is between **pipeline completion/evaluator scores** and **scientific correctness**. Automated evaluation is treated as evidence about pipeline behaviour, while load-bearing correctness claims are checked independently against the reference implementation.


## Requirements

- Python 3.10+
- [uv](https://docs.astral.sh/uv/)
- Git
- [git-lfs](https://git-lfs.com/)
- Docker (running)
- OpenAI API key

## Setup

1. `git clone https://github.com/Gigascale-Labs/sysrisk.git && cd sysrisk`
2. `git submodule update --init --recursive`
3. `git -C replicatoragent lfs install --local && git -C replicatoragent lfs pull`
4. `uv sync`
5. `uv pip install -r replicatoragent/replicatorbench/requirements-dev.txt`
6. `cp TEMPLATE_ENV .env` then set `OPENAI_API_KEY`

`replicatoragent/` is the ReplicatorBench submodule, pinned to the commit in `configs/replicatorbench_version.txt`. Its study datasets (`*.csv`, `*.dta`) are stored in Git LFS; without `git-lfs` installed, checkout leaves pointer-text stubs instead of real data, and `git lfs pull` is required to materialize them. `uv sync` creates `.venv` and installs this repo's deps from `pyproject.toml`/`uv.lock`; the second `uv pip install` adds ReplicatorBench's own deps (pytest, openai, pandas, docker, …) into the same environment.

## Run

1. `docker info` — confirm daemon is up
2. `./execution/scripts/verify_replicatorbench.sh` — checks submodule commit, deps, Docker
3. `uv run jupyter lab execution/notebooks/` — launches JupyterLab on the `uv`-managed `.venv`; open `replicatorbench_environment_setup.ipynb` or `replicatoragent_scarcity_validation.ipynb`
4. Select the `.venv` kernel, then Kernel → Restart Kernel and Run All Cells, top to bottom, no skipped cells

The notebook drives ReplicatorBench (`make extract-stage1`, `make pipeline-easy`) against the pinned commit; `for_reference/reference_model/{model.py,parser.py,plots.py}` implements the reference equations independently, with `tests.py` asserting correctness. Its own setup cell sets `PYTHONPATH` so the auto-approve shim (below) applies to every `make` call it makes.

## Adding a new benchmark study (submodule-native)

No scaffolding tool exists; create the folder by hand, locally (not upstreamed — submodule stays pinned to `configs/replicatorbench_version.txt`; `verify_replicatorbench.sh` only warns on local changes).

1. Create `replicatoragent/replicatorbench/data/original/<N>/` (next free integer ID) containing:
   - `original_paper.pdf` — source paper
   - `initial_details.txt` — orienting notes/hints
   - `replication_data/` — datasets/scripts (`.csv`, `.dta`, `.R`, `.do`, …)
   - `human_preregistration.(pdf|docx)`, `human_report.(pdf|docx)` — human reference docs
   - `expected_post_registration.json` — ground truth (schema: `replicatorbench/templates/`)
2. `cd replicatoragent/replicatorbench`
3. `make pipeline-easy STUDY=./data/original/<N> MODEL=gpt-5.4-mini`

Runs Extract → Design → Execute → Interpret against the study folder. Individual stages (`extract-stage1`, `design-easy`, `execute-easy`, `interpret-easy`) and evaluators (`evaluate-extract`, `evaluate-design`, `evaluate-execute`, `evaluate-summary`) take the same `STUDY=` arg. Prefer `execution/scripts/run_study.sh` (below) over calling `make` directly — it adds auto-approval and result snapshots.

## Custom studies (execution/our_models/)

For papers outside the submodule's benchmark set, `execution/our_models/<name>/input/` holds the study: `original_paper.pdf`, `initial_details.txt`, and `replication_data/` if there's a dataset (omit for a purely theoretical model). `replication_info.json` is normally generated by `make design-easy`; hand-author it to skip straight to `execute-easy`. No copying into `replicatoragent/` is required — ReplicatorBench resolves `STUDY=` to an absolute path dynamically, so any location works.

1. `./execution/scripts/run_study.sh execute-easy STUDY=execution/our_models/scarcity_of_labor/input MODEL=gpt-5.4-mini`
2. `./execution/scripts/run_study.sh interpret-easy STUDY=execution/our_models/scarcity_of_labor/input MODEL=gpt-5.4-mini`

`execution/scripts/run_study.sh <target> STUDY=<path> [MODEL=... ...]` wraps `make <target>` and:
- **Auto-approves** ReplicatorBench's human-confirmation prompts via `execution/scripts/autoapprove/sitecustomize.py`, loaded through `PYTHONPATH`. It monkey-patches `input()` to return `"yes"`. Without it, `core/tools.py`/`generator/execute_tools.py` block on stdin and crash (`EOFError`) in any non-interactive run.
- **Snapshots** the study dir (excluding `*.pdf`) to `for_reference/outputs/agent/<study_name>/<timestamp>/input/` after the run, success or failure. Required because ReplicatorBench overwrites `replication_info.json` / `execution_results.json` / `interpret_results.json` / generated artifacts in place on every run — the container bind-mounts `/workspace` directly onto `STUDY=`, and `core/agent.py` writes stage outputs with unconditional `open(path, "w")`. Without snapshotting, a rerun silently destroys the prior run's results.

## Cross-validating agent output

`for_reference/reference_model/` is a hand-written, independent Python implementation (`model.py`'s `compute_equilibrium()`, plus `parser.py`, `plots.py`, `tests.py`) usable as ground truth for numerically checking agent-generated results. This matters because **ReplicatorBench's own interpret stage does not do numeric comparison** — it only has an LLM compare free-text summaries of "original" vs. "replicated" results, so a wrong sign or magnitude can pass its own review undetected. Run `uv run python -m pytest for_reference/reference_model/tests.py` to check the reference implementation itself.

## Repository contents

```text
configs/                       Parameter files and pinned ReplicatorBench commit
agent_workspace/               Tracked Codex paper-only and reparameterisation artifacts
execution/coding_agents/       Agent runners, prompts, benchmark utilities, and validation scripts
execution/notebooks/           Environment setup and numerical validation notebooks
execution/our_models/          ReplicatorAgent/custom study workspaces and evaluation artifacts
execution/scripts/             ReplicatorBench verification and run wrappers
for_reference/reference_model/ Independent reference implementation + tests (ground truth)
for_reference/outputs/         Empirical benchmark results, saved agent runs, evaluator tests, and validation outputs
replicatoragent/               ReplicatorBench submodule (pinned)
pyproject.toml                 Python dependencies managed with uv
```

## Known limitations

- ReplicatorBench's interpret stage judges results as free text, not numbers — no tolerance-based numeric diff exists in the pipeline. Cross-check anything load-bearing against `for_reference/reference_model/model.py`.
- Reruns against the same `STUDY=` path overwrite in place; always use `execution/scripts/run_study.sh`, not raw `make`, to keep history.

## Common issues

- Kernel missing in Jupyter: `uv run python -m ipykernel install --user --name sysrisk-poc --display-name "Python (SysRisk POC)"`
- Docker errors: start Docker, rerun `docker info`
- API auth errors: confirm `.env` has a valid `OPENAI_API_KEY`, restart the kernel
- `make` hangs or crashes with `EOFError` on a confirmation prompt: you called `make` directly instead of `execution/scripts/run_study.sh`; either use the wrapper or `export PYTHONPATH=$(pwd)/execution/scripts/autoapprove` first
