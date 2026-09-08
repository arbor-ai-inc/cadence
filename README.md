# Cadence

Agent workflows for autonomous software development, as a Claude Code plugin.

Cadence is the workflow system Arbor AI uses to have coding agents pick up an
issue, build it, review it adversarially, and open a pull request without a
human in the loop until a decision genuinely needs one. It was extracted from a
production codebase after roughly forty tickets had been run through it, and the
parts that exist because something went wrong are marked as such.

> **Status: early.** The scaffolding, the configuration layer, and the release
> gate are in place. The workflows themselves are being ported. See
> [`docs/porting.md`](docs/porting.md) for what is landed and what is not.

## What is in it

Four things, which work together but are separately useful:

- **A two-gate spec pipeline.** Product intent is reviewed to `PRODUCT_READY`
  before any engineering design exists; the design is then graded against a
  rubric you supply. Each gate lands as its own merged pull request, and the
  artifact is hash-frozen at the first `READY` verdict so a spec cannot drift
  out from under the review that approved it.
- **An issue-execution loop.** One issue per invocation: branch, implement,
  lint, test, drive an adversarial review to LGTM, open a PR. It never merges —
  that stays a human decision.
- **Decision fan-out.** When an autonomous run reaches a decision with more than
  one defensible answer, it builds every option in its own git worktree and
  records the trade-offs, instead of stalling on a question nobody is awake to
  answer. Capped deliberately: the combinatorics break before the token cost
  does.
- **A recurrence-gated retro loop.** Every pull request leaves a fragment naming
  what it taught. Nothing becomes a rule until a trap has recurred — and a trap
  that recurs *after* a rule was written is treated as evidence the rule does
  not fire, so it gets mechanized as a check rather than reworded.

That last one is the piece with no public equivalent, and the argument for it is
measured rather than asserted. See [`examples/case-studies.md`](examples/case-studies.md).

## Install

```bash
/plugin marketplace add arbor-ai-inc/cadence
/plugin install cadence@cadence
```

Then copy [`templates/cadence.toml`](templates/cadence.toml) to your repository
root and edit it. Every section is optional; the defaults assume GitHub, no
issue tracker, and asking questions in-session, which needs no credentials.

The one section with no useful default is the **must-stop boundary** — the
surfaces where an agent must stop and ask rather than decide or fan out. Only
you know where those are in your system, and leaving it empty means an
autonomous run will never stop for a human.

## Configuration

Issue tracker, human-ask channel, and automated reviewer are pluggable. Linear,
Slack, and CodeRabbit implementations ship; so do fallbacks that need no setup.
See [`docs/configuration.md`](docs/configuration.md).

## Licence

Apache 2.0. See [`LICENSE`](LICENSE) and [`NOTICE`](NOTICE).
