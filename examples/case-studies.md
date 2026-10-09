# Case studies

The rules in `reference/` exist because something went wrong. Where a rule cites
evidence, it cites a case id from this file rather than asserting that the rule
is sensible — a rule with a measurement behind it can be argued with, and one
without cannot.

These are real measurements from the production codebase cadence was extracted
from, over roughly forty tickets. The issues and pull requests have been
renumbered; nothing else has been softened. Where a number looked bad for the
system that produced it, it is still here.

## Two kinds of reference

**`C-NN` — a case in this file.** A rule that cites one is pointing at the
measurement below.

**`T-NN` — an anonymized ticket**, cited inline in `reference/` where a rule
needs to name *which* incident without needing a whole case study. The mapping to
real issue ids is not published.

They are numbered separately and both are stable. The distinction that matters
when reading: two different `T-NN` in one paragraph are **two different
incidents**, and the same one repeated is one incident cited twice. That is
load-bearing — "three separate tickets hit this" is a stronger claim than "one
ticket hit it three times", and collapsing them to a generic "one ticket" would
have quietly turned the first into the second.

## How to read a case

Each case is one observation, not one ticket: a single ticket often hit three
traps and is evidence for all three. The `trap` slug is what the retro loop
clusters on, and the counts in [`templates/TRAPS.md`](../templates/TRAPS.md) are
cumulative across batches — which is the point, since no single batch can see
that a trap has now happened nine times.

---

## The argument for batching

These five cases are why capture and synthesis are separate steps rather than
one retro per ticket. They are the measurement behind
[`reference/retro.md`](../reference/retro.md) § *Why it is split*.

### C-01 — the baseline
Twelve consecutive retros over five weeks, each written as its own pull request
immediately after the ticket that produced it. Net effect on guidance: **+687
/ −18 lines.** Almost purely additive.

### C-02 — the cost of a rule from one ticket
One of those retros took **16 commits and 12 review comments to land a 102-line
documentation diff.** The reviewer was arguing a generalization back down: the
lesson had been written from a single occurrence and stated as universal.

### C-03 — the rule that would not have caught its own bug
Another retro's commit trailers record dropping a false claim during review. The
reviewer's objection is the one worth keeping: **the rule as written would not
have caught the bug that produced it.** Writing from n=1 does not just
over-generalize, it can produce a rule that is inert against its own origin.

### C-04 — monotonic accretion
Over ten weeks, two guidance documents roughly tripled: 179 → 578 lines, and
95 → 334 lines. **A rule nobody finishes reading does not fire**, so appending
forever defeats the purpose of appending at all.

### C-05 — the cost caused skipping
Because each retro was a whole pull request, it ran on roughly **one issue in
four**. The lessons that landed were not the important ones; they were a biased
sample of whoever had patience that day.

### C-06 — frequency is only visible across tickets
Clustering C-01's twelve retros by trap showed what the per-ticket loop
structurally could not: **seven of the twelve hit the same trap** — an artifact
asserting something that was accepted instead of checked — and it had been
answered as **seven separate prose bullets in four different documents.** Nobody
had compared them, because nothing ever put them side by side.

---

## The argument for a ledger in the repository

### C-08 — the out-of-repo lesson file
An earlier attempt accumulated lessons in a session file outside version
control. Across one 19-task epic no retro was ever run and the file reached
**1,397 lines** — unreviewable, unshareable, and lost on a fresh clone. About
526 of those lines were per-task retrospectives that each belonged in a
permanent home, and **evacuating them afterwards took four pull requests.**

This is an argument about the *site*, not the batching. Any ledger outside the
repository repeats it: a tracker comment or a scratch file cannot be grepped by
the agents that have to obey the rules drawn from it, cannot be diffed, and
cannot be reviewed.

---

## The argument for mechanizing over rewording

### C-09 — a reviewer that reports success without running
`trap: automation-silently-paused`. An automated reviewer renders a **passing
check row** for a review that never happened. Four separate signals produce it:
a rate-limited review, a skipped review, and a *stale* completed review all
bucket to `pass`; the bot's acknowledgement is edited in place from "review
triggered" to "action not completed" within seconds; every thread reply files a
body-less comment so the newest review is usually not the verdict; and the
stated quota refill is org-wide and can move backwards, so any derived one is
wrong by construction.

