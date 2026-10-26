---
name: handoff
description: >
  Use when asked to "save <slug> handoff", "update <slug> handoff", "pick up from
  <slug> handoff", "learn from <slug> handoff", "prune <slug> handoff", "close <slug>
  handoff" or "list handoffs", or when a multi-session track is about to end a
  session unfinished.
allowed-tools: Read, Grep, Glob, Bash, Edit, Write
---

Follow the canonical procedure in `${CLAUDE_PLUGIN_ROOT}/reference/handoff.md` exactly.

Run the mechanical steps with `python3 ${CLAUDE_PLUGIN_ROOT}/tools/handoff.py` (new, resolve, list, lint, backup).

On resume, check every state line against the real system before acting on it.

Never promote to the repo or memory, post outside the checkout, or delete a handoff without the user's yes.
