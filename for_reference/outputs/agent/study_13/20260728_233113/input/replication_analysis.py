#!/usr/bin/env python3
"""Replicate the supplied weighted parliamentary-distrust mixed model.

The supplied data are RDS files.  This script includes a deliberately small
reader for the XDR R serialization used by those files, avoiding an R runtime
or a network-installed RDS dependency.
"""
from __future__ import annotations

import gzip
import json
import math
import os
import struct
import sys
from pathlib import Path

sys.dont_write_bytecode = True
os.environ.setdefault("MPLCONFIGDIR", "/tmp/replication_matplotlib")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import scipy.stats as st
import statsmodels.formula.api as smf


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "task_input" / "replication_data" / "data_clean_5pct.rds"
OUT = ROOT / "results"
FORMULA = (
    "trstprl_rev ~ imm_concern + happy_rev + stflife_rev + sclmeet_rev + "
    "distrust_soc + stfeco_rev + hincfel + stfhlth_rev + stfedu_rev + "
    "vote_gov + vote_frparty + lrscale + hhinc_std + agea + educ + female + "
    "vote_share_fr + socexp + lt_imm_cntry + wgi + gdppc + unemp"
)


class RDSReader:
    """Minimal reader for base-R XDR serialization (numeric data frames)."""
    NIL, SYM, LIST, CHAR, LGL, INT, REAL, STR, VEC, RAW, NILVALUE, REF = (
        0, 1, 2, 9, 10, 13, 14, 16, 19, 24, 254, 255)

    def __init__(self, payload: bytes):
        # Header is X\n, format/writer/min-reader versions, then encoding length/name.
        if payload[:2] != b"X\n":
            raise ValueError("Only XDR RDS files are supported")
        self.buf = memoryview(payload)
        self.pos = 2
        self._i32(); self._i32(); self._i32()
        encoding_len = self._i32()
        self.pos += encoding_len
        self.refs: list[object] = []

    def _i32(self) -> int:
        value = struct.unpack_from(">i", self.buf, self.pos)[0]
        self.pos += 4
        return value

    def _f64s(self, n: int) -> np.ndarray:
        values = np.frombuffer(self.buf[self.pos:self.pos + 8 * n], dtype=">f8").astype(float)
        self.pos += 8 * n
        # R's NA_REAL has a distinct NaN payload; NumPy safely represents it as NaN.
        return values

    def read(self):
        return self._item()

    def _item(self):
        info = self._i32()
        typ = info & 255
        has_attr, has_tag = bool(info & 512), bool(info & 1024)
        if typ in (self.NIL, self.NILVALUE):
            return None
        if typ == self.REF:
            return self.refs[(info >> 8) - 1]
        if typ == self.CHAR:
            n = self._i32()
            if n < 0:
                return None
            value = bytes(self.buf[self.pos:self.pos + n]).decode("cp1252")
            self.pos += n
        elif typ == self.SYM:
            value = self._item()
        elif typ in (self.INT, self.LGL):
            n = self._i32()
            value = np.array([self._i32() for _ in range(n)], dtype=float)
            value[value == -2147483648] = np.nan
        elif typ == self.REAL:
            n = self._i32()
            value = self._f64s(n)
        elif typ == self.STR:
            n = self._i32()
            value = [self._item() for _ in range(n)]
        elif typ in (self.VEC, self.RAW):
            n = self._i32()
            if typ == self.RAW:
                value = bytes(self.buf[self.pos:self.pos + n])
                self.pos += n
            else:
                value = [self._item() for _ in range(n)]
        elif typ == self.LIST:
            # The pairlist tag is serialized before CAR and CDR.
            tag, car, cdr = self._item(), self._item(), self._item()
            value = (car, cdr, tag)
        else:
            raise ValueError(f"Unsupported R serialization type {typ} at byte {self.pos}")
        self.refs.append(value)
        if has_attr:
            attrs = self._item()
            value = (value, _pairlist_dict(attrs))
        if has_tag and typ != self.LIST:
            tag = self._item()
        return value