Seen **nine times** across nineteen tickets, with 380 lines of prose telling
agents how to read it by hand. It was mechanized on the ninth. This is the
canonical case for the rule in
[`reference/retro-synthesis.md`](../reference/retro-synthesis.md) § *Workflow*
step 4: a trap already `ruled` that recurs anyway is a **mechanization**
candidate, not a rewording one.

### C-10 — suites nobody runs
`trap: suite-not-wired-to-ci`. A test suite trusted as a gate that no CI job
runs. **An unrun suite and a passing suite look identical from the outside.**

Mechanizing it found **seven** unwired suites, and how they partition is the
argument for a check over another bullet: **one** was already known to a retro
fragment, **two** the check caught on its first run, and **four** surfaced only
after review noticed the discovery step could not see modules in one language or
standalone shell scripts at all. The last four are also the argument for
mutation-testing the check itself — the check was wrong in a way that looked
like success.

### C-11 — one slug over three traps
The umbrella trap from C-06 reached **n=24 while already `ruled` seven times in
four documents.** Step 4 reads that as a mechanize signal; step 2 reads it as one
slug stretched over more than one trap. Both were true. Splitting it into three
children is what made any of it writable, because *"verify assertions"* is not
actionable while *"an instance count in a ticket is a lower bound, never a set"*
is.

### C-15 — the trap that recurred inside its own fix
`trap: renumber-breaks-references`. Renaming a section broke a pointer to it —
**from the very check that same batch had just added.** Cheap to mechanize, and
still at n=2 at the time, so under the count rule it earned nothing. It is here
because the count rule held against a case that felt obvious, which is the only
kind of test that rule ever gets.

---

## The argument for verifying an issue's own claims

These are why [`reference/execute-issue.md`](../reference/execute-issue.md)
step 4 treats an issue's factual claims as premises rather than findings.

### C-13 — a guard built to a stale enum
An issue named the members of a set; the guard was built to that list and was
wrong, because a sibling change renamed a member between filing and execution.
`trap: issue-premise-stale`.

### C-14 — an absence audit over the wrong thing
A check encoded **the syntactic form the author happened to delete** rather than
the property being asserted. It passes on every other spelling of the same
mistake, so it fails as a silent **false negative** — the worst shape a guard
can take. Seen three times.
`trap: rule-over-one-syntactic-form`, `trap: guard-cannot-fire`.

---

## The argument for treating a timeout as unanswered

### C-12 — the question nobody saw
An agent posted a blocking question to a chat channel and waited. The post
succeeded; **no human ever saw it**, and the ask tool cannot tell a quiet
channel from a slow one. The run simply waited out its timeout.

Two rules come from this. A timeout is **unanswered**, never an answer and never
grounds to self-answer. And a whole ticket passing with no reply is a **delivery
defect to file**, not a condition to work around each run — working around it is
how it stayed broken.

### C-07 — the PR body that was silently discarded
A headless run opened a pull request whose carefully written body was rebuilt
from commit messages instead, because the convenience flag that fills a body
from commits was used alongside one that supplied it. The brief was simply gone,
and nothing reported an error. This is why
[`reference/git-pr-workflow.md`](../reference/git-pr-workflow.md) requires both
an explicit title and an explicit body file, and forbids the fill flag.

---

## Cases cited from the workflow docs

The full write-ups behind the one-line citations in
[`reference/code-review.md`](../reference/code-review.md),
[`reference/code-review-and-quality.md`](../reference/code-review-and-quality.md),
[`reference/test-driven-development.md`](../reference/test-driven-development.md) and
[`reference/execute-issue.md`](../reference/execute-issue.md). The docs keep the rule
and the id; the wording and numbers live here. Cases with no ticket id are headed by
the doc that cites them.

### T-01 — the reporting false negative, and the fixes nobody asserted
- *Scope completeness.* The canonical wrong-number case: a creative that serves a
  degraded fallback instead of the real unit must be a *distinguishable* count, not
  just another impression.
- *Falsify, do not corroborate.* T-01's false negative survived three review rounds
  because each round re-ran the author's own search.
- *A negative needs every name.* T-01 reported "no page consumes the reporting API"
  after grepping a browser-facing package for `reportingDaily|ReportingDailyRollup`;
  the campaign detail page imports `reportingApi` and has rendered impressions,
  clicks, CTR and spend since T-04. That wrong negative reached the project's
  current-state doc, the project's capability-status doc (where it replaced a line
  that was correct), the PR body, the Linear issue, and a follow-up ticket's whole
  premise, before anyone re-read the page it was about.
- *Loop step 4.* On T-02 and T-01 *most* round-N findings were defects introduced by
  the round-(N−1) fix, and the revert check is what caught them.
