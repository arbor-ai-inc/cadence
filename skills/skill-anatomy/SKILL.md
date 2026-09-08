---
name: skill-anatomy
description: >
  Use when authoring or updating a cadence workflow — contributing one upstream,
  or adding your own alongside it. Covers the canonical/adapter split, subagent
  format, and the presubmit guardrails.
allowed-tools: Read, Grep, Glob, Write, Edit, Bash
---

Follow the canonical procedure in `${CLAUDE_PLUGIN_ROOT}/reference/skill-anatomy.md` exactly.

**One canonical statement per workflow in `reference/`; every agent-facing file routes to it.** That split is load-bearing, not tidiness: a 900-line doc cannot sit in every session's context, and a rule in two places has already begun to drift.

An adapter refers to its canonical doc through `${CLAUDE_PLUGIN_ROOT}` — a repo-relative path resolves to nothing from an installed plugin.

**Never pin `model:` in anything shipped.** It silently overrides the user's choice for a role they are paying for. `tests/check_agent_skills.py` fails on a pin.

A subagent prompt carries role mechanics — who it is, what it may touch, the output and verdict format. The rules it grades by belong in the canonical doc.

Name the command, or name where the command is configured, never neither. Hardcoding one project's test invocation makes a workflow unusable elsewhere; "run the tests" makes it unusable anywhere.

Verify with `python3 tests/check_agent_skills.py`, and break any new check once to confirm it fires.
