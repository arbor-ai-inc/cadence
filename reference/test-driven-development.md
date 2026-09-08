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
- **For a UI change:** the existing component tests, and browser verification where
  the behaviour is visual or interactive. A screenshot is evidence; "it renders" is not.

**Prefer local conventions over introducing a framework or helper.** A second test
framework in one package doubles the ways a suite can silently not run, which is the
failure the whole *Coverage that does not exist* section below is about.

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
tests does not find what this finds.

Measured on the declarative-creatives epic: ~75 mutations across three tasks, all
eventually killed, but **twelve initially survived, and every one was a test asserting
less than it appeared to.** The recurring shapes, so they can be recognised rather than
rediscovered:

- a violation seeded on the *next* line, where the scanner recovers at the newline anyway;
- a count-only assertion that still passed with line attribution reverted;
- a guard made redundant by a sibling check, except in the one case nothing covered;
- an offset placed inside a construct that made it always zero;
- a "posts nothing" assertion that passed only because the fake host was already torn
  down — three times, in three files, until the teardown was scoped so it could not recur;
- collapsed/`aria` assertions that iterated the **render-time** DOM, which after lazy
  construction is one level deep — that one let a real defect reach review;
- an assertion on an observable a *neighbouring mechanism* also produces (see the next
  section) — the guard's absence changes nothing the test can see.

Five rules that follow from it:

- **Mutate the resolution, not just the original build.** A guard added in response to a
  review comment survived deletion, because a sibling line already provided the
  protection — so the guard implied a safety it did not add. Re-run mutations after
  refactors too; that is how a dead branch surfaced.
- **A survived mutation can indict the fix's *shape*, not the test.** The usual response —
  the resolution is unverified, so strengthen the assertion — is wrong when the fix is
  built so that nothing *can* reliably assert it. One report named the offending column
  from a re-scan over `sorted(...)` while the offending value came from a scan iterating a
  **frozenset**, so with two bad columns the error named one and quoted the other's
  snippet. The first fix compared the two searches; mutation-testing *that* showed its test
  passed with the defect reintroduced, because redness depended on the two iteration orders
  happening to differ. The fix was replaced with one search over one order. **Two searches
  that must agree is the shape to reject** — ask whether the mutation stays green by
  coincidence before adding an assertion to chase it.
- **A rule the harness cannot reach is a *placement* problem, not a coverage one.** The
  sibling of the case above: every mutation survives, and no assertion can fix it,
  because the rule sits somewhere the suite never executes. A browser-facing package with no DOM or
  React harness — `npm test` is bare `node --test` — so a rule inside an event handler is
  unmutatable by construction. #473's confirm gate lived in `handleSubmit`; deleting its
  create-only clause, dropping a `.trim()`, and inverting its comparison all left the
  suite green. The fix is to move the rule, not to test around it: it became a pure
  predicate in `lib/`, and all three mutations then failed by name. `lib/template-form.ts`
  is the standing precedent — *"the widgets live in `components/`; the rules live here."*
- **Then check what the extracted rule now *depends* on.** Extraction can relocate the
  risk rather than remove it. #473's predicate returned `false` whenever no key had been
  suggested, so its correctness rested on every path that opens the form also minting one
  — a precondition spread across three functions that nothing asserted, and a future entry
  point that skipped it would have switched the rule off silently with tests green. Round 2
  of the same review found it. Extract the state transitions too, as a reducer, and walk
  them exhaustively; ask what the rule reads that the mutation set never varies.
- **Treat any output that is not an explicit pass-or-fail as a harness error.** A broken
  harness reports every mutation as SURVIVED. Seen twice in one task (the runner off PATH,
  then the wrong working directory — "no tests ran in 0.00s"). Neither output contains
  the word `failed`, so a naive check reads both as survival. Print a baseline before the
  first mutation.

### State the rule over the name, not over the form you happened to delete

**Mutation testing only kills the mutants you think to write.** That is its one
structural limit, and batch 01 hit it nine times across three tickets. **Six of the
nine were false negatives** — an audit that quietly passes while the violation sits
in the file — and nothing here surfaces one, because a passing audit and a passing
audit look identical. Eight of the nine were absence audits; the ninth was a rule
over prose copy, and it is the false-positive case the last bullet is about.

