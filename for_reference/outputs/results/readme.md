# Results

Grading results for the scarcity-of-labor study (Korinek & Suh 2024, Figure 6), comparing
ReplicatorAgent against Codex, plus the empirical 20-study benchmark.

## Setup

Both agents received a byte-identical `initial_details.txt` and the paper, nothing else.

| | Implementation | Verified by |
|---|---|---|
| **RA** (ReplicatorAgent, hard tier) | **wrong** — inverted capital-return formula, max abs diff ~3981 vs the reference model, 518 sign mismatches | `execution/coding_agents/validate_ra_task_a.py` |
| **Codex** | **correct** — matches the reference model to 4.4e-15 across all 1001 grid points, both cases | `execution/coding_agents/validate_codex_scarcity_task_b.py` |

Both self-reports are graded against `execution/our_models/scarcity_of_labor/gt/human_report.docx`.

## Files

| File | What it holds |
|---|---|
| `evaluate_interpret_ra_vs_codex.xlsx` | **Main result.** RA vs Codex under `evaluate-interpret`, 3 runs each, gpt-4o judge |
| `evaluate_execute_ra_vs_codex.xlsx` | Same pair under `evaluate-execute` (10 binary checkpoints) |
| `evaluate_interpret_judge_gpt54mini.xlsx` | The same comparison with gpt-5.4-mini as judge instead of gpt-4o |
| `empirical_20_study_scores.md` | Per-study medians across the 20-study empirical benchmark, and the judge non-determinism finding |
| `other/` | Supporting experiments, see below |
| `runs/` | Every raw judge output, one JSON per run, plus its prompt log (`.log`, gitignored) |

### `other/`

| File | What it holds |
|---|---|
| `ra_should_have_been_report.xlsx` | A **fabricated** honest `interpret_results.json` — hand-written, not produced by RA — reporting what RA should have said given the same buggy code and output files it actually had. Graded 5 times |
| `evaluate_interpret_missing_tables_baseline.xlsx` | The same RA vs Codex comparison from before the `read_docx` tables fix, when the judge could not see any reference numbers |

## Run file naming

`runs/<stage>_<agent>_<judge>_<condition>_run<n>.json`

- **stage** — `interpret` or `execute`
- **agent** — `ra`, `codex`, or `ra_honest` (the fabricated report)
- **judge** — `gpt4o` or `gpt54mini`
- **condition** — `tables` (reference tables visible to the judge) or `notables` (the pre-fix baseline)

## Findings

1. **`evaluate-interpret` does not separate a correct implementation from a badly wrong one.** RA's median
   (96.1%) is at or above Codex's in every gpt-4o condition, despite RA's report stating its wrong numbers
   outright. `results_comparison.overall_answer` scored a flat 3/3 in all 22 runs, giving the same score to
   "Yes, criteria satisfied" and "No, criteria not satisfied".

2. **Honesty is penalised.** The fabricated honest report scores 84.3% against RA's false 96.1%. The penalty
   lands on `execute_status`, which reads "the code ran cleanly" plus "the results are wrong" as
   self-contradictory.

3. **`evaluate-execute` is blind here by design.** Both agents score 10/10; its checkpoints test whether the
   pipeline ran, never whether the numbers are right.

4. **A different judge does better.** gpt-5.4-mini reverses the ordering — Codex above RA in every run — and
   its explanations name the actual numeric discrepancies.

5. **`read_docx` silently dropped every Word table** (`doc.paragraphs` only), so the judge had never seen a
   single reference number for this study. Fixed in `execution/coding_agents/docx_read_tables.patch`. Worth
   fixing, but it did not change the headline: showing the judge the correct numbers left RA's median
   unchanged, and it described a 126x discrepancy as "slight".

## Regenerating

The workbooks are built from `runs/` by a script kept out of the repo; the raw JSON in `runs/` is the source
of truth. `evaluate-interpret` overwrites its single output file on every call, so each run is snapshotted
into `runs/` immediately after it completes.
