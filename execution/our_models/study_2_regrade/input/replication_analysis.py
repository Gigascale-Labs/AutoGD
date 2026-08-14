#!/usr/bin/env python3
"""Replication of the memorization x school-average-ability BFLPE claim.

The supplied data are an RDS file.  This script includes a deliberately small
reader for the base-R binary serialization used by that file, so execution does
not depend on R.  It reproduces the data exclusions, standardisation, five
plausible-value analyses, and Rubin-style pooling in the supplied R script.
"""
from __future__ import annotations

import gzip
import json
import math
import struct
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.stats import chi2, norm


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "task_input" / "replication_data" / "PISA2012.replication.RDS"
OUT = ROOT / "results"


class RdsReader:
    """Reader for the atomic vectors/lists/attributes in a base-R XDR RDS."""
    def __init__(self, path: Path):
        with gzip.open(path, "rb") as fh:
            self.buf = memoryview(fh.read())
        if self.buf[:2].tobytes() != b"X\n":
            raise ValueError("Expected an XDR (binary) RDS file")
        self.pos = 2
        self.version = self.i32()
        self.writer_version = self.i32()
        self.min_reader_version = self.i32()
        if self.version >= 3:
            n = self.i32()
            self.pos += n  # native encoding string
        self.refs: list[object] = []

    def i32(self) -> int:
        val = struct.unpack_from(">i", self.buf, self.pos)[0]
        self.pos += 4
        return val

    def f64(self, n: int) -> np.ndarray:
        nbytes = 8 * n
        arr = np.frombuffer(self.buf[self.pos:self.pos + nbytes], dtype=">f8").astype(float)
        self.pos += nbytes
        return arr

    def read(self):
        flags = self.i32()
        typ = flags & 0xff
        if typ == 254:  # NILVALUE_SXP, used internally in pairlist tails
            return None
        if typ == 255:  # REFSXP
            idx = flags >> 8
            if idx <= 0 or idx > len(self.refs):
                raise ValueError(f"Invalid RDS reference {idx}")
            return self.refs[idx - 1]

        # Base R SEXP type codes used in this file.
        if typ == 0:  # NILSXP
            obj = None
        elif typ in (10, 13):  # logical/integer
            n = self.i32()
            obj = np.frombuffer(self.buf[self.pos:self.pos + 4*n], dtype=">i4").astype(np.int64)
            self.pos += 4 * n
        elif typ == 14:  # real
            n = self.i32()
            obj = self.f64(n)
        elif typ == 16:  # string vector
            n = self.i32()
            obj = [self.read() for _ in range(n)]
        elif typ in (19, 20):  # generic/expression vector
            n = self.i32()
            obj = [self.read() for _ in range(n)]
        elif typ == 9:  # CHARSXP
            n = self.i32()
            if n < 0:
                obj = None
            else:
                obj = self.buf[self.pos:self.pos + n].tobytes().decode("cp1252", errors="replace")
                self.pos += n
        elif typ == 2:  # attribute pairlist: serialized as TAG, CAR, CDR
            tag = self.read()
            car = self.read()
            cdr = self.read()
            obj = (car, cdr, tag)
        elif typ == 1:  # symbol: print name
            obj = self.read()
        else:
            raise ValueError(f"Unsupported R SEXP type {typ} at byte {self.pos}")

        self.refs.append(obj)
        if flags & 0x200:  # has attributes
            attr = self.read()
            obj = (obj, attr)
            self.refs[-1] = obj
        return obj


def attrs_to_dict(pairlist):
    result = {}
    node = pairlist
    while node is not None:
        car, cdr, tag = node
        if isinstance(tag, tuple):
            tag = tag[0]
        result[str(tag)] = car[0] if isinstance(car, tuple) else car
        node = cdr
    return result


def read_rds_dataframe(path: Path) -> pd.DataFrame:
    top = RdsReader(path).read()
    values, attrs = top
    meta = attrs_to_dict(attrs)
    names = meta.get("names")
    if isinstance(names, tuple):
        names = names[0]
    if not isinstance(values, list) or not isinstance(names, list) or len(values) != len(names):
        raise ValueError("RDS object is not a named data frame")
    columns = {}
    for name, value in zip(names, values):
        if isinstance(value, tuple):
            value = value[0]
        columns[str(name)] = value
    return pd.DataFrame(columns)


def standardize(s: pd.Series) -> pd.Series:
    # R's sd() is the sample standard deviation (ddof=1).
    return (s - s.mean()) / s.std(ddof=1)


