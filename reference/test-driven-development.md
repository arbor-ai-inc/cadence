# Test-Driven Development

## Overview

Use this workflow to prove changed behavior with tests. For bug fixes, reproduce
the bug with a failing test or an equivalent deterministic check before fixing
it whenever practical.

## When To Use

- Implementing new logic or behavior.
- Fixing a bug that should receive regression coverage.
- Modifying existing functionality.
- Adding edge-case handling.
- Refactoring behavior where external semantics must be preserved.

Do not use this workflow for documentation-only changes, static content edits,
or pure configuration updates with no behavioral impact.

## Repo Context To Load

Start from the affected package, not from the repository root:

- **The nearest existing tests.** They tell you the framework, the fixtures, the
  naming, and the invocation. Read them before writing one.
- **How this package is actually run.** The project's `[commands].test` is the
  whole-repo command; a package usually has a narrower one in its own manifest or
  README. Use the narrow one for the loop and the configured one before you commit.
- **For a contract or API change:** whatever pins the shape — a schema file, or the
  doc that holds it in prose — plus the nearby handlers and their
  request/response tests.
- **For a UI change:** the component tests, plus browser verification for visual or
  interactive behaviour. A screenshot is evidence; "it renders" is not.

**Prefer local conventions over introducing a framework or helper.** A second test
framework doubles the ways a suite can silently not run.

## Workflow

1. Inspect nearby tests and the existing test style.
2. Choose the narrowest meaningful test level:
   - Unit tests for pure logic and edge cases.
   - Service or API tests for request/response behavior.
   - Integration tests for cross-component contracts.
   - UI or browser checks for user-visible workflows.
3. For a bug, write or identify a reproduction that fails before the fix.
4. For new behavior, write a failing test first when practical.
5. Implement the smallest change that makes the test pass.
6. Refactor only after tests are green, and rerun affected tests after each
   meaningful refactor.
7. Run focused tests first, then broaden verification when the blast radius
   justifies it.
8. Record commands run and anything that could not be verified.

## Test Quality Guidance

- Test behavior, not implementation details.
- Prefer real implementations, then fakes, then stubs. Use mocks sparingly at
  boundaries where real dependencies are slow, nondeterministic, or unsafe.
- Use descriptive test names that read like expected behavior.
- Keep tests isolated and deterministic.
- Prefer clear, self-contained tests over overly dry helpers that hide the
  scenario.
- Avoid broad snapshots unless the repo already uses them carefully.

### Mutation-test any change that adds a rule

When a change introduces a *rule* — a validator, a gate, a scanner, a guard — break
the rule deliberately, one edit at a time, and confirm a test fails. Reading your own
tests does not find what this finds: every survivor on one epic was a test asserting
less than it appeared to. Shapes to recognise: a violation seeded on the *next* line,
where the scanner recovers at the newline anyway; a count-only assertion that passes
with line attribution reverted; a guard redundant with a sibling check except in one
uncovered case; an offset inside a construct that makes it always zero; a "posts
nothing" assertion passing because the fake host was already torn down (scope the
teardown so it cannot recur); assertions iterating the **render-time** DOM, one level
deep after lazy construction; an observable a *neighbouring mechanism* also produces
(next section).

Five rules that follow:

- **Mutate the resolution, not just the original build** — a guard added for a review
  comment can be redundant, implying a safety it does not add. Re-run mutations after
  refactors too; that surfaces dead branches.
- **A survived mutation can indict the fix's *shape*, not the test** — when nothing
  *can* reliably assert the fix, strengthening the assertion is wrong. **Two searches
  that must agree is the shape to reject** (e.g. `sorted(...)` vs a frozenset order).
  Ask whether the mutation stays green by coincidence before chasing it.
- **A rule the harness cannot reach is a *placement* problem, not a coverage one.** If
  it sits where the suite never executes (e.g. an event handler under bare
  `node --test`), move it to a pure predicate in `lib/`; do not test around it. Precedent: `lib/template-form.ts` — *"the widgets live in
  `components/`; the rules live here."*
- **Then check what the extracted rule now *depends* on** — an unasserted precondition
  spread across callers relocates the risk. Extract the state transitions too, as a
  reducer, and walk them exhaustively; ask what the rule reads that the mutation set
  never varies.
- **Treat any output that is not an explicit pass-or-fail as a harness error.** A broken
  harness (runner off PATH; "no tests ran in 0.00s") reports every mutation as
  SURVIVED. Print a baseline before the first mutation.

### State the rule over the name, not over the form you happened to delete

**Mutation testing only kills the mutants you think to write.** An audit encoding **the
form the author happened to delete** rather than the property fails as a silent false
negative. First attempts with holes:

