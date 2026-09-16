---
name: as-is-architecture-docs
description: Use when creating or updating architecture or general-design documentation under ./docs/. Maintain a compact as-is representation of current architecture; keep it current and avoid duplicating implementation details in docs.
---

# As-Is & Architecture Documentation

## Skill synchronization

Skills are synchronized across agent environments via the pre-commit hook. Do not edit local copies independently — apply changes to `.kilo/skills/` and let pre-commit propagate them.

## Scope

`./docs/` is for **architectural and general-design-level documentation**.

Exception:

```text
./docs/todo/
```

is exclusively for TODOs.

Other `./docs/` subfolders/files must describe stable, system-level architecture or general design.

## As-Is requirement

Maintain a compact **as-is representation** of the current architecture and master design.

It must accurately describe the current implementation at the architectural level, including where applicable:

- Major components
- Component responsibilities
- Boundaries
- Dependencies
- Main data/control flows
- Important interfaces
- Architectural constraints
- Key system-wide design decisions

Do not turn as-is documentation into an inventory of implementation details.

## Keep it current

When architectural work is completed:

- Update the relevant as-is documentation.
- Ensure the documented architecture matches the actual current system.
- Remove obsolete descriptions.

Do not maintain historical versions or describe how the architecture evolved.

## Detail placement

Keep detailed knowledge near the code when it is specific to a component, such as:

- Algorithms
- Module-specific behavior
- API details
- Configuration
- Operational procedures
- Implementation-specific design

Avoid duplicating this information in `./docs/`.