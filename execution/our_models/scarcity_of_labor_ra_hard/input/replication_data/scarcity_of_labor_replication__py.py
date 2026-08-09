import json
from dataclasses import dataclass, asdict
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt


@dataclass
class ModelParams:
    sigma: float = 0.2
    A: float = 1.0
    phi_grid_size: int = 1001
    phi_min: float = 0.0
    phi_max: float = 1.0


@dataclass
class CaseParams:
    name: str
    K: float
    L: float


def region1_prices(phi: np.ndarray, K: float, L: float, sigma: float, A: float):
    """Static scarcity-of-labor model, region 1.

    Uses the factor-price frontier implied by the CES aggregator:
        w = [A^(1-sigma) - R^(1-sigma) * phi/(1-phi)]^(1/(1-sigma))
    and the marginal condition for the capital return:
        R = A * ((1-phi) * K / (phi * L))^sigma

    The wage bill and capital income are then computed as w*L and R*K.
    """
    eps = 1e-12
    phi_safe = np.clip(phi, eps, 1 - eps)
    R = A * (((1 - phi_safe) * K) / (phi_safe * L)) ** sigma
    inside = np.maximum(A ** (1 - sigma) - (R ** (1 - sigma)) * (phi_safe / (1 - phi_safe)), 0.0)
    w = inside ** (1.0 / (1.0 - sigma))
    Y = w * L + R * K
    return Y, w, R


def region2_prices(phi: np.ndarray, K: float, L: float, A: float):
    """Region 2: labor and capital are perfect substitutes at the margin."""
    w = np.full_like(phi, A, dtype=float)
    R = np.full_like(phi, A, dtype=float)
    Y = A * (K + L)
    return np.full_like(phi, Y, dtype=float), w, R


def threshold_phi(K: float, L: float):
    return K / (K + L)


def compute_case(case: CaseParams, params: ModelParams):
    phi = np.linspace(params.phi_min, params.phi_max, params.phi_grid_size)
    phi_star = threshold_phi(case.K, case.L)
    region1_mask = phi < phi_star

    Y = np.empty_like(phi)
    w = np.empty_like(phi)
    R = np.empty_like(phi)

    if np.any(region1_mask):
        Y1, w1, R1 = region1_prices(phi[region1_mask], case.K, case.L, params.sigma, params.A)
        Y[region1_mask], w[region1_mask], R[region1_mask] = Y1, w1, R1
    if np.any(~region1_mask):
        Y2, w2, R2 = region2_prices(phi[~region1_mask], case.K, case.L, params.A)
        Y[~region1_mask], w[~region1_mask], R[~region1_mask] = Y2, w2, R2

    wage_bill = w * case.L
    capital_income = R * case.K
    return {
        "case": asdict(case),
        "params": asdict(params),
        "phi_star": phi_star,
        "phi": phi,
        "output": Y,
        "wage_bill": wage_bill,
        "capital_income": capital_income,
        "wage_rate": w,
        "capital_return": R,
    }


def save_outputs(results, outdir: Path):
    outdir.mkdir(parents=True, exist_ok=True)
    for res in results:
        name = res["case"]["name"]
        np.savez(
            outdir / f"{name}_results.npz",
            phi=res["phi"],
            output=res["output"],
            wage_bill=res["wage_bill"],
            capital_income=res["capital_income"],
            wage_rate=res["wage_rate"],
            capital_return=res["capital_return"],
            phi_star=res["phi_star"],
        )
        with open(outdir / f"{name}_summary.json", "w") as f:
            json.dump(
                {
                    "case": res["case"],
                    "phi_star": float(res["phi_star"]),
                    "output_min": float(np.min(res["output"])),
                    "output_max": float(np.max(res["output"])),
                    "wage_bill_min": float(np.min(res["wage_bill"])),
                    "wage_bill_max": float(np.max(res["wage_bill"])),
                    "capital_income_min": float(np.min(res["capital_income"])),
                    "capital_income_max": float(np.max(res["capital_income"])),
                },
                f,
                indent=2,
            )


def plot_results(results, outpath: Path):
    fig, axes = plt.subplots(len(results), 1, figsize=(10, 8), sharex=True)
    if len(results) == 1:
        axes = [axes]
    for ax, res in zip(axes, results):
        phi = res["phi"]
        ax.plot(phi, res["output"], label="Total output", color="black", linewidth=2)
        ax.plot(phi, res["wage_bill"], label="Wage bill", color="tab:blue")
        ax.plot(phi, res["capital_income"], label="Capital income", color="tab:orange")
        ax.axvline(res["phi_star"], color="red", linestyle="--", alpha=0.7, label=r"$\phi^*$")
        ax.set_title(f"{res['case']['name']} (K={res['case']['K']}, L={res['case']['L']})")
        ax.set_ylabel("Level")
        ax.legend(loc="best")
        ax.grid(True, alpha=0.3)
    axes[-1].set_xlabel(r"Fraction automated tasks $\Phi$")
    fig.tight_layout()
    fig.savefig(outpath, dpi=200)
    plt.close(fig)


def main():
    base = Path("/app/data")
    outdir = base / "scarcity_of_labor_replication_outputs"
    params = ModelParams()
    cases = [CaseParams(name="equal_endowments", K=1.0, L=1.0), CaseParams(name="abundant_capital", K=10.0, L=1.0)]
    results = [compute_case(case, params) for case in cases]
    save_outputs(results, outdir)
    plot_results(results, outdir / "figure6_replication.png")
    with open(outdir / "run_metadata.json", "w") as f:
        json.dump({"model_params": asdict(params), "cases": [asdict(c) for c in cases]}, f, indent=2)
    print(json.dumps({"status": "ok", "output_dir": str(outdir)}, indent=2))


if __name__ == "__main__":
    main()
