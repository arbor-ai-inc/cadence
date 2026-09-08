# Getting started

Cadence is a set of workflows, not a framework. You can adopt one and ignore the
rest, and the order below is the one that pays off soonest.

## Install

```bash
/plugin marketplace add arbor-ai-inc/cadence
/plugin install cadence@cadence
```

Nothing is configured yet, and that is fine — the defaults need no credentials.
Try the router first:

```
/cadence:using-agent-skills
```

## Day one: the retro loop

Start here even if you never adopt anything else. It is the piece with no public
equivalent, and it costs almost nothing per ticket.

1. Run `/cadence:init`. That creates `cadence.toml` and the retro ledger, and
   never overwrites anything that already exists.
2. Set `[commands].lint` and `[commands].test` in `cadence.toml`. Two lines.
3. From now on, every pull request leaves one fragment in
   `docs/retros/pending/` naming what it taught. That is it — no rules, no
   judgement, just an observation and what it cost.
4. When `pending/` reaches 15, run `/cadence:retro-synthesis`.

**Do not write rules before then**, however obvious a lesson feels. That
judgement is exactly what the count table exists to overrule; it felt obvious the
last seven times too. See
[`C-01` through `C-06`](../examples/case-studies.md#the-argument-for-batching)
for the measurements behind that.

## Day two: the review loop

`/cadence:code-review` before the PR, `/cadence:git-pr-workflow` after it.

Set `[review].provider`. If you have no automated reviewer, `subagent` gives you
an adversarial pass with fresh context — never the context that wrote the change,
which is most of where the value is.

The rule worth internalising immediately: **a passing check row can mean the
reviewer never ran.** Read `./.cadence/cadence review-state --pr <n>` instead.

## Day three: autonomous execution

This is the one with a prerequisite. `/cadence:execute-issue` will branch,
implement, review, and open a PR without you — which means the boundary matters
before the autonomy does.

**Fill in `[[must_stop]]` first**, and install the scope hook:

```
/cadence:init --hook
```

writes `.cadence/check-scope`. Point your hook runner at that stable in-repo
path — `entry: ./.cadence/check-scope`, `always_run: true`.

Do not try to call the plugin's `fanout.py` directly from a hook. A hook runs in
a plain shell with no `${CLAUDE_PLUGIN_ROOT}`, and the plugin path is
version-pinned, so it breaks on the next release. The shim resolves it at run
time and fails loudly if it cannot find it.

Then set `[tracker].provider`, and `[ask].provider = "slack"` if you want runs
that continue while you are asleep.

Pair it with `/cadence:decision-fanout`, which is what keeps a run going when it
hits a decision with more than one defensible answer: each option gets built in
its own worktree and the trade-offs get logged, instead of the run stalling on a
question nobody is awake to answer.

## When you have a spec worth arguing about

`/cadence:spec` runs the two-gate pipeline. It is the heaviest workflow here and
the one to reach for least often — a spec that needs adversarial review is a spec
where being wrong is expensive, and most changes are not that.

Before the first run, write your rubric: Gate 2 grades a design against
`[paths].principles` and nothing else. See
[configuration](./configuration.md#pathsprinciples--the-gate-2-rubric).

## What to expect

These workflows are opinionated in specific places, and every place they are
opinionated is somewhere something went wrong. The **Common Rationalizations**
table in each doc is not rhetorical — each row is an excuse that was actually
used, paired with what it cost. If a rule seems excessive, check whether it cites
a case; if it does, the case is the argument.
