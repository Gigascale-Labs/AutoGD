You are implementing a deterministic theoretical economic model from an academic paper.

## Workspace restriction

Work only inside the current workspace.

You may read only:

- task_input/initial_details.txt
- task_input/original_paper.pdf
- files that you create during this task

Do not:

- access parent directories;
- inspect the surrounding repository;
- search for existing implementations;
- access hidden reference code, validators, or previous outputs;
- use web search or any network resource.

## Task

First read:

1. task_input/initial_details.txt
2. task_input/original_paper.pdf

Using only those files, identify and implement the static scarcity-of-labor model used to produce Figure 6 of the paper.

Do not use or assume access to a separate model specification.

Follow every requirement in task_input/initial_details.txt exactly.

Do not implement any dynamic model, AGI scenario, capital accumulation process, empirical analysis, or unrelated section of the paper.

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

- contain the equations and computational logic extracted from the paper;
- implement all regimes required by the Figure 6 model;
- compute the relevant automation threshold;
- compute total output;
- compute payments to labor;
- compute payments to capital;
- expose a clear function that evaluates the model for one automation value and one parameter set;
- not contain hard-coded expected output values;
- not contain baseline parameter values.

### parameters.json

This file must contain both Figure 6 parameter cases as extracted from the paper.

All baseline parameter values must be stored here rather than embedded in model.py.

### run_model.py

This file must:

- load parameters.json;
- evaluate both parameter cases over an automation grid covering the full Figure 6 range;
- call the functions in model.py;
- save complete numerical results for every evaluated value;
- generate the requested plot;
- create the outputs directory when necessary;
- exit with a nonzero status if any internal validation or accounting check fails.

### Numerical output contract

Both JSON result files must use this top-level structure:

{
  "case": "left or right",
  "parameters": {},
  "threshold": 0,
  "results": [
    {
      "phi": 0,
      "region": 0,
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
- Calculate the threshold from the extracted equations and parameters.

### Plot contract

Save one image as:

- outputs/figure6.png

The plot must show, for both parameter cases:

- total output;
- payments to labor;
- payments to capital;
- the automation share on the horizontal axis.

### requirements.txt

List only external Python packages actually required by the implementation.

### README.md

Include:

- a short description;
- the Python version assumed;
- dependency installation instructions;
- the exact command to run the implementation;
- the exact output paths;
- a brief explanation of the file structure;
- the paper sections and equations used.

## Required process

Before writing code:

1. Read all task requirements.
2. Locate the relevant model in the paper.
3. Identify the exact sections, equations, regime conditions, parameter values, and outputs needed for Figure 6.
4. Write a concise implementation plan in your reasoning.
5. If the requested model is ambiguous, stop and report the ambiguity instead of guessing.

Then:

1. Create the required files.
2. Install dependencies only when necessary.
3. Run the implementation.
4. Inspect all generated JSON files.
5. Verify that they conform exactly to the output contract.
6. Verify all numerical accounting identities implied by the model.
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

If an equation or requirement cannot be determined from the supplied paper, stop and clearly report the missing information instead of guessing.

## Completion response

At the end, report:

- paper sections and equations implemented;
- files created;
- command executed;
- whether execution succeeded;
- whether all validation checks passed;
- exact output paths;
- any unresolved issue.

Do not include the full implementation in the final response because the implementation must exist in the workspace files.
