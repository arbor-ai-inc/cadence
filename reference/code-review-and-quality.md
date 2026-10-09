# Code Review And Quality

## Overview

Use this workflow to review existing changes, harden an implementation, or
prepare work for merge. The standard is not perfection; the standard is that
the change improves the codebase without hiding correctness, security,
maintainability, or verification risks.

## When To Use

- Reviewing a PR, diff, or local change.
- Reviewing code written by an agent, a human, or yourself.
- Preparing a completed implementation for merge.
- Reviewing a bug fix and its regression coverage.
- Hardening a change that touches security, privacy, contracts, data, or
  operations.

## Repo Context To Load

Load the smallest context that explains the change:

- **The diff under review**: `git diff` or the PR diff.
- **Expected behaviour**: the spec, issue, ticket, or user request. Its factual
  claims are premises, not findings — see
  [`execute-issue`](./execute-issue.md) § *Procedure* step 4.
- **Architecture-sensitive changes**: your architecture docs, and
  `[paths].principles` § *How code review uses this doc*.
- **New, moved or retired routes, RPCs or topics**: `[paths].principles`, for
  whether this crosses a boundary and what must move with it if it does.
- **Who must approve, and what blocks the merge**: `[paths].review_standards`.
  Cadence describes how to review; that file is your project's policy on who
  signs off. Start from
  [`templates/code-review-standards.template.md`](../templates/code-review-standards.template.md).
- **Security-sensitive changes**: your own security guidance, plus the
  [`security-auditor`](./personas/security-auditor.md) persona.
- **Component changes**: that component's README, nearby code, nearby tests.
- **Deploy or operational changes**: the relevant runbook.

## Review Priorities

Lead with findings, ordered by severity:

1. Correctness bugs and behavioral regressions.
2. Security, privacy, auth, and data exposure risks.
3. Contract, migration, rollout, and compatibility issues.
4. Missing tests for changed behavior.
5. Maintainability problems that create real future risk.

Avoid broad style commentary unless it affects correctness, clarity, or local
consistency.

## Review Axes

- Correctness: Does the change do what it claims, including edge cases and
  error paths?
- Data compatibility: Does a read/`*Out` model tolerate legacy rows? A non-Optional
  field (especially an enum) fed by a nullable-with-default column 500s the *entire*
  listing on one legacy `NULL` — coerce `NULL → default` generically on a shared
  read-model base, never via a per-field list that rots (T-21/T-22).
- Tests: Would the tests catch a regression in the changed behavior?
- Architecture: Does the change fit existing patterns and ownership
  boundaries? A route one component calls on another must move the artifacts your
  rubric lists for that edge with it; nothing in CI checks this — see `code-review.md` § *Review contract (both reviewers)*.
- Contract compatibility: the pre-commit gates are drift detectors, not
  compatibility checkers — see `code-review.md` § *Scope completeness*.
- Scope completeness: an unmeasured or indistinguishable customer-affecting
  outcome, or a capability with no UI surface. Name the gap; the author
  scopes it in or files a follow-up. See `code-review.md` § *Scope completeness*.
- Security and privacy: Are inputs validated, secrets protected, and access
  controls preserved?
- Performance: Are there unbounded operations, N+1 queries, avoidable hot-path
  costs, or UI rendering issues?
- Simplicity: Are abstractions earning their complexity?
- Dependencies: Does the change avoid unnecessary new dependencies?

## Workflow

1. Understand the intent before judging the code.
2. Inspect tests first when they exist; they reveal intended behavior and
   coverage.
3. Review the implementation against the axes above.
4. Check whether the verification story is credible.
5. Label findings by severity and make required vs optional feedback clear.
6. If no issues are found, say so clearly and mention residual risk or test
   gaps.

## Working With Automated Reviewers

Which reviewer runs, if any, is `[review].provider` in `cadence.toml`. Provider
specifics live in [`providers/`](./providers/); this holds for any of them.

- **Take the concern, not necessarily the patch.** Verify every finding before
  applying it. **Accepting a wrong edit to close a comment makes the
  tree worse**, and it closes the comment either way.
- **Verify a CI or lint claim before acting on it** — see `code-review.md` § *Loop*
  step 3.
