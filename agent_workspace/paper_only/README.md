# Static scarcity-of-labor model for Figure 6

This implementation reproduces the paper's static equilibrium with rising automation and reports total output plus payments to labor and capital for both Figure 6 cases.

It assumes Python 3.10 or newer.

Install the sole external dependency and run the model from this directory:

```bash
python3 -m pip install -r requirements.txt
python3 run_model.py
```

The command writes:

- `outputs/left_results.json`
- `outputs/right_results.json`
- `outputs/figure6.png`

File structure:

- `model.py` contains the static equilibrium equations and the one-Phi evaluator.
- `parameters.json` stores the two Figure 6 parameter cases and the inclusive automation grid.
- `run_model.py` loads parameters, validates every equilibrium, writes complete JSON results, and creates the plot.
- `requirements.txt` lists the plotting dependency.

The implementation uses Section 2.2 (baseline task production), Section 2.3's Lemma 1 and equations (3)--(8), and Section 2.5 / Figure 6.  Equation (3) supplies the automation threshold; equation (4) supplies Region 1 output; equations (6)--(7) supply Region 1 factor returns; and equation (5) supplies Region 2 output and factor returns.  Figure 6 supplies the two cases: `(K, L, sigma) = (1, 1, 0.5)` and `(10, 1, 0.2)`, with the paper's normalized productivity scale `A = 1` used in the figure.