def fit_one(data: pd.DataFrame, pv: str) -> dict:
    ability = f"{pv}_z"
    school_ability = f"school_{pv}_z"
    interaction = f"cross_{pv}"
    x = pd.DataFrame({
        "const": 1.0,
        "ability": data[ability],
        "ability_sq": data[ability] ** 2,
        "school_ability": data[school_ability],
        "memorization": data["MEMOR_z"],
        "interaction": data[interaction],
    })
    # Country fixed effects preserve the cross-national adjustment.  Clustered
    # sandwich SEs at school level account for student nesting in schools.
    countries = pd.get_dummies(data["CNT"].astype(str), prefix="country", drop_first=True, dtype=float)
    x = pd.concat([x, countries], axis=1)
    model = sm.WLS(data["SCMAT_z"], x, weights=data["W_FSTUWT"]).fit(
        cov_type="cluster", cov_kwds={"groups": data["uniqueSchoolID"]}
    )
    return {
        "plausible_value": pv,
        "coefficient": float(model.params["interaction"]),
        "standard_error": float(model.bse["interaction"]),
        "z_statistic": float(model.tvalues["interaction"]),
        "p_value": float(model.pvalues["interaction"]),
        "n": int(model.nobs),
        "n_schools": int(data["uniqueSchoolID"].nunique()),
    }


def main() -> None:
    if not DATA.exists():
        raise FileNotFoundError(f"Missing supplied dataset: {DATA}")
    OUT.mkdir(exist_ok=True)
    raw = read_rds_dataframe(DATA)
    required = {"SCHOOLID", "CNT", "STIDSTD", "SCMAT", "MEMOR", "W_FSTUWT",
                "PV1MATH", "PV2MATH", "PV3MATH", "PV4MATH", "PV5MATH"}
    missing = sorted(required - set(raw.columns))
    if missing:
        raise ValueError(f"Dataset lacks required columns: {missing}")

    d = raw.copy()
    d["uniqueSchoolID"] = d["SCHOOLID"].astype(str) + "|" + d["CNT"].astype(str)
    d["uniqueStudentID"] = d["STIDSTD"].astype(str) + "|" + d["uniqueSchoolID"]
    pvs = [f"PV{i}MATH" for i in range(1, 6)]
    numeric = ["SCMAT", "MEMOR", "W_FSTUWT"] + pvs
    for col in numeric:
        d[col] = pd.to_numeric(d[col], errors="coerce")
    valid = d["SCMAT"].notna() & (d["SCMAT"] <= 997) & d["MEMOR"].notna() & (d["MEMOR"] <= 997)
    for pv in pvs:
        valid &= d[pv].notna() & (d[pv] <= 997)
    d = d.loc[valid].copy()
    d = d.groupby("uniqueSchoolID", group_keys=False).filter(lambda x: len(x) > 10).copy()
    if d.empty:
        raise ValueError("No observations remain after the supplied exclusions")

    d["SCMAT_z"] = standardize(d["SCMAT"])
    d["MEMOR_z"] = standardize(d["MEMOR"])
    for pv in pvs:
        z = f"{pv}_z"
        d[z] = standardize(d[pv])
        school = f"school_{pv}_z"
        d[school] = d.groupby("uniqueSchoolID")[z].transform("mean")
        d[f"cross_{pv}"] = d["MEMOR_z"] * d[school]

    results = [fit_one(d, pv) for pv in pvs]
    estimates = np.array([r["coefficient"] for r in results])
    ses = np.array([r["standard_error"] for r in results])
    pooled_b = float(estimates.mean())
    sampling_variance = float(np.mean(ses ** 2))
    imputation_variance = float(np.sum((estimates - pooled_b) ** 2) / 4)
    pooled_se = math.sqrt(sampling_variance + 1.2 * imputation_variance)
    z = pooled_b / pooled_se
    pooled_p = float(2 * norm.sf(abs(z)))
    fisher_stat = float(-2 * np.sum(np.log(np.maximum([r["p_value"] for r in results], np.finfo(float).tiny))))
    fisher_p = float(chi2.sf(fisher_stat, 2 * len(results)))
    outcome = {
        "hypothesis": "The memorization by school-average mathematical ability interaction is negative.",
        "decision_rule": "Support requires a negative pooled coefficient and two-sided pooled p < 0.05.",
        "decision": "supported" if pooled_b < 0 and pooled_p < 0.05 else "not_supported",
        "pooled_interaction_coefficient": pooled_b,
        "pooled_standard_error": pooled_se,
        "pooled_z_statistic": z,
        "pooled_two_sided_p_value": pooled_p,
        "fisher_combined_p_value": fisher_p,
        "original_claim_coefficient": -0.089,
        "original_claim_effect_size": -0.157,
        "sample_size": int(len(d)),
        "school_count": int(d["uniqueSchoolID"].nunique()),
        "country_count": int(d["CNT"].nunique()),
        "estimation_note": "Weighted least squares with country fixed effects and school-clustered sandwich SEs; this is a computationally feasible Python approximation to the supplied R random-slope multilevel models.",
        "plausible_value_results": results,
    }
    pd.DataFrame(results).to_csv(OUT / "plausible_value_interactions.csv", index=False)
    with (OUT / "replication_results.json").open("w", encoding="utf-8") as fh:
        json.dump(outcome, fh, indent=2)
    print("Replication completed")
    print(f"N={outcome['sample_size']:,}; schools={outcome['school_count']:,}; countries={outcome['country_count']}")
    print(f"Pooled interaction={pooled_b:.6f}, SE={pooled_se:.6f}, p={pooled_p:.6g}; decision={outcome['decision']}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Replication failed: {exc}", file=sys.stderr)
        raise
