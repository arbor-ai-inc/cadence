# code-review

Adversarial review-and-resolve loop for a feature branch, before the PR is opened
or updated. Reviewer must be a context that did not write the code.

## Invocation

`/code-review <issue-id>` — run on the issue's branch with all work committed.
Also invoked automatically by the execute-issue skill (step 7).

## Reviewer selection

**The one rule: the reviewer must not be the agent that wrote the code.** Fresh
context, and preferably a different model or a different agent entirely. Every
option below exists to satisfy that; which one you pick is `[review].provider`
in `cadence.toml`.

| `[review].provider` | What runs | Works when driving with |
|---|---|---|
| `codex` | `codex exec`, piped the branch diff | anything with the Codex CLI |
| `claude` | `claude -p`, piped the branch diff | anything with the Claude CLI |
| `subagent` | the bundled `code-reviewer` subagent, fresh context | **Claude Code only** — it needs the Task tool |
| `coderabbit` | a PR-time bot; not a pre-PR pass | anything |
| `none` | nothing | — |

**Pick the one that is a different agent from the one implementing.** If Claude
Code is doing the work, `codex` is the stronger choice; if Codex is doing the
work, `claude` is. `subagent` is the fallback when only one agent is available —
still fresh context, but the same model, so it is the weakest of the three at
finding what that model missed the first time.

### Driving with Codex

`subagent` is unavailable: Codex has no Task tool, so it cannot invoke a Claude
subagent. Use `claude` instead — shelling out to the Claude CLI gets you the same
cross-agent review from the other direction.

The **spec pipeline** is a separate matter and does not have this escape hatch.
Its reviewers are subagents with deliberately restricted tools —
`Read, Grep, Glob, Write`, and no `Edit` — and that restriction is what stops a
reviewer editing the spec it is reviewing. Under an agent without subagents the
roles collapse into one context and that guarantee is gone. Run the spec
pipeline from Claude Code, or accept that the separation is by convention only
and say so.

### Passing the reviewer its inputs