- *Hard rules.* The reconciliation guard's new measures under T-01 were asserted by
  nothing, in code whose own comment warned about exactly that.

### T-02 — one counter, two meanings
- *Scope completeness.* A rejected *impression* that happened to carry an
  `interaction_detail` incremented the interaction counter and logged "REJECTED
  interaction event" — so a billable impression loss was filed under the signal that
  exists to make interaction loss visible, and neither number meant anything
  afterwards.
- *Loop step 4.* See T-01: most round-N findings were introduced by the round-(N−1) fix.
- *Hard rules.* Both counters added under T-02 were unobservable — every test handler
  left `Metrics` nil.

### T-03 — endpoint and surface shipped together
A browser-facing package is where advertiser-facing functionality becomes real; the
config-history work shipped its endpoint and its UI affordance together (T-03 T4)
rather than leaving the endpoint stranded.

### T-05 — "one forbidden summary" was seven
A count quoted in a diff, issue or comment: T-05's "one forbidden summary" was seven.

### T-06 — "10 occurrences" was two
T-06's "10 occurrences" was two. `grep -c` counts lines where the claim says
occurrences.

### T-07 — "eight filter keys" was nine
T-07's "eight filter keys" was nine.

### T-08 — the hardened script that never runs
T-08's first round hardened two deploy scripts alone. Those scripts referenced a secret
under a name no environment actually used — which was itself the evidence they were not
the path that runs — while the script that *is* never mentioned that secret at all.
Round 2 wired it there, and **the PR as merged fixed all three**, so the tree no longer
shows the defect and grepping for it finds nothing. A fix in a script nothing executes
reads exactly like a fix, passes review, and closes the ticket.

### T-09 — a runbook smoke test that could not work
T-09 added a runbook whose smoke test could not work: `gcloud logging write` defaults to
`resource.type="global"`, so the synthetic entry missed the very filter it existed to
prove and would have read as a passing test while the metric stayed at zero. All 18
pre-commit hooks passed it — no hook checks CLI syntax in Markdown. `--help` would have
passed that very command, because every flag was valid and the wrong thing was the
*default*.

### T-10 — a write-time decision enforced only on read
`scanner.py` cited **D-U — reject where the author is** — as its whole reason for
existing, and every call site was a **read**. A `<script>` could be stored and was
refused only when someone tried to look at it, the opposite of what the citation says.

### T-11 — guessed ticket ids in source comments
T-11 put `T-12` and `T-13` into two source comments; Linear assigned `T-14` and `T-15`.

### T-16 — files outside the linter's allowlist
The ruff hooks are scoped by the `&python_roots` allowlist, so a green
`pre-commit run --all-files` says nothing about a file outside it (nine remained at the
time). The aggregate run reports "passed" and "never looked" identically, and it is the
one people cite.

### T-17 — a formatter change wrong about its size, and replies nobody read
- *Mechanical claims.* T-17 predicted the fallout would be "small — the code is
  `ruff format`-shaped already", and 35 of 51 files moved.
- *Replying where the reviewer listens.* On T-17 four declines posted as standalone
  top-level comments sat unprocessed while the review stayed `CHANGES_REQUESTED` — and
  were reported to the author as "answered", which was wrong.

### T-18 — lint findings for rules nobody enabled
An automated reviewer asserted RUF001 and RUF012 violations on T-18; neither rule is
enabled, `ruff check` passes, and **two of its four findings did not apply**. Resolving
a finding no gate can produce edits code to satisfy a linter that was never going to
run.

### T-19 — a retracted claim left in the test's docstring
On T-19 a retracted claim was removed from three places and left standing, in its
strongest form, in the docstring of the test it was about — where the next round found
it.

### T-20 — "not emitted yet" corrected in one file of nine
On T-20 a "not emitted yet" statement was corrected in one file while five others,
including both plane boundary tables, still asserted the opposite; three more sat in
the file already edited.

### T-23 — a "one-way" claim under six wordings
T-23 made retirement reversible and spent all three review rounds on the same defect:
the old "one-way" assertion corrected in some places and left standing in others. It
travelled under six wordings (`one-way`, `no tool un-deprecates`, `two writers`, `a
second writer`, `no longer transitions anything`, `manual SQL`). Round 1 swept `.md` and
`.py` and called it exhaustive; **the pipeline shell script that invokes the tool still
carried it**, because a script's comments are where its own reasoning lives. Round 2
added `.sh` and still missed two lines *inside a file it was editing*. Round 3 found
three more only by reading whole sections — including a paragraph headed **"Three
writers"** whose body named two and said the third tool "no longer transitions
anything", in a file already corrected twice for exactly that. A pointer added
elsewhere in the same change was routing readers straight at the stale one.

