import argparse
import math

def positive_float(value: str) -> float:
    """Parse a strictly positive finite float."""
    try:
        parsed = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"Expected a number, got {value!r}."
        ) from exc

    if not math.isfinite(parsed):
        raise argparse.ArgumentTypeError("Value must be finite.")

    if parsed <= 0:
        raise argparse.ArgumentTypeError("Value must be greater than 0.")

    return parsed


def phi_float(value: str) -> float:
    """Parse phi as a finite float in the closed interval [0, 1]."""
    try:
        parsed = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"Expected a number, got {value!r}."
        ) from exc

    if not math.isfinite(parsed):
        raise argparse.ArgumentTypeError("Phi must be finite.")

    if not 0 <= parsed <= 1:
        raise argparse.ArgumentTypeError("Phi must be between 0 and 1.")

    return parsed


def sigma_float(value: str) -> float:
    """
    Parse sigma.

    The paper's baseline model assumes 0 < sigma < 1.
    Sigma = 1 is also invalid because the CES formulas divide by sigma - 1.
    """
    parsed = positive_float(value)

    if parsed >= 1:
        raise argparse.ArgumentTypeError(
            "Sigma must satisfy 0 < sigma < 1."
        )

    return parsed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compute the static scarcity-of-labor equilibrium "
            "for a given automation share."
        )
    )

    parser.add_argument(
        "--phi",
        required=True,
        type=phi_float,
        help="Fraction of automatable tasks, between 0 and 1.",
    )

    parser.add_argument(
        "--capital",
        required=True,
        type=positive_float,
        help="Capital endowment K. Must be greater than 0.",
    )

    parser.add_argument(
        "--labor",
        required=True,
        type=positive_float,
        help="Labor endowment L. Must be greater than 0.",
    )

    parser.add_argument(
        "--sigma",
        required=True,
        type=sigma_float,
        help="Elasticity of substitution sigma, satisfying 0 < sigma < 1.",
    )

    parser.add_argument(
        "--productivity",
        required=True,
        type=positive_float,
        help="Total factor productivity A. Must be greater than 0.",
    )

    return parser.parse_args()