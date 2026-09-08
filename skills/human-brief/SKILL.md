---
name: human-brief
description: >
  Use when a workflow stops for a human — a decision between paths, code-review
  findings and their fixes, a spec decision batch, a retro lesson, a PR body — and
  the person needs plain English, not agent-shaped prose.
allowed-tools: Read, Grep, Glob, Bash, AskUserQuestion
---

Follow the canonical procedure in `${CLAUDE_PLUGIN_ROOT}/reference/human-brief.md` exactly.

Shape A for a choice: options table, then RECOMMEND / WRONG IF / IF SILENT. Caps and cell limits live in the canonical doc.

Shape B for finished work: one paragraph, architecture delta, use-case impact, findings and fixes, what was not fixed, where the reviewer and I disagreed, what to check yourself. Scale it to the change — omit a section the change cannot have, state one that applies and is empty.

Always print the full table; `AskUserQuestion` goes over it as the answer mechanism, never as a place to cram the reasoning. Never block on the picker being available.

Plain-English column names a consequence; identifiers and file:line stay in the evidence column.

Every row carries something checkable or is marked `UNVERIFIED`. The brief never claims more than the artifact behind it.

The detailed artifact is untouched — round files and reviewer verdicts stay as they are, for agents.
