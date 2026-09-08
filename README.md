# Cadence

Agent workflows for autonomous software development, as a Claude Code plugin.

Cadence is the workflow system Arbor AI uses to have coding agents pick up an
issue, build it, review it adversarially, and open a pull request — without a
human in the loop until a decision genuinely needs one. It was extracted from a
production codebase after roughly forty tickets had run through it.

**Every rule here exists because something went wrong, and the ones that cite a
case cite a measurement.** That is the main thing that distinguishes it from a
set of opinions about process. Several of these rules were argued down during
review and are narrower than their first draft; a few say plainly that they are
a known gap rather than a solved problem.

## Install

```bash
/plugin marketplace add arbor-ai-inc/cadence
/plugin install cadence@cadence
```

Then read [`docs/getting-started.md`](docs/getting-started.md). Nothing needs
configuring to try it — the defaults assume GitHub, no issue tracker, and asking
questions in-session, which needs no credentials.

## What is in it

Four things that work together and are separately useful.

### A recurrence-gated retro loop

Start here. Every pull request leaves a fragment naming what it taught. **Nothing
becomes a rule until a trap has recurred**, and a trap that recurs *after* a rule
was written is treated as evidence the rule does not fire — so it gets mechanized
as a check rather than reworded.

That gate is not a preference. Writing rules one ticket at a time was measured
over twelve consecutive retros and failed three ways at once: rules generalized
from single occurrences (one of which *would not have caught the bug that
produced it*), guidance documents that tripled in ten weeks until nobody
finished reading them, and a per-retro cost high enough that it ran on one issue
in four. See [`examples/case-studies.md`](examples/case-studies.md).

### An issue-execution loop

One issue per invocation: branch, implement, lint, test, drive an adversarial
review to LGTM, open a PR. **It never merges** — that stays a human decision, and
it holds even when a prompt pre-authorises it.

It treats an issue's own factual claims as premises to verify rather than
findings. Counts, file lists, quoted rules and named identifiers in a ticket are
wrong often enough that eleven tickets built on a bad one before the rule
existed.

### Decision fan-out

When an autonomous run reaches a decision with more than one defensible answer,
it builds **every option in its own git worktree**, records the trade-offs, and
keeps going — instead of stalling on a question nobody is awake to answer.

Deliberately capped: the combinatorics break before the token cost does. And it
refuses outright at the must-stop boundary, because N variants of a schema change
multiply reviewers rather than options. That refusal is enforced by a commit hook
derived from git, not by a rule in a prompt.

### A two-gate spec pipeline

Product intent is reviewed to `PRODUCT_READY` and **merged as its own pull
request** before any engineering design exists. The design is then graded against
a rubric you supply. Each artifact is hash-frozen at its first `READY` verdict, so
a spec cannot drift out from under the review that approved it.

## Configuration

One file at your repo root. [`templates/cadence.toml`](templates/cadence.toml)
documents every key; [`docs/configuration.md`](docs/configuration.md) explains
the choices that matter.

Issue tracker, human-ask transport and automated reviewer are pluggable, with
zero-setup fallbacks for each. The one section with no useful default is
`[[must_stop]]` — the surfaces where an agent must stop and ask. Only you know
where those are, and **an empty boundary means an autonomous run will never stop
for a human.**

## Layout

```
reference/     the canonical workflows — the substance
skills/        thin Claude Code adapters that route to them
agents/        subagent definitions (reviewers, editor)
adapters/codex/  the same adapters for Codex, generated
tools/         fanout, spec hashing, ask transport, review state
templates/     cadence.toml, spec templates, the retro ledger, a principles rubric
examples/      the measurements the rules cite
evals/         graded cases pinning four rules an agent has reason to break
tests/         the gates
```

The two-layer split is load-bearing rather than tidy: a 900-line workflow doc
cannot sit in every session's context, and a rule that exists in two places has
already started to drift.

## Verifying it

```bash
python3 tests/check_no_leaks.py           # nothing private survived the extraction
python3 tools/cadence_config.py --selftest
python3 tools/spec_hash.py --selftest
python3 tools/ask.py --selftest
python3 tools/review_state.py             # self-test
python3 scripts/gen_adapters.py --check
python3 tests/check_agent_skills.py
python3 tests/check_fanout.py             # 69 tests over real git worktrees
claude plugin validate ./
```

Each of those has been shown to fail, not just to pass. `check_fanout.py` is
mutation-tested against the boundary matcher; breaking it fails 14 tests.

## Contributing

Read [`reference/skill-anatomy.md`](reference/skill-anatomy.md) first. Two rules
that catch most first attempts: **never pin `model:`** in anything shipped, and
**never edit a generated adapter** — edit its source and regenerate.

If a rule here is wrong for your project, that is expected: put the correction in
your own repo, per
[`retro-synthesis`](reference/retro-synthesis.md) § *Workflow* step 6. A local
edit to `reference/` is silently reverted by the next plugin update.

## Licence

Apache 2.0. See [`LICENSE`](LICENSE) and [`NOTICE`](NOTICE).
