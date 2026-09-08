---
name: draft-plan
description: >
  Drafts design.md for a spec that has reached PRODUCT_READY (Gate 1), against
  the project's architectural principles. Gated by the merged product PR, the
  PRODUCT_READY verdict, and a product_hash match. Use when asked to draft the
  engineering design for a spec.
argument-hint: <specs>/<slug>/
allowed-tools: Read, Grep, Glob, Write, Edit, Bash
---

Follow the canonical procedure in `${CLAUDE_PLUGIN_ROOT}/reference/draft-plan.md` exactly.

**Refuse to draft unless all three hold**, and say which one failed: the product PR has merged so `product.md` is on `main`; the most recent Gate 1 round is PRODUCT_READY; and that round's recorded `product_hash` matches the current `product.md` under `python3 ${CLAUDE_PLUGIN_ROOT}/tools/spec_hash.py`. A product edit since the verdict re-opens Gate 1.

Write from `${CLAUDE_PLUGIN_ROOT}/templates/_design_template.md`, using `product.md` as input and the rubric at `[paths].principles` as guardrails.

The **Principles adherence** section states, per engaged principle, how the design satisfies it or why a trade-off is justified. Only principles the design actually engages — a padded table is a checklist nobody reads.

Every requirement (Rn) maps to a machine-checkable acceptance criterion, or to a named validation-plan entry saying why no test can prove it.

Hand back a Shape B brief naming which principles the design engages, with the principle numbers in the evidence column and never in the plain-English one.
