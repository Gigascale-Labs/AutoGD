# Full ReplicatorBench Data-Only Benchmark Agent

## Objective

Run the existing SysRisk Codex-to-ReplicatorBench data-only pipeline across the eligible ReplicatorBench studies, while preserving benchmark validity and recording all outcomes, failures, runtime, token usage, and cost data.

The existing pipeline entrypoint is:

```bash
execution/coding_agents/run_codex_rb_data_only.sh --study STUDY_ID

Do not redesign the pipeline unless a clearly identified infrastructure defect prevents execution.

Current repository state
Work only inside:
/Users/juanlopez/sysrisk-full-benchmark
Current branch:
benchmark/full-rb-data-only
The repository starts from the merged Codex/RB pipeline on main.
The ReplicatorAgent submodule is pinned at:
fb6a804fd710764f3ad3c8b84e1323c2804c4776
Required Git LFS benchmark datasets have already been downloaded.
API credentials are provided through environment variables.
Never print, inspect, copy, commit, or expose API-key values.
Non-negotiable rules
Never modify any file under these benchmark ground-truth or source-material locations:
replicatoragent/replicatorbench/data/original/*/input/replication_data/
original papers
human preregistrations
human replication reports
benchmark evaluation references
benchmark grading rubrics
benchmark labels
Never edit an agent-generated scientific implementation merely to improve its score or make a failed replication pass.
Treat scientific, methodological, statistical, or model-implementation failures as benchmark results.
Only fix problems that are clearly caused by shared infrastructure, including:
shell runner defects
path handling
output handoff
metadata collection
normalization code
malformed generated RB input structure
missing generic dependency handling
failures caused by our automation rather than by the model’s scientific work
Before making any infrastructure fix:
state the observed failure
identify the root cause
explain why it is infrastructure-related
identify every file that will be changed
Allow no more than one retry per study.
A retry is permitted only after a documented infrastructure fix.
Never silently skip a failed study.
Never run studies in parallel.
Never use:
--dangerously-bypass-approvals-and-sandbox
Do not modify the Git submodule commit.
Do not commit:
.env
API keys
credential files
downloaded datasets
LFS-hydrated files
large temporary files
Docker caches
generated secrets
Do not push anything to GitHub unless explicitly instructed by Juan.
Do not launch the full benchmark during the first task. The first task is audit-only.
Failure categories

Classify every study as exactly one primary category:

success
missing_input
infrastructure_failure
agent_model_failure
execution_failure
timeout
grading_failure
budget_stop
not_eligible

Add a concise secondary explanation where useful.

Required benchmark record

Create and maintain:

for_reference/outputs/full_benchmark/benchmark_summary.csv

with these columns:

study_id
eligible
attempt
command
start_time_utc
end_time_utc
runtime_seconds
codex_exit_code
rb_exit_code
status
failure_category
prompt_tokens
cached_input_tokens
completion_tokens
reasoning_tokens
estimated_cost_usd
run_directory
notes

Also create:

for_reference/outputs/full_benchmark/benchmark_summary.json

containing the same information in structured form.

Do not invent unavailable token or cost values. Leave them blank or null and state why.

Cost and budget controls
Run studies sequentially.
Read actual token metadata from generated run artifacts where available.
Calculate cost only from an explicitly documented pricing configuration.
Do not guess pricing.
Stop before launching another study if the configured benchmark budget would likely be exceeded.
If no budget configuration exists, stop and ask Juan before any paid benchmark run.
First task: audit only

For the first task, do not execute Codex, ReplicatorBench, Docker, grading, or any paid API call.

Perform only the following:

Inspect the current pipeline scripts and their arguments.
Determine which ReplicatorBench studies are eligible for the data-only benchmark.
Determine how eligibility is represented in the repository or benchmark metadata.
Inspect how the runner records:
Codex token usage
Codex exit status
RB execution status
RB grading results
runtime
output paths
Identify whether the current runner supports:
one study only
retries
resuming completed studies
skipping already completed studies
budget limits
batch execution
Identify all missing automation needed for a safe sequential full-benchmark run.
Produce an audit report at:
execution/coding_agents/benchmark_agent/AUDIT_REPORT.md

The report must include:

eligible study IDs
evidence for the eligibility decision
exact commands that would be used
expected artifacts per study
current cost-recording behavior
current retry/resume behavior
risks
recommended minimal implementation plan
files that would need modification
a proposed first two-study supervised test

Do not modify any production script during this audit.

At the end, stop and wait for Juan’s approval.
