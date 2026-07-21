import matplotlib.pyplot as plt
import numpy as np
import model
from pathlib import Path
import parser

def compute_series(
    capital: float,
    labor: float,
    sigma: float,
    productivity: float,
    num_points: int = 500,
) -> dict[str, list[float]]:
    """
    Compute output, wage bill, and capital income over a grid of phi values.
    """
    phi_values = np.linspace(0.0, 1.0, num_points)

    outputs = []
    wage_bills = []
    capital_incomes = []

    for phi in phi_values:
        result = model.compute_equilibrium(
            phi=phi,
            capital=capital,
            labor=labor,
            sigma=sigma,
            productivity=productivity,
        )
        outputs.append(result["output"])
        wage_bills.append(result["wage_bill"])
        capital_incomes.append(result["capital_income"])

    return {
        "phi": phi_values,
        "output": outputs,
        "wage_bill": wage_bills,
        "capital_income": capital_incomes,
    }

def plot_series(
    capital: float,
    labor: float,
    sigma: float,
    productivity: float,
    num_points: int = 500,
) -> None:
    """
    Plot Y, wL, and RK as functions of phi.
    """
    series = compute_series(
        capital=capital,
        labor=labor,
        sigma=sigma,
        productivity=productivity,
        num_points=num_points,
    )

    threshold = model.compute_threshold(capital=capital, labor=labor)

    plt.figure(figsize=(10, 6))
    plt.plot(series["phi"], series["output"], label="Output (Y)")
    plt.plot(series["phi"], series["wage_bill"], label="Wage bill (wL)")
    plt.plot(series["phi"], series["capital_income"], label="Capital income (RK)")

    plt.axvline(
        x=threshold,
        linestyle="--",
        label=f"Threshold = {threshold:.4f}",
    )

    plt.xlabel("Fraction of automated tasks, Φ")
    plt.ylabel("Value")
    plt.title(
        f"Scarcity of Labor Model: K={capital}, L={labor}, σ={sigma}, A={productivity}"
    )
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.show()


def plot_cases(
    cases,
    output_path: str | Path,
    number_of_points: int = 500,
) -> Path:
    """
    Plot one panel for each parameter case.

    Each case must contain:
        name, capital, labor, sigma, productivity

    Returns the path of the saved plot.
    """
    if not cases:
        raise ValueError("At least one parameter case is required.")

    number_of_cases = len(cases)

    figure, axes = plt.subplots(
        nrows=1,
        ncols=number_of_cases,
        figsize=(7 * number_of_cases, 5),
        squeeze=False,
    )

    axes = axes.flatten()

    for axis, case in zip(axes, cases):
        capital = case["capital"]
        labor = case["labor"]
        sigma = case["sigma"]
        productivity = case["productivity"]
        name = case["name"]

        series = compute_series(
        capital=capital,
        labor=labor,
        sigma=sigma,
        productivity=productivity,
        num_points=number_of_points,
        )

        threshold = model.compute_threshold(
            capital=capital,
            labor=labor,
        )

        axis.plot(
            series["phi"],
            series["output"],
            label="Output (Y)",
        )

        axis.plot(
            series["phi"],
            series["wage_bill"],
            label="Wage bill (wL)",
        )

        axis.plot(
            series["phi"],
            series["capital_income"],
            label="Capital income (RK)",
        )

        axis.axvline(
            threshold,
            linestyle="--",
            label=f"Threshold = {threshold:.3f}",
        )

        axis.set_title(
            f"{name}\n"
            f"K={capital}, L={labor}, "
            f"σ={sigma}, A={productivity}"
        )

        axis.set_xlabel("Automation share (φ)")
        axis.set_ylabel("Value")
        axis.set_xlim(0.0, 1.0)
        axis.grid(True, alpha=0.3)
        axis.legend()

    figure.tight_layout()

    saved_path = Path(output_path)
    saved_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    figure.savefig(
        saved_path,
        dpi=150,
        bbox_inches="tight",
    )

    plt.close(figure)

    return saved_path


def main() -> None:
    cases = parser.load_parameter_cases(
        "configs/reference_parameters.json"
    )

    plot_cases(
        cases=cases,
        output_path="outputs/reference/reference_plot.png",
    )


if __name__ == "__main__":
    main()