The shape is always an audit encoding **the form the author happened to delete**
rather than the property. Each of these was a first attempt with a hole:

| Audit as written | What would have passed it |
|---|---|
| `export function resolve` | `export { fetchMenu as resolve }` |
| `verdicts: X` as a property key | `{ ["verdicts"]: X }`, `ctx.verdicts = X` |
| `from "./resolve"` | `import "./resolve";`, `await import("./resolve")` |
| a scanner treating `//` as a comment start | `const s = /\/\//; await import("./resolve");` — the regex blanks the real import behind it |

The last is the one to keep: it is about the audit's **input**, not its rule. A
mis-tokenised line blanks whatever follows, so the audit passes over a file it never
read. One comment-stripping lexer produced four findings across four rounds, **two of
them introduced by the fix for the previous one**.

- **Stop enumerating forms; state the rule over the name.** What ended it was "the
  identifier may not appear in shipped code at all, except as the two `?: never`
  guards." Enumerations are where the holes live.
- **Ask "what else would pass this?", not only "does my seeded violation fail?"**
  Different questions; mutation testing only answers the second.
- **A tightening that fixes a false negative is where the false positive gets
  introduced — validate the permitted set in the same edit as the forbidden set.** A
  prose rule widened to catch `"The shopper qualifies…"` began flagging `"Customer
  loyalty discount qualifies…"`, where `customer` is adjectival. **A rule that fails
  on correct copy is one an author weakens rather than satisfies.**

### Assertions that pass for the wrong reason

- **Assert on the observable the guard changes, not on a field set downstream
  regardless.** If the value you assert is stamped unconditionally by the code
  *after* the guard, the assertion tests the builder and passes with the guard
  deleted. One test for "an undeclared event type is dropped" asserted on
  the posted event's `event_type` — which the event builder hardcodes — so every
  forwarded event was `interaction` either way. What distinguishes the two worlds
  is **how many events were posted**; assert that. Ask what observable differs
  between guard-present and guard-absent, and assert on exactly that.

  **The obvious discriminating test can itself fail to discriminate, and a mutation that
  dies is evidence about *this machine*, not proof.** One tool takes
  `SELECT … FOR UPDATE`, and deleting it left all 14 tests green. The natural fix — hold
  the row lock externally, assert the run blocks — *also* passed with the guard deleted,
  because the ORM's `UPDATE … WHERE id` takes its own row lock, so the run times out
  either way and the test reddens for the neighbouring mechanism. Two concurrent runs
  discriminate: without `FOR UPDATE` both transactions read the pre-state and both write
  an audit row, so `one transition, one audit row` fails at `2 == 1`. Round two then
  found even that insufficient — two runs launched together may execute *sequentially*,
  and if they do the second reads the post-state, takes the idempotent branch, writes no
  audit row, and passes with the guard deleted. So **force the interleaving**: a barrier
  after both have read and before either writes. The mutation check tells you an
  assertion **can** fail; only forcing the race tells you it **must**.
- **Build the fixture from where the message is constructed, not from what the
  message ought to look like.** A fixture that is not the producer's shape agrees
  with the bug: both the test and the code under test are wrong in the same
  direction, so the test confirms the defect instead of catching it. One
  tests hand-built `{ok: false, reason: "element threw"}` — a message the shipped
  `runtime.js` never produces, because it reports `ok: true` for its own degrades
  and puts the truth in `rendered`. Before asserting on a message, open its
  construction site and copy the shape from there.
- **A suite parametrised over a directory listing passes vacuously over an empty
  directory**, and reads identically in CI to one that checked everything. Every such
  suite needs an explicit non-empty guard as its first test. This shape appeared three
  times in one epic (a gate, a mutation harness, a skipped Postgres suite).
- **Check the skip count, not just the pass count.** A declared-but-uninstalled test
  dependency made 16 Postgres tests *skip rather than pass* for most of an epic, and a
  green run looked identical either way.
