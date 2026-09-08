# Engineering Design: <FEATURE NAME>

> Gate 2 artifact. Drafted by the pipeline (or `/cadence:spec`) from the
> PRODUCT_READY `product.md`, using the rubric at `[paths].principles` as
> guardrails. The eng-design-reviewer returns NOT_READY on unjustified
> principle violations, subjective acceptance criteria, or a decomposition that
> is not agent-ready. This file is `<[paths].specs>/<slug>/design.md`.

<!-- design drafted by /draft-plan, <date> — subject to Gate 2 review -->

## 1. Architecture
- **Files to create / touch:** <paths>
- **Interfaces / APIs:** <routes, function signatures, events, contracts>
- **Data model:** <tables, schemas, types — or "none">
- **Dependencies:** <libraries / services; explicitly flag any NEW external dependency>
- **Reuses:** <the already-built components, tables, endpoints and contracts this
  design stands on and does not change — or "none". Names what the reviewer would
  otherwise re-derive from the codebase every round.>
- **New components — why existing infrastructure cannot serve them:** <"none", or
  one line per NEW internal component, abstraction, table or service: the existing
  thing considered, and why it does not fit. Required whenever this design adds
  one; Gate 2 treats silence as a BLOCKER. A stated justification is accepted at
  Gate 2 and weighed on the design PR — see below.>
- **Cross-boundary endpoints:** <"none", or "rides the existing <name> edge", or
  a NEW edge — see below. Required whenever the **Interfaces / APIs** row names a
  route, RPC, or topic; Gate 2 treats silence as a BLOCKER.>

> **New internal components.** A new component with no justification is a BLOCKER
> (principles #4 / #6 / #12: abstractions are earned through repetition, not
> anticipated). An **explicit** justification is good enough for Gate 2 — the
> reviewer may record an advisory MAJOR against it but not a blocker, and the design
> PR reviewer weighs whether the reasoning holds. This mirrors how a stated
> principle trade-off is graded (§2).
>
> **A new file is not a new component.** One more router beside its siblings, one
> more schema in `schemas.py`, one more job in an existing runner — that is the
> existing pattern being used, and it needs no justification. What does: a new
> table, service, queue, cache, store, provider seam, or shared abstraction — a
> thing future code will have to route around or conform to.

> **New cross-boundary edge only.** Fill this in if any interface above is
> called by a component on the far side of one of your architecture's declared
> boundaries — whatever you call them: planes, services, bounded contexts,
> packages. Riding an existing edge needs no table; just say which one.
>
> **Define your boundaries in `[paths].principles`, or delete this row.** A
> boundary nobody wrote down is a boundary nobody can be found to have crossed,
> and the row then costs a line per design and catches nothing.

| Direction | Producer | Consumer | Shape pinned by | Docs updated by this work |
|---|---|---|---|---|
| <side → side> | <component> | <component> | <schema file, or the doc holding it in prose> | <which architecture docs this change must update> |

## 2. Principles adherence
> For every architectural principle this design engages, state how it is
> satisfied — or, if it is knowingly traded off, why the trade-off is justified
> (a justified trade-off is an advisory MAJOR; an unjustified violation is a
> BLOCKER). Reference principles by number from your `[paths].principles`
> rubric. **Only principles this design actually engages** — a padded table is
> a checklist nobody reads, not evidence.

| Principle | How this design satisfies it (or justified trade-off) |
|---|---|
| #<n> <name> | <one line> |

## 3. Component-level changes
<Per service / module: what changes and why.>

## 4. Data model / contract changes
<Migrations, schemas, message/contract diffs — or "none". Name the contract
files touched.>

## 5. Acceptance criteria (machine-checkable)
> Each item MUST be verifiable by an automated test or a single command, and
> map to a requirement (Rn) from product.md. Banned: "works well", "fast
> enough", "looks right".
- [ ] **AC-R1** <how R1 is proven — test or command>
- [ ] **AC-R2** <how R2 is proven>

**Validation plan (non-automated).** <"none" — the default — or, for a requirement
whose correctness no test or command can establish, how it will be validated instead
**and why a test cannot prove it**. This is not part of the AC set above and does not
relax the machine-checkable rule for anything a test *could* cover; it exists so a
requirement that depends on real-world ground truth has a home other than a subjective
AC. Every Rn must map to an AC or to an entry here.>

## 6. Edge cases & invariants
<The load-bearing invariants and the tricky cases the implementation must
honor.>

## 7. Task decomposition
> Every task: independent acceptance criteria, declared dependencies, and
> single-session scope (one PR, no context compaction). This list is the
> outcome — the tasks to implement.

| Task | Scope | Depends on |
|---|---|---|
| T1 | <scope> | — |

**Order:** <e.g. T1 ∥ T2 → T3>

## 8. Deferred — not in this design
> Engineering scope deliberately left out, so a missing capability reads as a decision
> rather than an omission the reviewer has to raise. Distinct from `product.md`
> § *Non-goals*, which bounds the **product**: this bounds the **build**.
>
> No entry here may cover a requirement (Rn) that `product.md` states. Deferring an Rn
> is a product-scope change, not a design decision — it re-opens Gate 1.

- <capability> — <why not yet, and what would bring it forward>

## 9. Stop-and-Ask Triggers
> The executing agent must PAUSE and ask a human before ANY of these — it may
> not decide them and may not fan out on them. Edit per feature.
>
> **The enforced boundary is `[[must_stop]]` in `cadence.toml`, not this list.**
> This section is the feature-specific addition to it; the path-based entries in
> the config are what the fan-out engine actually refuses on. If a trigger here
> is durable rather than specific to this feature, it belongs in the config.
- Introducing a NEW external dependency, library, or service
- Schema / database migrations
- Auth, permissions, or security-boundary changes
- Anything touching billing, payments, or money
- Public API contract changes
- <feature-specific trigger>
