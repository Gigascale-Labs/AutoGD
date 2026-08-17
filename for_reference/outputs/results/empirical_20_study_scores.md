# Empirical 20-study Codex grading results

Raw results from re-running `evaluate-execute`, `interpret-easy`, and `evaluate-interpret` on Codex's
existing outputs for the 20-study benchmark, with the `STUDY=` path bug fixed. Compiled for the blog.
No RA-side scores here, those are Codex-only; RA only has native data for studies 1, 2, and 20 (see
separate RA comparison, still pending Docker access for the rest).

We found `evaluate-execute` is not deterministic (same input can score very differently run to run),
so for the four studies where we specifically tested this (3, 13, 18, 20), the table below reports
every score we observed and the median, not just one run. For everything else we only have a single
run, marked n=1, treat those numbers as less certain than the n>=2 ones.

Studies 3, 16 failed for real reasons (genuine Docker build / dependency errors, not a grading
artifact). Study 19 is a separate case, the underlying analysis actually succeeded, but the agent
hit the 18-turn execute limit before writing its final report, so no `execution_results.json` exists
and it's excluded from `interpret-easy`/`evaluate-interpret` entirely (nothing to interpret).

## evaluate-execute (score out of 10)

| Study | Scores observed | Median | n |
|---|---|---|---|
| 1 | 10 | 10 | 1 |
| 2 | 10 | 10 | 1 |
| 3 | 5, 2, 6, 3 | 4 | 4 |
| 4 | 10 | 10 | 1 |
| 5 | 8, 5 | 6.5 | 2 |
| 6 | 10 | 10 | 1 |
| 7 | 10, 8 | 9 | 2 |
| 8 | 10 | 10 | 1 |
| 9 | 10 | 10 | 1 |
| 10 | 10 | 10 | 1 |
| 11 | 8, 10 | 9 | 2 |
| 12 | 6, 10 | 8 | 2 |
| 13 | 5, 10, 10, 9 | 9.5 | 4 |
| 14 | 4, 10 | 7 | 2 |
| 15 | 6, 10 | 8 | 2 |
| 16 | 6, 3 | 4.5 | 2 |
| 17 | 6, 10 | 8 | 2 |
| 18 | 10, 5, 9, 8 | 8.5 | 4 |
| 19 | — (no valid execution, turn-limit casualty) | — | — |
| 20 | 10, 7, 6 | 7 | 3 |

For studies with only 2 scores, the first is the original 20-study benchmark score and the second is
this session's regrade, not a repeated-sampling test, so treat those medians as weaker evidence of
"the true score" than the n=4 studies (3, 13, 18), which were run specifically to characterize the
judge's variance.

## interpret-easy + evaluate-interpret (score out of max gradable fields x3)

| Study | Scores observed | Median (or single run) | n |
|---|---|---|---|
| 1 | 41/45 | 41/45 | 1 |
| 2 | 22/39 | 22/39 | 1 |
| 4 | 29/33 | 29/33 | 1 |
| 5 | 27/33 | 27/33 | 1 |
| 6 | 33/33, 33/33, 33/33 | 33/33 | 3 |
| 7 | 34/45 | 34/45 | 1 |
| 8 | 25/33 | 25/33 | 1 |
| 9 | 30/33 | 30/33 | 1 |
| 10 | 26/36 | 26/36 | 1 |
| 11 | 29/33 | 29/33 | 1 |
| 12 | 28/33 | 28/33 | 1 |
| 13 | 28/33 | 28/33 | 1 |
| 14 | 32/33 | 32/33 | 1 |
| 15 | 29/33 | 29/33 | 1 |
| 17 | 38/39 | 38/39 | 1 |
| 18 | 24/36, 24/33, 23/36 | ~67% (24/36) | 3 |
| 20 | 30/39 | 30/39 | 1 |

`evaluate-interpret` (single-shot LLM call) was much more stable than `evaluate-execute` (multi-turn
ReAct agent) in our repeat tests, see study 6 (perfectly consistent 33/33 x3) vs study 20's execute
score (10, 7, 6). Treat interpret-easy/evaluate-interpret single-run scores as reasonably trustworthy;
treat evaluate-execute single-run scores with more caution given the demonstrated variance.

## Notable finding: Study 2

Study 2 scored notably lower on `evaluate-interpret` (22/39) than the rest. This is not grading noise.
The study's actual focal claim (`initial_details.txt`) is about the interaction between "use of
memorization" and school-average ability on mathematical self-concept. Codex's own `interpret_results.json`
never mentions memorization at all, describing the hypothesis tested as "the pooled interaction effect
across schools and countries" with a different coefficient (-0.520) than the paper's own stated effect
(-0.157). This looks like a real problem with Codex's Study 2 run (execution and/or interpretation),
not a grading artifact, flagged here for follow-up, not yet root-caused.
