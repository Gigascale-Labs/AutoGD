#!/usr/bin/env python3
"""Replicate the supplied bilingualism/English-achievement mixed model.

The input is an RDS file.  To keep the analysis runnable in a standard Python
container, this script includes a small reader for the vector/data-frame subset
of R's XDR RDS format used by the supplied file.
"""
from __future__ import annotations

import gzip
import json
import math
import os
import struct
import sys
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "task_input" / "replication_data" / "Final replication dataset.rds"
OUT = ROOT / "results"


class RDSReader:
    """Minimal reader for the atomic vectors, lists, and attributes in this RDS."""

    def __init__(self, path: Path):
        self.buffer = gzip.open(path, "rb").read()
        if self.buffer[:2] != b"X\n":
            raise ValueError("Expected an XDR-serialized RDS file")
        self.pos, self.refs = 2, []
        self._uint(); self._uint(); self._uint()  # serialization/R/minimum R versions
        charset_len = self._uint()
        self.charset = self.buffer[self.pos:self.pos + charset_len].decode("ascii")
        self.pos += charset_len

    def _uint(self) -> int:
        value = struct.unpack(">I", self.buffer[self.pos:self.pos + 4])[0]
        self.pos += 4
        return value

    def _int(self) -> int:
        value = struct.unpack(">i", self.buffer[self.pos:self.pos + 4])[0]
        self.pos += 4
        return value

    def read(self):
        flags = self._uint()
        sexptype = flags & 0xFF
        if sexptype == 255:  # REFSXP
            index = flags >> 8
            return self.refs[index - 1] if index else None
        if sexptype in (0, 254):  # NILSXP / NILVALUE_SXP
            return None
        if sexptype == 9:  # CHARSXP
            length = self._int()
            if length < 0:  # NA_STRING
                return None
            value = self.buffer[self.pos:self.pos + length].decode("cp1252", errors="replace")
            self.pos += length
            self.refs.append(value)
            return value
        if sexptype in (10, 13):  # logical/integer
            n = self._uint()
            value = list(struct.unpack(">" + "i" * n, self.buffer[self.pos:self.pos + 4 * n]))
            self.pos += 4 * n
        elif sexptype == 14:  # double
            n = self._uint()
            value = list(struct.unpack(">" + "d" * n, self.buffer[self.pos:self.pos + 8 * n]))
            self.pos += 8 * n
        elif sexptype in (16, 19):  # string vector/list
            n = self._uint()
            value = []
            self.refs.append(value)
            value.extend(self.read() for _ in range(n))
        elif sexptype == 2:  # pairlist; RDS writes tag, value, then next node
            value = (self.read(), self.read(), self.read())
            self.refs.append(value)
        elif sexptype == 1:  # symbol
            value = ("SYMBOL", self.read())
            self.refs.append(value)
        else:
            raise ValueError(f"Unsupported RDS SEXP type {sexptype} at byte {self.pos - 4}")
        # Atomic vectors, like lists, can be targets of later REFSXP entries.
        if sexptype in (10, 13, 14):
            self.refs.append(value)
        if flags & 0x200:  # HAS_ATTRIB
            return ("ATTR", value, self.read())
        return value


def attributes(pairlist):
    result = {}
    while pairlist is not None:
        tag, value, pairlist = pairlist
        if isinstance(tag, tuple) and tag[0] == "SYMBOL":
            result[tag[1]] = value
    return result


def unwrap(value):
    if isinstance(value, tuple) and value[0] == "ATTR":
        return value[1], attributes(value[2])
    return value, {}


def read_dataframe(path: Path) -> pd.DataFrame:
    obj = RDSReader(path).read()
    columns, attrs = unwrap(obj)
    names = attrs.get("names")
    if not names or len(columns) != len(names):
        raise ValueError("RDS object is not a named data frame")
    decoded = {}
    for name, column in zip(names, columns):
        values, col_attrs = unwrap(column)
        # R factors are integer codes plus a levels attribute.
        if "levels" in col_attrs:
            levels = col_attrs["levels"]
            values = [levels[v - 1] if isinstance(v, int) and v > 0 else None for v in values]
        elif isinstance(values, list) and values and isinstance(values[0], int):
            values = [np.nan if v == -2147483648 else v for v in values]
        decoded[name] = values
    return pd.DataFrame(decoded)


