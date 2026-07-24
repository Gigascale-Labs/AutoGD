"""Static scarcity-of-labor model from Korinek and Suh, Section 2.3."""

from __future__ import annotations

from typing import Mapping


def automation_threshold(K: float, L: float) -> float:
    """Return the automation threshold Phi-hat for factor endowments K and L."""
    if K <= 0 or L <= 0:
        raise ValueError("K and L must both be positive.")
    capital_labor_ratio = K / L
    return capital_labor_ratio / (1.0 + capital_labor_ratio)


def evaluate_model(phi: float, parameters: Mapping[str, float]) -> dict[str, float | int]:
    """Evaluate output and factor incomes at one automation share Phi.

    Parameters must provide positive K, L, A, and sigma.  The CES expression is
    undefined at sigma = 1, which is therefore excluded.
    """
    K = float(parameters["K"])
    L = float(parameters["L"])
    sigma = float(parameters["sigma"])
    A = float(parameters["A"])

    if K <= 0 or L <= 0 or A <= 0:
        raise ValueError("K, L, and A must all be positive.")
    if sigma <= 0 or sigma == 1.0:
        raise ValueError("sigma must be positive and different from 1.")
    if not 0.0 <= phi <= 1.0:
        raise ValueError("phi must be in the closed interval [0, 1].")

    capital_labor_ratio = K / L
    task_ratio = float("inf") if phi == 1.0 else phi / (1.0 - phi)

    if capital_labor_ratio > task_ratio:
        region = 1
        exponent = (sigma - 1.0) / sigma
        inverse_sigma = 1.0 / sigma
        ces_sum = (
            K**exponent * phi**inverse_sigma
            + L**exponent * (1.0 - phi) ** inverse_sigma
        )
        Y = A * ces_sum ** (sigma / (sigma - 1.0))
        w = A**exponent * Y**inverse_sigma * L**(-inverse_sigma) * (1.0 - phi) ** inverse_sigma
        R = A**exponent * Y**inverse_sigma * K**(-inverse_sigma) * phi**inverse_sigma
    else:
        region = 2
        Y = A * (K + L)
        w = A
        R = A

    wage_bill = w * L
    capital_income = R * K
    accounting_error = Y - (wage_bill + capital_income)

    return {
        "phi": phi,
        "region": region,
        "Y": Y,
        "w": w,
        "R": R,
        "wage_bill": wage_bill,
        "capital_income": capital_income,
        "accounting_error": accounting_error,
    }
