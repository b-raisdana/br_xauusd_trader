    Read:

`docs\todo\Vectorization Implementation Plan.md`

Create a table in:

`State-Variables.Glossary.csv`

The purpose is to document the corresponding MT5 and Python state variables and precisely show where each variable is used as an input and/or modified in each implementation.

### Variables to document

For each state variable listed under:

- **Global strategy-level state**
- **Core algorithmic state**

add one row to the table.

Do not add unrelated variables outside these two categories.

### Table columns

Create exactly these six columns:

| MT5-Name | Py-Difference | MT5 Used as Input | MT5 Modifies the Value | Py Used as Input | Py Modifies the Value |
| -------- | ------------- | ----------------- | ---------------------- | ---------------- | --------------------- |

Column meanings:

- **MT5-Name** — the MT5/MQL5 name of the corresponding state variable.
- **Py-Difference** — the Python variable name when it differs from the MT5 name. If the names are exactly identical, leave this cell empty.
- **MT5 Used as Input** — locations where the MT5 variable is read to calculate something else, derive a result, or make a decision.
- **MT5 Modifies the Value** — locations where the MT5 variable is assigned, changed, incremented/decremented, or otherwise mutated.
- **Py Used as Input** — locations where the Python variable is read to calculate something else, derive a result, or make a decision.
- **Py Modifies the Value** — locations where the Python variable is assigned, changed, incremented/decremented, or otherwise mutated.

If a variable exists only in Python, put `NA` in **MT5-Name**.

If a variable exists only in MT5, put `NA` in **Py-Difference** and document its MT5 usage/modification normally.

### Variable naming / addressing schema

Use this compact schema to identify the state variable itself:

`namespace_hierarchy.[class_->]attribute_name(type_and_annotations)`

Examples:

`strategy.execution.OrderManager->_position_size(float)`

`strategy.state._last_price(float | None)`

Use the actual namespace/module hierarchy, class name where applicable, attribute/variable name, and type/annotations from the code.

The `class_->` portion is included only when the variable belongs to a class/object.

Keep the representation compact while retaining enough information to uniquely identify the variable.

### Code-location addressing

For every input or modification, identify the exact code location using:

`namespace_hierarchy.file_name.[class_->]function.(line_numbers)`

For example:

`strategy.execution.on_tick.(10,15,19)`

If several relevant lines belong to the **same function/method**, list all line numbers together and do not repeat the function reference:

`strategy.execution.on_tick.(10,15,19)`

Do **not** write:

`strategy.execution.on_tick.(10), strategy.execution.on_tick.(15), strategy.execution.on_tick.(19)`

If relevant lines belong to **different functions/methods**, provide the complete function reference for each:

`strategy.execution.on_tick.(10,15); strategy.execution.reset.(42,47)`

Use the same rule for both input and modification columns.

### Classification rules

A variable can simultaneously be both **Used as Input** and **Modifies the Value**.

For example, if a function reads a variable on lines 10 and 15 and modifies it on line 19, put:

- Used as Input: `...function.(10,15)`
- Modifies the Value: `...function.(19)`

Record all relevant occurrences, not merely the first occurrence.

Count the following as modifications when they change the state:

- assignment;
- reassignment;
- increment/decrement;
- arithmetic update such as `+=` or `-=`;
- append/remove/insert operations;
- mutation of a list, dictionary, series, object, or other mutable state;
- equivalent operations that alter the stored state;
- initialization/reset when it establishes or changes the state value.

A variable is an input when its current value is used to:

- calculate another value;
- derive a result;
- determine a branch or decision;
- determine an order/action;
- control or otherwise influence algorithmic behavior.

Do not classify a variable merely from its name or conceptual description. Base the classification on actual code usage.

### Helper functions and indirect modification

If a variable is passed to another function and that function actually reads or modifies the state, investigate the called function and document the relevant actual usage/modification location.

Do not assume that merely passing a variable means it is modified.

### MT5 ↔ Python mapping

Determine the Python counterpart of each MT5 state variable.

If the Python implementation uses a different name for the same logical state, record that Python name in **Py-Difference**.

If the names are exactly the same, leave **Py-Difference** empty.

Do not treat a differently named variable as equivalent solely because the names or concepts look similar. Establish the correspondence from the implementation and the state described in the vectorization plan.

### Missing implementation

If a state variable has no counterpart in one implementation:

- Python-only variable → `MT5-Name = NA`
- MT5-only variable → `Py-Difference = NA`

Use `NA` only for absence of the corresponding implementation, not merely because there is no usage/modification in a particular column.

If a variable exists in both implementations but has no input or modification occurrence for a particular role, leave that specific cell empty.

### Investigation requirements

Investigate enough of the relevant MT5 and Python code to accurately establish:

1. the corresponding MT5 and Python state variables;
2. Python naming differences;
3. every relevant input usage;
4. every relevant modification;
5. the exact function/method containing each occurrence; and
6. the exact line numbers.

The resulting table must be sufficiently precise that the vectorization implementation can use it as a direct reference without requiring another broad investigation of the original state handling.

### Final verification

After creating the table, perform a final completeness check against:

`docs\todo\Vectorization Implementation Plan.md`

Verify that:

- every state variable under **Global strategy-level state** has a row;
- every state variable under **Core algorithmic state** has a row;
- MT5/Python name differences are correctly recorded;
- all relevant input occurrences are listed;
- all relevant modifications are listed;
- multiple lines in the same function are grouped as `(10,15,19)`;
- lines in different functions use separate full function references;
- exact line numbers are used;
- MT5-only and Python-only variables are explicitly marked `NA`; and
- no input/modification classification is based only on inference or variable naming.

Do not add explanatory prose instead of the table. The table is the primary deliverable.
