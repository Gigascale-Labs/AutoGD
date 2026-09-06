import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
RESULTS = (
    REPO_ROOT
    / "execution/our_models/scarcity_of_labor_ra_hard/input/replication_data/scarcity_of_labor_replication_outputs"
)
REFERENCE_MODEL_DIR = REPO_ROOT / "for_reference/reference_model"

sys.path.insert(0, str(REFERENCE_MODEL_DIR))
import model as reference_model

metadata = json.loads((RESULTS / "run_metadata.json").read_text())
model_params = metadata["model_params"]
cases = {c["name"]: c for c in metadata["cases"]}

# RA's own declared parameters: a single global sigma/A applied to both cases
# (run_metadata.json has no per-case sigma, unlike Codex's figure6_parameters.json).
params = {
    name: {"K": c["K"], "L": c["L"], "sigma": model_params["sigma"], "A": model_params["A"]}
    for name, c in cases.items()
}

frames = []
for case_name in cases:
    npz = np.load(RESULTS / f"{case_name}_results.npz")
    df = pd.DataFrame(
        {
            "phi": npz["phi"],
            "output": npz["output"],
            "wage": npz["wage_rate"],
            "capital_return": npz["capital_return"],
            "wage_bill": npz["wage_bill"],
            "capital_income": npz["capital_income"],
        }
    )
    df["case"] = case_name
    frames.append(df)

agent_df = pd.concat(frames, ignore_index=True)

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

print("Max absolute differences (RA's own declared parameters, sigma applied globally):")
print(summary)

overall_max = summary.to_numpy().max()
print(f"\nOverall max absolute difference: {overall_max:.3e}")

tolerance = 1e-6
if overall_max > tolerance:
    raise SystemExit(f"FAIL: exceeds tolerance {tolerance}")

print(f"PASS: all numerical outputs match reference within {tolerance}")
