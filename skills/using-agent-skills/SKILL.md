---
name: using-agent-skills
description: >
  Use when starting work and unsure which cadence workflow applies, or when
  combining a workflow with a specialist review lens. Produces a short routing
  decision — what to use, why, and what project context to load first — not the
  work itself.
allowed-tools: Read, Grep, Glob
---

Follow the canonical procedure in `${CLAUDE_PLUGIN_ROOT}/reference/using-agent-skills.md` exactly.

Classify the task by **outcome** first, then pick the narrowest workflow that covers it. The routing table in the canonical doc is the answer; do not re-derive it.

Add a persona (`${CLAUDE_PLUGIN_ROOT}/reference/personas/`) only when a specialist lens changes the expected output. A persona is a review lens, never a substitute for a verification gate.

Name the project context the task depends on before implementation starts. A roadmap entry is an intention, not a built feature; a current-state doc can be stale. Check the code.

For a routing-only request, output the recommendation, the reason, the context to inspect, and the next action. For an implementation request, keep the routing note to one or two sentences and get on with the selected workflow.
