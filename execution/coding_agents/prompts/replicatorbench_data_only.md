You are implementing a replication analysis for a ReplicatorBench study.

## Workspace restriction

Work only inside the current workspace.

You may read only:

- task_input/initial_details.txt
- task_input/original_paper.pdf
- task_input/post_registration.json
- files inside task_input/replication_data/
- files you create during this task

Do not access parent directories, hidden files, reference implementations,
previous outputs, graders, the surrounding repository, web search, or any
network resource.

## Task

Independently implement the analysis described by the supplied paper,
claim, preregistration, and datasets.

The workspace is data-only. Do not assume that an existing implementation
is available.

Create:

- one executable Python analysis script;
- `requirements.txt`;
- `replication_info.json`.

Run and debug the analysis before completing the task.

## ReplicatorBench compatibility

`replication_info.json` must use the structure shown in:

- `task_input/pre_registration_template.json`

Its `replication_study.codebase.files` field must list the executable Python
script you created.

Use a Docker-compatible Python base image and list every required Python
package under:

`replication_study.docker_specs.packages.python`

## Large dataset handling

Some datasets may contain millions of rows.

- Inspect schemas and small samples only during exploration.
- Never print or read an entire dataset into the conversation context.
- Use chunked reading or efficient dataframe operations where appropriate.
- Do not include raw dataset contents in logs or the completion response.

The analysis script must:

- read datasets using relative paths;
- execute without interactive input;
- test the supplied hypothesis;
- save machine-readable numerical results;
- save relevant tables or figures as files;
- print a concise execution summary;
- exit nonzero on failure.

Do not invent missing data or fabricate results. Document justified
interpretive choices when the paper does not fully specify an operation.

## Completion response

Report:

- files created;
- command executed;
- whether execution succeeded;
- main generated result files;
- unresolved ambiguities or failures.

Do not include full source code in the final response.
