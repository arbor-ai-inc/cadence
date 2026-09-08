# Spec-Driven Development

## Overview

Use this workflow to turn an unclear request into concrete expected behavior
before changing code. The output should be just enough specification to guide
implementation and verification.

## When To Use

- The request is a new feature, project, or significant behavior change.
- Requirements are ambiguous, incomplete, or only described as a rough goal.
- The change crosses UI, API, service logic, data, jobs, contracts, or
  operations boundaries.
- The task involves product, security, privacy, billing, migration, or rollout
  implications.
- Several implementation approaches are plausible and the tradeoffs matter.

Do not use this workflow for typo fixes, tiny mechanical edits, or
self-contained changes where the expected behavior is already clear.

## Repo Context To Load

Load only the context the task needs, and load it by **kind** rather than by a
remembered path — every project files these differently:

| Kind | What you are after |
|---|---|
| Architecture | how the system is shaped, and which boundaries this change crosses |
| Current state | what is **built** today, as distinct from what is planned |
| Roadmap | what is *intended*, which is never evidence that it exists |
| Conventions | the project's own engineering process and review expectations |
| Local | the nearest README to the code you are changing, and its tests |
| Operations | runbooks, deploy and rollout impact |

**A roadmap entry is not a built feature, and a current-state doc can be
stale.** Both failures look identical from the outside: you assert a capability
exists and nothing contradicts you until much later. Check the code.

## Workflow

1. Restate the user-visible outcome in concrete terms.
2. Surface assumptions before planning. Keep them specific and correctable.
3. Identify affected surfaces: UI, API, service logic, persistence, jobs,
   contracts, docs, operations, and rollout.
4. Inspect existing code and docs before proposing new structure.
5. Write acceptance criteria that can be verified.
6. Call out non-goals, boundaries, risks, and open questions.
7. Propose an implementation outline and verification plan.
8. Pause for human confirmation when the task is materially ambiguous, changes
   architecture, changes data contracts, or has high blast radius.

For small implementation requests, keep this lightweight. A two-line spec with
acceptance criteria is enough when the behavior is obvious.

## Output Shape

For planning-only requests, produce:

- Goal
- Non-goals
- Acceptance criteria
- Affected areas
- Assumptions
- Risks and open questions
- Implementation outline
- Verification plan

For implementation requests, write only the amount of spec needed to avoid
guessing, then proceed with the smallest safe change.

## Common Rationalizations

| Rationalization | Reality |
|---|---|
| "This is simple, so no spec is needed." | Simple tasks may not need long specs, but they still need clear acceptance criteria. |
| "I can write the spec after coding." | That is documentation, not specification. The value is clarifying behavior before implementation. |
| "The user knows what they want." | Clear requests still hide assumptions about scope, edge cases, and verification. |
| "A full spec will slow us down." | The workflow should scale down. Use a lightweight spec for small tasks. |

## Red Flags

- Starting implementation while expected behavior is still fuzzy.
- Making architecture or data-contract decisions without naming the tradeoff.
- Adding behavior that was not in the request, spec, or acceptance criteria.
- Treating a roadmap or planning doc as current without checking dates and code.
- Skipping verification planning because the change "looks straightforward."

## Verification

Before moving to implementation, confirm:

- [ ] The expected behavior is stated in concrete terms.
- [ ] Acceptance criteria are specific and testable.
- [ ] Relevant repo context has been inspected.
- [ ] Open questions or assumptions are explicit.
- [ ] The verification plan names concrete tests, commands, or manual checks.

## Escalation to Spec Pipeline

For substantial specs that need adversarial review and agent-ready
decomposition, escalate from spec-driven-development to the spec pipeline:

1. Use spec-driven-development to clarify product intent and shape
   `<[paths].specs>/<slug>/product.md`, from
   [`templates/_product_template.md`](../templates/_product_template.md).
2. `product.md` is product input — it may be drafted by the author or shaped
   by an agent, but must be author-confirmed before the pipeline reviews it.
3. Hand `product.md` to the spec pipeline, which adversarially reviews it
   (Gate 1 → PRODUCT_READY), **lands it as a merged product PR**, then — only
   once `product.md` is on `main` — drafts `design.md` against your
   `[paths].principles` rubric, reviews it (Gate 2 → DESIGN_READY), and lands
   the decomposition-bearing design as a second PR. Product-gate closure is a
   merged PR *before* any engineering design begins (see `spec-pipeline.md`
   § PR Gates).

   The ordering is the whole point: a design reviewed against an unsettled
   product intent gets re-reviewed when the intent settles, and the second
   review is the expensive one.

See [`spec-pipeline.md`](./spec-pipeline.md) for the full workflow.
