# Git PR Workflow

## Overview

Use this workflow to create branch, commit, push, and pull request changes in a
way that is easy to review and safe to merge.

## When To Use

- Starting a branch for repo work.
- Naming a branch for a ticket, task, or follow-up.
- Creating commits that should become a PR.
- Opening, updating, or preparing a PR for review.
- Cleaning up after merge.

Do not use this workflow for exploratory local-only changes that will not be
committed.

## Repo Context To Load

- Contribution and review expectations: `CONTRIBUTING.md` and
  `docs/engineering/code-review.md`
- Shared agent workflows: ``
- Current work context: the issue, ticket, user request, or spec
- Existing branch and worktree state: `git status --short --branch`

## Branch Naming

Prefer branch names that identify the owner and work:

```text
<owner>/<ticket-or-topic>
```

Examples:

```text
murty/eng-5-agent-skill-presubmit
murty/eng-5-git-pr-workflow
codex/update-reporting-tests
```

Guidelines:

- Use the user's requested branch name when provided.
- Use the ticket or project key when known.
- Use lowercase words separated by hyphens.
- Keep names descriptive enough to recognize in branch lists.
- Codex-created branches may use `codex/<topic>` when the user does not
  specify an owner or naming convention.

## Workflow

1. Start clean: run `git status --short --branch`.
2. Create or switch to the branch before editing.
3. Keep the branch focused on one logical change.
4. Commit related changes together with a concise imperative message.
5. Run focused verification before pushing — including the linters CI enforces.
   For `the API package`, run `ruff format` and `ruff check` yourself: the CI
   `pre-commit` job runs them with `--all-files`, and local git hooks are not
   guaranteed to be installed, so a format-only miss fails CI rather than your
   commit (T-21 #270).
6. **Adversarial review BEFORE the PR exists**, for anything non-trivial — run
   [`code-review`](./code-review.md) and drive it to LGTM or its 3-round circuit
   breaker. Reviewer must be a context that did not write the code. This is the
   cheapest point to find a wrong boundary, and it is where the mutation check
   (§ Loop step 4) happens.
7. Push the branch and create a PR, with a summary and verification section.
8. **Watch the automated review and address it**, before involving anyone else.
   Where `[review].provider` names a PR-time reviewer, it is normally configured as a blocking review and starts on its own. This step
   is not complete when the PR exists — it is complete when the review has
   *landed* and its findings are resolved or explicitly declined. See
   § [Watching the automated review](#watching-the-automated-review) for the
   terminal condition and the commands, and
   [`code-review-and-quality`](./code-review-and-quality.md) § *Working With
   Automated Reviewers* for how to judge a finding once you have it.
9. **Write the retro fragment**: one file at
   `docs/engineering/retros/pending/<issue-id>.md`, shaped by
   [`_fragment_template.md`](../templates/_fragment_template.md). It rides this PR, so a
   lesson costs no PR of its own. The slot is exact — after the automated review, so the
   fragment can cite the friction that review just surfaced, and before human reviewers,
   so pushing it cannot dismiss an approval you already hold. Record observations, never
   rules: whether a trap earns a rule is decided across ~15 tickets by
   [`retro-synthesis`](./retro-synthesis.md), not from this ticket. Reuse `trap` slugs
   from [`TRAPS.md`](../templates/TRAPS.md) — a fresh slug for a trap already listed hides
   the recurrence that would justify acting on it. Nothing durable happened? Write no
   file and say so in the PR summary; an empty fragment is noise. The same skip
   applies when every changed file falls under one of the project's exploratory
   trees (see the project's conventions doc,
   `docs/engineering/project-conventions.md`) — exploratory work is exempt from
   capture, and the PR summary states the skip. A PR that also touches any
   non-exploratory file captures as normal.
10. **Then add human reviewers**, where § *Review Process* says one is needed. After
    the automated pass has settled, not before — otherwise a human reads a diff that
    is about to churn, and the second read is the one that gets skimmed.
11. Respond to review with follow-up commits unless the reviewer asks for a
    different history shape.
12. After merge, switch to `main`, pull, prune, and delete local branches that
    are no longer needed.

## Watching The Automated Review

**Applies only when `[review].provider` names a PR-time reviewer.** With
`provider = "none"` this whole section is skipped, and a workflow must say so
rather than reporting an unrun review as settled.

The reasoning below is provider-neutral; it names commands by role. The literal
command for each role is tabulated in
[`providers/coderabbit.md`](./providers/coderabbit.md) § *Command map* — read that
once, then work from the roles here.


**Opening the PR is not the end of the work.** The review is asynchronous — the check
appears within ~30s and findings land a minute or two later — so an agent that looks
for comments immediately after `gh pr create` finds none, concludes there is nothing
to address, and stops. That is the most common way this step gets skipped: not
refusal, but a race. **Absence of findings on a freshly-opened PR means "not yet",
never "nothing to do."**

**Read the state with the script, not by eye:**

```bash
python3 tools/review_state.py --pr "${PR:?}"     # add --json for a monitor
```

It prints the head SHA, the newest **verdict-bearing** review and whether it is at
head, whether the bot's newest notice is a rate-limit refusal, whether that notice was
**edited in place** since it was posted, any stated refill window, any standing human
`CHANGES_REQUESTED`, and an `action`. The `action` values are the whole enum, and a
consumer should handle all six:

| `action` | Means | Do |
|---|---|---|
| `LANDED` | a **review-produced** `APPROVED` at head, no standing human objection | part 1 only — it sees neither part 2 nor thread resolution |
| `READ_FINDINGS` | bot verdict `CHANGES_REQUESTED` at head | enumerate and answer them |
| `REPORT_HUMAN_BLOCK` | the **bot** has landed clean, but a human's `CHANGES_REQUESTED` still stands | report it and stop; never ask the bot to clear it |
| `WAIT` | a review is running — an ask is already outstanding | do not ask again inside that window |
| `INELIGIBLE` | `Review skipped: …` — draft, an ignored title keyword, or every changed file under a `path_filter` | remove the cause, then re-trigger; asking again does nothing |
| `ASK` | no verdict at head and nothing running | the provider's **full re-review** command, on the backoff below |

**`action` describes the BOT loop; `standing_human_objection` is reported separately
and must be read on its own.** `LANDED` means only that **part 1** of the terminal
condition is met, and narrowly: an `APPROVED` bot verdict at head with no standing
HUMAN objection. A `CHANGES_REQUESTED` at head is also verdict-bearing and reports
`READ_FINDINGS`. It does **not** mean the PR is done. What it cannot see is part 2 —
whether every finding is answered — and the *thread-resolution* half of part 3. It
**does** see an active *Request changes* block: that is a `CHANGES_REQUESTED`
verdict, and it reports `READ_FINDINGS`. `LANDED` is also the only value a human
block *would* be able to hide behind, which is why `REPORT_HUMAN_BLOCK` preempts it
rather than leaving the block
to a sibling field. A stale bot verdict with a human blocking is still `ASK`, because the bot
re-review is genuinely outstanding and folding the block into `action` there would
stall a loop that has work to do.

Everything it reports used to be ~380 lines of instructions here for reading four
signals that render a passing state for a review that never ran. Batch 01 of the retro
ledger recorded agents getting it wrong **seven times in nineteen tickets** with those
instructions in front of them — n=9 cumulative with the prior batch, which is the
count the mechanize decision rests on
([`retro-synthesis`](./retro-synthesis.md) § *Workflow* step 4). The four signals, why
each lies, and the measurement behind each are in the script's own docstring — read it
there, and do not restate it here. What stays in this doc is the judgment the script
deliberately does not make.

Three things follow from that, and they are the whole reason not to hand-roll the
query again:

- **The check row is read for its *description*, never its bucket.** `Review completed`
  (possibly stale), `Review rate limited`, `Review skipped: …` and a self-paused bot
  all render as **`pass`**. Only the first can ever be terminal, and only at head.
- **`gh pr checks` and `reviewDecision` are summaries; the verdict is in the review
  list.** A `latestReviews` page can name no block on a PR that is `BLOCKED`.
- **Never round-trip the JSON through `echo`.** zsh's builtin decodes backslash
  escapes, so a `\n` inside a review body becomes a raw control character and `jq`
  dies with *"control characters … must be escaped"*. Under `2>/dev/null` in a polling
  loop that reads as **"no reviews found"** rather than as an error; it cost about an
  hour. Pipe directly, use `printf '%s'`, or just use the script, which never goes
  through a shell.

Everything about how to *judge* or *recover* a review has one definition elsewhere —
do not re-derive it:

- [`code-review-and-quality`](./code-review-and-quality.md) § *Working With Automated
  Reviewers* — the verified commands that enumerate a review's findings.
- [`docs/engineering/code-review.md`](./code-review.md) § *Automated AI review
  * — eligibility, exclusions, and the override path.
- **your reviewer's own config** — the source of truth for what actually runs.
  Cadence's notes for one reviewer are in
  [`providers/coderabbit.md`](./providers/coderabbit.md).

### The terminal condition

**Three things, not two — answering a finding is not the same as clearing the gate.**
a blocking-review setting makes the reviewer's *Request changes* a merge gate, and
`required_review_thread_resolution` in the ruleset means unresolved threads block merge
the way a human's do. A reply that declines a finding leaves both in place.

1. `pr_review_state.py --pr <n>` renders the verdict as `AT HEAD` (`--json` gives
   the `review_landed_at_head` field a monitor dispatches on).
2. Every finding — inline **and in the review body** — is fixed or answered. Neither
   surface is visible in the review state, and neither is counted by the other; use the
   enumeration commands in § *Working With Automated Reviewers*. A finding whose line
   falls outside the diff cannot be posted inline and arrives in the body instead: #604
   reported `unresolved threads: 0` with a Major finding open in prose.
3. **Any active reviewer block is cleared.** It lifts its own *Request changes* once
   its comments are resolved and no pre-merge check is failing, so a re-review at head
   usually does it. Where a finding was declined rather than fixed, clear it explicitly
   — resolve the thread, the provider's **approve** command as a top-level comment (**the PR author
   may do this themselves**), or the dismissal / ruleset-bypass paths in
   [`docs/engineering/code-review.md`](./code-review.md) § *Automated AI review
   *, in that order of preference.

Anything else is "keep waiting", "resume the review", or "clear the block".

**Take the concern, not necessarily the patch: declining a finding with a stated reason
is a legitimate terminal state for it; unaddressed and unanswered is not.**

**A standing human request is yours to notice and report, never to clear or to ask the
bot about.** The script reports it separately for that reason. "the reviewer is green at
head" is not "this PR is reviewed", and a monitor watching only the bot will call a PR
ready while a human waits on changes.

**If clearing the block is not available to you, escalate — do not call it done and do
not call it blocked-forever.** Thread resolution, the provider's **approve** command, review
dismissal and ruleset bypass all depend on the identity and write access the run
actually has, and an autonomous run may hold none of them. Post via
`tools/ask.py notify` with the PR number, the active block, the
clearance path attempted, and the current head and review state — then report the work
**not complete**. A terminal condition an agent cannot reach is not a stop rule; it is
a hang.

**Escalations here use `notify`, not `ask`.** Every hand-off in this section ends with
"report the work incomplete and stop", and `ask` does the opposite: it posts, then
blocks foreground polling for a reply until it gets one or the timeout expires
(default an hour), then exits non-zero. That turns a hand-off into an hour-long stall
followed by a failure code. `ask` is for a question the pipeline genuinely blocks on.

### Requesting the re-review

**A fix round ends with an explicit the provider's **full re-review** command.** By the time a fix
round ends the bot has usually paused itself (`auto_pause_after_reviewed_commits: 2`),
and the plain the provider's plain **incremental** command is then a no-op that still spends an attempt
([`providers/coderabbit.md`](./providers/coderabbit.md)). **Pushing is
not a request**, a thread reply is not one, and neither is the top-level
the provider's **resolve** command that closes out a round's dispositions. So the hang is the
*ordinary* sequence, not a misreading of it: fix, push, reply, resolve, then poll
forever for a review nobody requested. **Ask every round.**

**The rule, in one line: ask again whenever `action` is `ASK` — no verdict at head and
no review in progress — on a 10-minute / 30-minute / hourly backoff.** This paragraph
is where that is defined; everywhere else points here.

- **`WAIT` means an ask is already outstanding.** A review in progress holds the row at
  `pending · "Review in progress"` for minutes, and a poll landing inside that window
  spends a second allowance unit for a review that was already coming. The script will
  not return `WAIT` when the bot's current notice is a refusal, because the row's
  description outlives the truth by hours. **Where the row is unavailable entirely, a
  verdict-bearing review whose `submitted_at` post-dates your last ask is the same
  evidence arriving later** — the script has no ask timestamp, so that comparison is
  yours to make.
- **A stated refill is a cadence hint, never a deadline.** It is org-wide, so another
  PR can take your refill and the number can grow while you wait; a *derived* refill
  ("last review + one hour") is wrong by construction. Ask ~90s **after** a stated
  window rather than before it, and re-read the notice each round — the bot edits it in
  place. The script surfaces both the window and the edit; the ask is still the probe.
- **Gate the ask on the bot's state, never on the terminal condition.** Asking again
  because findings are unanswered, a thread is unresolved, `reviewDecision` is not
  `APPROVED`, or `mergeStateStatus` is `BLOCKED` asks the bot to fix things it has no
  power over — most obviously a human reviewer who has not looked yet. The ask can
  never succeed and the loop cannot end. Once there is a verdict at head, stop asking,
  even when the PR is nowhere near mergeable.
- **"Nothing since my last ask" diagnoses a dropped ask; it never authorises one.**
  Each ask resets that window, so after the first the answer is always "nothing since".

**That wait is long and it gets no deadline.** Throttling is by a rolling count of
review runs, so a round can take an hour or more, and every PR spends two automatic
runs before any manual trigger. A three-round loop is a multi-hour wall clock, most of
it waiting. This branch is the one place here with **no expiry**: unlike an absent
check row it names its own cause and its own resolution, and abandoning it at a
deadline throws away a PR that was going to be reviewed.

**The failure mode to design against is silence, not slowness.** At 90 minutes still
throttled, post via `tools/ask.py notify` with the PR number, the head
SHA and **the row description actually observed** — then repeat hourly and **keep
polling and keep asking**. What the escalation buys is a human who can see whether the
integration is wedged or whether this PR should go to human review without the bot; the
only lever the rate-limit notice names is one no agent holds. It does not buy
permission to stop. Do not report the work finished because a row was green, and do not
report it blocked merely because the wait was long.

### Batching: for coverage first, quota second

**After `auto_pause_after_reviewed_commits: 2` fires, further commits are simply not
reviewed** — and the row still reads `pass`, so an agent that has spent its two runs
can correctly conclude more commits cost nothing, which is exactly when the unreviewed
one lands. #620 and #627 each sat auto-paused behind a green row for ~12 hours,
unreviewed at head. The commit pushed after the pause is the one most likely to reach a
human unreviewed, and batching is what keeps the reviewed set and the merged set the
same set. The quota argument is the obvious one and the weaker one.

**Batch cohesively, and stop there.** The coverage argument says *push less often*; it
does not say *push more at once*, and read as the latter it licenses exactly what
§ *Merge Strategy* spends `allow_rebase_merge: false` to prevent. A batch is **one
round's findings and the fixes that belong with them**, not everything that fits before
the next review run. If it has grown to where a reviewer would want it split, it is
already too big, and a mechanical pass still does not travel with behaviour changes
(§ *The PR is the unit of separation*). Optimise for the human reading the diff, not
for the bot counting the runs.

**Batching narrows the window; it does not close it.** A cohesive batch pushed after
the pause is still unreviewed until an explicit re-review completes, so batching never
substitutes for the terminal condition. A green check row on a tidy batch is the same
lie as a green check row on a sprawling one.

### When no check row appears

Wait a bounded startup window (~2 minutes; the row is expected within ~30s), then
**diagnose eligibility rather than waiting longer** — the PR may not be getting a
review at all. Typical causes are: GitHub **draft** state
(`drafts: false`); a title containing `do not review` or `no review`; every changed
file falling under a a path-filter exclusion — the reviewer's config is the
authority on that list; lockfiles, the project's exploratory trees
(`docs/engineering/project-conventions.md`), generated artifacts, and spec-review
rounds are among them, so a spec-review-artifacts-only PR legitimately gets
nothing; or a **base branch** the `base_branches` regex does not match — what
skipped #377 before `.*` was set, and what a stacked PR would hit if that pattern
were narrowed again. A PR with **at least one** included path should still be
expected to review. A `Review skipped: …` row names its own cause, measured for
the draft and title-keyword cases; whether a `base_branches` miss renders as that
string or as no row at all is unestablished, so diagnose that one from the config
rather than by waiting for a string.

**Recovery is remove-the-cause-then-retrigger, not retrigger alone.** Undraft or
retitle first; the provider's plain **incremental** command on a still-ineligible PR does nothing. If the PR
is ineligible by deliberate config, record that it is going to human review unreviewed
by the bot — a stated no-review state, not a silent one.

**If the PR looks eligible and there is still no row, stop polling and hand off.** No
cause found is not a reason to keep waiting: the terminal condition is unreachable, and
waiting on it silently is the hang this section exists to prevent. Try one
the provider's plain **incremental** command, wait one more startup window, and if the row still does not
appear, escalate via `tools/ask.py notify` recording **the PR number,
the head SHA, the last state observed with its timestamp, the eligibility causes ruled
out, and that the work is incomplete.**

### Loop until settled, bounded — a separate counter

Bound the fix rounds at **three**, then post the open findings to the ask transport via
`tools/ask.py notify` and hand to a human.

**A round that changes code is verified before it is pushed** —
`the project's `[commands].lint`` and the repo's
test suite, green, exactly as
[`code-review`](./code-review.md) requires of every pre-PR resolution round. Nothing
about a finding arriving from a bot makes its fix need less proof, and without this the
terminal condition is reachable with an unverified commit as the last thing on the
branch. A docs-only round still runs pre-commit; it is cheap and it catches the hooks
that read prose.

**The bound counts rounds of fixes, not asks.** Round three still closes with the ask —
it costs nothing and it gives a human a re-reviewed head if the review lands before
they pick the PR up. What the bound forbids is opening a *fourth* round of fixes.

**This is a distinct counter from `code-review`'s pre-PR circuit breaker.** Start it at
the first automated review that lands after the PR is opened; do not carry over or
double-count pre-PR adversarial rounds. **Record the count somewhere the run can see
it** — T-26's review loop ran **fourteen** rounds against a documented three-round
breaker that never fired, because nothing in the run was tracking that the threshold
had been passed. A bound nobody counts against is not a bound. When it fires, apply
[`code-review-and-quality`](./code-review-and-quality.md) § *When Review Rounds Do Not
Converge*: **say in the PR that the last round's fixes were not re-reviewed, naming the
commit.**

**The order is the point, not the steps.** Each stage is cheaper than the one after it
and narrows what the next has to look at: a fresh-context reviewer before the diff is
public, an automated reviewer before a human spends attention, a human last and only
where judgment is actually required.

## Commit Guidance

Commit messages should be short, imperative, and specific:

```text
Add shared agent skill workflows
Add agent skill presubmit guard
```

Avoid vague messages like:

```text
Fix stuff
Updates
Address comments
```

When a change is docs-only, say so in the PR summary rather than stuffing
metadata into the commit subject.

## PR Creation

Every PR should include:

- Summary of what changed.
- Verification performed.
- Any intentionally skipped verification and why.
- Links to relevant docs, tickets, specs, or follow-up PRs.

Write the summary as a Shape B change brief — `human-brief`
([`human-brief`](./human-brief.md)): what changed in one paragraph, the architecture
delta, use-case impact (including an explicit "no user-visible change" when that is
the truth), findings and their fixes, what was not fixed, and what a reviewer should
check themselves. The PR body is where a human first meets the change; a summary that
lists file names is a diff restated, not a summary.

Suggested body:

```markdown
## Summary
<!-- One paragraph a reader who has not seen the diff can follow. -->

## Architecture delta
| Component | Before | After | Who notices |

## Use-case impact
| Scenario | Before | After |
<!-- State "no user-visible change" explicitly when that is the truth. -->

## Findings and fixes
| # | Sev | Problem in plain English | What changed | Evidence |

## Not fixed, and why

## Where the reviewer and I disagreed
<!-- Whenever a review ran. "Every finding was accepted as written" is complete. -->

## Verification
- ...

## What to check yourself
- ...
```

## Review Process

- Self-review the diff before asking for review.
- Use [`code-review`](./code-review.md) **before the PR is opened**, not merely before
  merge, for non-trivial changes — the skill's own contract is "before the PR is opened
  or updated". Opening first inverts the cost: the expensive findings are boundary ones,
  and those are cheap to fix while the diff is still private.
  [`code-review-and-quality`](./code-review-and-quality.md) carries the standards the
  review applies.
- Use
  [`test-driven-development`](./test-driven-development.md)
  when behavior changes need test evidence.
- Ask for human review on architecture, security, data-contract, migration, or
  production-impacting changes. Also on **a change under `specs/**`** (correcting a design
  or product doc is a design decision, not an implementation detail) and on **a new
  top-level folder** (the plane layout is settled, so a root directory is an architecture
  decision — getting this wrong once cost a follow-up commit touching 13 files).
  **Add them at step 10** — after the automated review has settled and the retro
  fragment is written — so the human reads the diff that is actually being proposed.
  A retro PR is always in this set: it writes the guidance other agents then follow, so
  a human should agree with the lesson before it becomes a rule.
- **Merging is a human decision.** An agent commits, reviews, resolves findings and opens
  the PR; it does not merge. See [`execute-issue`](./execute-issue.md), whose hard rules
  say the same thing unconditionally.
- Prefer follow-up commits during review. Squash merge can clean up the final
  history when intermediate commits are not meaningful.

## Spending The Review Quota

Measured over one night against one reviewer; the mechanics, not the numbers, are the
guidance.

**Concentrate the allowance on one PR until it reaches the terminal condition** in
§ *The terminal condition* — a review at head, every finding fixed or answered, the block
cleared. That is reached only when a review lands on a head with nothing outstanding, so
sharing the quota means none gets there before its next turn. Round-robin across three PRs produced nine
`CHANGES_REQUESTED` and no approvals over 11h25m — though the first 3h31m had only one PR
open, and every PR was still finding real defects, so this is suggestive, not measured.

**Never derive a refill.** The bot states one and it moves: 34, 49 and 55 minutes at
different points in the same night. Re-read the notice; § *Requesting the re-review* is
where that rule lives.

**A reply that starts no review does not suppress the next ask.** It is often prose
analysis carrying a real finding, and `pr_review_state.py` correctly still reports `ASK`.
Retries two minutes and twenty-six minutes later both started reviews — consistent with
[`../code-review.md`](./code-review.md)'s *"a refused attempt is free"*. A check row
reading `Review rate limited` is a different thing: that is a genuine refusal, so honour
the stated refill. Read the newest bot issue comment for findings the state field cannot
carry.

**Proof a review exists is a review object at head, or the script — never the
acknowledgement**, which mutates in place from "Review triggered" to "Review rate
limited" or "Review finished". Its comment shape is a useful early hint, nothing more.

**If a stale `CHANGES_REQUESTED` will not lift, ask for the verdict rather than the
review — and ask as a command, not a comment.** The lift condition in § *The terminal
condition* can be unsatisfiable: `review-gate` fails *because of* the block. Prose cannot
clear it, and plain the provider's plain **incremental** command is refused as incremental — "does not re-review
already reviewed commits" — no matter how long you wait. Post the provider's **full re-review** command
on its own first line, quote the bot's own clearance back, and name what is missing: the
gate reads review objects, not issue comments. Then confirm a verdict is `AT HEAD` with:

```bash
python3 tools/review_state.py --pr "${PR:?}"
```

## Merge Strategy

**This repo is squash-only. There is no strategy to choose.** `allow_squash_merge` is
`true` and `allow_merge_commit` / `allow_rebase_merge` are both `false` — check all
three, since two disabled strategies do not by themselves prove the third is on:

```bash
gh api repos/:owner/:repo --jq '{squash: .allow_squash_merge, merge_commit: .allow_merge_commit, rebase: .allow_rebase_merge}'
```

That is by design, and the two `false` values are false for **different** reasons —
worth knowing before you argue with either:

- `allow_merge_commit: false` is **mechanically forced**. The active `Protect main`
  ruleset requires linear history, and a merge commit has two parents; enabling the
  method would publish a merge button the ruleset then rejects.
- `allow_rebase_merge: false` is a **policy choice**. Rebase-merge is linear, so the
  ruleset permits it; it is off because it replays every intermediate commit onto
  `main`, defeating one-commit-per-logical-change, trivial per-PR revert, and clean
  bisect.

Policy is the project's decision log;
mechanism, verification commands, and the revisit condition are
the project's decision log.
So the general advice —
rebase-and-merge for a curated commit series, a merge commit to preserve topology
for stacked work — describes options this repo does not offer, and the second one
names the exact case that breaks below.

### The PR is the unit of separation, not the commit

**Squash-only means intra-branch commit boundaries do not reach `main`.** Splitting a
formatter pass into its own commit on the branch is good practice for the reviewer and
buys nothing durable: the squash collapses it. #618 carried three — `fix(offline):
remove dead imports`, `style(offline): apply ruff format`, `build(lint): bring
the offline jobs package under ruff` — and landed as the single commit `5560de1f`. An AST check
run against the style commit reports 0 structural diffs; run against what actually
merged it reports 7.

So the three properties this section spends `allow_rebase_merge: false` to protect —
one-commit-per-logical-change, trivial per-PR revert, clean bisect — are **per-PR
properties here, not per-commit ones.** A mixed PR forfeits all three no matter how
carefully its branch history is arranged.

Practically: **a formatter pass, a mechanical rename, or a generated-file refresh does
not share a PR with behaviour changes.** Not because the diff is hard to read — commit
separation solves that — but because after the squash there is no boundary left to
revert to, bisect to, or diff against. Sequence them instead (§ *Running siblings in
parallel*), which costs wall-clock and nothing else.

Before merging, confirm the PR includes every commit and file expected. This is
especially important after pushing late follow-up commits.

### A stacked branch does not survive its parent merging

A squash puts **one new commit with a new SHA** on `main`. A child branch still
carrying its parent's original commits therefore has a merge base *predating* the
squash, and GitHub renders the parent's whole diff inside the child's PR. #448 hit
this exactly: correct content, green CI, and **20 files shown instead of 12** — so
the reviewer would have re-reviewed the parent.

**Check with `gh pr diff <n> --name-only` and count the files.** `git diff main --stat`
does *not* catch it: that is a **2-dot** diff comparing content, and it reads clean
while GitHub's **3-dot** diff from the merge base does not.

**Merging `main` forward fixes it.** An earlier revision of this section said the merge
"would leave the duplicated diff anyway". That is **wrong**, and the error was
load-bearing — it is why #448 was rebuilt at all rather than updated in place. (That the
rebuild then had to become a *new* PR is a separate constraint, the force-push denial;
see the two-endings table below. The two explanations stack, they do not compete.)

Merging `main` into the child moves the merge base to **the merged `main` commit** (not
specifically the parent's squash — whatever tip you merge), which makes `main`'s tip an
ancestor of the child, so the 3-dot diff collapses to the 2-dot one: the child's own
changes.

That last step is a deduction, not an observation: once `main`'s tip is an ancestor of the
child, the 3-dot diff *is* the 2-dot diff, by definition.

**The mechanics are confirmed in production**, by `murty/alt-112-inventory-account-scoping`,
which merged `main` forward as `533c391` on the way to #561:

| | |
| --- | --- |
| merge base before | `076ea84` |
| merge base after | `6eaf9bf` — the merged `main` commit |
| `gh pr diff 561 --name-only` | **36** files, matching `git diff 6eaf9bf...533c391` |
| `git diff --name-only 076ea84...533c391` | **38** files — the *old* base against the same head, so GitHub demonstrably used the new one |
| squash landed as `9c3c894` | **one** parent, so `required_linear_history` is untouched |

Both diff figures above are **3-dot**. The 38 is not the 2-dot artifact an earlier
revision of this section mistakenly cited: `076ea84` is an ancestor of `533c391`, so for
that pair 3-dot and 2-dot coincide.

**That branch was a sibling, not a stacked child**, so it carried no duplicated parent
content and nothing collapsed — its rendered count was 36 before the merge and 36 after.
It evidences the merge-base move and that GitHub honours it; the collapse itself is the
deduction above. Do not read a shrinking file count as the thing to look for.

The merge commit lives on the branch and is discarded by the squash, which is why the
ruleset never sees it (it targets `~DEFAULT_BRANCH` only).

**Two conditions, or you get a worse problem than the one you fixed.** The collapse
assumes (a) the child's copy of the parent's content matches what the squash actually
landed, and (b) any conflict is resolved toward `main`. Where the parent's later commits
overlap the child's own edits — and always as add/add where the parent *created* a file,
since the merge base holds no ancestor blob — the three-way merge conflicts. Resolving in
favour of the child's stale copy both leaves the parent's files in the diff *and* silently
proposes reverting `main`; that is the hazard § *When rebase and cherry-pick are
unavailable* already names. Where the divergence does not overlap, the merge is clean and
the collapse is complete — a clean merge here is not suspicious.

**Afterwards, check the rendered list, not the count.** Re-run
`gh pr diff <n> --name-only` and confirm it equals the branch's own files. #561 went 36 →
36 on a correct merge-forward, so "the count dropped" is not the invariant.

**What an agent can actually run today.** Local `git merge` is denied by
`.claude/settings.json`. The server-side `gh api -X PUT
repos/:owner/:repo/pulls/<n>/update-branch` is not, and it performs the same merge and the
same merge-base move — see § *If a branch genuinely must be updated*. **But it only
completes a clean merge**: GitHub will not resolve conflicts server-side, so in the
conflicting case above there is no *in-place* update path. The recreate recipe below
still applies — that is what #448 → #451 did — so the fallback is a rebuild, not a dead
end. Lifting the local denial is tracked separately (T-27).

`update-branch` is a push, but since 2026-08-26 it **no longer costs a fresh approval**.
`require_last_push_approval` is off on `Protect main — review`
(the project's decision log),
so a push does not invalidate an existing approval. What still gates the merge is
`require_code_owner_review` on owned paths and `required_review_thread_resolution`
everywhere — a push that adds a new unresolved thread, or that touches an owned path
for the first time, can still block.

Historical, and the reason the rule was removed: while it was on, every merged PR by an
author with no ruleset bypass whose approval preceded the last commit — #536, #552, #553,
#554, #555 — needed a second approval after the push, with no counterexample in the repo.
Since 2026-08-26 that is no longer the case, so **do not plan for re-approval** after an
`update-branch`, merge-forward or follow-up commit; plan for an unresolved thread or a
newly-touched owned path instead.

Two ways to keep a child from going stale in the first place, in preference order:

1. **Do not stack.** Land one PR, then branch the next off fresh `main`. Sibling
   branches off the same `main` are fine — neither carries the other's commits, so
   neither renders the other's diff. Split by **topic**; if two topics want the
   same file, that is a sequencing decision — see below.
2. **Stack anyway, and merge `main` forward into each child once its parent lands** —
   the remedy above, and the cheap path: the PR keeps its number and its review
   history. Rebuilding the child is the fallback for when the merge conflicts badly
   enough that resolving it is riskier than re-creating the branch, using the recreate
   recipe in § *When rebase and cherry-pick are unavailable*: fresh branch off `main`,
   `git checkout <old-branch> -- <its own paths>`, then re-apply by hand any delta on
   files both tasks touched.

   **That recipe has two endings, and they are not interchangeable** — decide which
   before you start:

   | Ending | When | Cost |
   |---|---|---|
   | `git push --force-with-lease origin <new>:<oldname>` | force-push is available | **Preferred** — the PR keeps its number and its review history |
   | New branch, new PR, close the old one explicitly | force-push is unavailable, or the branch name itself must change | Review history does not carry over, so re-request review and say what the new PR supersedes |

   In *this* environment the first ending cannot run: `Bash(git push --force:*)` is in
   the permission layer's **deny** list, and that prefix covers `--force-with-lease`.
   So the second ending is the one available here, and it is why #448 was closed in
   favour of a new PR (#451) rather than force-updated in place. Naming the supersession
   in the new PR's body is what keeps the closed one from reading as abandoned work.

### Running siblings in parallel: file overlap is a signal to sequence

**Split by topic. That is what makes a PR reviewable**, and it is not negotiable
for the sake of merge mechanics — a reviewer needs the change and its reason in
one place.

Overlap is the constraint to plan around, not a reason to abandon that. Two
branches off the same `main` editing the same file do *not* automatically
conflict — git merges non-overlapping hunks fine. The risk is *overlapping*
edits, which you cannot see in a file list and will not discover until the second
PR is open. The recovery is **merge `main` forward into the second branch and resolve
the conflict there** (§ *A stacked branch does not survive its parent merging*) — #561
did exactly this. Re-creating the file by hand on a third branch is the fallback for
when that resolution is too risky, not the first move; an earlier revision of this
paragraph said otherwise, on the same wrong premise corrected above.

So when two topics want the same file, the choice is about **parallelism**, in
this order:

1. **Sequence them.** Land the first, branch the second off updated `main`. Costs
   wall-clock and nothing else — both PRs stay coherent. This is usually right.
2. **Run them in parallel anyway** if the edits are in clearly different parts of
   the file, and resolve any conflict by merging `main` forward into the second
   branch — #561 did exactly that, resolving a four-file overlap in place.
   Rebuilding the branch is the fallback for a resolution too risky to trust, not
   the expected cost.
3. **Move the shared file's edits into one PR** only when they are small and
   mechanical enough that a sentence in the PR body restores the context. This
   buys parallelism by spending reviewability, so spend it deliberately.

T-28 took (3) and paid for it: three PRs off one `main`, with every
`env-vars.md` edit pulled into `#525` even though half described the
`serving-crawler` that `#526` deploys. The merges were clean — `#525` landed and
`#526` needed no rebase and no update, then the same for `#527` — but `#525`'s
reviewer saw configuration for a service that did not exist yet. Worth it for
three PRs of mechanical config rows; not worth it for logic.

Whichever you pick, check the overlap before opening rather than after:

```bash
# Prints any file both branches touch. --no-renames because git reports only a
# rename's DESTINATION: two branches renaming one file to different names share
# no path here and still conflict. origin/ refs because the sibling is the branch
# you did not just check out.
comm -12 <(git diff --no-renames --name-only origin/main...origin/branch-a | sort) \
         <(git diff --no-renames --name-only origin/main...origin/branch-b | sort)
```

**Merge order matters even when conflicts do not.** Disjoint files mean the
*merge* is clean; they say nothing about whether the code works in either order.
If PR B deploys something PR A teaches the code to read, B merging first is green,
silent and wrong. State the required order in the PR body when one exists.

**Regenerate every generated file the merge touched — not only the ones that
conflicted.** A hand-merged derived value is **wrong but green**: the gate then
compares a hash nobody derived against content nobody regenerated. The conflict is
the *safe* case, because it forces you to look. The dangerous case is the silent
one — on #613 `tests/contracts/golden_hashes.json` conflicted while
`the contract seta generated registry` **auto-merged**, leaving a hash map
assembled from two branches and matching neither's source, with no marker to
prompt anyone. `git checkout --theirs` does not even apply to a file that never
conflicted.

So take the list from the merge, not from the conflicts:

```bash
git diff --name-only ORIG_HEAD..            # everything the merge moved
python3 a service package/tools/generate_runtime_registry.py
python3 tests/contracts/check_contracts.py --update
```

Then **prove it**, which is what separates "regenerated" from "regenerated and
shown to agree with source":

```bash
python3 a service package/tools/generate_runtime_registry.py --check   # no drift
python3 tests/contracts/check_contracts.py                           # 10/10 unchanged
```

Note the generator resolves paths from its own location rather than the cwd, so
invoking it by absolute path from another worktree is safe — worth checking per
generator, because the alternative silently writes to the wrong checkout.

**Forward-merge once, when you are next in the queue.** Total regenerations across
N branches sharing a generated file are N−1 whatever the order — every branch
after the first pays one. What varies is how often *each* branch pays: merge
`main` after every upstream landing and you regenerate per landing, wait until you
are next and you regenerate once. Four PRs shared
`a generated registry`/`golden_hashes.json` over two days, and the branches that
held off paid once each.

**Order by conflict complexity, not by size.** Put the branches whose conflicts are
*source-level* last, because that is judgment you do not want to repeat, and a
regeneration is not. In that same set #604 went last because its `tag.js` and
`tag.dom.test.js` overlap was the only conflict needing a decision rather than a
command; #611 went first because it was clean and already approved, not because it
was smallest.

### Being behind `main` is not what blocks you

When several PRs are open at once, the reflex on a red or blocked PR is to bring
the branch up to date. Here that reflex is wrong twice over: it is not required,
and acting on it is how a clean branch acquires a problem it did not have.

**A branch is never required to be up to date with `main`.** The `Protect main`
ruleset sets `strict_required_status_checks_policy: false`:

```bash
gh api repos/:owner/:repo/rules/branches/main \
  --jq '.[] | select(.type=="required_status_checks") | .parameters'
```

Note also that `GET /repos/:owner/:repo/branches/main/protection` returns
**404 "Branch not protected"** — `main` is protected by a *ruleset*, and the
classic endpoint reads as "unprotected" when it is not. Use the `rules/` endpoint
above.

So `gh pr view <n> --json mergeable,mergeStateStatus` returning
`mergeable=MERGEABLE` with `mergeStateStatus=BLOCKED` does **not** mean stale. It
means nothing conflicts and some rule has not been satisfied — a required check,
a review state, an unresolved thread. Find out which before touching the branch;
rebasing a mergeable branch changes nothing about the rule that is actually
holding it. Review-side blockers and how to clear them are
[`code-review-and-quality`](./code-review-and-quality.md)'s territory, not this
document's.

### If a branch genuinely must be updated

Rarely, and only after the check above says being behind is the actual problem —
for example when the branch and `main` really do touch the same lines. Local
`rebase`, `merge` and `--force-with-lease` are all unavailable here (§ *A stacked
branch does not survive its parent merging*), but GitHub will do it server-side:

```bash
gh api -X PUT "repos/:owner/:repo/pulls/${PR:?}/update-branch"
```

This keeps the PR number and its review history — the outcome the force-push
ending buys elsewhere. The merge commit it creates lands on the **branch**, never
on `main`: the ruleset targets the default branch only, and a branch carrying a
merge commit still squashes to a single-parent commit, so `required_linear_history`
is unaffected.

**Worth knowing before you reach for it:** `update-branch` is a push, but
`require_last_push_approval` is **off** as of 2026-08-26
(the project's decision log),
so a push no longer invalidates an approval and no re-approval is needed afterwards.
Verify before relying on either statement — and note the command above filters on
`required_status_checks`, so it cannot see this parameter. Select the
`pull_request` rule instead:

```bash
gh api repos/:owner/:repo/rules/branches/main \
  --jq '.[] | select(.type=="pull_request") | .parameters
        | {require_last_push_approval, dismiss_stale_reviews_on_push,
           require_code_owner_review, required_approving_review_count,
           required_review_thread_resolution}'
```
`dismiss_stale_reviews_on_push` is in that list because it is the *other* way a
push can cost an approval: `require_last_push_approval` being off is not
sufficient on its own if stale reviews are being dismissed. Both are `false`
today, which is why #657 kept the reviewer's approval across a later push.

Historical note, since it is cited elsewhere in this file: while the rule was on, an
approval predating the last push did **not** satisfy it — confirmed on five PRs
(§ *A stacked branch does not survive its parent merging*).

For anyone in `an infrastructure owners team` this is escapable — bypass on that ruleset covers the
whole `pull_request` rule inside a PR, though it must be invoked deliberately with
`gh pr merge --admin`, and each use is recorded as `result=bypass` in the rule-suite audit
trail. For everyone else, including the agent identity, the `pull_request` rule binds — but
since 2026-08-26 what it requires is code-owner review on owned paths and thread
resolution, **not a fresh approval after each push**. See
the project's decision log
and the project's decision log.

Two entry conditions to note, because § *A stacked branch does not survive its parent
merging* now routes readers here. First, that section's case is a **rendering** problem,
not a blocking one — #448 was correct content on green CI — so it does not have to fail
the `mergeStateStatus` check above to belong here. Second, for a stacked child this is
the primary agent-runnable remedy rather than a rarity; the "prefer the partition"
advice applies to a branch that is merely *behind*, not to one rendering its parent's
diff.

## Post-Merge Cleanup

After merge:

```bash
git switch main
git pull
git remote prune origin
git branch -d <branch>
find docs/engineering/retros/pending -maxdepth 1 -type f -name '*.md' | wc -l   # >= 15 -> /retro-synthesis
```

That last line is the whole trigger for [`retro-synthesis`](./retro-synthesis.md). At
fifteen or more fragments, a batch has enough samples to tell a recurring trap from a
one-off, which is the judgment no single ticket can make. `.github/workflows/hygiene.yml`
runs the same count on every PR and warns at the threshold, so this is the local echo of
a check that already fires.

If a PR was squash merged, Git may not recognize the local branch as merged.
Use `git branch -D <branch>` only after confirming the content is on `main`.

**Check content, not ancestry** — squash-merged branches always report as unmerged, so
"unmerged" is not evidence of unlanded work. Confirm the files are on `main`
(`git ls-tree --name-only origin/main <path>`) before deleting, and confirm the *absence*
of the content before assuming a branch is worth keeping. This check cut both ways on one
epic: two abandoned branches were safe to delete because every file was on `main` under a
different commit, while a third held a finished 250-line doc that existed nowhere else and
would have been thrown away by an ancestry check.

**Scope the check to the paths the branch owned.** With sibling PRs, a bare
`git diff main..<branch>` is alarming and meaningless: the branch predates its
siblings' merges, so *their* content shows up as deletions and the branch looks
like it would revert them. Diff only what the branch was responsible for — that is
the question you are actually asking:

```bash
# Derive the paths FROM THE BRANCH, never from memory, and check them one at a
# time. Silence is what authorises `git branch -D`, so every way of producing
# accidental silence has to be closed: a path containing a space would word-split
# into pathspecs that match nothing, and a mistyped branch name would derive no
# paths at all. Both would print nothing and read as "safe to delete".
BR=<branch>; n=0
while IFS= read -r -d '' p; do
  n=$((n + 1))
  git diff --quiet "main..$BR" -- "$p" || echo "NOT on main: $p"
done < <(git diff --no-renames --name-only -z "main...$BR")
[ "$n" -gt 0 ] || echo "derived no paths — check the branch name; do NOT delete"
```

No output means every line the branch owned is on `main`.

Both forms appear on purpose: three-dot (`main...$BR`) enumerates the branch's own
files, and two-dot (`main..$BR`) compares content — the same operator
§ *A stacked branch does not survive its parent merging* uses.

### When rebase and cherry-pick are unavailable

If the permission layer blocks `git rebase` / `git cherry-pick`, re-base a branch by
recreating it. **Check whether force-push is blocked too before relying on the last
line** — where it is, this recipe ends in a new PR instead; § *A stacked branch does
not survive its parent merging* has both endings and the condition.

```bash
git checkout -b <new> main
git checkout <oldbranch> -- <paths>          # copy just the files you own
git push --force-with-lease origin <new>:<oldname>   # PR keeps its number and history
```

**Re-apply by hand any file `main` also changed.** `git checkout <old> -- <paths>`
overwrites the working tree wholesale, so copying a file from a branch that predates other
merged work silently reverts that work. This happened while recovering a docs branch: the
copy reverted two plane docs to their pre-merge state, deleting three rows added by an
intervening PR. The diff is the tell — a "docs-only" recovery showing thousands of
deletions is reverting `main`, not adding to it.

### Identify a branch by what its PR pointed at, not by its name

A recreate-from-`main` workflow leaves near-duplicate branches, and a `-v2` suffix does
not mean newer. One recovery took a `…-v2` branch to be the latest work when the real PR
head was on the **unsuffixed** branch and carried an extra review-round commit — so the
first commit landed a pre-review version, 51 lines behind. Check
`gh pr view <n> --json headRefName,headRefOid,commits` and diff against it before
trusting any local branch as the source of truth.

Remote branch deletion is separate from local pruning. If GitHub does not delete
the branch automatically and it is no longer needed:

```bash
git push origin --delete <branch>
```

## Common Rationalizations

| Rationalization | Reality |
|---|---|
| "I'll branch after I make the change." | Branching first keeps unrelated local work out of the PR. |
| "The PR title is enough." | Reviewers need a summary and verification story without reconstructing it from the diff. |
| "Squash merge means branch cleanup is automatic." | Squash changes commit identity; local branches often need explicit cleanup. |
| "Tests passed earlier." | Verification should reflect the code being pushed. Rerun relevant checks after meaningful edits. |

## Red Flags

- Starting edits on `main`.
- A branch name that does not identify the work.
- A PR with no verification section.
- Late pushed commits not included in the merge decision.
- Deleting a local branch after squash merge without confirming content is on
  `main`.
- Remote branches left behind without a reason.

## Verification

Before considering the Git/PR workflow complete, confirm:

- [ ] The worktree is clean or remaining changes are intentionally left local.
- [ ] The branch name matches repo conventions or the user's request.
- [ ] The PR summary explains what changed.
- [ ] The PR verification section records concrete checks.
- [ ] Review-sensitive areas have been routed through the appropriate workflow.
- [ ] Post-merge cleanup has removed obsolete local and remote refs when safe.
