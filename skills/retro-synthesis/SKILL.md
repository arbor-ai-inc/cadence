---
name: retro-synthesis
description: >
  Use when the retros pending/ directory holds at least the configured number of
  fragments and the batch should become guidance changes, or when a guidance doc
  has grown past being read. Invoke as /cadence:retro-synthesis.
allowed-tools: Read, Grep, Glob, Write, Edit, Bash
---

Follow the canonical procedure in `${CLAUDE_PLUGIN_ROOT}/reference/retro-synthesis.md` exactly.

Read `[paths].retros` and `[retro].synthesis_threshold` from `cadence.toml` — `python3 ${CLAUDE_PLUGIN_ROOT}/tools/cadence_config.py --json` prints both. Never assume the defaults.

In: every `pending/*.md` fragment, plus prior counts from that directory's `TRAPS.md`.

Cluster by trap, add prior counts, then apply the canonical recurrence table — including its n=2 and subsystem-local exceptions — rather than a summary of it. A count is what decides the response, not how general the lesson feels.

A trap already ruled and recurring wants a hook or a test, not new prose. Mutation-test any check you write: break the thing, watch it fail, restore it.

Every touched doc gets a consolidation pass. A batch that only adds has half-failed.

Destinations are all in the user's repo. Cadence's own `reference/` docs are read-only — a local edit is reverted by the next plugin update; upstream it instead.

Out: one PR on `retro/batch-NN`, citations inline in the body, human reviewer. Never merge.