Whichever provider runs, it must end up with the same three things: the branch
diff (`git diff main...HEAD`), the issue's acceptance criteria, and the reading
set named in [Architectural context to load](#architectural-context-to-load).

**The asymmetry to watch:** the `subagent` provider gets the reading set from its
own definition, while a CLI provider gets it **only from the prompt you
construct**. So naming those files is not optional for `codex` or `claude`. A
review run without them is a correctness review, not an architecture review —
say so in the findings rather than implying the boundary questions were checked.

## Architectural context to load

A diff plus its acceptance criteria is enough to judge whether code *works*. It
is not enough to judge whether the change sits on the right boundary — and a
wrong boundary is the expensive kind of finding, because it is cheap to fix
before merge and costly after. Both reviewers load the context for the code the
diff actually touches. Read the cell that fits, not the whole tree:

| Diff touches | Load |
| --- | --- |
| any code | `[paths].principles` § *How code review uses this doc* |
| code inside one architectural boundary | that boundary's own architecture doc |
| a payload, schema, or message crossing a boundary | whatever pins the shape (a schema file, or the doc holding it in prose), plus whatever check gates it |
| **a new, moved, or retired route / RPC / topic** | `[paths].principles` — decide first whether it crosses a boundary; if it does, your rubric should list the artifacts that must move with it |
| a component's internals | that component's own README reading-set |
| behaviour claimed as already built, or as deferred | the project's current-state doc — never its roadmap, which is planned, not built |

Two rules that make the difference:

- **Trace to the consumer.** When a diff writes data another plane reads, follow
  the value to its reader before accepting "the consumer side is a follow-up".
  A deferral that is *unimplemented* is fine; one where the existing consumer
  already runs and silently does the wrong thing is a BLOCKER.
- **A contract gate almost never covers producers.** A hash or schema check
  guards the *declaration*. A change to the code that **writes** that payload — a
  new key, a nested object where a scalar is declared — passes the gate
  untouched. Verify the written shape against the declared one by reading both.
- **Usually no gate covers a new boundary edge at all.** Nothing in a hook or CI
  notices that a route was mounted, so a cross-boundary endpoint reaches
  production documented only if a reviewer asks. Read the route registration in
  the diff — wherever this project mounts handlers — and ask who calls it. If the
  caller is on the far side of a boundary, apply your rubric's checklist. Expect
  this to be the architectural check with no automation behind it.

## Scope completeness

The checks above ask whether the code in the diff is right. These ask whether
the diff is **finished** — three ways a change can be individually correct and
still land a half-built capability. A reviewer is the last point where that is
cheap to notice.

**1. Does the change break an interface a contract already captures?**

Your hooks try to validate this, and it is worth knowing exactly how far each
one gets, because the gap is the reviewer's job. The usual shapes:

| Gate | What it actually proves |
| --- | --- |
| a golden-hash check over declared contracts | those files still hash to their goldens — i.e. **a declaration did not change unnoticed** |
| a committed schema dump | the dump matches the models |
| a generated-doc check | the doc matches the generated dump |
| a schema or vocabulary validator | committed definitions are *well-formed*, not that they are *compatible* |

Every one of these is a **drift detector, not a compatibility checker.** They
answer "did the declared artifact change without anyone acknowledging it?" —
never "is the change safe for the consumer?" Refreshing a golden hash on a
breaking change turns the gate green. So the reviewer owns the questions no hook
asks:

- **Is a declared field removed, renamed, narrowed, or made required?** Any of
  these breaks a consumer that still runs. Find the consumer before accepting it —
  and across languages, since producer and consumer are often written in different
  ones and no single type checker sees both.
- **Did the code drift from the declaration without touching the file?** A hash
  gate watches the declaration; it cannot see a producer writing a new key, or a
  nested object where a scalar is declared. Read the writing code against the
  declared shape.
- **Is a golden refresh in this diff acknowledging a change nobody analysed?** A
  refreshed hash is a signature, not a review. If a gated file moved, the diff
  should say what changed and why it is compatible.
- **Is a new boundary-crossing interface missing from the contract set entirely?**
  Then no gate covers it at all — nothing will detect the *next* change to it.
  Ask whether it needs an entry naming producer and consumer, and whether that
  entry joins the gated set.

**2. Can the customer measure what this does?** (principle #15)

If the change adds a customer-affecting outcome — a new way to spend, serve,
fail, or convert — follow it to the reporting path and ask what an advertiser or
publisher would see. Two distinct outcomes:

- **A wrong number is a BLOCKER.** A new outcome silently merged into an
  existing count, so the customer cannot distinguish the two, misreports
  something they are billed against or judged on. The canonical case: a creative
  that serves a degraded fallback instead of the real unit must be a
  *distinguishable* count, not just another impression (T-01).
- **A missing number is a SHOULD.** Behavior that nothing records at all — no
  event type, no rollup dimension, no field on the read API — cannot be
  confirmed to work later. Name the metric that is absent.
- **An ambiguous signal is worse than a missing one, and this applies to
  operator signals too.** A counter or log line covering two distinct failures
  cannot be acted on, and reads as precise while being useless. Under T-02 a
  rejected *impression* that happened to carry an `interaction_detail`
  incremented the interaction counter and logged "REJECTED interaction event" —
  so a billable impression loss was filed under the signal that exists to make
  interaction loss visible, and neither number meant anything afterwards. One
  signal, one meaning: if a counter can be reached by two conditions, ask which
  one the operator is meant to conclude.

Check the actual chain, not intent: `event-schema.yaml` event types → the
`serving_events` payload → the `reporting_daily_rollup` dimensions → the read
API. A dimension added at one layer and missing at the next is the common defect.

**3. Can the customer reach it?** (principle #14)

A capability that exists only behind an API, with no console surface, is
invisible to the person it was built for. a browser-facing package is where advertiser-facing
functionality becomes real; the config-history work shipped its endpoint and its
UI affordance together (T-03 T4) rather than leaving the endpoint stranded.

**How to raise all three.** Name the specific gap — the contract entry, the
metric, the surface — and say what would close it. The resolution is the
author's: pull it into this PR, or file a tracked follow-up. Both are fine
answers; *silence* is what this check exists to prevent. Do not convert a
focused PR into a platform change, and do not require UI on a deliberately
backend-only slice whose issue says so — an explicitly deferred surface with an
issue behind it is complete, not incomplete.

## A claim the diff asserts is not evidence

A diff frequently makes claims about code *outside* itself — "nothing consumes
this endpoint", "no caller depends on that field", "this is the only writer".
Those claims are the author's premise, and a reviewer handed a premise
**confirms** it rather than testing it. Confirming is not reviewing.

**This is the most-ruled trap in the ledger and the one that keeps recurring** —
`unverified-artifact-claim`, n=24 across two batches. Everything below is one rule
stated once, per surface the claim arrives on, because seven separate prose bullets
in four documents is what a rule that does not fire looks like.

- **Falsify, do not corroborate.** Ask what would have to exist for the claim to
  be false, then look for *that*. T-01's false negative survived three review
  rounds because each round re-ran the author's own search.
- **A negative needs a search for every name the thing is known by.** One grep
  proving absence proves absence *of that identifier*. T-01 reported "no page
  consumes the reporting API" after grepping a browser-facing package for
  `reportingDaily|ReportingDailyRollup`; the campaign detail page imports
  `reportingApi` and has rendered impressions, clicks, CTR and spend since T-04.
  List the names the thing travels under — the typed client export, the route
  string, the table, the model, the feature's own vocabulary — and search each.
  **A wrong negative propagates further than a wrong positive**: that one reached
  `the project's current-state doc`, `the project's capability-status doc` (where it replaced a line that
  was correct), the PR body, the Linear issue, and a follow-up ticket's whole
  premise, before anyone re-read the page it was about.
- **A count or an enumeration in the diff, the issue, or a comment is a lower bound
  until it is recomputed.** Grep the field or identifier and read every value, not
  the quoted string: T-05's "one forbidden summary" was seven, T-06's "10
  occurrences" was two, T-07's "eight filter keys" was nine. `grep -c` counts
  lines where the claim says occurrences. The author-side rule is
  [`execute-issue.md`](./execute-issue.md) § *Procedure* step 4.
- **A fix to a script carries the claim "this script runs." Check it.** T-08's
  first round hardened two deploy scripts alone. Those scripts referenced a secret
  under a name no environment actually used — which was itself the evidence they
  were not the path that runs — while the script that *is* never mentioned that
  secret at all. Round 2 wired it there, and **the PR as merged fixed all three**,
  so the tree no longer shows the defect and grepping for it finds nothing.
  A fix in a script nothing executes reads exactly like a fix, passes review, and
  closes the ticket. Trace the caller — CI workflow, runbook step, `make` target.
  Step 4's revert check finds this too: reverting a dead script changes nothing.
- **A command written into a doc makes the same claim, and nothing gates it at all.**
  T-09 added a runbook whose smoke test could not work: `gcloud logging write`
  defaults to `resource.type="global"`, so the synthetic entry missed the very filter
  it existed to prove and would have read as a passing test while the metric stayed
  at zero. All 18 pre-commit hooks passed it — no hook checks CLI syntax in Markdown.
  **`--help` is necessary and not sufficient**: it would have passed that very
  command, because every flag was valid and the wrong thing was the *default*. Run
  the command in the environment the doc names and check the observable it promises;
  where that is unsafe or impossible, list it in the PR as unverified and say why.
- **A module citing a decision claims that decision is enforced.** Trace the
  *guard's* callers, not the caller of an edited file. `content_scan.py` cited
  **D-U — reject where the author is** — as its whole reason for existing, and every
  call site was a **read**. A `<script>` could be stored and was refused only when
  someone tried to look at it (T-10), the opposite of what the citation says.
- **A guessed identifier asserts a traceability that does not exist.** T-11 put
  `T-12` and `T-13` into two source comments; Linear assigned `T-14` and
  `T-15`. File first and read back the assigned id — one tool call.
- **"Mechanical", "formatting-only" and "no behaviour change" are claims about the
  diff itself, and they arrive attached to the diffs nobody reads line by line.**
  Do not skim and do not trust the summary — **parse every changed file before and
  after and compare the ASTs**, recording the parser and version and reporting any
  file the parser rejected rather than dropping it. Three preconditions decide
  whether the numbers mean anything:
  - **Compare per commit, with the mechanical change isolated in its own commit.**
    #618's formatter commit alone was 35 files, 33 AST-identical, 0 structural. The
    same PR *as squash-merged* reports 7 of 36 structurally different, because a
    sibling `fix:` commit removed dead imports in the same squash — and the merged
    commit is the obvious thing to reach for.
  - **Equal ASTs are necessary, not sufficient.** Python's `ast` discards comments,
    so deleting a `# noqa`, `# type: ignore` or `# fmt: off` leaves it identical
    while changing what the tooling does — those 35 files carry 48 `# noqa` across
    13 files, several the `# noqa: E402` that `sys.path`-manipulating test modules
    depend on. Pair the AST check with the linter, which does see comments, and with
    the suite; report all three.
  - **A green `pre-commit run --all-files` is not proof the linter looked.** The ruff
    hooks are scoped by the `&python_roots` allowlist, so a green run says nothing
    about a file outside it (nine remain today, T-16). `pre-commit run <hook>
    --files <paths>` renders `Skipped` and `Passed` differently; the aggregate run
    reports "passed" and "never looked" identically, and it is the one people cite.

  Expect the claim to be *wrong about its own size*: T-17 predicted the fallout
  would be "small — the code is `ruff format`-shaped already", and 35 of 51 files moved.

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
- **A claim the diff makes about code outside the diff is a finding to test, not
  a fact to accept** — see § *A claim the diff asserts is not evidence*. Verifying
  it by repeating the author's search is confirmation, and reads in the output
  exactly like verification.
- **Point the reviewer at the diff's assertive prose by name, in the prompt** — not a
  doc bullet. The prompt is what decides what a fresh-context reviewer looks at, and it
  is the one variable measured to change the outcome: a reviewer told to treat every
  *every / all / nothing can / the only* as a finding to test produced two extra
  defects, while the same reviewer aimed only at claims about *code* missed an
  equivalent claim about *policy*. So the prompt says **code, policy, and what another
  component does**. This trap is n=7 in one batch with the rule already written down
  twice; the prompt is where it fires. Two corollaries worth stating to the reviewer:
  - **Read every AND in a criterion as one test per conjunct, and check the count.**
    Three conjuncts need three tests, not two. A conjunction with one conjunct
    asserted reads exactly like the whole criterion. Six of one
    ticket's seven findings were a criterion **partly** asserted, never one asserted
    wrongly.
  - **A false claim is rarely in one place.** Sweep its distinctive phrase, not the
    reported line — one author swept app-wide and found five the reviewer had not.

  The author-side statement of the same rule is `test-driven-development.md` § *A
  comment that states a property is a test you have not written yet*.
- Cite a principle only when its **Check** question genuinely fails. A principle
  number attached to a finding that would stand without it is noise, and grading
  a diff against all 26 is how the review becomes ignorable.
- First line of output must be `LGTM` or `FINDINGS`. Reviewers never rewrite code.

## Loop

1. `the project's `[commands].lint``
   and tests must be green BEFORE the first review round. The PATH prefix is not
   optional: `db-schema-dump` shells to `python3` and needs the API venv's deps.
2. Run the reviewer. If `LGTM` → done.
3. Resolve every BLOCKER and SHOULD in the implementing context. NITs are judgment.
   If a finding requires a product decision, put it as a Shape A decision brief
   (`human-brief`, `human-brief.md`): `AskUserQuestion`
   where the harness offers it, otherwise the identical table as text via
   `tools/ask.py ask "<question>" --context "<issue-id> review"`.
   Codex has no picker; the text table is the defined path there, not a degraded one.
   Then mirror question + answer into the Linear issue.

   **A lint finding is a claim about *this repo's* config — check it before obeying.**
   Nothing here sets `select`, `extend-select`, or a rule flag on the hook's command
   line, so only ruff's default rules run. An automated reviewer asserted RUF001 and
   RUF012 violations on T-18; neither rule is enabled, `ruff check` passes, and
   **two of its four findings did not apply**. Resolving a finding no gate can produce
   edits code to satisfy a linter that was never going to run.

   Check all three rule sources — `[tool.ruff]` in every `pyproject.toml`/`ruff.toml`,
   not just the one nearest the file; then run the hook itself
   (`pre-commit run ruff --all-files`), which is the only answer that accounts for all
   of them. The same applies to a claim about any *other* tool's behaviour: run it.
   A reviewer on this very change asserted that `gh api repos/:owner/:repo` was invalid
   syntax needing `{owner}/{repo}` — one command disproved it.

   **A correct diagnosis can carry a wrong prescription — verify the fix separately.**
   The rule above catches a finding that is false. This catches one that is *true* and
   whose remedy is still wrong, which is harder to spot because the reasoning checks out.
   Both of #473's substantive findings were like this. Its major one — an unauthenticated
   `PATCH` can replace a live `pub_key` — was accurate, but the prescribed fix (strip
   `pub_key` from `body.model_dump()`) would have made the console's blank-key repair
   return `200` while changing nothing, silently. Its migration finding cited a real
   principle, but `s3a4b5c6d7e8` already did strictly heavier work on the same table in
   one transaction, and no migration in the repo uses `NOT VALID`. Both were withdrawn
   once answered with that evidence. Before applying a prescription, ask what in this
   repo it would break and whether repo precedent already settles it — then reply with
   what you checked, rather than either obeying or ignoring it.
   **A false claim is rarely in one place — sweep before calling it resolved.** When a
   finding is "this comment asserts something untrue", the same sentence has usually been
   copied into the docstring, the field comment, the architecture doc and the test that
   covers it. Fixing the instance the reviewer cited feels like fixing the claim and is
   not. On T-19 a retracted claim was removed from three places and left standing, in
   its strongest form, in the docstring of the test it was about — where the next round
   found it. On T-20 a "not emitted yet" statement was corrected in one file while five
   others, including both plane boundary tables, still asserted the opposite; three more
   sat in the file already edited. **Grep the claim's most distinctive phrase across the
   repo, fix every hit, and re-grep.** The phrase, not the ticket id — the copies rarely
   carry the id.

4. **Verify each resolution against the failure it claims to close.** For every
   BLOCKER and SHOULD you fixed **that changes executable behavior**, revert that
   fix — one at a time, `git stash` or a hand edit — run the tests, and confirm at
   least one **fails naming the behavior the finding was about**. Then restore it.
   If nothing fails, the resolution is unverified: add the assertion before
   re-review, not after. A test that was already green before the fix does not
   count.

   For a resolution with no executable behavior — a doc, a comment, a config
   value, a spec — the equivalent is the **deterministic check that covers that
   artifact**: the pre-commit hook, the contract gate, the link check, the schema
   dump. Revert and run *that*. Where genuinely nothing covers the artifact, say
   so in the round's notes and treat the gap as its own finding — an uncovered
   artifact is how a doc drifts into asserting something false. Do not invent a
   test to satisfy this step.

   This is not optional and it is not the same as step 1. Step 1 proves the suite
   passes; this proves the suite would notice if the fix went away. On T-02 and
   T-01 *most* round-N findings were defects introduced by the round-(N−1) fix,
   and this check is what caught them. `test-driven-development.md`
   § *Mutation-test any change that adds a rule* has the shapes that survive
   deletion — read it rather than re-deriving them, and treat any output that is
   not an explicit pass-or-fail as a broken harness, never as a survival.
5. Re-run pre-commit and tests, commit the resolutions, re-run the reviewer.
6. Circuit breaker: max 3 rounds. If not LGTM after round 3, post the open findings
   to Slack via `ask` as a Shape B change brief and stop — do not loop forever, do
   not open the PR silently.
7. On LGTM, write the Shape B change brief (`human-brief`,
   `human-brief.md`) and print it. This loop otherwise
   leaves a human nothing durable: there is no round file for code review, so the
   findings and their resolutions exist only in a transcript nobody re-reads. The
   brief is what the author reads instead, and it carries over as the PR body summary.
   Its *where the reviewer and I disagreed* section is required whenever the loop ran,
   and "every finding was accepted as written" is a complete answer — a review can be
   fully adversarial and produce no disagreement, because the findings were right. The
   section exists so that acceptance is visible rather than silent. Where you did push
   back, say what you checked and what it showed, per § *A correct diagnosis can carry a
   wrong prescription*.

## Hard rules

- The reviewer sees the diff, not the implementation conversation.
- Findings are resolved by fixing code, never by arguing with the reviewer in text.
- A round that changes code always re-runs pre-commit and tests before re-review.
- **A resolution nothing asserts is a resolution that can be silently reverted.**
  A counter, a log line, or a guard added to close a finding needs its own
  assertion, or the fix regresses without a red test. Both counters added under
  T-02 were unobservable — every test handler left `Metrics` nil — and the
  reconciliation guard's new measures under T-01 were asserted by nothing, in
  code whose own comment warned about exactly that.
