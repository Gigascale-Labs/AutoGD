"""Validate the Codex reparameterisation against the independent human reference."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

REPARAM_DIR = ROOT / "agent_workspace" / "reparameterized"
RUNNER = REPARAM_DIR / "run_reparameterized.py"
RESULTS_PATH = REPARAM_DIR / "outputs" / "reparameterized_results.json"

REFERENCE_MODEL_PATH = ROOT / "for_reference" / "reference_model" / "model.py"

SNAPSHOT_PATH = (
    ROOT
    / "for_reference"
    / "outputs"
    / "codex_reparameterized"
    / "20260729_114258"
    / "model.py.before"
)

FROZEN_MODEL_PATH = REPARAM_DIR / "model.py"

OUTPUT_PATH = (
    ROOT
    / "for_reference"
    / "outputs"
    / "codex_reparameterized"
    / "20260729_114258"
    / "validation_summary.reproduced.json"
)

TOLERANCE = 1e-12


def load_reference_module():
    spec = importlib.util.spec_from_file_location(
        "human_reference_model", REFERENCE_MODEL_PATH
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load independent reference model")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sign(value: float) -> int:
    return (value > 0) - (value < 0)


def main() -> int:
    # Re-run the frozen Codex implementation using the reparameterised inputs.
    subprocess.run(
        [sys.executable, str(RUNNER)],
        cwd=REPARAM_DIR,
        check=True,
    )

    with RESULTS_PATH.open("r", encoding="utf-8") as handle:
        codex_payload = json.load(handle)

    parameters = codex_payload["parameters"]
    codex_results = codex_payload["results"]

    reference = load_reference_module()

    threshold = reference.compute_threshold(
        capital=parameters["K"],
        labor=parameters["L"],
    )

    fields = {
        "Y": "output",
        "w": "wage",
        "R": "capital_return",
        "wage_bill": "wage_bill",
        "capital_income": "capital_income",
    }

    max_differences = {field: 0.0 for field in fields}
    sign_mismatches = {field: 0 for field in fields}
    max_accounting_error = 0.0

    for codex_row in codex_results:
        phi = float(codex_row["phi"])

        ref_row = reference.compute_equilibrium(
            phi=phi,
            capital=parameters["K"],
            labor=parameters["L"],
            sigma=parameters["sigma"],
            productivity=parameters["A"],
        )

        for codex_field, reference_field in fields.items():
            codex_value = float(codex_row[codex_field])
            reference_value = float(ref_row[reference_field])

            difference = abs(codex_value - reference_value)
            max_differences[codex_field] = max(
                max_differences[codex_field], difference
            )

            if sign(codex_value) != sign(reference_value):
                sign_mismatches[codex_field] += 1

        accounting_error = abs(
            float(codex_row["Y"])
            - float(codex_row["wage_bill"])
            - float(codex_row["capital_income"])
        )
        max_accounting_error = max(max_accounting_error, accounting_error)

    model_unchanged = (
        SNAPSHOT_PATH.exists()
        and FROZEN_MODEL_PATH.read_bytes() == SNAPSHOT_PATH.read_bytes()
    )

    threshold_matches = abs(
        float(codex_payload["threshold"]) - threshold
    ) <= TOLERANCE

    passed = (
        threshold_matches
        and model_unchanged
        and max_accounting_error <= TOLERANCE
        and all(value <= TOLERANCE for value in max_differences.values())
        and all(value == 0 for value in sign_mismatches.values())
    )

    summary = {
        "task": "scarcity_of_labor_reparameterization",
        "status": "passed" if passed else "failed",
        "parameters": parameters,
        "automation_grid_points": len(codex_results),
        "threshold": threshold,
        "threshold_matches": threshold_matches,
        "model_unchanged": model_unchanged,
        "max_accounting_error": max_accounting_error,
        "max_absolute_difference_vs_reference": max_differences,
        "sign_mismatches": sign_mismatches,
    }

    OUTPUT_PATH.write_text(
        json.dumps(summary, indent=2) + "\n",
        encoding="utf-8",
    )

    print(json.dumps(summary, indent=2))
    print(f"\nWrote reproduced validation to: {OUTPUT_PATH.relative_to(ROOT)}")

    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