def _pairlist_dict(node) -> dict:
    result = {}
    # Pairlist nodes can themselves carry attributes; for the data-frame
    # attribute list these are not substantive metadata.
    if isinstance(node, tuple) and len(node) == 2 and isinstance(node[1], dict):
        node = node[0]
    while node is not None:
        if not (isinstance(node, tuple) and len(node) == 3):
            raise ValueError(f"Malformed attribute pairlist node: {repr(node)[:300]}")
        car, cdr, tag = node
        result[str(tag)] = car
        node = cdr
    return result


def read_rds_frame(path: Path) -> pd.DataFrame:
    with gzip.open(path, "rb") as fh:
        obj = RDSReader(fh.read()).read()
    values, attrs = obj
    names = attrs["names"]
    return pd.DataFrame({name: value[0] if isinstance(value, tuple) else value
                         for name, value in zip(names, values)})


def main() -> None:
    OUT.mkdir(exist_ok=True)
    frame = read_rds_frame(DATA)
    required = ["trstprl_rev", "imm_concern", "cntry", "pspwght"]
    if missing := [c for c in required if c not in frame]:
        raise ValueError(f"RDS did not contain required fields: {missing}")
    # statsmodels MixedLM has no frequency/precision-weight interface.  Applying
    # sqrt survey weights to y and X is the WLS analogue used for the fixed effects.
    # Country fixed effects provide the intended random-intercept adjustment while
    # retaining weighted estimation and conventional coefficient tests.
    weighted_formula = FORMULA + " + C(cntry)"
    fitted = smf.wls(weighted_formula, frame, weights=frame["pspwght"]).fit()
    term = fitted.params.index.get_loc("imm_concern")
    beta = float(fitted.params.iloc[term])
    se = float(fitted.bse.iloc[term])
    t_value = float(fitted.tvalues.iloc[term])
    p_two = float(fitted.pvalues.iloc[term])
    p_one = float(p_two / 2 if beta > 0 else 1 - p_two / 2)
    ci = fitted.conf_int().loc["imm_concern"].tolist()
    decision = beta > 0 and p_one < 0.05
    results = {
        "analysis": "Weighted linear regression with country fixed effects; a Python-compatible approximation to the supplied weighted random-intercept lmer model.",
        "dataset": str(DATA.relative_to(ROOT)), "n_observations": int(fitted.nobs),
        "n_countries": int(fitted.model.data.frame["cntry"].nunique()), "formula": weighted_formula,
        "focal_term": {"term": "imm_concern", "estimate": beta, "standard_error": se,
                       "t_statistic": t_value, "p_value_two_sided": p_two,
                       "p_value_one_sided_positive": p_one, "ci_95": ci,
                       "supports_hypothesis": decision},
        "model_fit": {"r_squared": float(fitted.rsquared), "adjusted_r_squared": float(fitted.rsquared_adj),
                      "residual_df": float(fitted.df_resid)},
    }
    (OUT / "results.json").write_text(json.dumps(results, indent=2) + "\n")
    table = pd.DataFrame({"term": fitted.params.index, "estimate": fitted.params.values,
                          "standard_error": fitted.bse.values, "t_statistic": fitted.tvalues.values,
                          "p_value_two_sided": fitted.pvalues.values})
    table.to_csv(OUT / "coefficient_table.csv", index=False)
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.errorbar(beta, 0, xerr=[[beta - ci[0]], [ci[1] - beta]], fmt="o", color="#2166ac", capsize=4)
    ax.axvline(0, color="black", linewidth=0.8)
    ax.set(yticks=[], xlabel="Estimated change in parliamentary distrust per unit of immigration concern",
           title="Focal coefficient (95% CI)")
    fig.tight_layout(); fig.savefig(OUT / "immigration_concern_effect.png", dpi=160); plt.close(fig)
    print(f"n={int(fitted.nobs)}, countries={int(fitted.model.data.frame.cntry.nunique())}; imm_concern={beta:.4f}, SE={se:.4f}, one-sided p={p_one:.4g}; supports hypothesis={decision}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Analysis failed: {exc}", file=sys.stderr)
        raise
