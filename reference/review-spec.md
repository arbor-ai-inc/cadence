# Review Spec

## Overview

The review step of the spec pipeline. There are two review kinds, one per gate:

- **Gate 1 — product review** (`product-spec-reviewer`): adversarially reviews
  `<[paths].specs>/<slug>/product.md` — problem, user, user-verifiable
  requirements, success metrics, non-goals. Verdict PRODUCT_READY / NOT_READY.
- **Gate 2 — eng-design review** (`eng-design-reviewer`): adversarially reviews
  `<[paths].specs>/<slug>/design.md` against the rubric at `[paths].principles`,
  and for machine-checkable acceptance criteria and an agent-ready
  decomposition. Verdict DESIGN_READY / NOT_READY.

Both produce a round file under `<[paths].specs>/<slug>/review/round-N.md`.

**Gate 2 is only as good as the rubric you point it at.** Cadence ships a
starter at
[`templates/architectural-principles.starter.md`](../templates/architectural-principles.starter.md);
a design graded against principles nobody in your project wrote is graded
against nothing.

## When To Use

For the full pipeline loop (Gate 1 → draft → Gate 2 to DESIGN_READY), use
[spec-pipeline](./spec-pipeline.md) instead. Use this step directly only when
you need to run a single review round in isolation — for example, re-running
Gate 2 on an edited `design.md`.

## Workflow

See the full procedure in
[`spec-pipeline.md`](./spec-pipeline.md#workflow) — this step corresponds to the
review phase of the gate that matches the artifact under review. Compute hashes
with `python3 ${CLAUDE_PLUGIN_ROOT}/tools/spec_hash.py` before invoking the
reviewer role — never by hand, and never as a placeholder — and write the round
file per the schema in the canonical doc (setting `gate: product` or
`gate: design`).

### Decide the scope

**A closed gate may need no round at all.** Running this step in isolation is
exactly where a closed gate gets
relitigated, because there is no loop tracking state for you. One rule from [spec-pipeline](./spec-pipeline.md) is not optional here:

- **Apply the ordered state table** in
  [§ The rule](./spec-pipeline.md#the-rule-freeze-the-artifact-at-the-first-ready-verdict)
  as written — that section is authoritative and this one does not restate it. Apply it
  to the latest round **for the gate you are reviewing**: round numbers are global
  across gates (§ *Round File Schema*), so the highest-numbered round in the directory
  may belong to the *other* gate, and closing Gate 2 on a Gate 1 round is the failure
  filtering on `gate:` prevents. Its row 2 — zero blockers and a hash matching the
  artifact — means that gate is closed: **say so and stop without invoking a
  reviewer.**

### Reporting back

Report the verdict first — callers branch on it, so it must stay literally
`PRODUCT_READY`, `DESIGN_READY` or `NOT_READY` — and then hand back a Shape B
change brief ([`human-brief`](./human-brief.md)) rather than the reviewer's raw
findings. The round file is written for the editor and the next reviewer; the
author needs what the round found in plain English, with the round-file path as
its evidence.
