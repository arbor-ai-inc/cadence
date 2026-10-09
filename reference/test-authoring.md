# Test Authoring

## Overview

Use this workflow to plan the tests for a spec (§ *From a spec*), or to add or
change a test above unit level. For a test it picks the component, the level and
the harness, reuses existing fixtures, decides whether the change needs E2E or
smoke coverage, and records the test in the project's inventory.

Harnesses, fixture factories and the suite list are the project's: name them in
the overlay `<[paths].overlays>/test-authoring.md` or a testing-strategy doc.

**Priority.** P0: the core user path broken, a privacy or compliance breach,
wrong billing, or critical data loss. Most rows are P1 or P2.
**Levels,** cheapest first: unit, integration, component behavioral (one
component end to end, fakes at its edges), E2E (crosses components).
**Manual is allowed only for:** exploratory, subjective UX, unusual operations,
disproportionately expensive to automate, or a temporary gap.

## When To Use

- Planning the tests for a spec. Start with § *From a spec*, then run
  § *Workflow* for each `do now` row.
- Adding or changing an integration, component behavioral, smoke or E2E test, or
  a shared fixture.
- A change touches a cross-component contract edge or a user journey, even if it
  needs only unit tests itself.
- A change adds a deployed surface (a route, service or job in an environment).

Not for unit tests inside a feature PR: use
[`test-driven-development`](./test-driven-development.md), whose § *Test Quality
Guidance* applies to every test this workflow writes too.

## From a spec

Turns a spec into `<[paths].specs>/<slug>/testing-plan.md`: a plan a new
engineer can check, run and act on. This section is the one definition of that file.

**When it runs.**

- **With a new design.** `draft-plan` drafts the plan with `design.md`, and Gate 2
  reviews both. This applies to any design that has never reached DESIGN_READY,
  and to any design that already has a `testing-plan.md` or an opt-out line. For
  those the plan is required unless the design opts out; once a design has one,
  re-opening Gate 2 keeps it required (new ACs need rows). The opt-out waives the
  plan only; the decomposition rules in the design template still apply.
- **On request, any time** — for a design that reached DESIGN_READY without one,
  a spec with only `product.md`, or a refresh. Optional.

**Opting out.** One line in the design's *Test strategy*:
`Testing plan: skipped — <reason>`. Gate 2 records it as an advisory, so it lands
in the ack, and the human who approves the design PR approves the skip. It works
at any point; Gate 2 then stops grading the plan.

**What it reads.**

| The spec has | Rows come from | Test column starts as |
|---|---|---|
| `product.md` only | each requirement and success metric | `gap (to map)` |
| `design.md`, not built | each acceptance criterion and validation-plan item | `gap` |
| `design.md`, built (fully or partly) | the same | `file:line` or `gap` |

A design-only spec takes its requirements from the design's *Goals*. A rerun
keeps every *Decision* already made and maps old rows to new criteria.

**What you may edit.** Only `testing-plan.md`. The audit (step 5) makes temporary
code edits and reverts them.

**Who decides.** Every row is a recommendation. People decide in the file's
*Decisions* table: `do now`, `later` (with an issue) or `skip` (with a reason),
plus who and when. Agents leave *Decision* blank unless a person states one,
recorded with their name. The plan is outside `design_hash`, so after Gate 2
people may fill in decisions and audit results without re-opening the gate. After
Gate 2 rows are never deleted; a row nobody will build is `skip (why)`, and
lowering a priority needs a *Decisions* entry.

1. **Trace the product.** For every requirement, list the ACs that cover it. A
   requirement with none is a gap, unless *Deferred* names it. With no design
   yet, each requirement is a row; skip steps 3 and 5.
2. **One row per promise.** Each AC and each validation-plan item gets exactly
   one row. Then add a row for each *Edge Cases & Invariants* and *Risks* entry
   no AC covers, and for each path or caller the design names that an AC's test
   would miss. ACs are where tests start, not where they end.
3. **Find the existing test.** Search for the AC id and what it names; AC ids repeat
   across specs, so check a hit is this spec's. Record the `file:line` of the assertion that proves the row, or `gap`.
   A test that names the id but does not assert the row's outcome, or asserts an
   outcome the spec has since changed, is a `gap`. A found test reads **test
   found, not audited** until step 5 passes, then **covered (audited)**. Never
   write a bare "covered".
