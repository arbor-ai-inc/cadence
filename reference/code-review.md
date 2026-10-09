# code-review

Adversarial review-and-resolve loop for a feature branch, before the PR is opened
or updated. Reviewer must be a context that did not write the code.

## Invocation

`/code-review <issue-id>` — run on the issue's branch with all work committed.
Also invoked automatically by the execute-issue skill (step 7).

## Reviewer selection

**The one rule: the reviewer must not be the agent that wrote the code.** Fresh
context, preferably a different model or agent. `[review].provider` in
`cadence.toml` picks it:

| `[review].provider` | What runs | Works when driving with |
|---|---|---|
| `codex` | `codex exec`, piped the branch diff | anything with the Codex CLI |
| `claude` | `claude -p`, piped the branch diff | anything with the Claude CLI |
| `subagent` | the bundled `code-reviewer` subagent, fresh context | **Claude Code only** — it needs the Task tool |
| `coderabbit` | a PR-time bot; not a pre-PR pass | anything |
| `none` | nothing | — |

**Pick a different agent from the one implementing:** Claude Code → `codex`; Codex →
`claude`. `subagent` is the fallback when only one agent is available — same model, so
the weakest at finding what that model missed.

### Driving with Codex

`subagent` is unavailable (Codex has no Task tool); use `claude`.

The **spec pipeline** has no such escape hatch: its reviewer subagents are limited to
`Read, Grep, Glob, Write` — no `Edit` — so they cannot edit the spec they review.
Without subagents that guarantee is gone; run it from Claude Code, or say the
separation is by convention only.

### Passing the reviewer its inputs