| Audit as written | What would have passed it |
|---|---|
| `export function resolve` | `export { fetchMenu as resolve }` |
| `verdicts: X` as a property key | `{ ["verdicts"]: X }`, `ctx.verdicts = X` |
| `from "./resolve"` | `import "./resolve";`, `await import("./resolve")` |
| a scanner treating `//` as a comment start | `const s = /\/\//; await import("./resolve");` — the regex blanks the real import behind it |

The last is about the audit's **input**: a mis-tokenised line blanks whatever follows,
so the audit passes over a file it never read.

- **Stop enumerating forms; state the rule over the name** — e.g. "the identifier may
  not appear in shipped code at all, except as the two `?: never` guards."
  Enumerations are where the holes live.
- **Ask "what else would pass this?", not only "does my seeded violation fail?"**
  Different questions; mutation testing only answers the second.
- **A tightening that fixes a false negative is where the false positive gets
  introduced — validate the permitted set in the same edit as the forbidden set.**
  **A rule that fails on correct copy is one an author weakens rather than satisfies.**

### Assertions that pass for the wrong reason

- **Assert on the observable the guard changes, not on a field set downstream
  regardless** — e.g. *how many* events were posted, not an `event_type` the builder
  hardcodes. Ask what differs between guard-present and guard-absent, and assert that.

  **A mutation that dies is evidence about *this machine*, not proof.** For a lock such
  as `SELECT … FOR UPDATE`, an external lock can redden for a neighbouring mechanism,
  and concurrent runs may execute sequentially. **Force the interleaving**: a barrier
  after both have read and before either writes. Mutation tells you an assertion
  **can** fail; only forcing the race tells you it **must**.
- **Build the fixture from where the message is constructed, not from what the
  message ought to look like** — otherwise the fixture agrees with the bug. Open the
  construction site and copy the shape from there.
- **An assertion over a collection passes vacuously when it is empty** — `all(...)`, a
  loop of asserts, a sum, a parametrisation over a listing. Assert non-empty *first*, in
  the same test. Not when emptiness *is* the expected result ("no events emitted").
- **Check the skip count, not just the pass count** — an uninstalled dependency or
  absent database makes tests *skip*, and the run looks green either way. A guard that
  reads files outside its module needs a cache-busting run (`go test -count=1`).
- **A benchmark needs a correctness assertion over the same run** as its timing, or it
  measures whatever it was pointed at (`benchmark-has-no-verdict`, 4 times).
- **An assertion that a value is *absent* passes when the value is absent from the
  fixture too.** Pin the fixture's conformance, or add a positive control in the same
  block. JS footgun: **string** `includes` coerces — `"…undefined…".includes(undefined)`
  is `true`; **array** `includes` (SameValueZero) does not —
  `["undefined"].includes(undefined)` is `false`, so a genuinely `undefined` element
  flips an "is absent" assertion.
- **`assert.equal` in Node is `==`** (`"80.0000" == 80` is `true`). Use `strictEqual` /
  `deepStrictEqual` everywhere.
- **A test can pass because it asserted before a microtask ran.** Await **the promise
  the code under test returns**, or a signal that cannot resolve until the callback has
  run — not an unrelated or already-resolved promise.
- **Verify a guarantee survives a refactor, not just the tests.** After moving a gate,
  re-run the drift *reproduction* — a moved gate can point at nothing and stay green.
- **An assertion parametrised over the very value it exists to pin proves nothing.**
  - **The fixture's value equals the constant you are trying to catch.** Make the
    fixture **differ** from the constant, then assert.
  - **The override key does not exist on the type** — a spread accepts a dead key
    silently. **In a typed codebase, put the override in a typed position** so the
    compiler rejects it. Where you cannot, asserting the fixtures "differ" is not
    enough — **assert that the specific field the regression reads has changed**.
- **Mutate against the test that names the defect, not just against the suite.** A suite
  that goes red proves only that *some* test caught it. Run the mutation, then read
  *which* tests failed.
- **A test double that accepts configuration and discards it makes every test above it
  vacuous** (e.g. a `MutationObserver` double ignoring `attributeFilter`). For each
  option the code hands a double, delete it in the code and confirm a test fails.
  **Anything the double accepts and discards is a property nothing is testing.**

### A comment that states a property is a test you have not written yet

Does a *sentence* bind? A comment asserting a property the code lacks is the most
common failure, and only reviewers catch it. **Assertive prose must be falsifiable and
tied to a witness.**

**The rule.** A comment asserting an invariant, exhaustiveness, or guarantee — *every*,
*all*, *nothing can*, *cannot miss*, *asserted at source*, *the only remaining way* — is
a debt. Discharge it one of two ways:

