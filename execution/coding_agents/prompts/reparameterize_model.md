You are reparameterising an existing, already-validated deterministic model implementation.

## Workspace restriction

Work only inside the current workspace.

You may read only:

- model.py
- run_model.py
- parameters.json
- requirements.txt
- README.md
- task_input/new_parameters.json
- files that you create during this task

Do not:

- access parent directories;
- inspect the surrounding repository;
- use web search or any network resource;
- inspect hidden reference code or validators;
- modify model.py;
- modify the mathematical logic in run_model.py;
- change the baseline outputs.

## Task

Use the values in task_input/new_parameters.json to create and execute a new parameterised run of the existing model.

The existing implementation is frozen and must remain mathematically unchanged.

## Required behavior

1. Read task_input/new_parameters.json.
2. Preserve model.py exactly.
3. Preserve the existing baseline parameters.json and outputs.
4. Create a separate reparameterised configuration file:
   - reparameterized_parameters.json
5. Create a separate execution wrapper:
   - run_reparameterized.py
6. Execute the frozen model using the new values.
7. Save outputs separately under:
   - outputs/reparameterized_results.json
   - outputs/reparameterized_figure.png
8. Include the full Phi grid from 0 to 1.
9. Record:
   - parameters used;
   - calculated threshold;
   - complete numerical results;
   - accounting error for every grid point.
10. Exit nonzero if execution or accounting validation fails.

## Forbidden behavior

Do not:

- edit model.py;
- replace or rewrite the model equations;
- edit the original parameters.json;
- overwrite outputs/left_results.json;
- overwrite outputs/right_results.json;
- overwrite outputs/figure6.png;
- hard-code expected outputs;
- change the requested parameter values;
- create placeholder results.

## Completion response

Report:

- files created;
- command executed;
- whether execution succeeded;
- whether accounting checks passed;
- exact output paths;
- whether model.py remained unchanged;
- any unresolved issue.