Every provider gets the branch diff (`git diff main...HEAD`), the issue's acceptance
criteria, and the reading set in
[Architectural context to load](#architectural-context-to-load). `subagent` gets the
reading set from its definition; a CLI provider gets it **only from the prompt you
construct**, so naming those files is not optional for `codex` or `claude`. A review
without them is a correctness review, not an architecture review — say so in the
findings.

## Architectural context to load

A diff shows whether code *works*, not whether it sits on the right boundary — cheap
to fix before merge, costly after. Load the cell that fits, not the whole tree:

| Diff touches | Load |
| --- | --- |
| any code | `[paths].principles` § *How code review uses this doc* |
| code inside one architectural boundary | that boundary's own architecture doc |
| a payload, schema, or message crossing a boundary | whatever pins the shape (a schema file, or the doc holding it in prose), plus whatever check gates it |
| **a new, moved, or retired route / RPC / topic** | `[paths].principles` — decide first whether it crosses a boundary; if it does, your rubric should list the artifacts that must move with it |
| a component's internals | that component's own README reading-set |
| behaviour claimed as already built, or as deferred | the project's current-state doc — never its roadmap, which is planned, not built |

- **Trace to the consumer.** When a diff writes data another plane reads, follow it
  to its reader before accepting "the consumer side is a follow-up". An
  *unimplemented* deferral is fine; an existing consumer that silently does the wrong
  thing is a BLOCKER.
- **A contract gate almost never covers producers.** A hash or schema check guards
  the *declaration*; a change to the code that **writes** the payload — a new key, a
  nested object where a scalar is declared — passes it untouched. Read the written
  shape against the declared one.
- **Usually no gate covers a new boundary edge.** Read the route registration in the
  diff and ask who calls it; if the caller is across a boundary, apply your rubric's
  checklist.

## Scope completeness

Three ways a correct change still lands a half-built capability. The reviewer is the
last cheap point to notice.

**1. Does the change break an interface a contract already captures?** Typical gates
prove less than they seem: a golden-hash check proves **a declaration did not change
unnoticed**; a schema dump, that it matches the models; a generated-doc check, that the
doc matches the dump; a schema or vocabulary validator, that definitions are
*well-formed*, not *compatible*. Each is a **drift detector, not a compatibility
checker** — refreshing a golden hash on a breaking change turns it green. The reviewer
owns:

- **Is a declared field removed, renamed, narrowed, or made required?** Find the
  running consumer before accepting it — across languages; no one type checker sees
  both sides.
- **Did the code drift from the declaration without touching the file?** See *A
  contract gate almost never covers producers* above.
- **Is a golden refresh acknowledging a change nobody analysed?** A refreshed hash is
  a signature, not a review; the diff should say what changed and why it is compatible.
- **Is a new boundary-crossing interface missing from the contract set?** Then nothing
  detects its *next* change. Ask whether it needs an entry naming producer and
  consumer, and whether that entry joins the gated set.

**2. Can the customer measure what this does?** (principle #15) For a new way to
spend, serve, fail, or convert, follow it to the reporting path and ask what an
advertiser or publisher would see:

- **A wrong number is a BLOCKER** — a new outcome merged into an existing count, e.g. a
  degraded-fallback serve not *distinguishable* from an impression (T-01).
- **A missing number is a SHOULD** — no event type, rollup dimension, or read-API
  field. Name the absent metric.
- **An ambiguous signal is worse than a missing one, operator signals included.** One
  signal, one meaning: if a counter can be reached by two conditions, ask which one the
  operator is meant to conclude (T-02).

Check the actual chain: `event-schema.yaml` event types → the `serving_events` payload
→ the `reporting_daily_rollup` dimensions → the read API. A dimension added at one
layer and missing at the next is the common defect.

**3. Can the customer reach it?** (principle #14) A capability only behind an API, with
no console surface, is invisible to its user; ship endpoint and UI affordance together
(T-03).

**Raising them.** Name the gap and what would close it; the author pulls it in or
files a tracked follow-up — *silence* is the failure. Do not turn a focused PR into a
platform change, or require UI on a backend-only slice whose issue says so: a deferred
surface with an issue behind it is complete.

## A claim the diff asserts is not evidence

"Nothing consumes this endpoint", "no caller depends on that field", "the only
writer" — claims about code *outside* the diff are the author's premise, and a
reviewer handed a premise **confirms** it. Confirming is not reviewing. The
most-recurring trap in the ledger (`unverified-artifact-claim`, C-11), per surface:

- **Falsify, do not corroborate.** Look for what would make the claim false (T-01:
  three rounds re-ran the author's search).
- **A negative needs a search for every name the thing is known by** — typed client
  export, route string, table, model, feature vocabulary. **A wrong negative
  propagates further than a wrong positive** (T-01).
- **A count or enumeration is a lower bound until recomputed** (T-05, T-06, T-07) —
  see [`execute-issue.md`](./execute-issue.md) § *Procedure* step 4.
- **A script fix claims "this script runs."** A fix in a script nothing executes reads
  exactly like a fix (T-08). Trace the caller — CI workflow, runbook step, `make`
  target; step 4's revert check also catches it.
- **A docs-only diff is all claims about code outside it, nearly ungated** (T-29,
  T-30). **A spec sentence quoted into a doc is a premise** — recompute it. **A contract
  gate proves a declaration changed**, not that it matches the types it describes.
- **A command in a doc makes the same claim, ungated.** **`--help` is necessary, not
  sufficient** — a wrong *default* passes it (T-09). Run it in the environment the doc
  names and check the promised observable; if unsafe or impossible, list it in the PR
  as unverified and say why.
- **A module citing a decision claims it is enforced.** Trace the *guard's* callers,
  not the edited file's (T-10).
- **A guessed identifier asserts false traceability.** File first, read back the
  assigned id (T-11).
- **"Mechanical", "formatting-only", "no behaviour change" are claims about the diff
  itself.** Do not skim: **parse every changed file before and
  after and compare the ASTs**, recording parser and version and reporting files the
  parser rejected. Preconditions:
  - **Compare per commit, with the mechanical change isolated in its own commit** — a
    squash mixes in sibling fixes.
  - **Equal ASTs are necessary, not sufficient**: Python's `ast` drops comments, so a
    deleted `# noqa`, `# type: ignore` or `# fmt: off` is invisible. Pair it with the
    linter and the suite; report all three.
  - **A green `pre-commit run --all-files` is not proof the linter looked** — hooks
    scoped by an allowlist (e.g. `&python_roots`) skip other files (T-16).
    `pre-commit run <hook> --files <paths>` distinguishes `Skipped` from `Passed`; the
    aggregate does not.

  Expect the claim to be *wrong about its own size* (T-17).

## Review contract (both reviewers)

- Input: the diff, the issue body, acceptance criteria, repo conventions, and
  the architectural context above.
- Output: numbered findings, each tagged BLOCKER / SHOULD / NIT, with file:line.
- BLOCKER also covers: a payload shape that diverges from its declared contract;
  a discriminator, enum, or invariant placed outside the typed boundary its
  consumer dispatches on; an unversioned change to a persisted shape with no
  migration path; **a cross-plane endpoint whose plane graph, edge list, plane
  boundary tables, or component route table were not updated in the same diff**.
  Cite the principle whose **Check** question fails.
- **A claim about code outside the diff is a finding to test, not a fact** — see §
  *A claim the diff asserts is not evidence*.
- **Name the diff's assertive prose in the reviewer's prompt**, not a doc bullet — the
  prompt is the variable measured to change what a fresh reviewer finds. Tell it to
  test every *every / all / nothing can / the only* about **code, policy, and what
  another component does**, and:
  - **Read every AND in a criterion as one test per conjunct, and check the count.** A
    criterion **partly** asserted reads exactly like the whole one.
  - **A false claim is rarely in one place** — see § *Loop* step 3.

  Author-side: `test-driven-development.md` § *A comment that states a property is a
  test you have not written yet*.
- Cite a principle only when its **Check** question genuinely fails; grading a diff
  against all 26 makes the review ignorable.
- **A test for a P0 row in the spec's `testing-plan.md` must be able to fail.** No
  break-it result (the break; the failing line, on that row's assertion) and no
  *not audited* is a SHOULD; still passing after the break is a BLOCKER.
- First line of output must be `LGTM` or `FINDINGS`. Reviewers never rewrite code.

## Loop

1. `[commands].lint` and `[commands].test` must be green BEFORE the first review
   round. Run them exactly as configured; the config carries any environment they need.
2. Run the reviewer. If `LGTM` → done.
3. Resolve every BLOCKER and SHOULD in the implementing context. NITs are judgment.
   A product decision goes as a Shape A decision brief (`human-brief.md`):
   `AskUserQuestion` where offered, else the identical table as text via
   `tools/ask.py ask "<question>" --context "<issue-id> review"` (Codex's defined
   path, not a degraded one). Mirror question + answer into the Linear issue.

   **A lint finding is a claim about *this repo's* config — check it before obeying.**
   Nothing here sets `select`, `extend-select`, or a rule flag on the hook's command
   line, so only ruff's default rules run (T-18). Check `[tool.ruff]` in every
   `pyproject.toml`/`ruff.toml`, then run the hook itself
   (`pre-commit run ruff --all-files`) — the only answer covering every source. A claim
   about any *other* tool's behaviour: run it.

   **A correct diagnosis can carry a wrong prescription — verify the fix separately.**
   Before applying a prescription, ask what in this repo it would break and whether
   repo precedent already settles it; reply with what you checked, rather than obeying
   or ignoring it.

   **A false claim is rarely in one place — sweep before calling it resolved.** Copies
   sit in the docstring, field comment, architecture doc and covering test (T-19,
   T-20). **Grep the claim's most distinctive phrase across the repo, fix every hit,
   and re-grep** — the phrase, not the ticket id, which copies rarely carry.
   **Then sweep the dimension, not only the phrase:** ask which other value, mode,
   environment or sibling the same sentence was true of, and grep for those, including
   retired phrasings (T-31, T-32, T-33).

4. **Verify each resolution against the failure it claims to close.** For every
   BLOCKER and SHOULD fix **that changes executable behavior**, revert it — one at a
   time, `git stash` or a hand edit — run the tests, and confirm at least one **fails
   naming the behavior the finding was about**; then restore. If nothing fails, add the
   assertion before re-review. A test already green before the fix does not count.

   For a doc, comment, config value or spec, revert and run the **deterministic check
   that covers it** (hook, contract gate, link check, schema dump); where nothing does,
   say so in the round's notes and treat the gap as its own finding. Do not invent a
   test for this step.

   Not optional, and not step 1: this proves the suite would notice the fix going away
   — most round-N findings were introduced by the round-(N−1) fix (T-01, T-02). See
   `test-driven-development.md` § *Mutation-test any change that adds a rule*; output
   that is not an explicit pass-or-fail is a broken harness, never a survival.
5. Re-run pre-commit and tests, commit the resolutions, re-run the reviewer.
6. Circuit breaker: max 3 rounds. If not LGTM after round 3, post the open findings
   to Slack via `ask` as a Shape B change brief and stop. **Stop means stop:** no
   fourth round and no "one last fix" on the way out — a round-N finding is often a
   defect the round-(N−1) fix introduced (C-15). A commit after the last review is
   **named in the brief and PR body** with what it changed; never call that head LGTM.
7. On LGTM, write and print the Shape B change brief (`human-brief.md`) — the only
   durable record, and the PR body summary. Its *where the reviewer and I disagreed*
   section is required whenever the loop ran ("every finding was accepted as written"
   is a complete answer); where you pushed back, say what you checked and what it
   showed, per § *A correct diagnosis can carry a wrong prescription*.

## Hard rules

- The reviewer sees the diff, not the implementation conversation.
- Findings are resolved by fixing code, never by arguing with the reviewer in text.
- A round that changes code always re-runs pre-commit and tests before re-review.
- **A resolution nothing asserts can be silently reverted.** A counter, log line, or
  guard added to close a finding needs its own assertion (T-01, T-02).
