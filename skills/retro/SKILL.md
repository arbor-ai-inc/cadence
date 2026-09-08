---
name: retro
description: >
  Use when a ticket taught something worth keeping. Per-PR capture is a step in
  git-pr-workflow; batched synthesis is /cadence:retro-synthesis. Invoke
  /cadence:retro <PR or issue id> only for the narrow per-ticket escape hatch.
allowed-tools: Read, Grep, Glob, Write, Edit, Bash
---

Follow the canonical procedure in `${CLAUDE_PLUGIN_ROOT}/reference/retro.md` exactly.

Capture happens per PR in `git-pr-workflow` § Workflow step 9, and costs no extra PR. It writes one fragment to `<[paths].retros>/pending/`, shaped like `${CLAUDE_PLUGIN_ROOT}/templates/_fragment_template.md`.

Batches at or above `[retro].synthesis_threshold` become rules via `retro-synthesis`. That is the default path.

Harvesting one ticket directly needs both clauses: it would recur before the next batch, **and** the rule is enforceable exactly as written. "This feels important" is not the bar.

Deliver via `gh pr create --title "retro(<id>): <summary>" --body-file <brief>` — never `--fill`, never `--body-file` alone. Body is a Shape B brief.

Never merge; never touch main. A fragment only ever records an observation, never a rule.
