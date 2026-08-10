You are implementing a replication analysis for a ReplicatorBench-style study.

## Workspace restriction

Work only inside the current workspace.

You may inspect only files supplied inside `task_input/` and files you create during this task.

Do not access parent directories, hidden files, reference implementations,
previous outputs, graders, the surrounding repository, web search, or any
network resource.

## Task

Using only:

- `task_input/initial_details.txt`
- `task_input/original_paper.pdf`

identify and implement the requested static scarcity-of-labor model and reproduce
the focal Figure 6 results.

There is no input dataset. Do not search for or invent one.

Create exactly:

- one executable Python analysis script;
- `requirements.txt`;
- `replication_info.json`.

Do not create alternate metadata files such as `replication_info_rb.json`.

Run and debug the analysis before completing the task.

## ReplicatorBench compatibility

`replication_info.json` must follow the structure shown in:

- `task_input/pre_registration_template.json`

Its `replication_study.codebase.files` field must be a JSON object whose
keys are the exact executable filenames and whose values describe what each
file does.

Do not retain placeholder keys such as `file_name`.

Codex must determine and record its own executable files, dependencies, and
execution environment.

Use a Docker-compatible Python base image and list every required Python
package under:

`replication_study.docker_specs.packages.python`

## Analysis requirements

The implementation must:

- derive the model from the supplied paper rather than any external specification;
- implement both Figure 6 parameter cases;
- evaluate the requested quantities over the automation range;
- save machine-readable numerical results;
- save the reproduction figure;
- use relative paths;
- execute without interactive input;
- print a concise execution summary;
- exit nonzero on failure.

Do not invent equations, parameter values, missing evidence, or expected outputs.

If the model cannot be identified unambiguously from the supplied paper, report
the ambiguity rather than guessing.

## Completion response

Report:

- paper sections/equations implemented;
- files created;
- command executed;
- whether execution succeeded;
- validation checks performed;
- main generated result files;
- unresolved ambiguities or failures.

Do not include full source code in the final response.
