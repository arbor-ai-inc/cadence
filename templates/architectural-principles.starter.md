# Architectural Principles — starter rubric

Guardrails that anchor engineering design toward implementable, evidence-driven
systems. These are the **shared, adapter-neutral** input to two reviews:

- **Gate 2 — Eng Design Review** of the
  [spec pipeline](agent-skills/spec-pipeline.md): a design
  (`specs/<slug>/design.md`) must state which principles it satisfies, and a
  principle violation is a review **BLOCKER** unless the design justifies the
  trade-off explicitly. See [How Gate 2 uses this doc](#how-gate-2-uses-this-doc).
- **Code review** of a diff before merge
  ([`agent-skills/code-review.md`](agent-skills/code-review.md)), against a
  narrower subset — see
  [How code review uses this doc](#how-code-review-uses-this-doc). Not every
  diff goes through the spec pipeline, so this is the only architectural check
  some changes get.

They are deliberately general — the *statement* is the durable intent. The
**In your codebase** lines are what make them usable: each one pins a principle
to a concrete pattern or a binding decision already proven in your system, so
the reviewer has something objective to check rather than re-deriving "good
architecture" every time. **Check** is the question the design reviewer asks;
**Violation** is a concrete counter-example.

> ## Read this before using the file
>
> **This is a starting point, not a rubric.** Twenty-six principles with the
> pinning lines unfilled will produce a Gate 2 review that grades a design
> against generalities, which is worse than no gate: it manufactures the
> appearance of architectural review.
>
> So do three things before pointing `[paths].principles` at it:
>
> 1. **Delete every principle your system does not actually hold.** A principle
>    nobody would enforce is one a design can violate with a shrug, and that
>    teaches an agent the whole file is advisory. Ten principles you mean beat
>    twenty-six you inherited.
> 2. **Fill in the `In your codebase` line for each survivor.** If you cannot
>    name something concrete this principle already governs, that is evidence for
>    step 1.
> 3. **Renumber, and expect it to break references.** Prose elsewhere cites these
>    by number and nothing validates that. If a design or a review round cites
>    `#12`, renumbering silently repoints it.
>
> The **Check** and **Violation** lines are portable as written and are the part
> worth keeping intact — they are what turns a principle into a question.

## How Gate 2 uses this doc

1. The design's **"Principles adherence"** section lists the principles it
   engages and, for each, one line on how it satisfies (or consciously trades
   off) it.
2. The `eng-design-reviewer` grades the design against every applicable
   principle. An unjustified violation is a **BLOCKER**; a justified trade-off
   is recorded as an advisory `MAJOR`.
3. Principles are guardrails, not a checklist to maximize — a design that
   over-engineers against a hypothetical (violating #1/#6/#16) fails just as a
   design that under-builds a durable boundary (violating #2/#8/#19) does.
4. **New internal components are graded the same way.** `design.md` §1 must say
   why existing infrastructure cannot serve each new component, abstraction,
   table or service. No answer is a **BLOCKER** (#4 / #6 / #12); an explicit
   answer clears the gate even if the reviewer doubts it — that doubt is an
   advisory `MAJOR` for the design PR to weigh. Same principle as (2): the gate
   checks that the decision was made and recorded, not that it was optimal.

## How code review uses this doc

Gate 2 grades a *design* against every principle; code review grades a *diff*,
which most cannot breach. So code review
([`agent-skills/code-review.md`](agent-skills/code-review.md)) uses a narrow
subset: what a diff can break cheaply now and expensively later.

| Principle | What the reviewer checks on a diff |
| --- | --- |
| **#8** Contracts as durable boundaries | Does the written payload match the shape the contract declares? Is a new discriminator, enum, or invariant inside the typed boundary its consumer dispatches on, or hidden in an untyped bag? Is a change to a persisted shape versioned? |
| **#8 §** [Cross-boundary endpoints](#cross-boundary-endpoints) — a sub-check of #8, not a separate principle; cite it as `#8 § Cross-boundary endpoints` | Does the diff mount, move, or retire a route one plane calls on another? If so, did the plane graph, the edge list, **both** plane boundary tables, and the component route table move with it? A route that is reachable but undocumented is a BLOCKER, not a docs nit |
| **#19** Data integrity | Still one writer per table? Are state transitions explicit — does a read-path view mutate the state of record? Can a legacy or partial record be read without crashing or rendering nonsense? |
| **#2 / #10 / #11** Boundaries, modular monolith, critical path | Does unvalidated authoring-side data reach the serving critical path? Is validation where the plane doc says it belongs? Is authoring-only data riding on a latency-sensitive response? |
| **#18** Safe path is the easy path | Does the standard path produce a correct result by default, or does correctness depend on the author remembering a step? Any new unauthenticated mount or hand-rolled auth/account filtering? |
| **#4 / #12** Earned abstractions, thin foundations | At N=2, is the shared part actually factored, or is the trivial part extracted while the duplicated part is copy-pasted? Does this add a *third* parallel way to do something the repo already has two conventions for? |
| **#5** Deterministic core | Is non-determinism entering a path that must be reproducible? |
| **#26** Text is a maintenance commitment | Does the diff restate a fact with a canonical home, or push an artifact further over its ceiling unwaived? |
| **#15 / #14** Observable behavior, journey completeness | Does the change add customer-affecting behavior that nothing measures or nothing surfaces? A new outcome merged into an existing count so the customer cannot tell the two apart is a **wrong number**, not a missing feature. A capability reachable only by API, with no console surface, is invisible to the person it was built for — name the gap and let the author scope it or file it |
| **#22 / #23** Understandability, recorded decisions | Can the next engineer trace the touched flow from docs + code? Is a load-bearing decision made in this diff recorded anywhere? |

Two things follow from this being a *diff* review, not a design review:

- **A principle violation here is a BLOCKER only when it is load-bearing.** Gate
  2 can reject a design outright; code review cannot hold a PR hostage to a
  principle the change merely brushes against. Cite a principle when its
  **Check** question fails and the failure has a concrete consequence — name the
  consequence.
- **A missing `design.md` is itself a finding.** If a diff makes an
  architectural decision that never went through Gate 2, there is no recorded
  justification for the reviewer to weigh a violation against. Say so, rather
  than silently grading the diff as if the decision had been reviewed.

## Cross-boundary endpoints

A **cross-boundary endpoint** is any interface a component in one plane calls on a
component in another: an HTTP route, an RPC, a queue topic another plane drains,
or a table another plane reads directly. The test is **who calls it**, not where
it is defined — `POST /crawl` is implemented in the Serving plane but exists
because Platform jobs call it, and that is what makes it an edge.

The edges that exist today are enumerated in
[`your contract set: README.md`](../contracts/README.md#the-five-cross-boundary-boundary-contracts)
and drawn in [the plane graph](../architecture/README.md#plane-dependency-graph).
Adding one is an architectural decision, not a routing detail.

### Why this needs its own section

An audit of every exposed route against the docs (2026-07-27) found that two of
the six edges — *snapshot source* and *ingestion status* — existed only in the
plane docs, while `contracts/README.md` asserted "exactly four labelled edges"
and the graph drew five. It also found a component route table missing an
endpoint that its own plane doc documented.

Nobody introduced a wrong edge. Each author updated the doc nearest their
change, and no single doc owned the whole set. The failure mode is not
carelessness — it is that **the artifacts which must agree live in four
different files**, and a diff can satisfy any one of them while leaving the
others stale.

### The rule

A change that adds, removes, or repoints a cross-boundary endpoint updates **all**
of the following, in the same PR:

| # | Artifact | What changes |
|---|---|---|
| 1 | your architecture overview's boundary diagram | The labelled edge, **and** any count in the sentence beneath it |
| 2 | `your contract set: README.md` — enumerated edge list | A row: direction, and what pins the shape (a schema file, or the doc holding it in prose) |
| 3 | Both plane docs' *Boundary contracts* tables | The **producer** side and the **consumer** side. An edge listed on one side only is exactly the defect the audit found |
| 4 | The component doc's route table | The endpoint itself — method, path, auth/min role, purpose |
| 5 | The contract file, plus whatever set your gate checks | Only if the payload has a schema file. **Having no schema file is not an exemption** — two of the five edges are pinned in prose, and prose still has to change |

### Check

Asked at Gate 2 of a design, and on any diff that mounts or moves a route:

- Does this introduce a call from one plane into another? If so, is it a **new**
  edge, or does it ride an existing one? Riding an existing edge is the
  preferred answer and needs no graph change — but say so explicitly rather than
  leaving a reviewer to infer it.
- Are the producer and the consumer both named, in both plane docs?
- If the endpoint has no schema file, which doc pins its shape — and did that
  doc change?
- Is the endpoint's auth posture stated? A cross-boundary caller is a service
  identity, not a logged-in user, and that distinction belongs in the route
  table.

**Violation:** a route mounted in one plane and called from another, with the
route table and the graph untouched — reachable in production, invisible in the
architecture.

## Themes (index)

- **Learning & scope discipline:** 1, 3, 4, 6, 16
- **Boundaries & contracts:** 2, 8, 10, 11
- **Correctness & data integrity:** 5, 19
- **Reliability & operations:** 7, 9, 17, 20, 25
- **Safety & foundations:** 12, 18, 21
- **Customer & evidence orientation:** 13, 14, 15, 24
- **Understandability & stewardship:** 22, 23, 26

---

## 1. Optimize for learning before scale

Architecture should help the team test assumptions, observe user behavior, and
change direction quickly. Do not build for hypothetical scale until real usage,
customer commitments, or measurable bottlenecks justify it.

- **In your codebase:** _<name one concrete pattern or decision in your system that this principle already governs — the thing a reviewer can point at. Delete this principle if nothing here does.>_
- **Check:** does the design justify each scale-oriented component with real
  usage, a customer commitment, or a measured bottleneck — or a hypothetical?
- **Violation:** provisioning BigQuery + GCS + managed subscriptions before any
  event volume needs them (the rev-1 → rev-2 unwind).

## 2. Start simple, but keep boundaries clear

Prefer the simplest design that can reliably solve the current problem.
Simplicity does not mean putting everything everywhere. Maintain clear
ownership, interfaces, and separation between major business capabilities so
the system can evolve without a full rewrite.

- **In your codebase:** _<name one concrete pattern or decision in your system that this principle already governs — the thing a reviewer can point at. Delete this principle if nothing here does.>_
- **Check:** are ownership and interfaces between capabilities explicit? Can a
  capability change without editing another plane's internals?
- **Check:** **does each control live on the axis of the thing it controls?** Ask
  what the control actually varies with. If the answer is not the subsystem
  holding it, the control is in the wrong place — no matter how naturally it
  arrived there.
- **Violation:** a component reaching across a boundary edge directly (see #11).
- **Violation:** answering an adjacent question with the unit you happen to be
  holding. The format catalog grew a per-format activation lifecycle *and*
  per-format billing gates because "format" was the unit in hand — but nothing
  about billing varies by format (serving a `chat` unit and a `quote` unit raise
  the identical question), and what actually varied was **environment** and
  **account**. Caught in human review on #427; recorded as a binding decision. The tell is a
  control that must be re-decided identically for every new instance of the
  subsystem.

## 3. Build vertical slices before horizontal platforms

Deliver complete user or customer outcomes end to end before investing heavily
in generalized infrastructure. Extract horizontal capabilities only after
repeated use cases reveal a stable pattern.

- **Check:** does this deliver an end-to-end outcome, or is it a generalized
  platform ahead of a second consumer?
- **Violation:** building a shared "events platform" before a single reporting
  read path exists to consume it.

## 4. Earn abstractions through repetition

Do not generalize based on the first implementation. Build the first use case
directly, observe the second, and abstract when the common behavior and
meaningful differences are understood.

- **Check:** is a new abstraction backed by ≥2 concrete uses whose commonality
  and differences are understood?
- **Violation:** a plugin/strategy framework introduced for exactly one
  implementation.

## 5. Keep the core deterministic

Business-critical behavior such as eligibility, pricing, permissions,
budgeting, state transitions, and policy enforcement should be explicit,
testable, and reproducible. Use AI or probabilistic systems where they improve
the experience, but not where correctness requires predictable outcomes.

- **In your codebase:** _<name one concrete pattern or decision in your system that this principle already governs — the thing a reviewer can point at. Delete this principle if nothing here does.>_
- **Check:** is every correctness-critical decision deterministic and covered by
  a test that pins exact outputs?
- **Violation:** letting a probabilistic component decide budget enforcement or
  access control.

## 6. Design for change, not every possible future

Create systems that are easy to modify rather than systems that attempt to
anticipate every future requirement. Stable contracts, modular components,
feature flags, and reversible decisions usually provide more value than
extensive upfront flexibility.

- **Check:** does flexibility target *ease of change* (modularity, flags) rather
  than *predicting requirements* (speculative config surface)?
- **Violation:** a deeply parameterized config system for requirements nobody
  has asked for.

## 7. Prefer reversible decisions

Make early architectural choices easy to undo. Avoid deep vendor coupling,
irreversible data models, and broad shared dependencies unless the benefits
clearly outweigh the loss of flexibility.

- **In your codebase:** _<name one concrete pattern or decision in your system that this principle already governs — the thing a reviewer can point at. Delete this principle if nothing here does.>_
- **Check:** if this choice is wrong, what's the cost to reverse it? Is any
  vendor/data-model lock-in called out and justified?
- **Violation:** making a third-party warehouse the system of record, so leaving
  it requires re-modeling all durable data.

## 8. Treat APIs and contracts as durable boundaries

Internal and external contracts should be explicit, versioned when necessary,
and independently testable. Implementation details may change frequently;
contracts should change deliberately.

- **In your codebase:** _<name one concrete pattern or decision in your system that this principle already governs — the thing a reviewer can point at. Delete this principle if nothing here does.>_
- **Check:** is every cross-component interface an explicit, testable contract
  with a producer and consumer named? Is a breaking change versioned? If the
  interface crosses a **plane** edge, the stricter checklist in
  [Cross-boundary endpoints](#cross-boundary-endpoints) applies.
- **Violation:** consumers depending on an undocumented message shape that the
  producer can change silently.

## 9. Keep operational complexity proportional to team size

Every service, database, queue, framework, and deployment model introduces
ongoing cost. Choose technology based not only on what it can do, but also on
whether the team can understand, operate, debug, and recover it.

- **In your codebase:** _<name one concrete pattern or decision in your system that this principle already governs — the thing a reviewer can point at. Delete this principle if nothing here does.>_
- **Check:** does each new moving part (service/queue/store) earn its operational
  cost? Can the team debug and recover it?
- **Violation:** adding a warehouse + object store + two managed subscriptions a
  small team must now monitor, for volume a single table handles.

## 10. Default to a modular monolith

Begin with one deployable system unless there is a strong reason not to.
Separate modules by business capability and ownership. Move to independent
services when scaling, reliability, security, or organizational needs make the
additional complexity worthwhile.

- **In your codebase:** _<name one concrete pattern or decision in your system that this principle already governs — the thing a reviewer can point at. Delete this principle if nothing here does.>_
- **Check:** is a new service justified by scaling/reliability/security/org need,
  or would a module in an existing deployable do?
- **Violation:** standing up a separate reporting service when a router + offline
  job in the existing deployables suffices.

## 11. Separate the critical path from everything else

Keep latency-sensitive and customer-facing paths small, predictable, and
resilient. Move reporting, enrichment, experimentation analysis, notifications,
and other non-critical work to asynchronous or offline processing where
appropriate.

- **In your codebase:** _<name one concrete pattern or decision in your system that this principle already governs — the thing a reviewer can point at. Delete this principle if nothing here does.>_
- **Check:** is non-critical work kept off the latency-sensitive path? Does a
  failure in it degrade gracefully rather than breaking the customer path?
- **Violation:** the retired serving-plane Go rollup job — synchronous reporting
  writes coupled into the serving tree (a plane-boundary breach *and* critical-
  path contamination).

## 12. Build foundational capabilities thinly

Invest early in a small number of horizontal foundations such as identity,
configuration, observability, auditability, experimentation, deployment, and
data contracts. Keep each foundation narrow and practical rather than turning it
into an internal platform project.

- **Check:** is a foundation being built to the *current* need, or expanded into
  a speculative internal platform?
- **Violation:** a general-purpose experimentation framework when one A/B toggle
  is required.

## 13. Make customer impact the architecture metric

Technology exists to improve customer experience, product quality, reliability,
and the team's ability to respond. Architectural sophistication has little value
unless it produces a better customer outcome or materially lowers operational
cost.

- **Check:** does the design tie back to a customer outcome or an operational-cost
  reduction in the product spec? Is sophistication that does neither trimmed?
- **Violation:** a technically elegant redesign with no user-visible or cost
  effect.

## 14. Design from the user journey backward

Start with what the user is trying to accomplish, then define the product
behavior, data flow, reliability needs, and system boundaries. Avoid allowing
technology choices to dictate the customer experience.

- **In your codebase:** _<name one concrete pattern or decision in your system that this principle already governs — the thing a reviewer can point at. Delete this principle if nothing here does.>_
- **Check:** does the design derive from the Gate-1 product spec's user journey,
  not from a preferred technology?
- **Violation:** choosing a datastore first, then reshaping the user-facing
  behavior to fit it.

## 15. Make important customer behavior observable

Instrument the product around user journeys, conversion points, failures,
latency, quality, and retention. Architecture decisions should be informed by
evidence rather than intuition alone.

- **In your codebase:** _<name one concrete pattern or decision in your system that this principle already governs — the thing a reviewer can point at. Delete this principle if nothing here does.>_
- **Check:** are the journeys, failures, and latencies this change touches
  instrumented? Can we later tell whether it worked?
- **Violation:** shipping a flow with no metric or log to confirm it succeeds.

## 16. Measure before optimizing

Establish baselines before introducing caches, queues, sharding, specialized
storage, or complex distributed designs. Optimize the bottleneck that exists,
not the one the team imagines.

- **In your codebase:** _<name one concrete pattern or decision in your system that this principle already governs — the thing a reviewer can point at. Delete this principle if nothing here does.>_
- **Check:** is each optimization backed by a baseline/measurement, with the
  trigger to escalate stated?
- **Violation:** adding sharding or a cache with no measured bottleneck.

## 17. Reliability is part of the product

Failures should be anticipated, detected, and recoverable. Favor graceful
degradation, idempotency, bounded retries, clear timeouts, safe fallbacks, and
operational visibility over attempting to eliminate every possible failure.

- **In your codebase:** _<name one concrete pattern or decision in your system that this principle already governs — the thing a reviewer can point at. Delete this principle if nothing here does.>_
- **Check:** are failure modes named with detection + recovery? Is re-running
  safe (idempotent)? Are retries/timeouts bounded?
- **Violation:** an additive (non-idempotent) load that double-counts on retry
  — the exact R5 bug the 4-col-PK overwrite fixes.

## 18. Make the safe path the easy path

Security, privacy, access control, auditability, testing, and deployment safety
should be built into common workflows. Engineers should not need exceptional
discipline to avoid common mistakes.

- **In your codebase:** _<name one concrete pattern or decision in your system that this principle already governs — the thing a reviewer can point at. Delete this principle if nothing here does.>_
- **Check:** does the safe choice (auth, scoping, migration safety) come for free
  from the standard pattern, or does it rely on the author remembering?
- **Violation:** a new unauthenticated mount, or hand-rolled account filtering
  that diverges from the shared dependency.
- **Count the mechanisms defending a convenience.** T-08's guard first shipped
  with an escape hatch so local dev could run with zero config — which then needed
  a `K_SERVICE` check to stop the hatch working on a deployed service, and a
  warning log to make the hatch observable. Three mechanisms protecting a
  convenience nobody had asked for. **When a hatch needs its own guards, the hatch
  is the defect**: delete it and give the value one source per environment.

  **Scope:** this applies to **secrets and other security-critical values** —
  signing keys, credentials, tokens, anything whose knowledge confers authority.
  For those, a committed fallback is a value an attacker can also compute, so it
  is not a default but a published key. Ordinary defaults (a timeout, a page size,
  a log level) are fine and often good; the distinguishing question is *what does
  knowing this value let someone do?* **Permitted alternative:** where zero-config
  local dev genuinely matters, generate a random value per process rather than
  committing a constant — that keeps the convenience without publishing a key.
  **Assumes** one secret store per environment, which `_platform_up.sh` provides.
  **Revisit if** a deployment target has no secret store, which would need a
  different answer than a fallback.

## 19. Preserve data integrity over implementation convenience

Define ownership of important data, maintain clear source-of-truth systems, and
make state transitions explicit. Avoid duplicating mutable state without a
defined consistency and reconciliation model.

- **In your codebase:** _<name one concrete pattern or decision in your system that this principle already governs — the thing a reviewer can point at. Delete this principle if nothing here does.>_
- **Check:** does each important table have exactly one writer / source of truth?
  If state is duplicated, is the reconciliation model defined? Is any state the code
  repairs on read one the schema could have refused on write?
- **Violation:** two processes writing the same rollup (the pre-retirement Go job
  + the offline job), with no defined reconciliation.

## 20. Prefer boring technology for the foundation

Use well-understood tools for databases, networking, deployment, and critical
infrastructure. Introduce newer or specialized technology where it creates a
meaningful product advantage, not merely because it is technically interesting.

- **In your codebase:** _<name one concrete pattern or decision in your system that this principle already governs — the thing a reviewer can point at. Delete this principle if nothing here does.>_
- **Check:** is any new/specialized technology justified by a product advantage,
  and is the boring option ruled out for a stated reason?
- **Violation:** a specialized store chosen for novelty where Postgres meets the
  requirement.

## 21. Automate recurring friction, not hypothetical work

Automate tasks that are frequent, error-prone, or slowing delivery. Avoid
building elaborate internal tooling before the workflow and requirements have
stabilized.

- **Check:** does automation target a frequent/error-prone task with a stable
  workflow, or a speculative one?
- **Violation:** an elaborate internal tool for a workflow that has run twice.

## 22. Make systems understandable

An engineer should be able to trace a customer request, identify ownership,
understand major state transitions, and debug failures without needing
institutional knowledge from one person.

- **In your codebase:** _<name one concrete pattern or decision in your system that this principle already governs — the thing a reviewer can point at. Delete this principle if nothing here does.>_
- **Check:** can a new engineer trace the touched flow, find its owner, and debug
  it from the docs + code alone?
- **Violation:** a data path whose behavior lives only in one person's head or an
  undocumented script.

## 23. Document decisions, not everything

Capture important architectural choices, assumptions, trade-offs, alternatives,
and conditions that would cause the decision to be revisited. Keep documentation
close to the code and update it when the decision changes.

- **In your codebase:** _<name one concrete pattern or decision in your system that this principle already governs — the thing a reviewer can point at. Delete this principle if nothing here does.>_
- **Check:** are the load-bearing decisions (with alternatives + revisit
  conditions) recorded, rather than every implementation detail?
- **Violation:** exhaustive prose docs for trivia while the key trade-off and its
  revisit trigger go unrecorded.

## 24. Revisit architecture based on evidence

Architecture is not a one-time design exercise. Review major choices when
customer needs, traffic, reliability requirements, team structure, or
operational cost materially change.

- **In your codebase:** _<name one concrete pattern or decision in your system that this principle already governs — the thing a reviewer can point at. Delete this principle if nothing here does.>_
- **Check:** does each major decision state the evidence/conditions that would
  cause it to be revisited?
- **Violation:** a "final" decision with no stated trigger for reconsideration.

## 25. Pay the computation cost once, not on every read

For frequently read data, move durable transformations and aggregations to
write-time, asynchronous processing, or offline computation. Keep read paths
simple, fast, and predictable, while making derived data rebuildable and its
freshness explicit.

- **In your codebase:** _<name one concrete pattern or decision in your system that this principle already governs — the thing a reviewer can point at. Delete this principle if nothing here does.>_
- **Check:** for a frequently read path, is expensive
  transformation/aggregation done at write/offline time rather than per read? Is
  the derived data rebuildable, and is its freshness (staleness window) explicit?
  Conversely — does the design **materialize** a value it could derive cheaply,
  and if so, what measured read cost justifies the column?
- **Violation:** computing per-campaign aggregates by joining creatives →
  line_items → campaigns on every reporting page load, instead of
  precomputing/denormalizing them onto the rollup.
- **Violation (converse):** storing a column whose value is a subtraction of two
  columns beside it, with no measured read cost to justify it — paying a column,
  a write path and a drift risk to save an operator.

## 26. Text is a maintenance commitment

Every sentence is a thing that can go stale. Prefer **one canonical home per
fact**; everywhere else links to it. Length is a promise to keep something
accurate, so write the shortest version that survives being read alone.

Per-category ceilings — a trigger, not a wall. Exceed one by saying why on a
`**Long-form**: <reason> — <why>` line, both halves required, directly below the
title.

**The rule is diff-checkable, not date-based: a change must not push an artifact
further over its ceiling.** Under it a new artifact must land inside; an existing
one over the line is grandfathered and may be edited freely, but not grown. That
is answerable from the diff alone — no one has to know when a section was
written, which the corpus does not record anyway.

| Artifact | Path | Ceiling |
| --- | --- | --- |
| Decision entry | your decision log | 100 words |
| Product spec | `specs/*/product.md` | owned by [`specs/_product_template.md`](../../specs/_product_template.md), which measures it against shipped specs |
| Design doc | `specs/*/design.md` | 2,500 words (~5 pages) |
| Proposal | `docs/proposals/*.md` | 1,500 words (~3 pages) |
| Reference-doc *section* | `docs/engineering/**.md` | 400 words |
| Code comment | anywhere | no number — see below |

- **In your codebase:** _<name one concrete pattern or decision in your system that this principle already governs — the thing a reviewer can point at. Delete this principle if nothing here does.>_
- **Check:** could this be half as long? Does it restate a fact that already has
  a canonical home?
- **Violation:** the same fact stated in three files; a rule buried under its own
  justification; worked examples that go stale before the rule they support;
  a comment narrating the line beneath it. Related: [#23](#23-document-decisions-not-everything)
  governs *what* to record — this governs how much, and in how many places.
