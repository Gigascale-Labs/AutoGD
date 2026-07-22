import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import model


REL_TOL = 1e-6
ABS_TOL = 1e-9


def assert_close(actual: float, expected: float) -> None:
    assert math.isclose(
        actual,
        expected,
        rel_tol=REL_TOL,
        abs_tol=ABS_TOL,
    ), f"Expected {expected}, got {actual}"


def assert_accounting_identity(result: dict[str, float]) -> None:
    assert_close(
        result["output"],
        result["wage_bill"] + result["capital_income"],
    )


def test_left_baseline_threshold() -> None:
    threshold = model.compute_threshold(
        capital=1.0,
        labor=1.0,
    )

    assert_close(threshold, 0.5)


def test_left_baseline_region_1_spot_check() -> None:
    result = model.compute_equilibrium(
        phi=0.25,
        capital=1.0,
        labor=1.0,
        sigma=0.5,
        productivity=1.0,
    )

    assert result["region"] == 1
    assert_close(result["output"], 1.6)
    assert_close(result["wage_bill"], 1.44)
    assert_close(result["capital_income"], 0.16)
    assert_accounting_identity(result)


def test_left_baseline_at_threshold() -> None:
    result = model.compute_equilibrium(
        phi=0.5,
        capital=1.0,
        labor=1.0,
        sigma=0.5,
        productivity=1.0,
    )

    assert result["region"] == 2
    assert_close(result["threshold"], 0.5)
    assert_close(result["output"], 2.0)
    assert_close(result["wage_bill"], 1.0)
    assert_close(result["capital_income"], 1.0)
    assert_accounting_identity(result)


def test_right_baseline_threshold() -> None:
    threshold = model.compute_threshold(
        capital=10.0,
        labor=1.0,
    )

    assert_close(threshold, 10.0 / 11.0)


def test_right_baseline_region_1_spot_check() -> None:
    result = model.compute_equilibrium(
        phi=0.75,
        capital=10.0,
        labor=1.0,
        sigma=0.2,
        productivity=1.0,
    )

    assert result["region"] == 1
    assert_close(result["output"], 5.623001456214986)
    assert_close(result["wage_bill"], 5.489604077140471)
    assert_close(result["capital_income"], 0.13339737907451343)
    assert_accounting_identity(result)


def test_right_baseline_at_threshold() -> None:
    threshold = 10.0 / 11.0

    result = model.compute_equilibrium(
        phi=threshold,
        capital=10.0,
        labor=1.0,
        sigma=0.2,
        productivity=1.0,
    )

    assert result["region"] == 2
    assert_close(result["output"], 11.0)
    assert_close(result["wage_bill"], 1.0)
    assert_close(result["capital_income"], 10.0)
    assert_accounting_identity(result)


def test_right_baseline_just_below_threshold() -> None:
    threshold = 10.0 / 11.0

    result = model.compute_equilibrium(
        phi=threshold - 1e-6,
        capital=10.0,
        labor=1.0,
        sigma=0.2,
        productivity=1.0,
    )

    assert result["region"] == 1
    assert_close(result["output"], 10.999999999667246)
    assert_close(result["wage_bill"], 1.0000550010587563)
    assert_close(result["capital_income"], 9.999944998608486)
    assert_accounting_identity(result)


def test_right_baseline_above_threshold() -> None:
    result = model.compute_equilibrium(
        phi=0.95,
        capital=10.0,
        labor=1.0,
        sigma=0.2,
        productivity=1.0,
    )

    assert result["region"] == 2
    assert_close(result["output"], 11.0)
    assert_close(result["wage_bill"], 1.0)
    assert_close(result["capital_income"], 10.0)
    assert_accounting_identity(result)