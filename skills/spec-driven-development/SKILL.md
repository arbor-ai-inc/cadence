---
name: spec-driven-development
description: >
  Use when a request needs concrete expected behavior before code changes — a
  new feature, an ambiguous goal, a change crossing several surfaces, or a
  choice between plausible approaches whose tradeoffs matter. Not for typo fixes
  or self-contained changes whose behavior is already clear.
allowed-tools: Read, Grep, Glob, Write, Edit, Bash
---

Follow the canonical procedure in `${CLAUDE_PLUGIN_ROOT}/reference/spec-driven-development.md` exactly.

Restate the user-visible outcome concretely, surface assumptions before planning, and write acceptance criteria that can actually be verified.

**Scale down.** A two-line spec with acceptance criteria is the right answer when the behavior is obvious. The workflow failing by being too heavy is as real as it failing by being too light.

Load project context by kind, not by remembered path. A roadmap entry is not a built feature and a current-state doc can be stale — both failures look identical from outside, so check the code.

Pause for a human when the task is materially ambiguous, changes architecture, changes a data contract, or has wide blast radius. Use a Shape A brief (`${CLAUDE_PLUGIN_ROOT}/reference/human-brief.md`).

For a substantial spec, escalate to `${CLAUDE_PLUGIN_ROOT}/reference/spec-pipeline.md`: product intent reviewed and merged as its own PR *before* any engineering design begins.
