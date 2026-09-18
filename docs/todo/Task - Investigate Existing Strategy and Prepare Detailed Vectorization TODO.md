# Task: Investigate Existing Strategy and Prepare Detailed Vectorization TODO

Before implementing the vectorized version, thoroughly investigate the existing event-loop implementation and prepare a detailed implementation plan as TODO documentation.

The purpose of this task is **investigation and documentation only**. Do not implement the vectorized strategy yet.

## Scope

Reference implementation: `src/application/xauusd_trading_strategy_1/on_tick.py`
Future implementation target: `src/application/xauusd_trading_strategy_1_vector/`
Create and modify only documentation under `docs/todo/`.

Treat the existing implementation as read-only reference code.

---

# Primary Goal

Investigate the existing event-loop strategy deeply enough that the later implementation phase can be performed with **minimal additional code investigation**.

The investigation must reconstruct the complete strategy logic and explain it clearly. The documentation should allow an implementer to understand:

- what happens; in what order; what each calculation depends on; which variables represent persistent state; when state is read, updated, reset; which results are produced; which depend on previous ticks; which calculations are independent; which require sequential processing; where each result originates; how the event-loop behavior maps to a future data processing implementation.

---

# Required Investigations

## 1. Complete Execution Flow

Trace the complete execution flow from input tick arrival through final observable result. For each step identify: inputs consumed, conditions evaluated, calculations performed, state variables read/changed, intermediate values created, results produced, conditions affecting later processing, state resets or boundary transitions, final outputs.

Do not document only functions individually. Reconstruct the **actual logical execution sequence**.

## 2. Algorithm Explanation in Plain Terms

Produce a clear explanation of the algorithm. Translate implementation details into understandable algorithmic descriptions. Include: major processing stages, decision points, state transitions, calculations, dependencies, boundaries, outputs.

## 3. Calculation and Result Inventory

Identify **every meaningful calculation, intermediate result, and observable result**. For each document: name, description, inputs, previous state dependency, calculation (plain terms), updated state, output destination, vectorization potential, dependency ordering.

## 4. Persistent State Identification

Find every variable whose value persists between ticks. For each document: initialization, first-use behavior, read locations, update locations, reset locations, reset conditions, whether reset is unconditional or conditional, dependency on broker/symbol/date, whether previous value is required, whether observable, whether representable as data column.

## 5. Previous-Row Semantics

Identify every calculation following the pattern: `state[t] = f(input[t], state[t-1])`. For each explain which value belongs to current tick, previous tick, or updated state. Identify operations requiring shift/diff/cumsum/cumprod/expanding/ewm/groupby cumulative/Numba equivalents.

## 6. Time and Ordering Semantics

Document: timestamp comparisons, second/millisecond behavior, date/session boundaries, day changes, timing windows, time-based resets, ordering assumptions, end-of-stream behavior, implicit temporal assumptions. Document whether relative row order matters when timestamps are identical.

## 7. Broker and Symbol State Isolation

Document ownership of every state variable. Determine which calculations can use grouped operations vs require global state.

## 8. Vectorization Analysis

For every calculation or state transition, determine the most appropriate implementation strategy. Prefer: vectorized operations, grouped operations, cumulative formulations, then sequential mechanisms.

## 9. Irreducibly Sequential Logic

Explicitly identify calculations that genuinely require sequential processing. For each document: why sequential, why normal vectorization doesn't apply, alternatives considered, cumulative formulation exists, sequential part size, remaining pipeline vectorization.

## 10. Data Schema Design

Plan for a single main data structure containing: input columns, derived columns, intermediate calculations, persistent state columns, event-level results, final action columns. Document proposed columns with purpose, source, calculation, dependency, type.

## 11. Output Contract

Determine exact final output contract: column name `action`, exact action values and meanings, row count, row order, index structure, which input columns must remain.

---

# Deferred Correctness Validation and Testing

Testing and correctness validation are intentionally **postponed**.

However, the documentation must contain an appendix documenting exactly what will eventually be validated and why it is deferred.

### Reference comparison
Run both implementations against the same deterministic input. Compare action for every row, all observable per-tick results, all observable state, relevant intermediate results.

### Numerical comparison
Define explicit numerical comparison rules: exact equality where appropriate, tolerance for floating-point values, documented tolerance values, NaN/NA equality handling.

### Edge cases
Eventually test: empty input, single-row, first-row, duplicate timestamps, multiple rows at same millisecond/second, multiple brokers/symbols, state isolation, day/session boundaries, state resets, threshold transitions, boundary conditions, end-of-stream.

### Determinism
Use deterministic fixtures. Repeated execution with same input must produce same result.

### Regression tests
Eventually create tests establishing behavioral equivalence to original implementation.

### Why deferred
Correctness validation is deferred because the immediate objective is first to establish the vectorized implementation and its complete end-to-end computational flow.

The intended order:
1. Investigate original algorithm
2. Document algorithm and implementation plan
3. Implement vectorized version
4. Make the complete vectorized flow operational
5. Then perform systematic correctness validation
6. Add regression/edge-case tests
7. Benchmark and optimize based on evidence

Do not mark deferred tests as completed.
