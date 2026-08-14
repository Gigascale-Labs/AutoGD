"""Static scarcity-of-labor equilibrium used for Figure 6.

The equations implemented here are equations (3)--(8) in Sections 2.3--2.5
of the supplied paper.  ``phi`` is the paper's automation share Phi(I).
"""

from __future__ import annotations

import math
from typing import Mapping


def automation_threshold(parameters: Mapping[str, float]) -> float:
    """Return Phi(I-hat) from equation (3)."""
    capital = float(parameters["K"])
    labor = float(parameters["L"])
    _validate_parameters(float(parameters["A"]), capital, labor, float(parameters["sigma"]))
    return capital / (capital + labor)


def evaluate(phi: float, parameters: Mapping[str, float]) -> dict[str, float | int]:
    """Evaluate one static equilibrium at automation share ``phi``.

    Region 1 (Phi < Phi-hat) uses the CES output function in equation (4)
    and its marginal products in equations (6)--(7).  Region 2 (Phi >=
    Phi-hat) uses equation (5), where both factor returns equal A.
    """
    phi = float(phi)
    productivity = float(parameters["A"])
    capital = float(parameters["K"])
    labor = float(parameters["L"])
    sigma = float(parameters["sigma"])
    _validate_parameters(productivity, capital, labor, sigma)
    if not 0.0 <= phi <= 1.0:
        raise ValueError("phi must lie in the closed interval [0, 1]")

    threshold = capital / (capital + labor)
    if phi >= threshold:
        region = 2
        output = productivity * (capital + labor)
        wage = productivity
        rental_rate = productivity
    else:
        region = 1
        ces_power = (sigma - 1.0) / sigma
        task_term = (
            capital ** ces_power * phi ** (1.0 / sigma)
            + labor ** ces_power * (1.0 - phi) ** (1.0 / sigma)
        )
        output = productivity * task_term ** (1.0 / ces_power)

        # Equations (6) and (7), written as A * (Y/A)^(1/sigma).
        marginal_product_scale = productivity * (output / productivity) ** (1.0 / sigma)
        rental_rate = (
            marginal_product_scale
            * capital ** (-1.0 / sigma)
            * phi ** (1.0 / sigma)
        )
        wage = (
            marginal_product_scale
            * labor ** (-1.0 / sigma)
            * (1.0 - phi) ** (1.0 / sigma)
        )

    wage_bill = wage * labor
    capital_income = rental_rate * capital
    accounting_error = output - wage_bill - capital_income
    values = (output, wage, rental_rate, wage_bill, capital_income, accounting_error)
    if not all(math.isfinite(value) for value in values):
        raise ArithmeticError("model evaluation produced a non-finite value")

    return {
        "phi": phi,
        "region": region,
        "Y": output,
        "w": wage,
        "R": rental_rate,
        "wage_bill": wage_bill,
        "capital_income": capital_income,
        "accounting_error": accounting_error,
    }


def _validate_parameters(productivity: float, capital: float, labor: float, sigma: float) -> None:
    if productivity <= 0.0:
        raise ValueError("A must be positive")
    if capital <= 0.0 or labor <= 0.0:
        raise ValueError("K and L must be positive")
    if sigma <= 0.0 or sigma == 1.0:
        raise ValueError("sigma must be positive and different from one")
