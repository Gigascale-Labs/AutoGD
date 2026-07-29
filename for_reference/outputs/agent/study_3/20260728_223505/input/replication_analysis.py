#!/usr/bin/env python3
"""Replicate Hossain (2020)'s democracy/COVID OLS claim on supplied data.

The supplied Stata file is release 110, which current pandas deliberately does
not import.  ``read_stata_110`` below reads the primitive numeric/string layout
needed for this supplied, unlabelled data file.  It is intentionally narrow:
it validates the expected variables and fails rather than silently guessing.
"""
from __future__ import annotations

import csv
import json
import os
import struct
import sys
from pathlib import Path

# Keep Matplotlib's cache in a writable, ephemeral location in containers.
os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-replication")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.api as sm


DATA_PATH = Path("task_input/replication_data/COVID replication.dta")
OUTDIR = Path("replication_results")
EXPECTED = {
    "country_name", "country_code", "Democracy index (EIU)", "popData2019",
    "COVID_12_31_04_03", "Annual_temp", "trade_2016",
}


def _cstring(raw: bytes) -> str:
    return raw.split(b"\0", 1)[0].decode("latin-1").strip()


def read_stata_110(path: Path) -> pd.DataFrame:
    """Read the simple Stata release-110 file supplied with this study.

    The implementation derives the start of observations by validating all
    records, avoiding assumptions about Stata metadata-block lengths.
    """
    blob = path.read_bytes()
    if len(blob) < 120 or blob[0] != 110:
        raise ValueError("Expected a Stata release-110 .dta file")
    endian = "<" if blob[1] == 2 else ">" if blob[1] == 1 else None
    if endian is None:
        raise ValueError("Unrecognized Stata byte order")
    nvar = struct.unpack_from(endian + "H", blob, 4)[0]
    nobs = struct.unpack_from(endian + "I", blob, 6)[0]
    types_at = 109
    type_codes = list(blob[types_at:types_at + nvar])
    names_at = types_at + nvar
    names = [_cstring(blob[names_at + 33*i:names_at + 33*(i+1)]) for i in range(nvar)]
    if not EXPECTED.issubset(names):
        raise ValueError(f"Unexpected Stata variables: {names}")

    widths, readers = [], []
    for code in type_codes:
        # In this legacy Stata format string widths are stored as 127 + width.
        if 128 <= code <= 244:
            width = code - 127
            widths.append(width)
            readers.append(("string", width))
        elif code == ord("b"):
            widths.append(1); readers.append(("numeric", "b"))
        elif code == ord("i"):
            widths.append(2); readers.append(("numeric", "h"))
        elif code == ord("l"):
            widths.append(4); readers.append(("numeric", "i"))
        elif code == ord("f"):
            widths.append(4); readers.append(("numeric", "f"))
        elif code == ord("d"):
            widths.append(8); readers.append(("numeric", "d"))
        else:
            raise ValueError(f"Unsupported Stata type code {code}")
    row_width = sum(widths)

    # Find the observation block. A valid candidate has nobs country-name and
    # ISO-like three-letter code fields at every fixed-width record boundary.
    first_string_widths = [w for (kind, w) in readers if kind == "string"]
    if len(first_string_widths) < 2 or first_string_widths[1] != 3:
        raise ValueError("Dataset does not have the expected country string layout")
    max_start = len(blob) - nobs * row_width
    data_start = None
    for start in range(names_at + nvar * 33, max_start + 1):
        valid = True
        for row in range(nobs):
            pos = start + row * row_width
            country = _cstring(blob[pos:pos + first_string_widths[0]])
            code_pos = pos + first_string_widths[0]
            code = _cstring(blob[code_pos:code_pos + 3])
            if not country or not code.isalpha() or len(code) != 3:
                valid = False
                break
        if valid:
            data_start = start
            break
    if data_start is None:
        raise ValueError("Could not locate a valid fixed-width observation block")

    rows = []
    for row in range(nobs):
        pos = data_start + row * row_width
        values = []
        for (kind, spec), width in zip(readers, widths):
            raw = blob[pos:pos + width]
            if kind == "string":
                values.append(_cstring(raw))
            else:
                value = struct.unpack(endian + spec, raw)[0]
                # Stata's numeric missing codes are extreme positive values.
                values.append(np.nan if isinstance(value, float) and value > 1e300 else value)
            pos += width
        rows.append(values)
    return pd.DataFrame(rows, columns=names)


