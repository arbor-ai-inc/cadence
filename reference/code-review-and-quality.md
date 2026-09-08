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
- Data compatibility: Does a read/`*Out` model tolerate legacy rows? A
  non-Optional field (especially an enum) fed by a nullable-with-default
  column 500s the *entire* listing on one legacy `NULL` — coerce
  `NULL → default` generically on a shared read-model base, never via a
  per-field list that silently rots as columns/models are added (T-21/T-22).
- Tests: Would the tests catch a regression in the changed behavior?
- Architecture: Does the change fit existing patterns and ownership
  boundaries? If it mounts a route one plane calls on another, did the plane
  graph, edge list, both plane boundary tables, and the component route table
  move with it? Nothing in CI checks this.
- Contract compatibility: The pre-commit gates are drift detectors, not
  compatibility checkers — a refreshed golden hash turns them green on a
  breaking change. Does the diff remove, rename, narrow, or require a declared
  field that a running consumer still reads?
- Scope completeness: Does the change leave a customer-affecting outcome that
  nothing measures, or one merged into an existing count so the customer cannot
  distinguish it (a wrong number, not a missing one)? Does it add a capability
  with no console surface? Name the gap; the author scopes it in or files a
  follow-up. See `code-review.md` § *Scope completeness*.
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
specifics — the exact commands, the exact API quirks — live in
[`providers/`](./providers/); this section is what holds regardless of which one
you use.

- **Take the concern, not necessarily the patch.** Verify every finding against
  the code before applying it. One review asked to narrow a "nothing renders yet"
  statement in a way that would have made it *false*; the real defect was a
  different line implying a component was live. **Accepting a wrong edit to close
  a comment makes the tree worse**, and it closes the comment either way.
- **Verify a CI claim before acting on it.** A reviewer asserted two lint findings
  "will fail the CI job" when the project enables neither rule. Check it —
  run the hook against the files. Accepting such a claim quietly becomes an
  argument for widening the lint config later.
- **State the disagreement in the reply.** When declining a patch, say which
  decision it would reverse and why the concern is still addressed. A reviewer
  that runs its own verification will often confirm and withdraw the finding.
- **Reply where the reviewer is listening, or the disagreement is not stated at
  all.** A standalone top-level comment is frequently not a reply. On T-17 four
  declines posted that way sat unprocessed while the review stayed
  `CHANGES_REQUESTED` — and were reported to the author as "answered", which was
  wrong.
- **A passing status does not mean it said nothing.** Read the inline comments
  even on an approving review.
