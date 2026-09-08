---
name: code-review
description: >
  Use when a feature branch needs adversarial review before PR: Codex-first
  reviewer, resolve findings, re-run pre-commit and tests, loop to LGTM.
allowed-tools: Read, Grep, Glob, Write, Edit, Bash, Task
---

Reviewer is `[review].provider`: `codex` (`codex exec`), `claude` (`claude -p`), `subagent` (Claude Code only — needs Task), `coderabbit`, or `none`. **Pick a different agent from the one that wrote the code**; that is the whole point.

Follow the canonical procedure in `${CLAUDE_PLUGIN_ROOT}/reference/code-review.md` exactly.

Reviewer: `codex exec` on the diff; fallback to the `code-reviewer` subagent, never same context.

Give the reviewer the architectural context, not just the diff: principles subset, plane docs, contract files. Trace written payloads to their consumer.

Pre-commit + tests green before round 1 and after every resolution round.

Resolve all BLOCKER/SHOULD findings; product questions go to the ask transport via `slack_ask.py ask`.

Circuit breaker at 3 rounds: post open findings to the ask transport and stop. Never merge.

On LGTM, hand back a Shape B change brief per `${CLAUDE_PLUGIN_ROOT}/reference/human-brief.md` — plain-English consequences, evidence per row, and where the reviewer and I disagreed.
