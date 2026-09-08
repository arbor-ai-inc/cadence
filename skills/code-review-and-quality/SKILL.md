---
name: code-review-and-quality
description: >
  Use when reviewing a diff, hardening code, or preparing a change for merge —
  the broad quality pass across correctness, tests, architecture, security and
  performance. For the pre-PR adversarial loop specifically, use /cadence:code-review.
allowed-tools: Read, Grep, Glob, Bash
---

Follow the canonical procedure in `${CLAUDE_PLUGIN_ROOT}/reference/code-review-and-quality.md` exactly.

Load the smallest context that explains the change — and treat the issue's own factual claims as premises to verify, not findings.

Every finding names a **consequence**, not a symbol. `BLOCKER … file.go:214` says something is wrong, not what it costs or who feels it.

**Take the concern, not necessarily the patch.** Verify each automated finding against the code first; accepting a wrong edit to close a comment makes the tree worse and closes the comment anyway.

**A passing status can mean it never looked.** Read the row's description, or better, `python3 ${CLAUDE_PLUGIN_ROOT}/tools/review_state.py`. Unresolved-thread count is not finding count — a finding outside the diff lands in the review body, which no thread count reflects.

Provider specifics live in `${CLAUDE_PLUGIN_ROOT}/reference/providers/`; the workflow itself names commands by role.

Hand findings back as a Shape B brief (`${CLAUDE_PLUGIN_ROOT}/reference/human-brief.md`), never as raw reviewer output.
