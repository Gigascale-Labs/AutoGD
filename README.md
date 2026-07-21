# SysRisk ReplicatorAgent POC

This repository contains a Jupyter notebook for testing whether ReplicatorAgent can reproduce a simple social-science model and rerun the same implementation with a different parameter set.

## Requirements

Install before running:

- Python 3.9+
- Git
- Docker Desktop or Docker Engine
- An OpenAI API key

Docker must be running while the notebook executes.

## Setup

Clone this repository and enter it:

```bash
git clone https://github.com/Gigascale-Labs/sysrisk.git
cd sysrisk
```

Create a virtual environment and install the dependencies:

### macOS or Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements-poc.txt
```

### Windows PowerShell

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements-poc.txt
```

Clone the required ReplicatorBench repository beside this repository and use the pinned commit:

```bash
cd ..
git clone https://github.com/CenterForOpenScience/llm-benchmarking.git
cd llm-benchmarking
git checkout fb6a804fd710764f3ad3c8b84e1323c2804c4776
cd ../<REPOSITORY_DIRECTORY>
```

The folders should be arranged as follows:

```text
parent-directory/
├── llm-benchmarking/
└── <REPOSITORY_DIRECTORY>/
```

## API key

Create a `.env` file in the repository root:

```env
OPENAI_API_KEY=your_api_key_here
```

Do not commit this file.

## Run the notebook

Confirm that Docker is running:

```bash
docker info
```

Then launch Jupyter from the repository root:

```bash
jupyter lab notebooks/day1_environment_setup.ipynb
```

Select the `.venv` Python kernel when prompted. In Jupyter, use **Kernel → Restart Kernel and Run All Cells** and run the notebook from top to bottom without skipping cells.

## Repository contents

```text
configs/                  Configuration and parameter files
notebooks/                Jupyter notebook
scripts/                  Helper scripts
requirements-poc.txt      Python dependencies
```

## Common issues

If Jupyter does not show the virtual environment, run:

```bash
python -m ipykernel install --user --name sysrisk-poc --display-name "Python (SysRisk POC)"
```

For Docker errors, start Docker Desktop or Docker Engine and rerun `docker info`. For API authentication errors, check that `.env` exists and restart the notebook kernel.