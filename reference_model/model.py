"""
Helper functions for computing the equations
"""
def compute_threshold(capital: float, labor: float) -> float:
    """
    Compute the automation-share threshold separating the two regions.

    threshold = K / (K + L)

    At phi < threshold, the economy is in Region 1.
    At phi >= threshold, the economy is in Region 2.
    """
    return capital / (capital + labor)

def compute_region_1(
    phi: float,
    capital: float,
    labor: float,
    sigma: float,
    productivity: float,
) -> dict[str, float]:
    """
    Compute equilibrium values in Region 1.

    - Labor is scarce and automation ios low
    """
    exponent = (sigma - 1.0) / sigma

    aggregate_term = (
        capital**exponent * phi ** (1.0 / sigma)
        + labor**exponent * (1.0 - phi) ** (1.0 / sigma)
    )

    output = productivity * aggregate_term ** (sigma / (sigma - 1.0))

    wage = (
        productivity**exponent
        * output ** (1.0 / sigma)
        * labor ** (-1.0 / sigma)
        * (1.0 - phi) ** (1.0 / sigma)
    )

    capital_return = (
        productivity**exponent
        * output ** (1.0 / sigma)
        * capital ** (-1.0 / sigma)
        * phi ** (1.0 / sigma)
    )

    return {
        "region": 1,
        "output": output,
        "wage": wage,
        "capital_return": capital_return,
        "wage_bill": wage * labor,
        "capital_income": capital_return * capital,
    }


def compute_region_2(
    capital: float,
    labor: float,
    productivity: float,
) -> dict[str, float]:
    """
    Compute equilibrium values in Region 2.

    - Labor and capital are perfect substitutes at the
    margin, so they earn the same return.
    """
    output = productivity * (capital + labor)
    wage = productivity
    capital_return = productivity

    return {
        "region": 2,
        "output": output,
        "wage": wage,
        "capital_return": capital_return,
        "wage_bill": wage * labor,
        "capital_income": capital_return * capital,
    }

def compute_equilibrium(
    phi: float,
    capital: float,
    labor: float,
    sigma: float,
    productivity: float,
) -> dict[str, float]:
    threshold = compute_threshold(capital, labor)

    if phi < threshold:
        result = compute_region_1(
            phi=phi,
            capital=capital,
            labor=labor,
            sigma=sigma,
            productivity=productivity,
        )
    else:
        result = compute_region_2(
            capital=capital,
            labor=labor,
            productivity=productivity,
        )

    result["phi"] = phi
    result["threshold"] = threshold

    return result