def main() -> None:
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Missing input dataset: {DATA_PATH}")
    OUTDIR.mkdir(exist_ok=True)
    data = read_stata_110(DATA_PATH)
    data["cases_per_million"] = data["COVID_12_31_04_03"] / data["popData2019"] * 1_000_000
    # The supplied data's field label is "Democracy index (EIU)"; it is the
    # democracy field called Democracy in the accompanying Stata script.
    data["democracy_index"] = data["Democracy index (EIU)"] / 10.0
    model_columns = ["cases_per_million", "democracy_index", "Annual_temp", "trade_2016"]
    analysis = data.loc[:, model_columns].replace([np.inf, -np.inf], np.nan).dropna().copy()
    if len(analysis) < 5:
        raise ValueError("Too few complete observations for the planned OLS model")

    x = sm.add_constant(analysis[["democracy_index", "Annual_temp", "trade_2016"]], has_constant="add")
    fitted = sm.OLS(analysis["cases_per_million"], x).fit()
    focal = fitted.params["democracy_index"]
    focal_p = fitted.pvalues["democracy_index"]
    result = {
        "analysis": "OLS mirroring supplied Stata script: cases per million on democracy index, annual temperature, and trade openness",
        "outcome_period": "2020-12-31 through 2020-04-03",
        "n_input_rows": int(len(data)),
        "n_complete_cases": int(len(analysis)),
        "democracy_coefficient": float(focal),
        "democracy_standard_error": float(fitted.bse["democracy_index"]),
        "democracy_t_statistic": float(fitted.tvalues["democracy_index"]),
        "democracy_p_value_two_sided": float(focal_p),
        "r_squared": float(fitted.rsquared),
        "adjusted_r_squared": float(fitted.rsquared_adj),
        "residual_df": float(fitted.df_resid),
        "supports_positive_association_at_0_05": bool(focal > 0 and focal_p < 0.05),
        "original_claim_reference": {"coefficient": 86.76467, "p_value": 0.0001},
    }
    (OUTDIR / "results.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    table = pd.DataFrame({
        "term": fitted.params.index,
        "coefficient": fitted.params.values,
        "standard_error": fitted.bse.values,
        "t_statistic": fitted.tvalues.values,
        "p_value_two_sided": fitted.pvalues.values,
        "ci_95_lower": fitted.conf_int().iloc[:, 0].values,
        "ci_95_upper": fitted.conf_int().iloc[:, 1].values,
    })
    table.to_csv(OUTDIR / "ols_coefficients.csv", index=False, quoting=csv.QUOTE_NONNUMERIC)
    data[["country_name", "country_code"] + model_columns + ["democracy_index"]].to_csv(
        OUTDIR / "analysis_data.csv", index=False
    )

    ci = fitted.conf_int().loc["democracy_index"]
    plt.figure(figsize=(6, 3.5))
    plt.errorbar([focal], ["Democracy index"], xerr=[[focal - ci.iloc[0]], [ci.iloc[1] - focal]],
                 fmt="o", color="#1769aa", capsize=4)
    plt.axvline(0, color="black", linewidth=0.8)
    plt.xlabel("OLS coefficient (95% confidence interval)")
    plt.tight_layout()
    plt.savefig(OUTDIR / "democracy_coefficient.png", dpi=160)
    plt.close()

    print("Replication completed successfully")
    print(f"Rows: {len(data)}; complete cases: {len(analysis)}")
    print(f"Democracy coefficient: {focal:.6f}; two-sided p-value: {focal_p:.6g}")
    print(f"Supports positive association at alpha=0.05: {result['supports_positive_association_at_0_05']}")
    print(f"Results written to: {OUTDIR}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Replication failed: {exc}", file=sys.stderr)
        raise
