# Spec Pipeline

## Overview

Use this workflow to take a feature from a product spec through **two
independent review gates** to an agent-ready task decomposition — with the
author consulted only for decisions.

The pipeline is split so each gate reviews a small, focused surface:

- **Gate 1 — Product Spec Review.** Adversarially reviews the product spec
  (`product.md`) — problem, user, user-verifiable requirements, success
  metrics, non-goals. No architecture. Verdict: **PRODUCT_READY**. Gate 1
  **closes with a merged product PR** — engineering design does not begin until
  it lands on `main` (see [PR Gates](#pr-gates)).
- **Gate 2 — Eng Design Review.** Takes the PRODUCT_READY product spec plus the
  rubric at `[paths].principles` as guardrails,
  drafts the engineering design (`design.md`), and adversarially reviews it
  against those principles and for machine-checkable acceptance criteria and
  agent-ready decomposition. Verdict: **DESIGN_READY**. Gate 2 **closes with a
  merged design PR**; the decomposition is the set of tasks to implement.

The seam between the gates is the load-bearing idea: **the product spec is the
input, the architectural principles are the guardrails, the eng-design
iteration is the review, and the decomposition is the outcome.** Splitting them
keeps each review small and lets a product change re-open only Gate 1 while an
engineering-only change re-runs only Gate 2.

## When To Use

- A spec has passed spec-driven-development and needs adversarial hardening.
- The task is substantial enough to need a formal engineering design and
  Linear-ready task decomposition.
- You want agent-ready acceptance criteria, not just clarified intent.

Do not use this workflow for quick clarifications or small features where
spec-driven-development is sufficient.

## Relationship to spec-driven-development

spec-driven-development clarifies product intent. Its result becomes
`product.md` — the Gate 1 input. `product.md` may be drafted by the author or
shaped by an agent using spec-driven-development, but must be author-confirmed
before Gate 1 reviews it. The pipeline then reviews `product.md` (Gate 1),
drafts `design.md`, and reviews `design.md` against the architectural
principles (Gate 2) to produce a DESIGN_READY, decomposition-bearing spec.

## Repo Context To Load

- **The Gate 2 rubric: `[paths].principles`.** Gate 2 grades the design against
  this and nothing else, so a project that has not written one is running Gate 2
  against an empty rubric. Start from
  [`templates/architectural-principles.starter.md`](../templates/architectural-principles.starter.md).
- Your architecture overview, for the boundaries the design must respect.
- The project's current-state doc, for what is **built** — never its roadmap,
  which is planned.
- Spec templates: [`templates/_product_template.md`](../templates/_product_template.md),
  [`templates/_design_template.md`](../templates/_design_template.md).
- Shared hash helper: `tools/spec_hash.py`. Run it; never compute a hash any
  other way and never write a placeholder.

## Spec File Structure

Specs live in a per-slug directory `<[paths].specs>/<slug>/` with two artifacts, one per
gate:

- **`<[paths].specs>/<slug>/product.md`** — Product Spec: problem, user, requirements
  (user-verifiable), success metrics, non-goals. Author input; the Gate 1
  artifact. Follows `templates/_product_template.md`.
- **`<[paths].specs>/<slug>/design.md`** — Engineering Design: architecture (including what
  it reuses and why any new component is needed), principles adherence, acceptance
  criteria, task decomposition, deferred scope, edge cases, invariants.
  Drafted by the pipeline; the Gate 2 artifact. Follows
  `templates/_design_template.md`.

The slug is chosen once, by whatever entry point drafts `product.md`. A spec
whose deliverable lives under one of the project's exploratory trees carries the
project's prototype slug prefix (see `docs/engineering/project-conventions.md`);
the prefix is part of the slug, and the pipeline never inspects it.

Before Gate 1 issues PRODUCT_READY, `design.md` does not yet exist (or contains
only the `<!-- TODO -->` marker from the template). Its absence signals the
spec is at the product gate.

**Keep each artifact to its own job.** `product.md` targets ≤150 lines and carries
no implementation detail, no per-claim `file:line` evidence, and no justification or
review-history prose — see `templates/_product_template.md` § *Keep it short, and keep
implementation out* for where each of those belongs. A spec directory may also carry
supporting analysis (e.g. `assessment.md`) that the gate artifacts reference rather
than restate; it is author material and is not itself reviewed by either gate.

> **Legacy single-file specs are read-only.** Four older specs are a single
> `<[paths].specs>/<slug>.md` carrying `## Section 1 — Product Spec` and `## Section 2 —
> Engineering Plan`, with their rounds under `<[paths].specs>/<slug>.review/`. Those files and
> their review history stay where they are and remain readable — **but the pipeline
> does not run on them.** To take one further, split it into `product.md` and
> `design.md` first; the pipeline then treats it as any other spec.
>
> This is a deliberate narrowing. Supporting both layouts live meant every step
> carried a "which layout is this?" branch — which artifact to hash, which of two
> hash modes, which gate (one file holds both sections, so the artifact cannot say),
> which filename to commit. Four consecutive review rounds found gaps in that
> branching and the last one listed six more sites. All four legacy specs are
> historical: three closed at READY or DESIGN_READY, and the fourth stopped at
> NOT_READY after two rounds in June. The branch was being maintained for no live
> caller.

## Workflow

`product.md` is author-confirmed product input; the pipeline owns `design.md`
and the review artifacts.

1. Author drafts `product.md` (from `templates/_product_template.md`).
2. Author runs the pipeline entry point (see adapter-specific invocation
   below).
3. The pipeline loops autonomously:
   - **Gate 1 (product)** while `design.md` is absent / `<!-- TODO -->`:
     the `product-spec-reviewer` reviews `product.md`.
   - **Gate 2 (design)** after PRODUCT_READY: the `eng-design-reviewer`
     reviews `design.md` against the `[paths].principles` rubric.
   - If NOT_READY: the editor resolves all `decision: mechanical` items
     automatically **in one pass covering every blocker in the round**, then
     pauses once per round to present `decision: author`
     items as a single batch. Each item is a Shape A decision brief
     (`human-brief`, `human-brief.md`) — options,
     what the author would notice, a recommendation and the fact that would flip
     it — never the reviewer's raw round-file prose, which is written for the
     editor and not for the author. Deliver via `AskUserQuestion` where the
     harness offers it, otherwise the identical tables as text through
     `python3 tools/ask.py ask "<batched questions>"
     --context "<slug> spec"`, blocking until the author replies in the
     Slack thread. Author answers are applied and recorded in the round
     files, and the loop continues.
   - On **PRODUCT_READY** — the **product PR gate** (see [PR Gates](#pr-gates)):
     the pipeline **stops editing `product.md`** (advisory findings are not applied
     — see [Closing A Gate](#closing-a-gate)),
     commits `product.md` + its Gate 1 review rounds to a branch,
     opens the **product PR** (`spec(product): <slug>`), and **STOPS**. It does
     NOT draft `design.md`. The author reviews, approves, and merges the product
     PR (no self-merge). Re-running the pipeline after that merge resumes at
     Gate 2: the drafter (gated on `product.md` being on `main`) writes
     `design.md` (including its Principles adherence section), and review
     continues.
   - On **DESIGN_READY**: the pipeline **stops editing `design.md`** and opens the
     **design PR** (`spec(design): <slug>`) carrying `design.md`, its Gate 2
     rounds, and `ack-round-N.md`. That file records the decomposition, the
     advisory open items, and the cumulative mechanical-edit changelog **as a
     Shape B change brief** (`human-brief`,
     `human-brief.md`) — the author is being asked
     to ratify edits made without asking, so each one needs its plain-English
     consequence and something to check it against. Then it **STOPS**. **The
     author's approval of that PR is the acknowledgment**; there is no separate
     Slack ack round-trip, so the brief is read on the PR rather than in a
     thread. See [Acknowledgment](#acknowledgment).
4. After the design PR merges, the author takes the decomposition to Linear as
   tasks.

Author touchpoints, exhaustively: `product.md` authorship, answering decision
batches, and **approving + merging the product PR (Gate 1 closure) and the design
PR (Gate 2 closure)** — the latter approval also being the changelog
acknowledgment. Decision batches
and circuit-breaker escalations are delivered via
Slack (`tools/ask.py`); the terminal session blocks until the
author replies in-thread. Answers are recorded in the round files — Slack is
transport, not record.

Pipeline state is entirely file-based. Re-running the entry point resumes from
the latest round.

## PR Gates

Each gate closes with its own merged PR, so product intent is reviewed and
committed to `main` **before** any engineering design work begins. This is the
load-bearing rule: **product-gate closure is a merged PR, not just a verdict.**

- **Product PR (Gate 1 closure).** On PRODUCT_READY the pipeline commits
  `product.md` + its Gate 1 review rounds (`review/round-*.md` with
  `gate: product`) + `carried-advisories.md` to a branch and opens a PR titled
  `spec(product): <slug>`,
  then **stops**. The author reviews, approves, and **merges** it — the
  pipeline never self-merges. Gate 2 is blocked until this PR lands on `main`.
  Advisory review comments on this PR are recorded, not applied; an artifact edit
  pushed here reopens Gate 1 and needs a fresh full round before merge (see
  [Editing on a gate PR](#editing-on-a-gate-pr)).
- **Design PR (Gate 2 closure).** On DESIGN_READY the pipeline commits `design.md`
  + its Gate 2 rounds + `carried-advisories.md` + `ack-round-N.md` to a branch and
  opens a PR titled
  `spec(design): <slug>`, then **stops** for author review + merge. **Approving
  this PR is the changelog acknowledgment** (see
  [Acknowledgment](#acknowledgment)). Advisory review comments here are recorded,
  not applied; editing `design.md` on this PR reopens Gate 2 and needs a fresh
  full round before merge — and it also invalidates the ack, whose
  changelog described a different artifact (see
  [Editing on a gate PR](#editing-on-a-gate-pr)). The decomposition is filed to
  Linear after this PR merges.

### Watching the review on a gate PR

**A gate PR is a pull request, so whatever reviews your pull requests reviews it.**
That was a gap for a long time: the pipeline opened the PR, stopped, and nothing
looked at the review. Comments arrived on `product.md` and `design.md` and the
author found them by chance or not at all. "Recorded, not applied" presumes
somebody read them, and no step made sure.

So after opening either gate PR, and before telling the author it is ready:

1. **Read the review state**, once the reviewer has had time to start:

   ```bash
   python3 tools/review_state.py --pr "${PR:?}"
   ```

   With `[review].provider = "none"` this reports that no reviewer is configured
   and there is nothing to read. Say that in the handoff — it is not the same as
   a review that has not landed yet, and the two look identical if you only
   report silence.

2. **Never read the check row instead.** It renders `pass` for a skipped,
   rate-limited, paused and stale review alike. Nine measured occurrences:
   [`C-09`](../examples/case-studies.md#c-09--a-reviewer-that-reports-success-without-running).

3. **Surface every finding to the author, in the handoff.** Inline comments and
   the review **body** are different surfaces, and a finding whose line falls
   outside the diff lands in the body — which no thread count reflects. Provider
   specifics are in [`providers/`](./providers/).

4. **Do not apply them.** This is the one place a gate PR differs from a code
   PR: an edit to the artifact here **reopens the gate** and needs a fresh full
   round before merge (see [Editing on a gate PR](#editing-on-a-gate-pr)). So a
   reviewer finding on a spec is *reported*, and the author decides whether it is
   worth reopening. Applying it silently costs a round nobody asked for.

That last point is why this is a report step and not the `git-pr-workflow`
watch loop. There, the loop drives the review to settled because fixes are
cheap. Here, the fix is a gate reopening — so the loop is: read, surface, stop.

**Why two PRs.** The product PR is a durable, independently-reviewable record of
*what* we're building and *why*, merged before a single line of engineering
design is drafted — so a product-intent disagreement is caught and resolved on
its own PR, not tangled into a design review. The design PR then reviews *how*
against a product spec that is already settled on `main`.

**Drafter gate (reinforced).** The drafter refuses to write `design.md` unless
`product.md` is present on `main` (the product PR merged) **and** the most
recent Gate 1 PRODUCT_READY verdict's `product_hash` matches it (see
[Hash Gates](#hash-gates)). Merged-but-then-edited `product.md` re-opens Gate 1.

## Review Requirements

Every question in a round file must:

- Be tagged **BLOCKER**, **MAJOR**, or **MINOR**.
- Be tagged `decision: author` (multiple defensible answers — product
  tradeoffs, scope, intent) or `decision: mechanical` (single defensible
  resolution — definitions, inconsistencies, missing specifics implied by
  context). Default to `author` when uncertain.
- Reference the spec by section anchor and a short quoted snippet.
- State why it matters for agent execution.
- State what would resolve it.

A **Gate 2** question that asserts a principle violation must name the
principle (by number, from the `[paths].principles` rubric) and quote the design
text that breaches it — and it is a BLOCKER unless `design.md` already records a
justified trade-off, in which case it is at most a MAJOR (see Verdicts).

**Cross-plane endpoints are a standing Gate 2 question.** If §1 *Architecture*
names any route, RPC, or topic, the reviewer establishes whether it crosses a
plane edge before grading anything else about it — a design that adds an edge
without saying so has skipped an architectural decision, not a formatting step.
When it is a new edge, the design must name the direction, the producer, the
consumer, what pins the payload shape, and the doc set that will change with it
(your `[paths].principles` rubric's cross-boundary section). Riding an **existing**
edge is the preferred answer and is fully acceptable — but it must be stated,
not left to inference. Silence here is a BLOCKER; the decomposition that follows
will otherwise land the endpoint with no doc task attached to it.

**A new internal component must say why existing infrastructure cannot serve it.**
§1 *Architecture* carries a **Reuses** line and, for every NEW internal component,
abstraction, table or service, one line on the existing thing considered and why it
does not fit. Silence is a BLOCKER (#4 / #6 / #12) — an abstraction that arrives
without a reason is the over-engineering failure the principles doc calls out as
equal to under-building. **An explicit justification is good enough at Gate 2**: the
reviewer may record an advisory MAJOR against reasoning it doubts, but not a blocker,
and the design PR reviewer weighs whether it holds. This is deliberately the same
grading as a stated principle trade-off — the gate checks that the decision was made
and written down, not that it was the best one. When the reason is already evident
elsewhere in the design, the finding is `decision: mechanical` (surface it in §1);
when it is genuinely absent, it is `decision: author` — the editor must not invent an
architectural justification, which would be originating a judgment.

**Requirements a test cannot prove need a named validation plan, not a soft AC.** §5
stays machine-checkable, and every Rn must map to an AC **or** to a §5 *Validation
plan* entry that says how it will be validated and why no test or command can prove
it. An Rn with neither is a BLOCKER; so is a validation-plan entry for something a
test could have covered, which is the escape hatch this slot would otherwise open.

**Deferred scope is a decision, not a gap.** §8 *Deferred* bounds the build the way
`product.md` § *Non-goals* bounds the product, so the reviewer raises no finding for
a capability §8 defers. The one exception: an entry covering a stated requirement
(Rn) is a BLOCKER — a design cannot defer what the product spec requires, so either
the design absorbs it or `product.md` changes and Gate 1 re-opens.

A round contains at most 15 new questions (cap). Carried-forward unresolved
blockers do not count against the cap.

**Once unresolved blockers are at zero, at most 3 advisories are written out in
full.** A gate is closing; the reviewer's remaining job is to say so, not to fill a
budget. Zero is the expected number — see [Closing A Gate](#closing-a-gate). This
is a hard limit, not a weighting: `publisher-metrics` produced 44 advisory majors
after its gates had already closed, every one of them under prose that merely asked
the reviewer to weigh proportionality.

Two things this limit is **not**:

- **It never applies to blockers.** Itemise every blocker, always, however many. The
  limit exists to stop advisory volume, and a round can legitimately find new
  blockers at zero prior blockers — the reopened-gate round
  ([row 3](#the-rule-freeze-the-artifact-at-the-first-ready-verdict)) is now the only
  round that runs from a zero-blocker state, and it is the one where **nothing has yet
  read the current bytes**. Capping blockers there would suppress findings on the least
  reviewed artifact in the pipeline.
- **It caps the write-up, not the record.** `majors:` and `minors:` in the front
  matter are always the true totals. Beyond the 3 written out in full, **every further
  advisory still gets a one-line entry** — an id and a single sentence naming the
  concern, enough to identify and disposition it later, and nothing more. What this
  section measured was reviewer *output* — 15,002 lines on one spec — and one line per
  finding is not what produced that number; paragraphs of reasoning per finding is.

  This is load-bearing rather than tidiness: [Dispositioning the
  advisories](#dispositioning-the-advisories) requires **every** advisory open at gate
  close to be dispositioned into `carried-advisories.md`, and a Linear follow-up has to
  restate the concern to stand alone. An advisory the reviewer counted but never wrote
  down cannot be dispositioned, filed, or carried — it is just a number, which is the
  evaporation this section exists to prevent.

**The count is the signal, so keep it honest.** `blockers: 0` with `majors: 3` and
`blockers: 0` with `majors: 20` are different situations, and the second is when a
human should look *harder*. If the number were capped too, they would serialize
identically — and the diagnosis behind this whole section came from counting 44 majors
on one spec, so a cap that stopped anyone counting past 3 would retire its own
evidence and could not find the next instance. Pick the 3 most material to write out in
full, one-line the rest, and report the total regardless.

**3 is tuned from one corpus, so here is what would move it.** Because the totals stay
honest, both signals are now measurable rather than anecdotal: raise it if suppressed
advisories keep turning up as real problems in gate PR review, and lower it — or drop
it to zero — if the ones that *are* written out keep arriving as PR comments nobody
acts on. Neither requires re-running the corpus count.

## Round File Schema

### The review directory

Everything the pipeline writes about a review lives in `<[paths].specs>/<slug>/review/` and
nowhere else: `round-N.md`, `edits-round-N.md`, `ack-round-N.md`, and
`carried-advisories.md`. One layout, so there is nothing to resolve and nothing that
can drift between a read and a write.

Round files live at `<[paths].specs>/<slug>/review/round-N.md` (N is global across
gates). They are immutable once written.

```yaml
---
spec: specs/<slug>/           # the spec directory
round: N
gate: product | design
verdict: PRODUCT_READY | DESIGN_READY | NOT_READY
product_hash:
design_hash:                  # omit / null at Gate 1
blockers:
majors:
minors:
carried_unresolved:
date:
---
```

**No field was added for the stop rule, and none is needed.** Its three inputs are
already here: the latest round *for the gate* (filter on `gate:`, take the highest
`round:`), that round's `blockers:`, and whether its recorded hash still matches the
artifact on disk. A resumed run with no memory reads the same answer from the same
files — which matters, because pipeline state is file-based (see Workflow) and any
rule the loop must enforce has to be reconstructable from these fields alone.


`product_hash` and `design_hash` are computed by the adapter (not the reviewer
subagent) and passed in — see Hash Gates.

## Verdicts

- **PRODUCT_READY** (Gate 1): zero unresolved blockers in `product.md`.
  Unlocks the drafter.
- **DESIGN_READY** (Gate 2): zero unresolved blockers across all rounds
  (including zero unjustified principle violations) AND a successful
  decomposition dry-run (every task has independent acceptance criteria,
  declared dependencies, and single-session scope — one PR, no context
  compaction).
- **NOT_READY**: one or more unresolved blockers.

Open majors and minors are advisory and do not block any verdict. A principle
trade-off that `design.md` states and justifies is recorded as an advisory
MAJOR, not a blocker; an *un*justified principle violation is a blocker.

## Closing A Gate

**A gate closes on blockers reaching zero, not on findings reaching zero.** Majors
and minors are advisory by definition (see Verdicts), so nothing about them can gate
a verdict — and the [Circuit Breaker](#circuit-breaker) watches blockers, not
findings. **This section is therefore the only thing that stops the loop.** Without
it, a spec at zero blockers with a healthy supply of majors produces rounds forever.

This is measured across the two-file corpus, not inferred. Of **83 review rounds over
7 specs (25,172 lines of reviewer output), 35 — 42% — ran at zero blockers on a gate
that had already issued a READY verdict:**

| spec | rounds | rounds at 0 blockers after close |
|---|---|---|
| `publisher-metrics` | 34 | **21** |
| `serving-path-integrity` | 7 | 4 |
| `lighthouse-chat` | 6 | 3 |
| `reporting-data-foundation` | 8 | 3 |
| `declarative-creatives` | 17 | 2 |
| `line-item-cleared-spend-store` | 6 | 1 |
| `config-versioning-audit` | 5 | 1 |

The four legacy `specs/*.review/` directories are excluded — 39 further round files,
32% of the 122 in the tree — so the real figure is if anything understated.

`publisher-metrics` reached PRODUCT_READY at round 4 and DESIGN_READY at round 22,
then ran **26 further rounds** and 15,002 lines of review over 13 days. It needed two
acknowledgments because the design grew 76 → 94 criteria *between the ack and the
merge*. Round 19 is a five-audit review of one edited sentence. Its `design-round-10`
describes itself as "the one confirmation round" the rule allows — and five more
rounds followed it.

### Why it ran away

Two individually-correct rules compose into an unbounded loop:

1. The editor resolves findings — including advisory ones, which gate nothing.
2. Any edit changes the hash, and the [hash gate](#hash-gates) requires a verdict
   matching the current file.

So: READY → an advisory nit is fixed → the hash invalidates → a re-review is now
*mandatory* → a fresh-context reviewer re-reads the artifact and the 592-line
principles doc → finds new advisory material in prose it has not seen → edit →
repeat. `publisher-metrics` reached MINOR-74 and MAJOR-72 this way.

### The rule: freeze the artifact at the first READY verdict

**A READY verdict is computed against the artifact as it stands, so its hash already
matches. Freeze the artifact and that hash stays valid — so no further round is
needed at all.** Open the gate's PR.

That invariant has one precondition, and the corpus shows it being broken: **nothing
may edit the artifact between the reviewer reading it and the adapter recording the
hash.** `round-19.md` records its verdict as reached at `77bd5786…`, then MINOR-74 —
an *advisory* minor — was applied afterwards and the hash re-pointed to `800a68b6…`,
the value in its front matter. Freezing is what makes the invariant hold; re-pointing
a hash around a post-verdict edit is the behaviour this section forbids.

- **Zero further rounds is the default, the expected case, and the only cheap one.**
  Do not apply advisory edits before opening the PR. Remaining majors and minors are
  **dispositioned, not dropped** — see
  [Dispositioning the advisories](#dispositioning-the-advisories) — and where that
  disposition is a PR comment, it is recorded and **not applied** on that branch.
- **Any edit to the artifact costs a full round.** Not a cheap re-confirmation, not a
  hash re-point: a full round at `round: N+1`, reviewing the artifact as it now
  stands. That is true before the PR is opened and after (see
  [Editing on a gate PR](#editing-on-a-gate-pr)) — **one act, one price.** An earlier
  draft of this section charged less for a pre-PR edit than a post-PR one, which made
  the cost depend on whether the PR happened to be open yet; that asymmetry bought a
  cheap hatch and five mechanisms to guard it, against a rule whose whole point is
  that the artifact should not be edited at all.

The loop, not the reviewer, enforces this. **This table is the single authoritative
statement of that rule**; the adapters point at it and must not restate it. It keys off
the **latest round for the current gate** plus whether that round's recorded hash
matches the artifact on disk. Evaluate in order; the first matching row wins.

| # | Latest round for the gate | Hash vs. artifact | Loop does |
|---|---|---|---|
| 1 | none yet, or `blockers > 0` | — | run a round (the normal loop) |
| 2 | `blockers: 0` | **matches** | **gate closed — write `carried-advisories.md`, then open the PR** |
| 3 | `blockers: 0` | differs | run a round — the gate has reopened |

Rows 1 and 3 are the same action, so **at zero blockers there is exactly one question:
does the hash still match?** Two things that encodes:

- **A matching hash means closed.** A verdict names the bytes it read; if those are
  the bytes on disk, the gate is done and no further round can be justified.
- **Closed is not the same as finished.** Row 2 permits no further *round*; it does
  not permit opening the PR with advisories undispositioned. Before the PR,
  `carried-advisories.md` must exist and carry exactly one disposition for every
  advisory open at close — see
  [Dispositioning the advisories](#dispositioning-the-advisories), which this row is
  the entry point to rather than an exception from.
- **A differing hash always costs a round**, because no verdict covers what is on
  disk. There is no cheaper branch to reach for, which is the point — the rule
  discourages editing a closed artifact, and a discount on doing so worked against it.

### The reviewer should say when it is done

A round that returns READY states plainly whether any remaining finding is a genuine
obstacle to the next gate, or whether the residue is next-gate material. **"Close the
gate" is a legitimate and useful output**, and at zero blockers it is usually the
correct one.

### Batch blocker fixes

Fix every blocker in a round in **one** editor pass, then re-review once.
`declarative-creatives` went 4 → 3 → 2 → 1 → 0 blockers across four rounds — one
blocker per round, each costing a full reviewer invocation. Blockers within a round
are independent; nothing requires clearing them serially.

### Dispositioning the advisories

Freezing the artifact means the open majors and minors leave the loop, and the failure
mode to guard against is that they simply evaporate — the gate closes, the PR merges,
and a real observation is now only in a round file nobody will reopen. **Every advisory
open at gate close gets an explicit disposition, and "silently dropped" is not one of
them.**

The record is `<[paths].specs>/<slug>/review/carried-advisories.md`, written when the gate closes and shipped
in the gate's PR beside the round files. It costs nothing in hash terms: `spec_hash.py`
hashes `product.md` / `design.md` only, never the review directory, so adding this file
cannot disturb a verdict.

`publisher-metrics` invented the idea, and its file is the **ancestor, not the
template** — it predates this schema, groups advisories into "input to Gate 2" /
"remaining" / "not carried" buckets rather than itemising them, and carries a prose
`status:` line instead of a verdict. Do not copy its shape. Going forward the file
carries front matter naming the spec, the gate, the closing verdict and its hash, and a
date; and a body with **one entry per carried advisory**, each naming the finding, the
round it came from, and exactly one disposition:

**Test them in this order and take the first that fits** — they overlap in the obvious
reading, since next-gate design work is also "work someone does later":

1. **Next-gate acceptance criterion** — a Gate 1 advisory that directly constrains
   `design.md`. Gate 2 will settle it, so name the requirement or section it attaches
   to and let it arrive as input rather than being rediscovered.
2. **PR review comment** — answerable on the gate PR, needing no artifact change and
   leaving no owner behind it: wording, a clarification, an altitude nit. It dies on
   the PR once answered. **Do not file an issue for one of these**; a ticket per minor
   is how a tracker stops being read.
3. **A Linear follow-up issue** — it survives this gate and the next, or it needs
   implementation or process work after the spec closes: a capability gap, a
   durability or correctness concern, a boundary that wants revisiting. File it
   against the team with the label `<slug>-followup` (e.g.
   `publisher-metrics-followup`), and give it the context that makes it actionable
   months later: the finding as written, the round it came from, the spec and hash it
   was raised against, and — the part that is usually missing — **why it was filed
   rather than fixed in the gate.** Record the issue id back in
   `carried-advisories.md`, so the file and the tracker point at each other.

**Nothing may fall through.** An advisory that fits none of the three is not a
disposition — escalate it to the author with the other decision items rather than
inventing a fourth bucket or quietly dropping it. If the author's answer is that it
needs no follow-up, record it as `no follow-up` **with their reason**; an empty line
in this file is indistinguishable from an oversight, which is the whole failure mode.

**The issue must stand on its own.** An advisory reduced to "MAJOR-49 from round 10"
is not a follow-up, it is a pointer into a document written for a different audience at
a different time. Restate the concern in terms someone who never read the spec can act
on. T-25's spillover table is the shape to copy: each row names the issue, its
priority, and one line on why it was filed rather than folded in.

This is the disposition step that makes freezing safe. A gate that closes with
advisories and no `carried-advisories.md` has not finished closing.

### Editing on a gate PR

Advisory findings travel to the gate's PR, so the obvious next move — the author
resolves one by pushing a commit to the PR branch — must be specified, because it
collides with the [hash gate](#hash-gates). The drafter checks the *merged*
`product.md` against the most recent PRODUCT_READY verdict's `product_hash`; an edit
on the PR branch means the artifact that merges is not the artifact that was
reviewed, and Gate 2 blocks on a hash that no round matches.

- **Default: comments are recorded, not applied.** An advisory comment on a gate PR
  is resolved by carrying it to the next gate as an acceptance criterion, or by
  filing it — not by editing the artifact on that branch. This is the whole point of
  freezing: the reviewed bytes and the merged bytes are the same bytes.
- **If the artifact IS edited on the gate PR, the gate has reopened.** That is a
  legitimate choice — round 19's corrected false premise is the case that earns it —
  but it costs a full round, not a hash re-point. Before merge, a new
  full round must land on that branch, reviewing the edited artifact
  and recording a verdict whose hash matches what will merge. Merging a gate PR whose
  artifact no round has reviewed at its final hash is the failure this rule exists to
  prevent; it strands the drafter with no matching verdict.

  **The closure record is replaced, not carried over.** `carried-advisories.md` was
  written against the *earlier* closure — a different artifact, and possibly a
  different set of advisories, since the new round can resolve old ones and raise new
  ones. Regenerate it against the round that actually closes the gate, and reject a
  record whose gate, verdict, source round or hash belongs to the previous closure.
  Otherwise the PR merges carrying dispositions for bytes nobody closed, which reads
  as a completed disposition step and is not one.
- **Never re-point a hash to cover a post-verdict edit.** A verdict names the bytes it
  read. Editing the bytes and moving the hash to match is not a confirmation — it is
  an unreviewed change wearing a verdict's front matter.

## Carry-Forward

Every round dispositions each prior blocker and major as resolved /
unresolved / superseded with one line of evidence. No PRODUCT_READY or
DESIGN_READY verdict may be issued while any blocker from any prior round is
unresolved.

**MAJOR vs MINOR is a persistence dial, and this line is the only mechanical
difference between them in this document.** Majors carry forward and must be
dispositioned each round; minors do not and may simply lapse. So choose the tag by
asking *"should this still be answered a round from now?"* — not by grading severity in
the abstract. The two failure modes bound each other: collapse the distinction one way
and every advisory is re-litigated every round, collapse it the other and advisories
evaporate after a single round. Severity is what BLOCKER encodes, and blockers gate
verdicts; the advisory pair encodes how long an unanswered point survives.


## Hash Gates

Two hashes gate the pipeline. Both are computed with
`tools/spec_hash.py` and used verbatim:

- **product_hash**: whole-file hash of `product.md`
  (`spec_hash.py spec specs/<slug>/product.md`). Freezes the Gate 1 input.
- **design_hash**: whole-file hash of `design.md`
  (`spec_hash.py spec specs/<slug>/design.md`). Drives skip-unchanged
  re-reviews at Gate 2.

The **drafter gate**: the drafter checks that (a) `product.md` is present on
`main` — i.e. the product PR has merged (see [PR Gates](#pr-gates)) — and
(b) the most recent Gate 1 PRODUCT_READY verdict's `product_hash` matches the
current `product.md`. A product edit after the verdict invalidates the gate and
re-opens Gate 1; an unmerged product PR blocks the drafter outright. An
engineering-only change (`design.md` only) leaves `product_hash` intact, so
Gate 2 re-runs without re-reviewing the product spec.

> `spec_hash.py` keeps a `product` mode that hashes the `## Section 1` slice of a
> single-file spec. It is what the legacy rounds recorded and is retained so those
> hashes stay reproducible; the pipeline itself no longer calls it, because legacy
> specs are [read-only](#spec-file-structure).

## Circuit Breaker

If unresolved blocker count fails to strictly decrease across three
consecutive review rounds, the pipeline pauses and escalates all open
questions to the author via `ask.py ask` regardless of decision tags.

**The breaker applies only while blockers are above zero.** A gate at zero
blockers is closed, not stuck — it exits via [Closing A Gate](#closing-a-gate),
not via escalation. Reading `0, 0, 0` as "failed to strictly decrease" would
escalate a finished gate to the author, and is the reading that let advisory
rounds accumulate without either mechanism stopping them.

## Roles

- **product-spec-reviewer**: reads `product.md` and, as needed, the codebase
  to sanity-check feasibility. Runs the Gate 1 (product) passes and writes
  round files. Reviews product intent only — never architecture. Never
  modifies the spec. Tools: Read, Grep, Glob, Write.
- **eng-design-reviewer**: reads `design.md`, the PRODUCT_READY `product.md`,
  **Gate 1's `<[paths].specs>/<slug>/review/carried-advisories.md`**,
  the `[paths].principles` rubric, and the codebase. Every advisory that file
  dispositions as a *next-gate acceptance criterion* is Gate 2 input: check the
  design answers it, and raise a finding if it does not. Without that read the
  disposition is a note nobody acts on, and Gate 2 rediscovers the same point or
  misses it. Runs the Gate 2 (design)
  passes — principles adherence, reuse / new-component justification,
  machine-checkable acceptance criteria, decomposition dry-run — and writes round
  files. Never modifies the spec.
  Tools: Read, Grep, Glob, Write.
- **editor** (`spec-editor`): applies mechanical resolutions and author
  decisions to `product.md` / `design.md`. Never originates review judgments.
  Tools: Read, Grep, Glob, Edit, Write.
- **drafter**: reads `product.md`, **Gate 1's `<[paths].specs>/<slug>/review/carried-advisories.md`** (its next-gate-criterion entries are
  requirements on the design, not background), the `[paths].principles` rubric, and the
  codebase, and writes `design.md` (including its Principles adherence
  section). Gated by the product PR being merged to `main`, the PRODUCT_READY
  verdict, and a matching product_hash (see the drafter gate under
  [Hash Gates](#hash-gates)). Pinned to `fable` in
  `${CLAUDE_PLUGIN_ROOT}/skills/draft-plan/SKILL.md`, with the rest of the pipeline: the drafter
  reads `product.md`, the principles, and up to 30 grounding files, so it is the
  step least served by inheriting whatever model the session happens to hold.
  The pin binds the invoking turn only, like every skill pin — see § *Model pins*.

## Which model runs this

**Cadence pins no model, and cannot.** That is a limitation of the harness, not
a preference, and it is worth understanding because the failure it produces is
invisible.

Three facts, each verified against the harness docs:

1. A skill's `model:` pin **applies only to the turn that invoked the skill.**
   Your session model resumes on your next prompt.
2. A **subagent's** pin does hold for that subagent's whole run.
3. **Nothing else persists.** No hook can change a model. There is no per-role
   override — the `modelOverrides` setting maps provider model IDs, it does not
   assign models to agents.

Now put that against this workflow: it **stops to ask the author** every round.
So a pin on the pipeline skill covers the first turn and nothing after. The
review rounds are subagents and genuinely hold their model; the orchestration
between them silently falls back. A pipeline pinned this way reads as running on
one model throughout and does not.

That is the whole reason the pin was removed rather than translated.

### What replaces it

`[models].recommended` in `cadence.toml`, and a check at the top of the
pipeline. The check reads the recommendation, compares it to the model actually
running, and **stops if they differ** — naming both and how to switch.

It enforces nothing about the model. What it enforces is that you find out. The
defect being fixed is not "the wrong model ran", it is "the wrong model ran and
nothing said so".

### Making it actually stick

Two ways, both the harness's own:

- **`/model <name>`** before you start the pipeline. Lasts the session.
- **`"model"` in `.claude/settings.json`** — durable, and shared with your team
  if committed. `.claude/settings.local.json` for yourself only.

One thing to rule out if a model choice appears to be ignored: an
`availableModels` allowlist. A value excluded by it **is not used and the
session keeps its current model**, silently. That looks identical to a pin that
did not hold.

## Acknowledgment

At DESIGN_READY the author must acknowledge the cumulative mechanical-edit
changelog before the decomposition is treated as final. **That acknowledgment is
the author's approval of the design PR** — the changelog, decomposition, and
advisory open items are written into a create-only
`<[paths].specs>/<slug>/review/ack-round-N.md` that ships *in* the PR, so the artifact the
author approves and the artifact that merges are the same commit. Reclassifying any
mechanical edit instead reopens the loop.

**Do not ask for an ack before opening the PR.** Acking a `design_hash` that the
pipeline then keeps editing is what forced `publisher-metrics` to ack twice: the
design moved 76 → 94 criteria and 14 → 15 tasks between `ack-round-29` and
`ack-round-32`, invalidating the first assent. Approval on the PR cannot drift from
what it approved.

## Adapter-Specific Invocation

- **Claude Code**: `/review-spec`, `/draft-plan`, `/spec-pipeline`
- **Codex**: `review-spec`, `draft-plan`, `spec-pipeline` skills

## Non-Goals (v1)

- Does not create Linear issues **for the task decomposition** — that stays
  copy-paste material after the design PR merges; full Linear MCP integration for it
  is v2. It *does* file advisory follow-up issues at gate close, which are a different
  thing: a bounded number of independently-schedulable items, not the epic's task
  graph. See [Dispositioning the advisories](#dispositioning-the-advisories).
- Does not review code, PRs, or already-decomposed tasks.
- No web research; grounded only in the spec, the architectural principles,
  and the repo.
- No multi-spec consistency review.
- DESIGN_READY is advisory: nothing technically prevents decomposing a
  NOT_READY spec. Enforcement is the author's responsibility in v1.
