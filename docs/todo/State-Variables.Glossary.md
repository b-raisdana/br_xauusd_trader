# State-Variables.Glossary

Read: `docs/todo/Vectorization Implementation Plan.md`

Create a table documenting the corresponding MT5 and Python state variables showing where each variable is used as an input and/or modified in each implementation.

### Variables to document

For each state variable under:
- **Global strategy-level state**
- **Core algorithmic state**

add one row to the table.

### Table columns

| MT5-Name | Py-Difference | MT5 Used as Input | MT5 Modifies the Value | Py Used as Input | Py Modifies the Value |

Column meanings:
- **MT5-Name** — the MT5/MQL5 name of the corresponding state variable
- **Py-Difference** — the Python variable name when it differs from the MT5 name (empty if identical)
- **MT5 Used as Input** — locations where the MT5 variable is read to calculate something else or make a decision
- **MT5 Modifies the Value** — locations where the MT5 variable is assigned, changed, or mutated
- **Py Used as Input** — locations where the Python variable is read
- **Py Modifies the Value** — locations where the Python variable is assigned, changed, or mutated

### Classification rules

A variable can simultaneously be both **Used as Input** and **Modifies the Value**. Record all relevant occurrences, not merely the first occurrence.

Count as modifications: assignment, reassignment, increment/decrement, arithmetic update, append/remove/insert, mutation of mutable state, initialization/reset.

A variable is an input when its current value is used to calculate another value, derive a result, determine a branch/decision, determine an order/action, or control algorithmic behavior.

Do not classify from variable names alone. Base on actual code usage.
