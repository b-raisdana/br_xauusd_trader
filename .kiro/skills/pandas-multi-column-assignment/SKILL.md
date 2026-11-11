---
name: pandas-multi-column-assignment
description: When assigning multiple columns from a sequence of Series in a DataFrame, use explicit 2-D construction (pd.concat[..., axis=1]) with named columns, never a plain Python list[Series]; and prefer true runtime schema validation over typing.cast() as a type-only assertion.
---

# Pandas multi-column assignment & runtime validation

Trigger: pandas strategy calculations, incremental temporary DataFrames, assigning multiple new columns from `Series`, or annotating/returning a validated DataFrame.

## Strategy vectorization and temporary frames

- Use complete vectorized pandas `DataFrame`/`Series` column operations, `shift` and `eval` only for strategy calculations. NumPy and Python iteration are prohibited: no `for`/`while`, comprehensions, row scans, `iterrows`, `apply(axis=1)`, callbacks or alternate array/compiled kernels.
- Put every numeric parameter and configurable column/window count in the strategy component `config/`, validated against its canonical settings model; no calculation literals. Trend lookback/column count remains configurable for later optimization.
- Build temporary DataFrames from newly derived columns only. Do not copy existing DataFrame columns into temporary frames; preserve their index and align/map by index at use time.
- Pass large artifacts between modules through a manifest that identifies the disk-resident payload, schema and index/partition metadata; do not pass or copy the full in-memory DataFrame.

## Multi-column assignment

Do **not** assign a plain Python `list[Series]`:

```python
df[columns] = [s1, s2, s3]            # ❌ ValueError: Columns must be same length as key
```

A list is 1-D; pandas can't map N series to N columns reliably.

**Use** explicit 2-D construction:

```python
columns = ["a", "b", "c"]
df[columns] = pd.concat([s1, s2, s3], axis=1).set_axis(columns, axis=1)
```

- `pd.concat([...], axis=1)` builds a rows × columns object.
- `set_axis(columns, axis=1)` pins the column names explicitly — never leave them positional.
- Index alignment is preserved. NumPy conversion is prohibited in strategy calculations; keep the pandas index intact.

For repeated dynamic assignments, define the column-name list once:

```python
result_columns = [...]                # define once
df[result_columns] = pd.concat([...], axis=1).set_axis(result_columns, axis=1)
```

Drop any now-unnecessary `# type: ignore[...]` after restructuring; re-run the type checker and keep an ignore only for a genuine, unavoidable issue.

## Runtime validation over typing.cast

`cast()` is static-only — it does **not** validate, convert, or enforce at runtime:

```python
return cast(pt.DataFrame[SomeSchema], df)   # ❌ type-checker lies, runtime is unchecked
```

When a runtime schema validator exists, use it:

```python
return SomeSchema.validate(df)             # ✅ true runtime validation
```

For a function transforming schema A → schema B, return the **validated** result:

```python
return TargetSchema.validate(result)       # not cast(pt.DataFrame[TargetSchema], result)
```

Objective: make type/schema claims **true at runtime**, not merely accepted by the type checker.

Combine with [pandera-dataframe-validation](../pandera-dataframe-validation/SKILL.md) — decorated functions get this enforcement for free; the `cast` anti-pattern is for paths *without* `@pandera_validate`.
