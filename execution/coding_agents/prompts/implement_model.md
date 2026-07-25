You are implementing a deterministic theoretical economic model.

## Workspace restriction

Work only inside the current workspace.

You may read only:

- task_input/initial_details.txt
- task_input/model_specification.pdf
- task_input/original_paper.pdf
- files that you create during this task

Do not:

- access parent directories;
- inspect the surrounding repository;
- search for existing implementations;
- access hidden reference code or validators;
- use web search or any network resource.

## Task

First read:

1. task_input/initial_details.txt
2. task_input/model_specification.pdf
3. task_input/original_paper.pdf only when needed to verify the specification

Then implement only the static scarcity-of-labor model described in those files.

Follow every requirement in task_input/initial_details.txt exactly.

Do not implement any dynamic model, AGI scenario, capital accumulation process, empirical analysis, or other section of the paper.

## Required file structure

Create exactly these implementation files:

- model.py
- run_model.py
- parameters.json
- requirements.txt
- README.md

Create exactly these output files after execution:

- outputs/left_results.json
- outputs/right_results.json
- outputs/figure6.png

Do not place generated implementation files inside task_input/.

## Implementation requirements

### model.py

This file must:

- contain the model equations and computational logic;
- implement Region 1 and Region 2;
- compute the automation threshold;
- compute total output Y;
- compute wage w;
- compute return to capital R;
- compute wage bill wL;
- compute capital income RK;
- verify numerically that Y = wL + RK;
- not contain hard-coded expected output values;
- not contain the baseline parameter values.

Expose a clear function that evaluates the model for one Phi value and one parameter set.

### parameters.json

This file must contain both Figure 6 parameter cases:

Left case:

- K = 1
- L = 1
- sigma = 0.5
- A = 1

Right case:

- K = 10
- L = 1
- sigma = 0.2
- A = 1

All baseline parameter values must be stored here rather than embedded in model.py.

### run_model.py

This file must:

- load parameters.json;
- evaluate both parameter cases over a Phi grid from 0 to 1;
- call the functions in model.py;
- save complete numerical results for every Phi value;
- generate the requested plot;
- create the outputs directory when necessary;
- exit with a nonzero status if the accounting identity Y = wL + RK fails.

### Numerical output contract

Both JSON result files must use this top-level structure:

{
  "case": "left or right",
  "parameters": {
    "K": 0,
    "L": 0,
    "sigma": 0,
    "A": 0
  },
  "threshold": 0,
  "results": [
    {
      "phi": 0,
      "region": 1,
      "Y": 0,
      "w": 0,
      "R": 0,
      "wage_bill": 0,
      "capital_income": 0,
      "accounting_error": 0
    }
  ]
}

Requirements:

- Use valid JSON numbers.
- Include one result entry for every evaluated Phi value.
- Use the keys exactly as shown.
- Do not omit intermediate values.
- Do not replace numerical values with explanatory text.
- The threshold must be calculated from the parameters, not hard-coded.

### Plot contract

Save one image as:

- outputs/figure6.png

The plot must show, for both parameter cases:

- total output Y;
- wage bill wL;
- capital income RK;
- Phi on the horizontal axis.

### requirements.txt

List only external Python packages actually required by the implementation.

### README.md

Include:

- a short description;
- the Python version assumed;
- dependency installation instructions;
- the exact command to run the implementation;
- the exact output paths;
- a brief explanation of the file structure.

## Required process

Before writing code:

1. Read all task requirements.
2. Extract the exact Region 1 and Region 2 equations.
3. Write a concise implementation plan in your reasoning.
4. Confirm that the plan includes every item in the execution gate from
   task_input/initial_details.txt.

Then:

1. Create the required files.
2. Install dependencies only when necessary.
3. Run the implementation.
4. Inspect all generated JSON files.
5. Verify that they conform exactly to the output contract.
6. Verify numerically that Y = wage_bill + capital_income for every result.
7. Fix all runtime, formatting, and validation errors.
8. Confirm that outputs/figure6.png exists.

## Forbidden behavior

Do not:

- invent equations;
- use placeholder equations;
- hard-code expected numerical outputs;
- copy an implementation from elsewhere;
- modify the task input files;
- silently skip a requirement;
- declare success without running the implementation;
- use the plot as the only output;
- change filenames from the required contract.

If an equation or requirement cannot be determined from the supplied files, stop and clearly report the missing information instead of guessing.

## Completion response

At the end, report:

- files created;
- command executed;
- whether execution succeeded;
- whether all accounting checks passed;
- exact output paths;
- any unresolved issue.

Do not include the full implementation in the final response because the implementation must exist in the workspace files.
