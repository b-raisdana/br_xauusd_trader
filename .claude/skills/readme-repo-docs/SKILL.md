---
name: readme-repo-docs
description: Use when creating or updating README.md files or repository-level documentation. Root README is the project entry point; folder READMEs only for meaningful boundaries; follow placement rules for all documentation.
---

# README & Repository Documentation

## Skill synchronization

Skills are synchronized across agent environments via the pre-commit hook. Do not edit local copies independently — apply changes to `.kilo/skills/` and let pre-commit propagate them.

## Root README

The root `README.md` is the project's primary entry point.

Keep it focused on:

- What the project is
- Main capabilities
- High-level architecture
- Repository structure
- Setup/prerequisites
- Basic development and test commands
- Links to deeper documentation

Do not put detailed architectural or implementation documentation here.

## Folder READMEs

Do **not** create a README in every folder.

Create a folder `README.md` only when the folder represents a meaningful:

- Package
- Module
- Subsystem
- Tool
- Independently understandable boundary

The README must make the folder's **scope and responsibility** immediately clear.

It should answer, as applicable:

1. What belongs here?
2. What is this component responsible for?
3. What explicitly does not belong here?
4. What are its important entry points/interfaces?
5. How does it relate to neighboring components?
6. How is it used, run, or tested?

Keep it compact.

Do not use folder READMEs to:

- Describe every file
- Repeat source code
- Duplicate the root README
- Replace API/type documentation
- Store TODOs
- Preserve historical information

## Placement rule

- Project-wide entry point → root `README.md`
- Architecture/general design → `./docs/`
- TODOs → `./docs/todo/`
- Component-specific knowledge → documentation near the relevant code
- Code-specific explanation → names, types, docstrings, and exceptional comments