### T-24 — each round's fix was the next round's finding
On T-24 this held **four times running**, counting the automated reviewer as the
fourth: round 2 replaced a control that nothing pinned; round 3 found round 2's fix was
itself a regression — it moved a fetch to its own effect and left the matching state
resets behind in an effect keyed on the ranking, so every sort click blanked a panel
*permanently*, while the commit message claimed to have removed a flicker. The
automated pass then found round 3's own regression test was pinned to nothing. Giving
the reviewer the delta separately, and re-running the mutation campaign against the
fix, are what surfaced every one of these. Both times the circuit breaker fired, the
final findings were mechanical enough to fix with confidence.

### code-review — the formatter commit, before and after squash
#NNN's formatter commit alone was 35 files, 33 AST-identical, 0 structural. The same PR
*as squash-merged* reports 7 of 36 structurally different, because a sibling `fix:`
commit removed dead imports in the same squash — and the merged commit is the obvious
thing to reach for. Those 35 files carry 48 `# noqa` across 13 files, several the
`# noqa: E402` that `sys.path`-manipulating test modules depend on.

### code-review — the reviewer prompt is the variable that fires
A reviewer told to treat every *every / all / nothing can / the only* as a finding to
test produced two extra defects, while the same reviewer aimed only at claims about
*code* missed an equivalent claim about *policy*. This trap was n=7 in one batch with
the rule already written down twice. Six of one ticket's seven findings were a
criterion **partly** asserted, never one asserted wrongly. One author swept app-wide
for a false claim's phrase and found five the reviewer had not.

### code-review — a tool-syntax claim disproved by one command
A reviewer on the change that introduced this rule asserted that
`gh api repos/:owner/:repo` was invalid syntax needing `{owner}/{repo}` — one command
disproved it.

### code-review — a correct diagnosis with a wrong prescription
Both of #NNN's substantive findings were like this. Its major one — an unauthenticated
`PATCH` can replace a live `api_key` — was accurate, but the prescribed fix (strip
`api_key` from `body.model_dump()`) would have made the console's blank-key repair
return `200` while changing nothing, silently. Its migration finding cited a real
principle, but `s3a4b5c6d7e8` already did strictly heavier work on the same table in one
transaction, and no migration in the repo uses `NOT VALID`. Both were withdrawn once
answered with that evidence.

### code-review-and-quality — a patch that would have made a statement false
One review asked to narrow a "nothing renders yet" statement in a way that would have
made it *false*; the real defect was a different line implying a component was live.

### code-review-and-quality — a CI claim for rules the project does not enable
A reviewer asserted two lint findings "will fail the CI job" when the project enables
neither rule. Accepting such a claim quietly becomes an argument for widening the lint
config later.

### code-review-and-quality — the verdict query, and a finding no thread counted
The verdict query was wrong three times before it was right; reading it wrong is
`automation-silently-paused`, nine occurrences in one batch (C-09). Separately, one PR
reported `unresolved threads: 0` with a Major finding open — a real defect in the test
harness, described in the review body in prose that nothing counted.

### code-review-and-quality — sibling holes one function away
An unanchored-regex hole was closed in one function and the identical hole sat one
function away. A prototype-pollution hazard was found in one content-keyed map and the
same hazard was in another the reviewer had not looked at. Three holes in three rounds
of one scanner is what finally justified rebuilding it rather than patching a fourth
time.

### code-review-and-quality — sweeps that answered the wrong question
`query-answered-partially`, n=11 across two batches, and the one most often mistaken
for `unverified-artifact-claim` from outside.
- `grep -rn … --include=*.ts` aborts under zsh — the unquoted glob word-splits and zsh
  dies *before grep starts*, printing nothing directly above the author's own
  `--- (empty = clean) ---`. Quoting turned three "clean" sweeps into 60+ hits.
- A sweep took three passes and still missed a line — the third pass found a site in a
  file the second had already edited. Each pass answered the wrong question.
- After a squash, one branch listed three commits under `git log origin/main..branch`;
  reading that as "three are missing" was wrong exactly as "nothing is missing" would
  have been — the real answer was one stranded commit, and it came from diffing file
  **contents** against `origin/main`.