- **A passing status can also mean it never looked**, and this is the one to
  build a habit around. A check row is synthesized from review state, and
  **skipped, rate-limited, paused, stale and clean all render identically.**
  Read the row's *description*, never its bucket — or better, do not read the row:

  ```bash
  python3 tools/review_state.py --pr "${PR:?}"
  ```

  **Do not hand-roll the verdict query.** It was wrong three times before it was
  right, and reading it wrong is `automation-silently-paused` —
  [`C-09`](../examples/case-studies.md#c-09--a-reviewer-that-reports-success-without-running),
  nine occurrences in one batch. Every detail that makes it load-bearing is
  implemented and self-tested in that script, with the case each was measured on.
  Read the script, not a second copy of its reasoning.
- **Unresolved-thread count is not finding count.** A finding whose line falls
  outside the diff cannot be posted inline, so it arrives in the **review body**
  instead. One PR reported `unresolved threads: 0` with a Major finding open — a
  real defect in the test harness, described in prose that nothing counted. **Read
  the review body even when the thread count is zero.**
- **Findings live on several surfaces and the review state shows none of them.**
  A verdict tells you `state` and which commit; it never tells you what was
  found. Enumerate every surface your provider uses — review bodies, inline
  comments, and resolution state are usually three different endpoints, and no
  one of them counts the others. The provider notes have the commands.

## When Review Rounds Do Not Converge

Three rounds is the circuit breaker, and it has fired. When it does:

1. Resolve what can be resolved, and mutation-test the resolutions.
2. **Say in the PR that the last round's fixes were not re-reviewed, naming the commit.**
   Both times this happened the final findings were mechanical enough to fix with
   confidence — the disclosure is what keeps that honest rather than assumed.

**Expect each round's own fix to be the next round's top finding.** On T-24 this held
**four times running**, counting the automated reviewer as the fourth: round 2 replaced a
control that nothing pinned; round 3 found round 2's fix was itself a regression — it
moved a fetch to its own effect and left the matching state resets behind in an effect
keyed on the ranking, so every sort click blanked a panel *permanently*, while the commit
message claimed to have removed a flicker. The automated pass then found round 3's own
regression test was pinned to nothing.

Two practices came out of that, and they are what surfaced every one of these:

- **Give the reviewer the delta separately from the full diff, and say to weight the
  delta.** The newest commit is the least-reviewed code on the branch, and after a
  circuit-breaker stop it has had no adversarial pass at all.
- **Re-run the mutation campaign against the fix, not just the suite.** A fix that closes
  a finding is new code with no review behind it. See *test-driven-development.md* §
  *Mutation-test any change that adds a rule*, and the *mutate against the test that names
  the defect* bullet under § *Assertions that pass for the wrong reason*.

## Habits That Repeatedly Found Real Defects


- **Fixing one instance of a pattern is the moment to grep for its siblings.** An
  unanchored-regex hole was closed in one function and the identical hole sat one function
  away. A prototype-pollution hazard was found in one content-keyed map and the same
  hazard was in another the reviewer had not looked at. Three holes in three rounds of one
  scanner is what finally justified rebuilding it rather than patching a fourth time.

  **When the sibling is a *claim* rather than code, grep finds a phrasing and not the
  claim** — so enumerate the phrasings first, then sweep three axes. T-23 made
  retirement reversible and spent all three review rounds on the same defect: the old
  "one-way" assertion corrected in some places and left standing in others. It travelled
  under six wordings (`one-way`, `no tool un-deprecates`, `two writers`, `a second
  writer`, `no longer transitions anything`, `manual SQL`). Round 1 swept `.md` and `.py`
  and called it exhaustive; **the pipeline shell script that invokes the tool still
  carried it**, because a script's comments are where its own reasoning lives. Round 2
  added `.sh` and still missed two lines *inside a file it was editing*. Round 3 found
  three more only by reading whole sections — including a paragraph headed **"Three
  writers"** whose body named two and said the third tool "no longer transitions
  anything", in a file already corrected twice for exactly that. **A heading and its body
  are two separate claims**, and a pointer added elsewhere in the same change was routing
  readers straight at the stale one.
- **A sweep answers "did I get the ones I looked at", never "did I enumerate every
  site" — and the two read identically in the output.** `query-answered-partially`,
  n=11 across two batches, and the one most often mistaken for
  `unverified-artifact-claim` from outside. Three shapes:
  - **The sweep that never ran.** `grep -rn … --include=*.ts` aborts under zsh — the
    unquoted glob word-splits and zsh dies *before grep starts*, printing nothing
    directly above the author's own `--- (empty = clean) ---`. Quoting turned three
    "clean" sweeps into 60+ hits. **Quote every glob, never suppress stderr on a sweep,
    and read the exit status:** empty output and a failed command look the same.
  - **The sweep that took three passes and still missed a line** — the third pass found
    a site in a file the second had already edited. Each pass answered the wrong
    question.
  - **The signal that answers neither way.** After a squash, `git log origin/main..branch`
    lists every commit as unmerged, because the squash writes a new SHA. One branch
    listed three; reading that as "three are missing" was wrong exactly as "nothing is
    missing" would have been — the real answer was one stranded commit, and it came from
    diffing file **contents** against `origin/main`. See `git-pr-workflow`
    § *Post-Merge Cleanup*.

  Where a compiler or type system can enumerate, let it rather than grepping — the
  author-side statement, with its evidence, is [`execute-issue.md`](./execute-issue.md)
  § *Procedure* step 4.
- **A comment that describes code you did not write is a defect, not a typo.** One
  blocker was exactly this: the comment said work happened lazily, the code built the
  whole tree eagerly, and the reviewer measured 1.28M DOM nodes. The *fix* commit then
  cited a constant it had just deleted. Grep for the identifier before claiming it exists.
- **Comment-only changes are the one class no test can catch.** A round that corrected
  six stale comments got two of them newly wrong — one contradicting a passing test 380
  lines below it. Re-verify prose against the code the way you would a behaviour change.
- **Never write that something is impossible without trying it.** Distinct from the
  hypothesis rule below, because it shows up as *justification for a weaker test*. Three
  times on one epic: *"this repo has no renderer and no dependency budget for one"* —
  disproved in forty lines, and three forbidden strings were reaching the rendered page
  behind the substitute; *"there is no behavioural assertion available here"*, used to
  justify source-checking a control's handlers — false, since the components are hook-free
  and their `onChange` can simply be invoked. **The tell is any comment explaining why a
  criterion was met a *different* way than written.** Either the command is in your
  scrollback, or the sentence does not go in.
- **Treat a pre-review self-assessment as a hypothesis.** Three consecutive PRs shipped a
  sentence in the body or a code comment that review proved false ("both call sites are
  load-bearing", "drift is impossible"). Reproduce the hole yourself before fixing it —
  a demonstration turns an argument into a fact.
- **When a reviewer offers a measurement, that is the finding to act on first.** The
  strongest findings in one epic all came with numbers.
- **Prefer narrow reviewers over broad ones.** A single broad prompt burned large token
  budgets twice and produced nothing; two reviewers with one question each both delivered.

## Guards, Shells, And Threads That Do Not Close

- **A guard that cannot halt is not a guard.** In shell, `exit 1` inside `$( )` leaves
  only the subshell: `cmd "$(validate ...)"` runs `cmd` with an empty string. A validator
  written that way was correct, called on every path, tested — and would have deployed
  `--set-env-vars ""`, wiping a service's environment. Assign and check:
  `V="$(validate ...)" || exit 1`. Assert the *halt*, with the positive control
  *test-driven-development.md* § *Assertions that pass for the wrong reason* requires.

- **An enumerated guard is the same shape as the bug it fixes.** A delimiter check taking
  a hand-written list of fields missed four, one appended forty lines later. Validate *as
  you assemble*, and assert the **structure** — a test enumerating the same names passes
  beside the defect.

- **One normalisation, shared.** "Is this allowlist open?" had three implementations and a
  docstring calling that one too many — then a fourth, a regex in a test, which rejected a
  value the runtime accepts, refusing what it existed to bless.

- **`sed FILE | grep -q PATTERN` under `pipefail` dies on a big enough file.** `grep -q`
  exits at its first match and closes the pipe; survival is a scheduling race, not a size
  rule and not GNU-versus-BSD. The signature is a bare `rc=141` with empty stderr — logs
  carry no "Broken pipe". Prefer one `awk` reading the file directly, and check under
  Linux (stash-compare first; some suites fail there on the baseline):

  ```bash
  docker run --rm -v "$PWD":/w -w /w bash:5 sh -c \
    'apk add --no-cache gawk grep sed coreutils python3 && bash "$1"' \
    _ operations/dev/tests/test_example.sh
  ```

  Strip comments before matching source, too — the prose explaining a guard otherwise
  satisfies the check for it.

- **The bot's own thread resolution often fails**, leaving a thread that reads as pending
  on you — fifteen times in one night. Filter to **bot-originated** threads first: an
  unfiltered list hands you human ids, and `required_review_thread_resolution` means
  closing one clears live feedback *and* makes the gate read satisfied.

  Reuse the enumeration query in § *Findings live on three surfaces* — adding `id` to its
  selection set and filtering on the **first** comment's author, since `last` is merely
  who spoke most recently — then `resolveReviewThread(input:{threadId:$t})` per id. A
  human thread stays open until its own author is satisfied.

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
