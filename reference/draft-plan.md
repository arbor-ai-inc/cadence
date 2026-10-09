# Draft Plan

## Overview

The drafting step of the spec pipeline. Writes
`<[paths].specs>/<slug>/design.md` against the rubric at `[paths].principles`.
**With a `product.md`**, the spec must be PRODUCT_READY (Gate 1), its product PR
merged to `main`, and `product_hash` matching. **With none**, see *No product gate*.

Its **Principles adherence** section covers only the principles the design
engages: how each is satisfied, or why a trade-off is justified.

**Size and shape it per
[the template](../templates/_design_template.md)'s § *How to use this template***:
drop that block, classify the change in the executive summary,
include an optional section only where it applies. Where the template says to
split, `design.md` is the HLD and each area gets `design/<area>.md` — one Gate 2
artifact under one `design_hash`, reviewed, edited and committed together.

**No product gate.** A refactor, migration or infra change with no
user-verifiable requirement — nothing a customer could see, be billed for, or
complain about — needs no `product.md` and no Gate 1. A missing `product.md` is
not by itself the test. The input is the request that prompted it; the
design's *Goals, Non-goals & Requirements* carries the Rn and one line on why no
product gate is needed. User-visible with no `product.md`: refuse; name it. Gate 2
grades the claim; a user-visible goal is a BLOCKER fixed by a `product.md`.

## When To Use

Drafting `design.md` alone; for the full loop use
[spec-pipeline](./spec-pipeline.md).

## Workflow

With a `product.md`, refuse unless all three conditions above hold
([PR gate](./spec-pipeline.md#pr-gates), [hash gate](./spec-pipeline.md#hash-gates)),
and say which failed.

Then draft `testing-plan.md` from the sized design, per
[`test-authoring`](./test-authoring.md) § *From a spec*, unless the design's
*Test strategy* opts out.

Hand back a Shape B brief ([`human-brief`](./human-brief.md)) naming the
principles engaged — numbers in the evidence column only.