### code-review-and-quality — comments that were wrong
- One blocker: the comment said work happened lazily, the code built the whole tree
  eagerly, and the reviewer measured 1.28M DOM nodes. The *fix* commit then cited a
  constant it had just deleted.
- A round that corrected six stale comments got two of them newly wrong — one
  contradicting a passing test 380 lines below it.
- "Impossible", three times on one epic: *"this repo has no renderer and no dependency
  budget for one"* — disproved in forty lines, and three forbidden strings were reaching
  the rendered page behind the substitute; *"there is no behavioural assertion available
  here"*, used to justify source-checking a control's handlers — false, since the
  components are hook-free and their `onChange` can simply be invoked.
- Three consecutive PRs shipped a sentence in the body or a code comment that review
  proved false ("both call sites are load-bearing", "drift is impossible").

### code-review-and-quality — measurements and narrow reviewers
The strongest findings in one epic all came with numbers. A single broad reviewer prompt
burned large token budgets twice and produced nothing; two reviewers with one question
each both delivered.

### code-review-and-quality — guards that do not halt, and threads that do not close
- A shell validator written as `cmd "$(validate ...)"` was correct, called on every
  path, tested — and would have deployed `--set-env-vars ""`, wiping a service's
  environment.
- A delimiter check taking a hand-written list of fields missed four, one appended
  forty lines later.
- "Is this allowlist open?" had three implementations and a docstring calling that one
  too many — then a fourth, a regex in a test, which rejected a value the runtime
  accepts, refusing what it existed to bless.
- The bot's own thread resolution failed fifteen times in one night, leaving threads
  that read as pending on the author.

### test-driven-development — mutation testing on one epic
Measured on the spec-d epic: ~75 mutations across three tasks, all
eventually killed, but **twelve initially survived, and every one was a test asserting
less than it appeared to.** The "posts nothing" teardown shape occurred three times, in
three files; the render-time-DOM shape let a real defect reach review.
- *Mutate the resolution.* A guard added in response to a review comment survived
  deletion, because a sibling line already provided the protection.
- *A fix's shape.* One report named the offending column from a re-scan over
  `sorted(...)` while the offending value came from a scan iterating a **frozenset**, so
  with two bad columns the error named one and quoted the other's snippet. The first fix
  compared the two searches; mutation-testing *that* showed its test passed with the
  defect reintroduced, because redness depended on the two iteration orders happening to
  differ. The fix was replaced with one search over one order.
- *Harness errors.* Seen twice in one task (the runner off PATH, then the wrong working
  directory — "no tests ran in 0.00s"). Neither output contains the word `failed`, so a
  naive check reads both as survival.

### test-driven-development — a rule the harness could not reach
A browser-facing package with no DOM or React harness — `npm test` is bare
`node --test` — so a rule inside an event handler is unmutatable by construction. #NNN's
confirm gate lived in `handleSubmit`; deleting its create-only clause, dropping a
`.trim()`, and inverting its comparison all left the suite green. It became a pure
predicate in `lib/`, and all three mutations then failed by name. That predicate then
returned `false` whenever no key had been suggested, so its correctness rested on every
path that opens the form also minting one — a precondition spread across three
functions that nothing asserted, and a future entry point that skipped it would have
switched the rule off silently with tests green. Round 2 of the same review found it.

### test-driven-development — audits over the deleted form
Batch 01 hit the "rule over one syntactic form" limit nine times across three tickets.
**Six of the nine were false negatives** — an audit that quietly passes while the
violation sits in the file. Eight of the nine were absence audits; the ninth was a rule
over prose copy. One comment-stripping lexer produced four findings across four rounds,
**two of them introduced by the fix for the previous one**. The prose rule, widened to
catch `"The shopper qualifies…"`, began flagging `"Customer loyalty discount
qualifies…"`, where `customer` is adjectival.

### test-driven-development — assertions that passed for the wrong reason
- One test for "an undeclared event type is dropped" asserted on the posted event's
  `event_type` — which the event builder hardcodes — so every forwarded event was
  `interaction` either way.
- One tool takes `SELECT … FOR UPDATE`, and deleting it left all 14 tests green. Holding
  the row lock externally *also* passed with the guard deleted, because the ORM's
  `UPDATE … WHERE id` takes its own row lock. Two concurrent runs discriminate — without
  `FOR UPDATE` both write an audit row, so `one transition, one audit row` fails at
  `2 == 1` — until round two found that two runs launched together may execute
  *sequentially* and pass with the guard deleted.
