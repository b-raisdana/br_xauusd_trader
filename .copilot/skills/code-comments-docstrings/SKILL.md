---
name: code-comments-docstrings
description: Use when writing or reviewing code comments and docstrings. Prefer self-explanatory code over documentation; add comments only for genuinely non-obvious behavior, and keep docstrings compact and purposeful.
---

# Code Comments & Docstrings

## Skill synchronization

Skills are synchronized across agent environments via the pre-commit hook. Do not edit local copies independently — apply changes to `.kilo/skills/` and let pre-commit propagate them.

## Principle

Prefer self-explanatory code over comments and docstrings.

### Naming first

- Before adding documentation, improve the function/class/variable name if it does not clearly express the purpose.
- Prefer a precise, descriptive function name over a long docstring.
- Use structure, types, and decomposition to make behavior obvious.

### Comments

Add comments only when naming, function separation, types, or structure cannot adequately explain **why or non-obvious behavior**.

Do not add comments that:

- Restate the code.
- Explain obvious control flow.
- Describe what a well-named function already communicates.
- Record implementation history.

### Docstrings

Use a compact docstring when the function/class name alone does not adequately communicate:

- Purpose
- Important behavior
- Contract or constraints
- Side effects
- Non-obvious usage requirements

Keep docstrings concise. Do not document obvious implementation details.

### Priority

1. Better naming
2. Better decomposition/structure
3. Types and contracts
4. Compact docstring
5. Comment only for genuinely non-obvious information