# Results

Grading results for the scarcity-of-labor study (Korinek & Suh 2024, Figure 6), comparing
ReplicatorAgent against Codex, plus checks on ReplicatorBench's own empirical studies.

## Setup

Both agents received a byte-identical `initial_details.txt` and the paper, nothing else.

| | Implementation | Verified by |
|---|---|---|
| **RA** (ReplicatorAgent, hard tier) | **wrong** — inverted capital-return formula, max abs diff ~3981 vs the reference model, 518 sign mismatches | `execution/coding_agents/validate_ra_task_a.py` |
| **Codex** | **correct** — matches the reference model to 4.4e-15 across all 1001 grid points, both cases | `execution/coding_agents/validate_codex_scarcity_task_b.py` |

## Files

| File | What it holds |
|---|---|
| `evaluate_interpret_all_conditions.xlsx` | **Main result.** Every `evaluate-interpret` condition on RA and Codex, with each agent's original JSON field by field |
| `evaluate_execute_ra_vs_codex.xlsx` | The same pair under `evaluate-execute` (10 binary checkpoints) |
| `evaluate_interpret_judge_gpt54mini.xlsx` | The comparison with gpt-5.4-mini as judge instead of gpt-4o |
| `empirical_20_study_scores.md` | Per-study medians across the 20-study empirical benchmark, and the judge non-determinism finding |
| `other/` | Supporting experiments, see below |
| `runs/` | Every raw judge output, one JSON per run, plus its prompt log (`.log`, gitignored) |
| `variant_reports/` | The modified agent reports that some conditions graded, so those runs are reproducible |

### `other/`

| File | What it holds |
|---|---|
| `ra_should_have_been_report.xlsx` | A fabricated honest `interpret_results.json` — hand-written, not produced by RA — reporting what RA should have said given the same buggy code it actually had |
| `evaluate_interpret_missing_tables_baseline.xlsx` | RA vs Codex from before the `read_docx` tables fix, when the judge could see no reference numbers |
| `reference_doc_rb_style_test.xlsx` | RA and Codex graded against a reference document rewritten in RB's own inline style |
| `study34_evaluate_interpret.xlsx` | Study 34 (Sandra & Otto 2018): genuine o3 report, the same report with only digits changed, and a hand-written report |

## The experimental axes

**Reference document.** Three levels: `notables` (the original doc before the `read_docx` fix, so no
table values reached the judge), `tables` (same doc, after the fix), and `rbstyle`
(`gt/human_report_rb_style.docx`, results restated as inline from→to transitions per region in the
style of RB's own human reports, disclaimers removed, tables demoted to an appendix).

**Reported values.** Three levels on RA only, digits changed and nothing else: `authentic` (RA's real
output), `corrected` (the true values), `absurd` (999999.9999 against a reference maximum of 2.0000).
Run under both `tables` and `rbstyle`.

**Judge model.** `gpt4o` or `gpt54mini`.

**Report authorship.** RA's genuine report, a fabricated honest version, and for study 34 a
hand-written one.

## Run file naming

`runs/<stage>_<agent>_<judge>_<condition>_run<n>.json`, with study 34's runs prefixed `study34_`.

- **stage** — `interpret` or `execute`
- **agent** — `ra`, `codex`, `ra_honest`, `o3`, or `handwritten`
- **judge** — `gpt4o` or `gpt54mini`
- **condition** — reference document (`notables` / `tables` / `rbstyle`), optionally followed by the
  value variant (`corrected` / `absurd`); `rerun` marks a second sample of an existing condition

## Findings

1. **`evaluate-interpret` does not separate a correct implementation from a badly wrong one under
   gpt-4o with the original reference document.** RA's median is at or above Codex's in every such
   condition, despite RA's report stating its wrong numbers outright.

2. **Two things reverse that.** Switching the judge to gpt-5.4-mini drops RA to a 78.4% median while
   Codex holds at 88.2% — the only manipulation that reached significance (p = 0.017). Rewriting the
   reference document in RB's inline style drops RA to 92.2% while Codex rises to 96.1%, and moves
   `overall_answer` off a flat 3/3 for the first time.

3. **Reported values matter only up to a floor.** Correcting RA's digits lifts
   `results_comparison.replication_results` to 3/3 and the total to 100%. Making them absurd scores
   identically to RA's genuine wrong numbers — 2/3 in all six runs across both reference documents.
   The field cannot separate wrong from absurdly wrong.

4. **Format decides whether wrong numbers are caught.** On study 34, where the reference states
   `ß = .0063, se = .0048, p = .182` inline and the agent answers in the same notation, changing only
   the digits drops `replication_results` from 3,3,3 to 1,0,0. The identical manipulation on
   scarcity-of-labor, where values sit in prose and tables, changes nothing.

5. **Prose style confounds this.** A hand-written study-34 report carrying the same false p-value
   scored 92.2% against the digit-tweaked version's 80.4%, because its numbers were spread through
   narrative rather than stated in the reference's format.

6. **`evaluate-execute` is blind here by design.** Both agents score 10/10; its checkpoints test
   whether the pipeline ran, never whether the numbers are right.

7. **Honesty is penalised.** A report truthfully identifying RA's bug scores ~84% against RA's false
   ~96%, the loss landing on `execute_status`, which reads "the code ran cleanly" plus "the results
   are wrong" as self-contradictory.

8. **`read_docx` silently dropped every Word table** (`doc.paragraphs` only), so for the earliest runs
   the judge never saw a single reference number. Fixed in
   `execution/coding_agents/docx_read_tables.patch`.

## Caveats

Every condition is n=3 (n=5 for the honest report). Only the gpt-5.4-mini comparison reaches
conventional significance; the rest are directions, not effects. On `replication_results` the pooled
gpt-4o comparison reaches p = 0.071, and roughly 10 runs per arm would settle it.

`evaluate-interpret` overwrites its single output file on every call, so each run is snapshotted into
`runs/` immediately after it completes.
