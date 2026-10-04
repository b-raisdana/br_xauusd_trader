---
name: dataframe-contracts
description: Use when editing a DataFrame schema, producer/consumer chain, manifest or persistence boundary. Preserves index, dtypes, timestamp precision and rejection behavior.
---

# DataFrame contracts

Frames crossing a module boundary are contracts, not containers. Pandera
validates them via `@pandera_validate`; the schema and the index are both part
of the contract.

## Workflow

1. **Trace the chain.** Identify the producer, every consumer, and the
   persistence boundary. A schema edit is not complete until all three are known.
2. **Preserve index and dtypes.** Index level names and order, column order,
   dtypes and nullable-ness must survive a change. Convert with `to_numpy()` at a
   hot-path boundary and convert back explicitly; do not rely on implicit
   restoration.
3. **Keep timestamp precision.** Persist with an explicit unit (`.as_unit("ns")`)
   and an explicit timezone. A round trip that silently drops tz or changes unit
   is a contract break.
4. **Test rejection, not just acceptance.** Empty frames, all-null columns,
   wrong dtypes, wrong index order, duplicate keys and boundary timestamps each
   need a negative case.
5. **Round-trip.** Where a frame is persisted and re-read, assert equality
   across the boundary rather than only within one process.

## Conventions

- Import heavy third-party symbols from `helper.importer` (`pt`, `pa`, `pya`) so
  the cost is paid once.
- Combine frames with `merge`/`join`/`concat` in vectorized form; a loop that
  grows a list of frames defeats both the schema and the memory contract.
- State artifacts are large. Write them through the existing fire-and-forget
  executor; do not concatenate them in memory.
- When a schema must widen (new optional field), state explicitly whether
  existing persisted artifacts remain readable.

## Diagnostics

A failing stage should identify stream, day, category and the violated
invariant, then re-raise with context. Do not dump the whole frame into a log
or an exception message.