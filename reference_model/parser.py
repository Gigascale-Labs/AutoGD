import json
import math
from pathlib import Path
from typing import Any


REQUIRED_PARAMETERS = {
    "name",
    "capital",
    "labor",
    "sigma",
    "productivity",
}


def load_parameter_cases(
    json_path: str | Path,
) -> list[dict[str, Any]]:
    """
    Load and validate model parameter cases from a JSON file.
    """
    path = Path(json_path)

    if not path.is_file():
        raise FileNotFoundError(f"Parameter file not found: {path}")

    try:
        with path.open("r", encoding="utf-8") as file:
            document = json.load(file)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Invalid JSON in parameter file {path}: {exc}"
        ) from exc

    cases = document.get("cases")

    if not isinstance(cases, list) or not cases:
        raise ValueError(
            "The parameter file must contain a non-empty 'cases' list."
        )

    validated_cases = []

    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            raise ValueError(f"Case {index} must be a JSON object.")

        missing = REQUIRED_PARAMETERS - case.keys()

        if missing:
            missing_names = ", ".join(sorted(missing))
            raise ValueError(
                f"Case {index} is missing required fields: {missing_names}"
            )

        validated_case = {
            "name": case["name"],
            "capital": _validate_positive_number(
                case["capital"], "capital", index
            ),
            "labor": _validate_positive_number(
                case["labor"], "labor", index
            ),
            "sigma": _validate_sigma(case["sigma"], index),
            "productivity": _validate_positive_number(
                case["productivity"], "productivity", index
            ),
        }

        if not isinstance(validated_case["name"], str):
            raise ValueError(
                f"Case {index}: 'name' must be a string."
            )

        if not validated_case["name"].strip():
            raise ValueError(
                f"Case {index}: 'name' cannot be empty."
            )

        validated_cases.append(validated_case)

    return validated_cases

def _validate_positive_number(
    value: object,
    parameter_name: str,
    case_index: int,
) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(
            f"Case {case_index}: '{parameter_name}' must be numeric."
        )

    parsed = float(value)

    if not math.isfinite(parsed) or parsed <= 0:
        raise ValueError(
            f"Case {case_index}: '{parameter_name}' must be "
            "finite and greater than zero."
        )

    return parsed


def _validate_sigma(value: object, case_index: int) -> float:
    sigma = _validate_positive_number(value, "sigma", case_index)

    if sigma >= 1:
        raise ValueError(
            f"Case {case_index}: 'sigma' must satisfy 0 < sigma < 1."
        )

    return sigma