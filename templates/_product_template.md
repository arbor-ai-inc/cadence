# Product Spec: <FEATURE NAME>

> Gate 1 artifact. Author input. Fill EVERY section concretely — the
> product-spec-reviewer returns NOT_READY on vague requirements or ones written
> as implementation instructions rather than user-verifiable outcomes.
> This file is `<specs>/<slug>/product.md`, where `<specs>` is `[paths].specs`
> from `cadence.toml`. The engineering design lives beside it in `design.md`,
> drafted only after this reaches PRODUCT_READY.

## Keep it short, and keep implementation out

**Target ≤150 lines.** Across four shipped specs the range was 102–147 lines
and 815–1,223 words. A product spec twice that length is not twice as clear: one
reached 260 lines before being cut back to about 150 with **nothing load-bearing
lost**, which is the measurement behind this number rather than a preference.

Three things do **not** belong in `product.md`, and each one is what inflates it:

| Don't | Why | Where it goes |
|---|---|---|
| **Implementation detail** — named mechanisms, algorithms, model/table/column names, thresholds expressed as formulas | It forecloses the design gate's choices, and a requirement can be unambiguous without saying how it is built | `design.md` |
| **Per-claim `file:line` evidence** | The spec states *what must be true*; proving today's gap is a different document's job | an `assessment.md` beside it, or the PR description |
| **Justification and review history** — why a metric is phrased as it is, how a prior round's blocker was resolved | Written to satisfy a reviewer, read by nobody afterwards | the `review/round-N.md` files, which already hold it |

A requirement must be **falsifiable**, which is not the same as detailed. "An alert
fires when a key's request count exceeds a configured threshold" is falsifiable and
implementation-free. "An alert fires when volume departs from its recent norm" is
neither. "An alert fires when volume exceeds the trailing 7-day median by 3×" is
falsifiable but has picked the design's algorithm — write the first.

## Problem
<Why does this exist? What is broken or missing today? One short paragraph.>

## User
<Who uses this / who is the actor? Where does it fit in the product?>

## What it is
<One paragraph: the outcome this delivers, in plain terms.>

## Requirements (user-verifiable)
> Each requirement is an OBSERVABLE outcome, not an implementation instruction.
> Number them R1, R2, … so the design and its acceptance criteria can reference
> them.
- **R1** <e.g. An authenticated advertiser sees only their own account's rows.>
- **R2** <e.g. A duplicate event is counted exactly once.>

## Success metrics
<How we know this worked — concrete and attributable to this work.>

## Non-goals
> What this pass explicitly does NOT do.
- <deferred thing>

## Open questions
<Anything still undecided — or "none". Buried, unresolved questions are a
Gate 1 blocker.>