1. **Name the test that fails when the property stops holding, and prove it** by deleting
   the *property* (not the code — remove the list entry, reorder the tuple, add the fourth
   branch) and watching it go red. If nothing reddens, the sentence is decoration.
2. **Downgrade the prose to intent:** *"Intended; not enforced — see <issue-id>"*. A
   property stated as fact and enforced by nothing is worse than no comment — it stops
   the next reader from checking.
3. **In an architecture or state doc, write the test that reads the doc** — no hook
   reads prose. Scope it to the field's own table **row and column**: a whole-section
   `Contains` passes on the prose beside the table.

**Three shapes to watch for:**

- **The claim about code outside this file.** If the sentence asserts what another
  component does, open that component before writing it — the author-side twin of
  `code-review.md` § *A claim the diff asserts is not evidence*.
- **The cited artifact that does not exist.** **Before naming a test, function or
  constant in prose, grep for it.**
- **The check that asserts the opposite direction** (e.g. proving nobody builds a
  *second* event, which a third entrypoint that publishes nothing passes). State what
  the check proves, and say plainly what it does not.

**Position is not enforcement.** Textual position is not control-flow dominance, and
"I read the code and it looks right" is the reasoning this section distrusts. Delete
the property and run the suite.

### Coverage that does not exist reports the same green as coverage that passes

The artifact looks covered and is not; **the cost is never the repair: it is that
nobody finds out.**

**A suite no CI job runs** (type checks included) looks identical to a passing one.
**So enumerate every suite in a manifest that names what runs it, and check the
manifest.** A suite with no CI job is recorded as such **with an issue id** —
enumerated, never silent. Adding a suite means adding a row. **A check is only as good
as the classes it enumerates** ([`C-10`](../examples/case-studies.md#c-10--suites-nobody-run)),
so the discovery step must itself be mutation-tested over each class it claims to cover.
**Give the manifest a local runner and run all of it before pushing** — a shared-artifact
change fires guards in suites it does not seem to touch. Report passed, failed and
*unavailable* (could not run here) separately.

**A migration nothing executes.** If a project builds its test schema by creating
tables directly from the models, the migration files are never run. A migration is covered by exactly
one thing: **a test that applies it, against the same engine production uses.** Without
one, two defects that only appear on real data are invisible:

- A database-side default versus a language-side one. Only a real upgrade shows
  whether **existing rows** get a value.
- A raw-SQL writer with an explicit column list. It silently never writes a column
  missing from that list, while every model-level test passes.

**Any diff that adds or alters a migration needs such a test in the same diff.** A
project with more than one migration system (an ORM's plus a database platform's, say)
needs a harness written for each — applying this rule to the second by analogy leaves
it uncovered. Name the engine explicitly in the test's command; the default in-memory
database is exactly the substitution this rule exists to prevent.

## Common Rationalizations

| Rationalization | Reality |
|---|---|
| "I'll add tests after the code works." | Tests added afterward often mirror the implementation instead of proving behavior. |
| "This is too simple to test." | Simple behavior is still behavior. A small regression test is often cheap insurance. |
| "I tested it manually." | Manual testing does not persist as a regression guard. |
| "The existing suite is enough." | Existing tests only help if they cover the changed behavior. |
| "The test passed on the first run." | A test that never failed may not prove the intended behavior. Check that it can fail for the right reason. |

## Red Flags

- Bug fixes without a reproduction test or documented reason one was not added.
- Tests that assert internal method calls instead of outcomes.
- Vague test names like "works" or "handles errors."
- Skipped, disabled, or weakened tests to make the suite pass.
- Running the same command repeatedly without code changes and treating that as
  added confidence.
- Introducing a new testing library where local tooling already works.
- A new rule (validator, gate, scanner, guard) shipped without mutation evidence.
- A suite parametrised over a glob with no non-empty guard.
- A green run whose skip count was never checked.
- A migration with no real-Postgres test in the same diff.
- A fixture hand-written to match the assertion rather than copied from the producer.
- A comment asserting *every*, *all*, *nothing can* or *asserted at source*, with no test
  named beside it that fails when the property stops holding.
- A comment naming a test, function or constant that `grep` does not find.

## Verification

After implementation, confirm:

- [ ] New or changed behavior has a corresponding test or a documented reason
      it cannot be automated yet.
- [ ] Bug fixes include a reproduction test or equivalent deterministic check
      when practical.
- [ ] Focused tests pass.
- [ ] Broader tests were run when the change has cross-module blast radius.
- [ ] No tests were skipped, disabled, or weakened without explicit approval.
- [ ] Verification commands and results are recorded in the final summary.
