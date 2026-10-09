---
name: code-review
description: >
  Use when a feature branch needs adversarial review before PR: the configured
  reviewer, resolve findings, re-run lint and tests, loop to LGTM.
allowed-tools: Read, Grep, Glob, Write, Edit, Bash, Task
---

**Check the model first, and again on every resume after a stop.** Read `model_pins["code-review"]` from `python3 ${CLAUDE_PLUGIN_ROOT}/tools/cadence_config.py --json`; if it is set and you are not running on it, say so and stop — name both models and how to switch (`/model <name>`). Continue only if the author says to. Unset: no check.

Reviewer is `[review].provider`: `codex` (`codex exec`), `claude` (`claude -p`), `subagent` (Claude Code only — needs Task), `coderabbit`, or `none`. **Pick a different agent from the one that wrote the code**; that is the whole point.

Follow the canonical procedure in `${CLAUDE_PLUGIN_ROOT}/reference/code-review.md` exactly.

Never the context that wrote the code. Give the reviewer the architectural context, not just the diff: principles subset, boundary docs, contract files. Trace written payloads to their consumer.

Lint + tests green before round 1 and after every resolution round.

Resolve all BLOCKER/SHOULD findings; product questions go to the ask transport via `${CLAUDE_PLUGIN_ROOT}/tools/ask.py`.

Circuit breaker at 3 rounds: post open findings on the issue and to the ask transport, and stop. Never merge.

On LGTM, hand back a Shape B change brief per `${CLAUDE_PLUGIN_ROOT}/reference/human-brief.md` — plain-English consequences, evidence per row, and where the reviewer and I disagreed.
