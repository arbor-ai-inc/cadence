# Automated PR review

Watching a PR-time automated reviewer until its review has landed and every finding is
settled. Step 8 of [`git-pr-workflow`](./git-pr-workflow.md) routes here.

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

1. `tools/review_state.py --pr <n>` renders the verdict as `AT HEAD` (`--json` gives
   the `review_landed_at_head` field a monitor dispatches on).
2. Every finding — inline **and in the review body** — is fixed or answered. Neither
   surface is visible in the review state, and neither is counted by the other; use the
   enumeration commands in § *Working With Automated Reviewers*. A finding whose line
   falls outside the diff cannot be posted inline and arrives in the body instead: PR M
   reported `unresolved threads: 0` with a Major finding open in prose.
3. **Any active reviewer block is cleared.** It lifts its own *Request changes* once
   its comments are resolved and no pre-merge check is failing, so a re-review at head
   usually does it. Where a finding was declined rather than fixed, clear it explicitly
   — resolve the thread, the provider's **approve** command as a top-level comment (**the PR author
   may do this themselves**), or the dismissal / ruleset-bypass paths in
   [`docs/engineering/code-review.md`](./code-review.md) § *Automated AI review
   *, in that order of preference.

Anything else is "keep waiting", "resume the review", or "clear the block".

**Check all three every round, not only part 1.** The review-state script reports the
verdict, never individual findings or thread resolution, so a watch built on it alone
misses a finding posted after your replies. Each round also run the enumeration queries
in `code-review-and-quality` § *Working With Automated Reviewers*, and re-arm the watch
after every push and reply.

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

**One push per fix round, and never while a review is running.** Fix or answer every
finding in the round, get lint and tests green, then push once. A push inside a running
review supersedes it: the result never posts and the allowance is spent. Nothing on the
PR shows that, so ask the bot for its remaining allowance (the provider notes name a
command that costs no attempt) rather than infer.

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
- **A stated refill is a cadence hint, never a deadline.** It is per developer
  across all your PRs (and shared by every PR under a shared bot identity), so another
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
one lands. PR P and PR Q each sat auto-paused behind a green row for ~12 hours,
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
skipped PR R before `.*` was set, and what a stacked PR would hit if that pattern
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
analysis carrying a real finding, and `tools/review_state.py` correctly still reports `ASK`.
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
