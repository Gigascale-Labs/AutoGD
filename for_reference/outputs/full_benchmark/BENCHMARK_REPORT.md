# Full Codex ReplicatorBench Benchmark

## Executive summary

Codex was tested across all **20 ReplicatorBench studies**. It successfully executed **18 of 20 studies**. The remaining **2 studies** reached the grading stage but failed during execution because of environment or dependency issues.

Across all studies, Codex achieved an average score of **7.55/10** and a median score of **7.5/10**. **8 studies received a perfect 10/10 score.**

## Key results

- Studies evaluated: **20**
- Successful executions: **18/20**
- Execution failures: **2/20**
- Average score: **7.55/10**
- Median score: **7.5/10**
- Perfect scores: **8**
- Lowest score: **4/10**
- Total measured runtime: **109.3 minutes**

## Results by study

| Study | Score | Execution result |
|---:|---:|---|
| 1 | 7/10 | Successful |
| 2 | 6/10 | Successful |
| 3 | 5/10 | Execution failed; grading completed |
| 4 | 10/10 | Successful |
| 5 | 8/10 | Successful |
| 6 | 10/10 | Successful |
| 7 | 10/10 | Successful |
| 8 | 10/10 | Successful |
| 9 | 10/10 | Successful |
| 10 | 10/10 | Successful |
| 11 | 8/10 | Successful |
| 12 | 6/10 | Successful |
| 13 | 5/10 | Successful |
| 14 | 4/10 | Successful |
| 15 | 6/10 | Successful |
| 16 | 6/10 | Execution failed; grading completed |
| 17 | 6/10 | Successful |
| 18 | 10/10 | Successful |
| 19 | 4/10 | Successful |
| 20 | 10/10 | Successful |

## Execution failures

### Study 3 — 5/10

The study produced enough material to be graded, but the analysis did not execute successfully in the ReplicatorBench environment.

**Grader findings:** evaluate_design.environment.1.1.2: No mention or evidence of a manifest file being checked or existing. | execute.code_execution.2.1.1: Persistent Docker build failures and dependency issues indicate data loading was not successfully executed. | execute.code_execution.2.2.2: The main code/model did not execute successfully due to repeated dependency and Docker build failures. | execute.execution_report.2.3.1: The required execution results report was not found, implying the expected output files were not generated or logged successfully. | execute.execution_report.2.3.2: The absence of execution_results.json, combined with execution failures, indicates it was not filled out.

### Study 16 — 6/10

The study produced enough material to be graded, but the analysis did not execute successfully in the ReplicatorBench environment.

**Grader findings:** evaluate_design.environment.1.1.1: The Dockerfile is missing, making it impossible to verify the existence of docker_specs.base_image. | execute.code_execution.2.1.1: Data could not be successfully loaded due to an ImportError with scipy, preventing the execution of the analysis. | execute.code_execution.2.2.2: The main code/model did not execute successfully because of an ImportError as reported in execution_results.json. | execute.execution_report.2.3.1: Expected output files were not generated because the main code execution failed.

## Runtime and model usage

- Codex input tokens: **9,029,892**
- Cached input tokens: **8,288,626**
- Codex output tokens: **204,689**
- Total measured runtime: **109.3 minutes**

Most input tokens were cached, which substantially reduced the amount of newly processed input relative to the headline token count.

## How to interpret the scores

Each study was evaluated using ReplicatorBench's ten execution and design checks. The score therefore reflects whether the generated replication was correctly packaged, executable, documented, and able to produce the expected outputs.

A lower score does not always mean the underlying statistical reasoning was entirely incorrect. Some deductions resulted from missing manifests, incomplete execution reports, path visibility, or dependency failures.

## Important caveats

- The implementation model was **gpt-5.6-terra**.
- ReplicatorBench grading used **GPT-4o**.
- LLM generation and grading are nondeterministic, so repeated runs may produce slightly different scores.
- The report uses one designated benchmark run per study rather than selecting the highest score from repeated tests.
- Studies 3 and 16 are reported as execution failures even though the grader was still able to produce partial scores.

## Included files

- `benchmark_results.csv`: detailed result for every study
- `benchmark_results.json`: machine-readable detailed results
- `benchmark_summary.csv`: compact benchmark summary
- `benchmark_summary.json`: machine-readable compact summary
- `batch_status.csv`: batch-run completion statuses