- **An assertion that a value is *absent* passes when the value is absent from the
  fixture too.** Pin the fixture's conformance, or add a positive control in the same
  block. The JS footgun is **string** `includes`, which coerces its argument — so
  `"…undefined…".includes(undefined)` is `true` and a rendered-output check can pass for
  the wrong reason. **Array** `includes` uses SameValueZero and does not coerce
  (`["undefined"].includes(undefined)` is `false`), so it fails the opposite way: a
  genuinely `undefined` element flips an "is absent" assertion.
- **`assert.equal` in Node is `==`.** `"80.0000" == 80` is `true`, so a rendered string
  compared against a number passes while the types disagree. Use `strictEqual` /
  `deepStrictEqual` everywhere.
- **A test can pass because it asserted before a microtask ran.** If the test exercises a
  promise callback, await **the promise the code under test returns**, or a signal that
  cannot resolve until the callback has run. Awaiting an unrelated or already-resolved
  promise yields one microtask turn and proves nothing about ordering. A zero-height guard
  test stayed green with the guard deleted.
- **Verify a guarantee survives a refactor, not just that the tests do.** Relocating a
  gate kept 630 tests green; what needed re-running was the drift *reproduction*, because
  a moved gate can point at nothing and still pass its own suite.
- **An assertion parametrised over the very value it exists to pin proves nothing.** It
  always looks like coverage. One branch shipped seven of them. Two forms:

  **The fixture's value equals the constant you are trying to catch.** A test asserted a
  sort control against `view.sortDirection`, but the fixture's direction *was* the
  hardcoded `"desc"` the assertion existed to catch — so replacing the variable with the
  literal changed nothing and the mutation was invisible. Make the fixture **differ** from
  the constant, then assert.

  **The override key does not exist on the type.** A fixture spread
  `{...body().totals, gross_spend: …}` to vary a baseline between two calls — but
  `PublisherTotals` has no `gross_spend` field (the name exists elsewhere as a *sort key*,
  which is what made it read as plausible). A spread accepts any key silently, so both
  calls returned the fixture default and the assertion could not distinguish "the value
  survived" from "it was replaced by an identical one". **In a typed codebase, put the
  override in a typed position** so the compiler rejects the dead key. Where you cannot,
  asserting that the two fixtures "differ" is not enough — they can differ in an unrelated
  field while the invalid key stays ignored. **Assert that the specific field the
  regression reads has changed**, which is the same discriminating-observable question as
  the first bullet in this section.
- **Mutate against the test that names the defect, not just against the suite.** A suite
  that goes red proves *some* test caught the mutation — which is exactly how a vacuous
  test hides. When the branch's headline regression test was mutation-checked in isolation
  it stayed **green**; two neighbouring tests were failing on its behalf. Run the mutation,
  then read *which* tests failed.
- **A test double that accepts configuration and discards it makes every test above it
  vacuous.** One `MutationObserver` double stored each `observe()` target and
  options, then notified every observer of every record — so deleting
  `attributes`/`attributeFilter` from the real `observe()` call left **all 316 tests
  green**. Unlike the bullets above, this is invisible from either end: the assertion is
  well chosen and the rule is reachable, and the mutation survives because the *double*
  answers the same way whatever the code configured. (Two more in the same file: a slot
  whose `getAttribute` was hardcoded to a pinned size, so no test *could* express the
  unpinned slot that was the real defect; and a `document.contains` assertion against a
  node the harness never attached.) The check is cheap — for each option the code hands
  a double, delete it in the code and confirm a test fails. **Anything the double
  accepts and discards is a property nothing is testing.**

### A comment that states a property is a test you have not written yet

The sections above ask whether a *test* binds. This one asks whether a *sentence* does,
and it is the failure this repo produces most: **nine times across one epic**
(one measured instance), a comment asserted a property the
code did not have. Reviewers caught every one; nothing else did.

That is a consequence of a deliberate choice. This codebase carries design rationale in
comments rather than in a wiki, which is a real strength — and it means a large surface of
prose that reads as fact. The discipline that makes it safe: **assertive prose must be
falsifiable and tied to a witness.**