- One test hand-built `{ok: false, reason: "element threw"}` — a message the shipped
  `runtime.js` never produces, because it reports `ok: true` for its own degrades and
  puts the truth in `rendered`.
- The empty-directory shape appeared three times in one epic (a gate, a mutation
  harness, a skipped Postgres suite). A declared-but-uninstalled test dependency made
  16 Postgres tests skip rather than pass for most of an epic.
- A zero-height guard test (the microtask-ordering rule) stayed green with the guard
  deleted.
- Relocating a gate kept 630 tests green; what needed re-running was the drift
  reproduction.
- One branch shipped seven assertions parametrised over the value they pinned. A test
  asserted a sort control against `view.sortDirection`, but the fixture's direction
  *was* the hardcoded `"desc"` the assertion existed to catch. A fixture spread
  `{...body().totals, gross_spend: …}`, but `PublisherTotals` has no `gross_spend` field
  (the name exists elsewhere as a *sort key*), so both calls returned the fixture
  default.
- When the branch's headline regression test was mutation-checked in isolation it
  stayed **green**; two neighbouring tests were failing on its behalf.
- One `MutationObserver` double stored each `observe()` target and options, then
  notified every observer of every record — so deleting `attributes`/`attributeFilter`
  from the real `observe()` call left **all 316 tests green**. Two more in the same
  file: a slot whose `getAttribute` was hardcoded to a pinned size, so no test *could*
  express the unpinned slot that was the real defect; and a `document.contains`
  assertion against a node the harness never attached.

### test-driven-development — comments that stated properties
Nine times across one epic (one measured instance), a comment asserted a property the
code did not have; reviewers caught every one, nothing else did. The codebase carries
design rationale in comments rather than a wiki.
- *"the alert routing reads it"* — nothing parses it; the exit code is what routes.
  *"One R3 provably cannot see"* — R3 sees that case at full value, in both money and
  volume.
- A comment claimed a named test enumerated every non-publishing return; `grep` found
  the identifier in exactly one place — that comment.
- *"Asserted at source so a third entrypoint cannot miss it"* — the check proved nobody
  builds a *second* event, which a third entrypoint that publishes nothing passes
  unchanged.
- A structural check built on source order looked like it enumerated every early
  return; because one signal call sat near the top of the function, every later return
  passed unconditionally.

### test-driven-development — coverage that did not exist
One shell suite exited **127** on `main` for six weeks after an unrelated change moved
the helper it substitutes a fake for; nothing noticed. On another surface the
acceptance criterion was literally "typecheck passes" and no job ran the type checker:
the mutation that breaks its strongest guard leaves the unit suite at 390/390 green and
fails only the type check. Moving a migration out of the migrations directory left every
test green, because the test schema was built from the models. See also C-10.

### execute-issue — issue premises that were wrong
Eleven tickets built on a wrong premise (C-13, C-14).
- One issue quoted a single forbidden value; there were seven, in three phrasings.
  Another's "10 occurrences" was 2 at every commit in that file's history.
- Six files became twelve when three sibling PRs landed between filing and execution.
  A compiler run found 21 errors across 7 files.
- A decomposed epic's end-state vocabulary appeared, with the same substitution, in
  every sibling ticket.
- One issue quoted a rule to explain why *this* half was hard; the same rule's list
  contradicted what it said about the *other* half.
- An issue named the field a bad decode arrives through and named the wrong one — the
  real path is screened a module upstream, so a guard placed as directed would have
  left it open.
- One issue asked for a counter that had never held a value in the environment it
  named — metrics were disabled there, and three files in the repo already said so.

### T-29 — a docs-only diff that was all claims

Nine documentation files changed; all seven review findings were sentences the shipped
code does not do. One copied a design sentence about a startup script into the
project's current-state doc; reading the two line numbers the spec itself cited would
have settled it in about thirty seconds.

### T-30 — runbooks reviewed fourteen times

Five runbooks took 14 review rounds, most findings in prose written *between* rounds
rather than in the runbooks themselves.

### T-31 — nine copies of an unscoped requirement

One requirement was scoped to a single mode; nine further sentences still asserted the
unscoped version. They were found one per round over eight rounds, until round 10
grepped the *retired* phrasings instead of the reported line.

### T-32 — one baseline patched, its sibling untested

A fix patched one of two parallel baselines and left the other with no test at all.

### T-33 — a correction that introduced a new false claim

Correcting one prose description of a narrowed field introduced a new false claim in
its replacement.

