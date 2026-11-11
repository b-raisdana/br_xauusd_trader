---
name: persian-markdown-layout
description: Format Persian and other right-to-left Markdown lines and tables in this repository. Use whenever creating or editing Persian Markdown content.
---

# Persian Markdown Layout

For Persian Markdown files, every nonempty content line MUST begin with a Persian word after Markdown syntax. Apply this to headings, paragraphs, wrapped continuation lines, list/checklist items, blockquotes, captions, link labels, footnotes, and every table cell. Put English identifiers, paths, numbers, and abbreviations after a Persian label, for example `نسخهٔ Playwright` or `صف محلی (queue)`; a Persian digit or an RTL wrapper alone does not satisfy the rule.

Check every content line and table cell before finishing a Persian Markdown edit, including unchanged lines and cells. Blank lines, table separators, fence delimiters, and other syntax-only lines are structural. Preserve executable code and machine-readable syntax inside explicit fenced blocks without adding Persian prefixes that would corrupt them. Prefer inline technical identifiers in Persian sentences when a code block is unnecessary. Use the same language-first convention for other right-to-left prose.