- **State the disagreement in the reply.** When declining a patch, say which
  decision it would reverse and why the concern is still addressed; a reviewer that
  verifies will often withdraw the finding.
- **Reply where the reviewer is listening, or the disagreement is not stated at
  all.** A standalone top-level comment is frequently not a reply, and must not be
  reported to the author as "answered" (T-17).
- **A passing status does not mean it said nothing** — read inline comments on an
  approving review too.
- **A passing status can also mean it never looked.** A check row is synthesized
  from review state, and **skipped, rate-limited, paused, stale and clean all render
  identically.** Read the row's *description*, never its bucket — or better, do not
  read the row:

  ```bash
  python3 tools/review_state.py --pr "${PR:?}"
  ```

  **Do not hand-roll the verdict query** (`automation-silently-paused`,
  [`C-09`](../examples/case-studies.md#c-09--a-reviewer-that-reports-success-without-running));
  the script implements and self-tests every load-bearing detail.
- **Unresolved-thread count is not finding count.** A finding outside the diff lands
  in the **review body**. **Read it even when the thread count is zero.**
- **Findings live on several surfaces and the review state shows none of them.**
  A verdict gives `state` and commit, never what was found. Enumerate every surface
  your provider uses — review bodies, inline comments, and resolution state are
  usually three endpoints, none counting the others. The provider notes have the
  commands.

## When Review Rounds Do Not Converge

When the three-round circuit breaker fires:

1. Resolve what can be resolved, and mutation-test the resolutions.
2. **Say in the PR that the last round's fixes were not re-reviewed, naming the commit**
   — the disclosure keeps confidence in them honest rather than assumed.

**Expect each round's own fix to be the next round's top finding** (T-24). So:

- **Give the reviewer the delta separately from the full diff, and say to weight the
  delta** — the newest commit is the least-reviewed code on the branch.
- **Re-run the mutation campaign against the fix, not just the suite** — see
  *test-driven-development.md* § *Mutation-test any change that adds a rule* and the
  *mutate against the test that names the defect* bullet under § *Assertions that pass
  for the wrong reason*.

## Habits That Repeatedly Found Real Defects

- **Fixing one instance of a pattern is the moment to grep for its siblings** — the
  identical hole usually sits one function away.

  **When the sibling is a *claim*, grep finds a phrasing, not the claim** — enumerate
  the phrasings first, then sweep three axes: every wording, every file type (scripts'
  comments included), and whole sections read rather than matched lines (T-23). **A heading and its body are two
  separate claims.**
- **A sweep answers "did I get the ones I looked at", never "did I enumerate every
  site" — and the two read identically** (`query-answered-partially`). E.g.:
  - **The sweep that never ran.** Under zsh an unquoted glob (`--include=*.ts`) aborts
    *before grep starts* and prints nothing. **Quote every glob, never suppress stderr
    on a sweep, and read the exit status:** empty output and a failed command look the
    same.
  - **The signal that answers neither way.** After a squash, `git log origin/main..branch`
    lists every commit as unmerged (new SHA); diff file **contents** against
    `origin/main` instead. See `git-pr-workflow`
    § *Post-Merge Cleanup*.

  Where a compiler or type system can enumerate, let it rather than grepping — see
  [`execute-issue.md`](./execute-issue.md) § *Procedure* step 4.
- **A comment that describes code you did not write is a defect, not a typo** — see
  *test-driven-development.md* § *A comment that states a property is a test you have
  not written yet*.
- **Comment-only changes are the one class no test can catch** — re-verify prose
  against the code like a behaviour change.
- **Never write that something is impossible without trying it**, typically as
  *justification for a weaker test*. **The tell is any comment explaining why a
  criterion was met a *different* way than written.** Either the command is in your
  scrollback, or the sentence does not go in.
- **Treat a pre-review self-assessment as a hypothesis.** Reproduce the hole yourself
  before fixing it — a demonstration turns an argument into a fact.
- **When a reviewer offers a measurement, that is the finding to act on first.**
- **Prefer narrow reviewers over broad ones** — one question each.
- **Read across the open queue.** Two PRs touching *different* files can still break
  `main` together (two migrations naming one parent). When a PR adds a migration,
  package `__init__` or registry entry, run the covering test on the merged tree
  (`git merge-tree --write-tree pr-a pr-b`, then `git archive` that OID); a clean
  `merge-tree` means it applies, not that it is valid.
- **A test double quieter than the real dependency** (no stderr, always 200) makes the
  assertion decorative. Patch below the contract.
- **After `main` is merged in**, read `git show --remerge-diff` and recount keys in
  generated files. Pin a posted review to `headRefOid`.

## Guards, Shells, And Threads That Do Not Close

- **A guard that cannot halt is not a guard.** In shell, `exit 1` inside `$( )` leaves
  only the subshell: `cmd "$(validate ...)"` runs `cmd` with an empty string. Assign and
  check: `V="$(validate ...)" || exit 1`. Assert the *halt*, with the positive control
  *test-driven-development.md* § *Assertions that pass for the wrong reason* requires.

- **An enumerated guard is the same shape as the bug it fixes.** Validate *as you
  assemble*, and assert the **structure** — a test enumerating the same names passes
  beside the defect.

- **One normalisation, shared.** A second implementation of the same check — even a
  regex in a test — drifts from the runtime.

- **`sed FILE | grep -q PATTERN` under `pipefail` can die** — `grep -q` closes the pipe
  at its first match; survival is a scheduling race, not size or GNU-versus-BSD. The
  signature is a bare `rc=141` with empty stderr. Prefer one `awk` reading the file directly, and check under
  Linux (stash-compare first; some suites fail there on the baseline):

  ```bash
  docker run --rm -v "$PWD":/w -w /w bash:5 sh -c \
    'apk add --no-cache gawk grep sed coreutils python3 && bash "$1"' \
    _ operations/dev/tests/test_example.sh
  ```

  Strip comments before matching source, too — the prose explaining a guard otherwise
  satisfies the check for it.

- **The bot's own thread resolution often fails**, leaving threads pending on you.
  Filter to **bot-originated** threads first: under
  `required_review_thread_resolution`, closing a human's clears live feedback *and*
  makes the gate read satisfied. Reuse the enumeration query in § *Findings live on
  several surfaces*, adding `id` and filtering on the **first** comment's author (`last`
  is merely who spoke most recently), then `resolveReviewThread(input:{threadId:$t})`
  per id. A human thread stays open until its own author is satisfied.

## Finding Format

Use this shape for actionable findings:

```text
[Severity] Short issue title
File: path/to/file.ext:line
Problem: What can go wrong.
Why it matters: The concrete user, system, security, or maintenance impact.
Fix: The smallest reasonable correction or direction.
```

For normal final review responses, lead with findings and keep summaries brief.

## Change Sizing

Prefer small, focused changes:

- Around 100 changed lines: easy to review.
- Around 300 changed lines: acceptable for one coherent change.
- Around 1000 changed lines: usually too large; split unless mostly generated,
  deleted, or mechanical.

Separate refactoring from behavior changes unless the refactor is tiny and
directly enables the behavior.

## Common Rationalizations

| Rationalization | Reality |
|---|---|
| "The tests pass, so it is good." | Tests are necessary but do not catch every architecture, security, or readability problem. |
| "I wrote it, so I know it is correct." | Authors are least likely to see their own assumptions. |
| "We can clean it up later." | Deferred cleanup often becomes permanent. Fix required issues before merge. |
| "AI-generated code is probably fine." | Agent-written code needs careful review because it can be confident and wrong. |
| "This is just a nit." | If it affects behavior, safety, or future maintenance, it is not a nit. |

## Red Flags

- "LGTM" without evidence of actual review.
- Security-sensitive changes without security-focused review.
- Bug fixes without regression coverage.
- Large diffs that are too broad to review coherently.
- Review comments without severity or required/optional distinction.
- Dead code left behind after refactors.
- New dependencies without justification.

## Verification

After review, confirm:

- [ ] Findings are ordered by severity.
- [ ] Required vs optional feedback is clear.
- [ ] Tests and build status are known or explicitly not run.
- [ ] Security, privacy, and data-contract risks were considered when relevant.
- [ ] Residual risk or missing verification is documented.
