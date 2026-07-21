# Reference Model

## Overview

This directory contains the human-written reference implementation of the **scarcity of labor model**.

The implementation reproduces the static model used for Figure 6 of the paper. For fixed capital and labor endowments, it calculates how total output and factor incomes change as the fraction of automatable tasks increases from 0 to 1.

The main outputs are:

- total output, `Y`;
- the wage bill, `wL`;
- capital income, `RK`.

The reference implementation is independent of the implementation produced by ReplicatorAgent. It will be used as the trusted baseline for determining whether the agent correctly reproduces the model and applies new parameter values.

## Work completed

The reference model was implemented by translating the two-region piecewise equations from the model specification into Python.

The implementation includes:

- calculation of the automation threshold;
- selection between Region 1 and Region 2;
- calculation of output, wages, returns to capital, the wage bill, and capital income;
- generation of the two baseline plots corresponding to the parameter sets used in Figure 6;
- numerical tests covering the published baseline cases, threshold behavior, and the factor-income accounting identity.

## Parameter design

Parameters are stored in a JSON file rather than being hardcoded inside the model equations or supplied through individual command-line flags.

The parameter file is:

```text
configs/reference_parameters.json