**The rule.** When you write a comment asserting an invariant, an exhaustiveness, or a
guarantee — *every*, *all*, *nothing can*, *cannot miss*, *asserted at source*, *the only
remaining way* — you have taken on a debt. Discharge it one of two ways:

1. **Name the test that fails when the property stops holding, and prove it** by deleting
   the property and watching that test go red. Not the code — the *property*: remove the
   entry from the list, reorder the tuple, add the fourth branch. If nothing reddens, the
   sentence is decoration.
2. **Downgrade the prose to intent.** *"Intended; not enforced — see <issue-id>"* is honest
   and costs nothing. A property stated as fact and enforced by nothing is worse than no
   comment, because it stops the next reader from checking.

**Three shapes to watch for, all observed:**

- **The claim about code outside this file.** *"the alert routing reads it"* — nothing
  parses it; the exit code is what routes. *"One R3 provably cannot see"* — R3 sees that
  case at full value, in both money and volume. If the sentence asserts what another
  component does, open that component before writing it. This is the author-side twin of
  `code-review.md` § *A claim the diff asserts is not evidence*.
- **The cited artifact that does not exist.** A comment claimed a named test enumerated
  every non-publishing return; `grep` found the identifier in exactly one place — that
  comment. **Before naming a test, function or constant in prose, grep for it.**
- **The check that asserts the opposite direction.** *"Asserted at source so a third
  entrypoint cannot miss it"* — the check proved nobody builds a *second* event, which a
  third entrypoint that publishes nothing passes unchanged. State what the check proves,
  and say plainly what it does not.

**Position is not enforcement.** A structural check built on source order looked like it
enumerated every early return; because one signal call sat near the top of the function,
every later return passed unconditionally. Textual position is not control-flow dominance,
and "I read the code and it looks right" is the reasoning this whole section exists to
distrust. Delete the property and run the suite.

### Coverage that does not exist reports the same green as coverage that passes

One trap at two altitudes — a suite, a migration. The artifact looks covered and is
not, and **the cost is never the repair: it is that nobody finds out.**

**A suite no CI job runs.** One shell suite exited **127** on `main` for six weeks
after an unrelated change moved the helper it substitutes a fake for; nothing noticed,
because an unrun suite and a passing suite look identical from outside. On another
surface the acceptance criterion was literally "typecheck passes" and no job ran the
type checker: the mutation that breaks its strongest guard leaves the unit suite at
390/390 green and fails only the type check.

**So enumerate every suite in a manifest that names what runs it, and check the
manifest.** A suite with no CI job is recorded as such **with an issue id** —
enumerated, never silent. Adding a suite means adding a row.

That mechanism paid for itself immediately and then taught a second lesson.
[`C-10`](../examples/case-studies.md#c-10--suites-nobody-run) has the numbers: seven
unwired suites found, of which **only one** had ever appeared in a retro fragment, and
**four surfaced only after review noticed the discovery step was blind to whole
classes** — modules in one language, and standalone shell scripts. So a manifest beats
another prose rule, *and* **a check is only as good as the classes it enumerates**,
which is why the discovery step must itself be mutation-tested over each class it
claims to cover.

**A migration nothing executes.** If a project builds its test schema by creating
tables directly from the models, the migration files are never run, and moving one out
of the migrations directory leaves every test green. A migration is covered by exactly
one thing: **a test that applies it, against the same engine production uses.**

Two defects are invisible without one, and both are the kind that only appear on real
data:

- A database-side default versus a language-side one. Only a real upgrade shows
  whether **existing rows** get a value.
- A raw-SQL writer with an explicit column list. It silently never writes a column
  missing from that list, while every model-level test passes.

**Any diff that adds or alters a migration needs such a test in the same diff.** Scope
this rule to the migration system it was written for: a project with more than one —
an ORM's migrations plus a database platform's own, say — needs a harness written for
each, and applying this rule to the second by analogy is how the second one ends up
uncovered. Name the engine explicitly in the test's command; the default in-memory
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
