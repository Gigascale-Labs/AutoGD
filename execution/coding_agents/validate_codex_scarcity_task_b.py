import json
import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
RESULTS = REPO_ROOT / "agent_workspace/codex_scarcity_task_b/rb_input/results"
REFERENCE_MODEL_DIR = REPO_ROOT / "for_reference/reference_model"

sys.path.insert(0, str(REFERENCE_MODEL_DIR))
import model as reference_model

params = json.loads((RESULTS / "figure6_parameters.json").read_text())["parameters"]
agent_df = pd.read_csv(RESULTS / "figure6_results.csv")

fields = {
    "output": "output",
    "wage": "wage",
    "capital_return": "capital_return",
    "wage_bill": "wage_bill",
    "capital_income": "capital_income",
}

rows = []

for case_name, case_df in agent_df.groupby("case"):
    p = params[case_name]

    for _, row in case_df.iterrows():
        ref = reference_model.compute_equilibrium(
            phi=row["phi"],
            capital=p["K"],
            labor=p["L"],
            sigma=p["sigma"],
            productivity=p["A"],
        )

        out = {"case": case_name, "phi": row["phi"]}

        for agent_field, reference_field in fields.items():
            out[f"abs_diff_{agent_field}"] = abs(
                row[agent_field] - ref[reference_field]
            )

        rows.append(out)

comparison = pd.DataFrame(rows)

diff_cols = [c for c in comparison.columns if c.startswith("abs_diff_")]
summary = comparison.groupby("case")[diff_cols].max()

print("Max absolute differences:")
print(summary)

overall_max = summary.to_numpy().max()
print(f"\nOverall max absolute difference: {overall_max:.3e}")

tolerance = 1e-6
if overall_max > tolerance:
    raise SystemExit(f"FAIL: exceeds tolerance {tolerance}")

print(f"PASS: all numerical outputs match reference within {tolerance}")