def build_analysis_data(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    d = raw.copy()
    # This exactly follows the supplied R expression: (2 | 3) evaluates to TRUE
    # in R, which is coerced to 1 for comparison.  We retain this fidelity choice.
    d["bilingual"] = (pd.to_numeric(d["I03_ST_A_S26A"], errors="coerce") != 1).astype(float)
    d = d.loc[pd.to_numeric(d["I03_ST_A_S27B"], errors="coerce") == 0].copy()
    d["average_english"] = d[[
        "PV1_WRIT_C", "PV2_WRIT_C", "PV3_WRIT_C", "PV4_WRIT_C", "PV5_WRIT_C",
        "PV1_READ", "PV2_READ", "PV3_READ", "PV4_READ", "PV5_READ",
        "PV1_LIST", "PV2_LIST", "PV3_LIST", "PV4_LIST", "PV5_LIST",
    ]].apply(pd.to_numeric, errors="coerce").mean(axis=1)
    books = {"0-10 books": 0, "11-25 books": 1, "26-100 books": 2,
             "101-200 books": 3, "201-500 books": 4, "More than 500 books": 5,
             1: 0, 2: 1, 3: 2, 4: 3, 5: 4, 6: 5}
    # In the RDS the ordered factor is stored as its 1--6 integer codes; these
    # are the same ordered book categories recoded by the supplied R script.
    d["cultural_capital"] = d["SQt21i01"].map(books)
    d = d.loc[(pd.to_numeric(d["FSW_WRIT_TR"], errors="coerce") > 0) |
              (pd.to_numeric(d["FSW_READ_TR"], errors="coerce") > 0) |
              (pd.to_numeric(d["FSW_LIST_TR"], errors="coerce") > 0)].copy()
    for old, new in [("I08_ST_A_S02A", "c_age"), ("HISEI", "c_hisei")]:
        d[new] = pd.to_numeric(d[old], errors="coerce")
        d[new] -= d[new].mean(skipna=True)
    for old, new in [("PARED", "z_parental"), ("cultural_capital", "z_cultural")]:
        x = pd.to_numeric(d[old], errors="coerce")
        d[new] = (x - x.mean(skipna=True)) / x.std(skipna=True, ddof=1)
    d["gender"] = d["SQt01i01"].astype(object)
    d["country"] = d["country_id"].astype(object)
    d["school_nested"] = d["country"].astype(str) + "_" + d["school_id"].astype(str)
    required = ["average_english", "bilingual", "gender", "c_age", "c_hisei", "z_parental",
                "z_cultural", "country", "school_nested"]
    model_data = d.dropna(subset=required).copy()
    details = {"raw_rows": int(len(raw)), "after_home_language_exclusion": int(len(d)),
               "complete_cases": int(len(model_data)), "countries": int(model_data["country"].nunique()),
               "schools": int(model_data["school_nested"].nunique())}
    return model_data, details


def main() -> None:
    if not DATA.exists():
        raise FileNotFoundError(f"Missing input: {DATA.relative_to(ROOT)}")
    OUT.mkdir(exist_ok=True)
    raw = read_dataframe(DATA)
    d, sample = build_analysis_data(raw)
    formula = "average_english ~ bilingual + C(gender) + c_age + c_hisei + z_parental + z_cultural"
    model = smf.mixedlm(formula, d, groups=d["country"], re_formula="1",
                        vc_formula={"school": "0 + C(school_nested)"})
    fit = model.fit(reml=True, method="lbfgs", maxiter=500, disp=False)
    coef = pd.DataFrame({"term": fit.params.index, "estimate": fit.params.values,
                         "std_error": fit.bse.reindex(fit.params.index).values,
                         "z_value": fit.tvalues.reindex(fit.params.index).values,
                         "p_value": fit.pvalues.reindex(fit.params.index).values})
    coef.to_csv(OUT / "model_coefficients.csv", index=False)
    bilingual_row = coef.loc[coef.term == "bilingual"].iloc[0]
    result = {"model": "three-level random-intercept linear mixed model (country, school nested in country)",
              "formula": formula, "sample": sample,
              "bilingual_estimate": float(bilingual_row.estimate),
              "bilingual_standard_error": float(bilingual_row.std_error),
              "bilingual_p_value": float(bilingual_row.p_value),
              "converged": bool(fit.converged),
              "decision": "supports positive association" if bilingual_row.estimate > 0 and bilingual_row.p_value < .05 else "does not support positive association",
              "coding_note": "Primary coding exactly reproduces the supplied R expression I03_ST_A_S26A == (2 | 3), which evaluates as comparison to 1 in R."}
    (OUT / "analysis_results.json").write_text(json.dumps(result, indent=2) + "\n")
    pd.DataFrame([sample]).to_csv(OUT / "sample_summary.csv", index=False)
    means = d.groupby("bilingual", observed=True)["average_english"].agg(["mean", "count"]).reset_index()
    ax = means.plot.bar(x="bilingual", y="mean", legend=False, color="#4472c4")
    ax.set(xlabel="Bilingual indicator (supplied-code coding)", ylabel="Mean English achievement")
    plt.tight_layout(); plt.savefig(OUT / "english_achievement_by_group.png", dpi=160); plt.close()
    print("Replication completed")
    print(f"N={sample['complete_cases']}; bilingual estimate={result['bilingual_estimate']:.3f}; p={result['bilingual_p_value']:.4g}")
    print(f"Decision: {result['decision']}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Replication failed: {exc}", file=sys.stderr)
        raise
