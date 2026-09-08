# retro

Turn what a ticket taught into guidance the next ticket obeys.

The work splits in two, because capturing an observation and deciding it is a rule
have very different costs and want very different moments:

| Phase | When | Where | Cost |
|---|---|---|---|
| **Capture** | every PR | [`git-pr-workflow`](./git-pr-workflow.md) § *Workflow* step 9 | no extra PR |
| **Synthesis** | every ~15 tickets | [`retro-synthesis`](./retro-synthesis.md) | one reviewed PR |

Memory compounds only if corrections land as diffs. Capture makes that cheap enough to
happen every time; synthesis makes it accurate enough to be worth obeying.

Capture has one scope cut worth configuring: a PR entirely under a tree the
project treats as exploratory — spikes, prototypes, scratch — is exempt and says
so in its summary. Cadence does not guess which trees those are; name them in
your own conventions doc and state the exemption there, so that a skipped
fragment is a decision on record rather than an omission.

## Why it is split

Writing rules one ticket at a time was measured over twelve consecutive retros
([`C-01`](../examples/case-studies.md#c-01--the-baseline)), and it failed in three
ways at once:

- **Rules from n=1.** One ticket cannot tell a recurring trap from an anecdote, so the
  lesson over-generalized and a reviewer had to argue it back. One such retro took 16
  commits and 12 review comments for a 102-line doc diff ([`C-02`](../examples/case-studies.md));
  another's own commit trailers record dropping a false claim, and the reviewer's
  objection was that the rule as written would not have caught the bug that produced
  it ([`C-03`](../examples/case-studies.md)).
- **Monotonic accretion.** ~+687/−18 lines across those twelve. Over ten weeks two
  guidance docs roughly tripled — 179 → 578 lines and 95 → 334
  ([`C-04`](../examples/case-studies.md)). A rule nobody finishes reading does not fire,
  so appending forever defeats the purpose.
- **Cost caused skipping.** Because each retro was a whole PR, it ran on roughly one
  issue in four ([`C-05`](../examples/case-studies.md)). The lessons that landed were a
  biased sample of whoever had patience that day.

Clustering those twelve by trap shows what the per-ticket loop structurally could not:
**seven of them hit the same trap** — an artifact asserting something that was accepted
instead of checked — addressed as seven separate prose bullets in four different docs
([`C-06`](../examples/case-studies.md)). Frequency is only visible across tickets, and
consolidation is only possible in a batch. The ledger that makes it visible is
`TRAPS.md`, in your `[paths].retros` directory; start from
[`templates/TRAPS.md`](../templates/TRAPS.md).

## Where the ledger lives, and why in the repo

Your `[paths].retros` directory, which defaults to `docs/retros/`:

```text
docs/retros/
  TRAPS.md              cumulative occurrence counts across batches
  _fragment_template.md the shape a capture writes
  pending/              one fragment per ticket, awaiting a batch
  archive/batch-NN.md   the fragments a batch consumed
```

An earlier attempt at accumulating lessons used a gitignored session file. On one
19-task epic no retro was ever run and it reached 1,397 lines — unreviewable,
unshareable, and lost on a fresh clone. ~526 of those lines were per-task
retrospectives that each belonged in a permanent home, and evacuating them afterwards
took four PRs ([`C-08`](../examples/case-studies.md#c-08--the-out-of-repo-lesson-file)).

That is an argument about the *site*, not the batching. Any ledger outside the repo
repeats it: a tracker comment or a scratch file cannot be grepped by the agents that
have to obey the rules drawn from it, cannot be diffed, and cannot be reviewed.
Fragments are committed files for exactly that reason.

## The escape hatch

`/cadence:retro <PR number | issue id>` still does the old thing — harvest one ticket
straight into its destination doc as its own PR — and the bar for it is narrow:

> the same mistake would recur before the next synthesis run, **and** the rule is
> enforceable exactly as written.

Both clauses, not either. "This feels important" is not the bar; that judgment is what
the frequency table in [`retro-synthesis`](./retro-synthesis.md) exists to overrule.
Everything else writes a fragment and waits for the batch.

When the hatch is used, the procedure is `retro-synthesis` § *Workflow* **step 1,
then steps 5-9** applied to a single fragment: get on a branch before editing
anything, check whether a rule already exists that should have fired, prefer
mechanizing it, route to exactly one destination, consolidate what you touch, and
open one PR.

Step 1 is not optional here even though 2-4 are. Steps 6-8 edit guidance docs and
delete files, and step 9 opens the PR from *the step 1 branch* — so citing 5-9 alone
would name a range whose last member depends on a step outside it, and an agent
following it literally would start by editing guidance on whatever branch it happened
to be on. Skipping 2-4 is deliberate: at n=1 the count table would forbid the edit
outright, which is the whole reason the hatch exists.

## Opening the PR

Both phases end in a PR, and both open it the same way — carried forward from
[`C-07`](../examples/case-studies.md#c-07--the-pr-body-that-was-silently-discarded),
which learned it the hard way:

```bash
gh pr create --title "retro(<issue-id>): <summary>" --body-file <brief>
```

Both flags are required. `--fill` rebuilds the body from commit messages and discards
the brief; `--body-file` without `--title` prompts for a title and therefore **fails in
a headless run**.

The body is a Shape B change brief ([`human-brief`](./human-brief.md)). That shape is
the right one here for a specific reason: a lesson is a change to how every later agent
behaves, so the brief has to say in plain English which behaviour changes and which past
run would have gone differently. "Who notices" is the next agent to hit the same rule.

For a synthesis batch the brief also carries what
[`retro-synthesis`](./retro-synthesis.md) § *Workflow* step 9 requires — the cluster
histogram, per-doc line deltas, and how many rules became checks.

## Hard rules

- **Never merge.** Beyond the standing rule that merging is a human decision: this
  writes the guidance other agents then follow, so a human should agree with the lesson
  before it becomes a rule. The spec templates in `[paths].specs` are a design surface
  too.
- Never edit files outside the destination list in `retro-synthesis` § *Workflow* step 6.
- Never commit to main.
- A fragment records an observation. Only synthesis writes rules.
