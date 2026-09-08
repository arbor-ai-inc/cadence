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

## Setup

### 1. Install the plugin

```bash
/plugin marketplace add arbor-ai-inc/cadence
/plugin install cadence@cadence
```

Nothing is configured yet, and it already works. Try the router:

```
/cadence:using-agent-skills
```

The defaults assume git and GitHub, no issue tracker, and asking questions in
the current session — **no credentials, no config file.** Everything below is
opt-in, in the order it pays off.

### 2. Tell it how your project lints and tests

Copy [`templates/cadence.toml`](templates/cadence.toml) to your repository root
and set two keys:

```toml
[commands]
lint = "pre-commit run --all-files"   # whatever yours is, in full
test = "pytest"
```

Cadence runs these verbatim, so put the whole incantation in — venv activation,
env vars, workspace filters. Workflows refer to *"the lint command"* and never
hardcode one. Check what is in effect with:

```bash
python3 tools/cadence_config.py
```

A missing `cadence.toml` is fine. A malformed one raises rather than falling back
to defaults, because silently running on defaults when you wrote a config is how
a safety boundary stops being enforced.

### 3. Start the retro ledger

> `<plugin>` below is wherever the plugin installed — under
> `~/.claude/plugins/`. `${CLAUDE_PLUGIN_ROOT}` resolves inside a skill but not
> in your shell, so copy the path once from `/plugin list`.


This is the highest-value thing here and it takes one command:

```bash
mkdir -p docs/retros/pending docs/retros/archive
touch docs/retros/pending/.gitkeep docs/retros/archive/.gitkeep
cp <plugin>/templates/TRAPS.md docs/retros/
cp <plugin>/templates/_fragment_template.md docs/retros/
```

From now on every PR leaves one fragment naming what it taught. At 15 fragments,
run `/cadence:retro-synthesis`. **Write no rules before then** — that judgement
is exactly what the count table exists to overrule.

### 4. Before you let it run unattended: the must-stop boundary

`/cadence:execute-issue` will branch, implement, review and open a PR without
you. **Set the boundary before you use it**, because that is what makes the
autonomy safe rather than fast:

```toml
[[must_stop]]
path = "db/migrations/"
reason = "a schema migration"

[[must_stop]]
path = "src/billing/"
reason = "money-bearing logic"
```

These are the surfaces where an agent must **stop and ask** — never decide,
never fan out. Only you know where yours are, so cadence ships none, and **an
empty boundary means an autonomous run will never stop for a human.**

`path` ending in `/` covers that directory and everything under it; without a
trailing slash it is an exact file. `reason` is required — it is what the agent
shows you when it stops.

Then enforce it, which is the part that matters:

```bash
# as a pre-commit hook
python3 <plugin>/tools/fanout.py check-scope
```

That hook is derived from git, not from a rule in a prompt, so no reasoning
inside a run gets past it. **Absent enforcement and working enforcement look
identical from inside a run**, which is why `fanout.py init` warns when the hook
is missing.

### 5. Optional: the rest

| Want | Set | Notes |
|---|---|---|
| An issue tracker | `[tracker].provider` | `linear`, `github`, or `none` (body passed inline) |
| Unattended runs | `[ask].provider = "slack"` | needs a bot token; otherwise questions come to your session |
| An automated PR reviewer | `[review].provider` | `coderabbit`, `codex`, `subagent`, or `none` |
| The spec pipeline | `[paths].principles` | Gate 2 grades against this file and nothing else — write it first, from [the starter](templates/architectural-principles.starter.md) |
| Approval policy | `[paths].review_standards` | who signs off, what blocks a merge — from [the template](templates/code-review-standards.template.md) |

Full reference: [`docs/configuration.md`](docs/configuration.md). Adoption order
and what to expect: [`docs/getting-started.md`](docs/getting-started.md).
Different stack: [`docs/porting.md`](docs/porting.md).

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

## Layout

```
reference/     the canonical workflows — the substance
skills/        thin Claude Code adapters that route to them
agents/        subagent definitions (reviewers, editor)
adapters/codex/  the same adapters for Codex, generated
tools/         fanout, spec hashing, ask transport, review state
templates/     cadence.toml, spec templates, the retro ledger, a principles
               rubric, a review-policy template, a tools inventory stub
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