4. **Fill in each row:** *Behavior* (one plain sentence about what breaks for a
   user or operator); *Priority*; *Level* (the cheapest that protects it — an
   in-process test can set what a real client can't fake, so "can't fake it from
   a laptop" makes a row manual only when no in-process test can reach it);
   *Kind* (automated, or manual with its allowed reason); *How to run* (exact
   command and setup); *Who* (*agent*, *engineer*, *operator* or *product lead*),
   plus **blocked by** and what unblocks it.
5. **Audit the P0 rows — only on request.** Stop after the plan and ask the
   engineer or author to confirm the P0 rows with their lead; the answer goes in
   *Decisions*. Then, if asked, break-it check each confirmed P0 row that has a
   test: a one-line change that breaks the behavior (flip the condition, drop the
   guard), run the test, revert.
   - **It must fail on the row's own assertion.** Quote the failing line. A
     failure elsewhere, or none, makes the row a `gap`.
   - **Break every place the row depends on**, one at a time: each request path,
     each copy of a query, each call site the design names.
   - **A second agent with no context from your run repeats the checks** with its
     own breaks. Where the two disagree, the row is a `gap` until someone finds out why.
6. **See it work.** If a person can see the feature, add up to three optional
   walkthroughs, marked *optional — automated by row N*.
7. **Manual and walkthrough steps are copy-paste:** the exact command, what to
   look at, and what a pass looks like, in the named environment.
8. **Answer the cross-cutting questions once:** the capability row (§ *Workflow*
   step 1), E2E and smoke (step 9) and the inventory (step 10).
9. **Write the file** from
   [`templates/_testing_plan_template.md`](../templates/_testing_plan_template.md)
   (or the project's copy in `[paths].templates`),
   which sets its sections and order. Update an existing file in place. Under
   `draft-plan`, its Shape B brief is the reply. Otherwise reply with the summary
   line, the path, and either the proposed P0 rows ("Agree the P0 rows with your
   lead, then ask me to audit them") or the audit results.

The reviewer's checklist:

- [ ] Every requirement maps to a row, or to the design's *Deferred*.
- [ ] Every AC and validation-plan item has exactly one row (count both).
- [ ] Every row says `file:line` or `gap`; two `file:line` cells picked at random
      open on an assertion of that row's outcome.
- [ ] Every P0 row meets the P0 definition above.
- [ ] P0 rows were confirmed by named people, or the plan says they are proposed.
      Each audited row failed on its own assertion at every place it depends on,
      repeated by a second agent; the rest say *test found, not audited*.
- [ ] No row is E2E when one component could prove it.
- [ ] Every manual row has copy-paste steps and names its allowed reason.
- [ ] Every row says how to run it and who does it; every blocked row says what
      unblocks it.
- [ ] The capability row, the E2E answer and the inventory change are stated.
- [ ] Every recommendation has a row in *Decisions*, filled in by people or blank.

Then build the `do now` rows. When the design's decomposition owns a row's AC,
its tests ship in that task's PR. Otherwise run § *Workflow* per row, batching by
component into as few PRs as review allows.

## Workflow

1. **Name the behavior** in one sentence about what a user or operator would see
   break. Pick its row in the project's capability inventory, if it keeps one,
   and its priority. If no row fits, say so in the PR; don't invent one.
2. **Pick the component and the boundary.** The faked side of each boundary is
   what that component's harness already fakes. A harness on in-memory or
   embedded storage is `integration` for anything that depends on the real
   store's behavior (locks, scripts, replication); that needs a real-store test.
3. **Find the existing tests** for that behavior: grep the handler or job name
   and the suite inventory. Extend a test that already covers the scenario rather
   than writing a second one.
4. **Reuse fixtures.** Start from the project's canonical entities and override
   only what the scenario needs. Add a missing entity to the shared factory;
   don't write a private seed helper.
5. **Choose the cheapest level that protects the behavior.** Cover each scenario
   once; permutations belong below E2E.
6. **Prefer component behavioral over E2E.** Use E2E only for what no single
   component can prove.
7. **Skip unit tests a behavioral test already proves**, unless one pins a
   failure better (one branch, one rule).
8. **Don't add an expensive suite to a blocking CI stage on your own.** One that
   fits an existing job's services can be wired there. One needing a live
   environment, a full stack or a long run goes in unwired, with an issue, and
   the PR says why. Wiring it into a blocking job is the user's call.
9. **Check E2E and smoke.**
   - Does the change cross a cross-component contract edge or the main user
     journey? Extend the project's E2E test with a step or assertion. For a
     journey it doesn't cover, add a manual entry to the project's manual-check
     inventory and name it in the PR.
   - Does it add a deployed surface? Add a check to that environment's smoke
     script, or say in the PR why not.
10. **Update the inventory.** A new suite gets a row in the project's suite list,
    with its component, level, priority and capability where the list records them.
11. **Run it, then run everything.** The focused test first, then
    `[commands].test`. Read the skip count as well as the pass count: a suite
    that skipped didn't run.

## Common Rationalizations

| Rationalization | Reality |
|---|---|
| "A unit test is enough; it's faster." | A unit test can't see wiring. If the behavior crosses components, a component behavioral test is the cheapest one that protects it. |
| "I'll write my own seed." | Extend the factory. Private seeds drift. |
| "The E2E doesn't cover this journey." | Then add a manual entry; it keeps the gap visible. |
| "The suite passed." | Check what was skipped. |
| "I'll add it to the PR job so it always runs." | Wiring an expensive suite into a blocking job is the user's call. Propose it; don't wire it. |

## Red Flags

- A private seed helper or hand-built fixture next to an existing factory.
- A behavioral test asserting on internals (private fields, call counts) rather
  than responses, events, rows or artifacts.
- A change to a contract edge with no E2E extension, no manual entry, and no word in the PR.
- A new suite with no inventory row.
- A suite recorded as behavioral that runs on in-memory or embedded state.

## Verification

From a spec:

- [ ] `testing-plan.md` holds the table and the checklist, every box answered.

Each test:

- [ ] For a P0 row of the spec's `testing-plan.md`, the PR records a break-it
      result (the break and the failing line on that row's assertion) or says
      *not audited*.
- [ ] The PR names the behavior, capability, component, level and priority.
- [ ] Existing tests and fixtures were searched, and the PR says which were reused.
- [ ] The E2E/smoke question was answered in the PR, even as "not applicable, because…".
- [ ] Focused test output and `[commands].test` output are quoted, with the skip count.
