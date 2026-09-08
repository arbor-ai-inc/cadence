# Draft Plan

## Overview

The drafting step of the spec pipeline. Writes
`<[paths].specs>/<slug>/design.md` — the engineering design for a spec whose
product spec has reached **PRODUCT_READY** (Gate 1) **and whose product PR has
merged to `main`** — using `product.md` as input and the rubric at
`[paths].principles` as guardrails. Gated by the merged product PR and a
`product_hash` check.

The drafted `design.md` must include a **Principles adherence** section (per
[`templates/_design_template.md`](../templates/_design_template.md)) stating,
for each engaged principle, how the design satisfies it or why a trade-off is
justified. Gate 2 reviews against that section.

**A principle the design does not engage is not a row.** The section is
evidence about the trade-offs this design actually makes; padding it with every
principle in the rubric turns a reviewable claim into a checklist nobody
reads.

## When To Use

For the full pipeline loop (Gate 1 → draft → Gate 2 to DESIGN_READY), use
[spec-pipeline](./spec-pipeline.md) instead. Use this step directly only when
you need to draft `design.md` in isolation after a confirmed PRODUCT_READY
verdict.

## Workflow

See the full procedure in
[`spec-pipeline.md`](./spec-pipeline.md#hash-gates) — this step corresponds to
the drafting phase of that workflow. Refuse to draft unless **the product PR
has merged (`product.md` is on `main` — the [product PR gate](./spec-pipeline.md#pr-gates))**,
the most recent Gate 1 round is PRODUCT_READY, and its recorded `product_hash`
matches the current `product.md` (a product edit since the verdict re-opens
Gate 1).

Hand the result back as a Shape B change brief
([`human-brief`](./human-brief.md)), naming which principles the design engages —
the principle numbers belong in the brief's evidence column, not in its
plain-English one.
