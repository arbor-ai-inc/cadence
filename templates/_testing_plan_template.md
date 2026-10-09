# Testing Plan: <FEATURE NAME>

> Drafted by an agent with cadence's `test-authoring` workflow § *From a spec*,
> which defines this file. Every row is a recommendation; the engineer, the lead
> and the product lead decide. This file is `<[paths].specs>/<slug>/testing-plan.md`.
> It is reviewed at Gate 2 but is outside `design_hash`.

<!-- testing plan drafted from <product.md | design.md>, <date> -->

## How to use this template — delete this section when you instantiate

- **Write for someone new.** Simple English, one short sentence per row.
- **Shortest first.** Keep the sections in this order.
- **Agents leave *Decision* and *Who decided* blank**, unless a person states a
  decision to them; then record it with that person's name. A rerun keeps them.
- **From `product.md` only:** rows are requirements and success metrics, the
  test cell is `gap (to map)`, and there is no audit yet.
- Delete a section that can't apply (say, *See it work* when there is nothing a
  person can see).

---

**<N> items: <X> covered (audited), <Y> test found (not audited), <Z> gaps, <W> manual.**

## Decisions

One row per recommendation: each gap, each manual and see-it-work item, and the
audit of the proposed P0 rows.

| # | Recommendation | Decision | Who decided, when |
|---|---|---|---|
| 1 | <add test: what, at what level> | | |
| 2 | Confirm P0 rows <list>, then audit them | | |

*Decision* is `do now`, `later (issue)` or `skip (why)`.

## Test plan

**Automated (P0 first, up to 10)**
1. **<P0 | P1 | P2>, <test found, not audited | covered (audited) | gap | gap (to map)>.**
   <what must hold, in one plain line>

**Manual** (reason: exploratory / subjective UX / unusual operations / too
expensive to automate / temporary gap)
- **M1, <name> (<who>).** <steps to copy and paste>. Pass: <what you see>.

**See it work** (optional; automated by row <n>)
- **W1, <name>.** <steps>. You should see <what>.

## How to write and run them

| Component | Where tests go | Run one | Setup |
|---|---|---|---|
| <component> | <path> | <command> | <none / container / venv / …> |

- Run everything with the project's `[commands].test`, and read the skip count.
- For each gap: <what to add, in which file>.

## Pre-work, by who

| Who | Setup | Blocked by |
|---|---|---|
| Agent | | |
| Engineer | | |
| Operator | | |
| Product lead | | |

## Break-it audit (P0)

<Not run. Proposed P0 rows: <list>.> Who confirmed them: see *Decisions*.

| Row | Break | Failing line | Second agent agrees? |
|---|---|---|---|

## Full table

| # | Spec item | Product req | Behavior | Priority | Level | Kind | How to run | Who | Test |
|---|---|---|---|---|---|---|---|---|---|

## Checklist

<Copy the reviewer checklist from `test-authoring` § *From a spec* and answer
every box.>

## Cross-cutting

- **Capability row:** <the row in the project's capability or feature inventory, or "none fits">
- **E2E and smoke:** <extend, manual entry, or not needed and why>
- **Inventory:** <suite-list rows and manual-check inventory entries this adds>
