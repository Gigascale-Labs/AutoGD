# SysRisk ReplicatorAgent POC

Jupyter notebook testing whether ReplicatorAgent can reproduce a social-science model and rerun it under a different parameter set.

## Requirements

- Python 3.10+
- [uv](https://docs.astral.sh/uv/)
- Git
- [git-lfs](https://git-lfs.com/)
- Docker (running)
- OpenAI API key

## Setup

```bash
git clone https://github.com/Gigascale-Labs/sysrisk.git && cd sysrisk
git submodule update --init --recursive
git -C replicatoragent lfs install --local && git -C replicatoragent lfs pull
uv sync
uv pip install -r replicatoragent/replicatorbench/requirements-dev.txt
cp TEMPLATE_ENV .env   # then set OPENAI_API_KEY
```

`replicatoragent/` is the ReplicatorBench submodule, pinned to the commit in `configs/replicatorbench_version.txt`. Its study datasets (`*.csv`, `*.dta`) are stored in Git LFS; without `git-lfs` installed, checkout leaves pointer-text stubs instead of real data, and `git lfs pull` is required to materialize them. `uv sync` creates `.venv` and installs this repo's deps from `pyproject.toml`/`uv.lock`; the second `uv pip install` adds ReplicatorBench's own deps (pytest, openai, pandas, docker, …) into the same environment.

## Run

```bash
docker info                              # confirm daemon is up
./scripts/verify_replicatorbench.sh      # checks submodule commit, deps, Docker
uv run jupyter lab notebooks/day1_environment_setup.ipynb
```

Select the `.venv` kernel. Kernel → Restart Kernel and Run All Cells, top to bottom, no skipped cells. The notebook drives ReplicatorBench (`make extract-stage1`, `make pipeline-easy`) against the pinned commit; `reference_model/{model.py,parser.py,plots.py}` implements the reference equations independently, with `tests.py` asserting correctness.

## Adding a new study

No scaffolding tool exists; create the folder by hand, locally (not upstreamed — submodule stays pinned to `configs/replicatorbench_version.txt`; `verify_replicatorbench.sh` only warns on local changes).

Create `replicatoragent/replicatorbench/data/original/<N>/` (next free integer ID) containing:
- `original_paper.pdf` — source paper
- `initial_details.txt` — orienting notes/hints
- `replication_data/` — datasets/scripts (`.csv`, `.dta`, `.R`, `.do`, …)
- `human_preregistration.(pdf|docx)`, `human_report.(pdf|docx)` — human reference docs
- `expected_post_registration.json` — ground truth (schema: `replicatorbench/templates/`)

### Running it

```bash
cd replicatoragent/replicatorbench
make pipeline-easy STUDY=./data/original/<N> MODEL=gpt-5.4-mini
```

Runs Extract → Design → Execute → Interpret against the new study folder. Individual stages (`extract-stage1`, `design-easy`, `execute-easy`, `interpret-easy`) and evaluators (`evaluate-extract`, `evaluate-design`, `evaluate-execute`, `evaluate-summary`) take the same `STUDY=` arg.

## Repository contents

```text
configs/          Parameter files, pinned ReplicatorBench commit
notebooks/        Jupyter notebook
reference_model/  Reference model implementation, parser, plots, tests
replicatoragent/  ReplicatorBench submodule
scripts/          Verification script
pyproject.toml    Python deps (uv)
```

## Common issues

- Kernel missing in Jupyter: `uv run python -m ipykernel install --user --name sysrisk-poc --display-name "Python (SysRisk POC)"`
- Docker errors: start Docker, rerun `docker info`
- API auth errors: confirm `.env` has a valid `OPENAI_API_KEY`, restart the kernel
