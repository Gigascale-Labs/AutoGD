# Static scarcity-of-labor model

This implementation evaluates the static scarcity-of-labor model in Korinek and Suh (Section 2.3) for the two Figure 6 parameter cases.

It assumes Python 3.10 or newer.

No external Python packages are required.

If you want to create an isolated environment before running the standard-library implementation:

```sh
python3 -m venv .venv
```

Run the model from this directory:

```sh
python3 run_model.py
```

The command writes complete numerical results to `outputs/left_results.json` and `outputs/right_results.json`, and the comparison plot to `outputs/figure6.png`.

`model.py` contains the equations and one-Phi evaluator. `parameters.json` holds the two parameter cases. `run_model.py` loads those parameters, evaluates the Phi grid, checks accounting, and writes outputs. `requirements.txt` lists the plotting dependency.
