---
name: decision-fanout
description: >
  Use when an autonomous implementation run hits a decision with more than one
  defensible answer: build each option in its own worktree, log the decision,
  and keep going instead of blocking on the author.
allowed-tools: Read, Grep, Glob, Write, Edit, Bash, Task
---

Follow `${CLAUDE_PLUGIN_ROOT}/reference/decision-fanout.md` exactly.

Classify first: mechanical and reversible decisions get a `record` line, not a branch.

Anything inside `[[must_stop]]` → stop and ask. Never fork. Check it, do not recall it:
`python3 ${CLAUDE_PLUGIN_ROOT}/tools/cadence_config.py must-stop <path>...` exits 5 when a path is inside.
An **empty** boundary means nothing will ever stop — say so rather than concluding nothing was one-way.

Drive every tree through `${CLAUDE_PLUGIN_ROOT}/tools/fanout.py`. Exit 3 means refused: ask instead.

Each leaf needs a test outcome and a `--lost` line; each decision needs a `recommend`.

Leaves stay local: never push, never open a PR, never start a server in one.
