# Case studies

The rules in `reference/` exist because something went wrong. Where a rule cites
evidence, it cites a case id from this file rather than asserting that the rule
is sensible — a rule with a measurement behind it can be argued with, and one
without cannot.

These are real measurements from the production codebase cadence was extracted
from, over roughly forty tickets. The issues and pull requests have been
renumbered; nothing else has been softened. Where a number looked bad for the
system that produced it, it is still here.

## How to read a case

Each case is one observation, not one ticket: a single ticket often hit three
traps and is evidence for all three. The `trap` slug is what the retro loop
clusters on, and the counts in [`templates/TRAPS.md`](../templates/TRAPS.md) are
cumulative across batches — which is the point, since no single batch can see
that a trap has now happened nine times.

---

## The argument for batching

These five cases are why capture and synthesis are separate steps rather than
one retro per ticket. They are the measurement behind
[`reference/retro.md`](../reference/retro.md) § *Why it is split*.

### C-01 — the baseline
Twelve consecutive retros over five weeks, each written as its own pull request
immediately after the ticket that produced it. Net effect on guidance: **+687
/ −18 lines.** Almost purely additive.

### C-02 — the cost of a rule from one ticket
One of those retros took **16 commits and 12 review comments to land a 102-line
documentation diff.** The reviewer was arguing a generalization back down: the
lesson had been written from a single occurrence and stated as universal.

### C-03 — the rule that would not have caught its own bug
Another retro's commit trailers record dropping a false claim during review. The
reviewer's objection is the one worth keeping: **the rule as written would not
have caught the bug that produced it.** Writing from n=1 does not just
over-generalize, it can produce a rule that is inert against its own origin.

### C-04 — monotonic accretion
Over ten weeks, two guidance documents roughly tripled: 179 → 578 lines, and
95 → 334 lines. **A rule nobody finishes reading does not fire**, so appending
forever defeats the purpose of appending at all.

### C-05 — the cost caused skipping
Because each retro was a whole pull request, it ran on roughly **one issue in
four**. The lessons that landed were not the important ones; they were a biased
sample of whoever had patience that day.

### C-06 — frequency is only visible across tickets
Clustering C-01's twelve retros by trap showed what the per-ticket loop
structurally could not: **seven of the twelve hit the same trap** — an artifact
asserting something that was accepted instead of checked — and it had been
answered as **seven separate prose bullets in four different documents.** Nobody
had compared them, because nothing ever put them side by side.

---

## The argument for a ledger in the repository

### C-08 — the out-of-repo lesson file
An earlier attempt accumulated lessons in a session file outside version
control. Across one 19-task epic no retro was ever run and the file reached
**1,397 lines** — unreviewable, unshareable, and lost on a fresh clone. About
526 of those lines were per-task retrospectives that each belonged in a
permanent home, and **evacuating them afterwards took four pull requests.**

This is an argument about the *site*, not the batching. Any ledger outside the
repository repeats it: a tracker comment or a scratch file cannot be grepped by
the agents that have to obey the rules drawn from it, cannot be diffed, and
cannot be reviewed.

---

## The argument for mechanizing over rewording

### C-09 — a reviewer that reports success without running
`trap: automation-silently-paused`. An automated reviewer renders a **passing
check row** for a review that never happened. Four separate signals produce it:
a rate-limited review, a skipped review, and a *stale* completed review all
bucket to `pass`; the bot's acknowledgement is edited in place from "review
triggered" to "action not completed" within seconds; every thread reply files a
body-less comment so the newest review is usually not the verdict; and the
stated quota refill is org-wide and can move backwards, so any derived one is
wrong by construction.

Seen **nine times** across nineteen tickets, with 380 lines of prose telling
agents how to read it by hand. It was mechanized on the ninth. This is the
canonical case for the rule in
[`reference/retro-synthesis.md`](../reference/retro-synthesis.md) § *Workflow*
step 4: a trap already `ruled` that recurs anyway is a **mechanization**
candidate, not a rewording one.

### C-10 — suites nobody runs
`trap: suite-not-wired-to-ci`. A test suite trusted as a gate that no CI job
runs. **An unrun suite and a passing suite look identical from the outside.**

Mechanizing it found **seven** unwired suites, and how they partition is the
argument for a check over another bullet: **one** was already known to a retro
fragment, **two** the check caught on its first run, and **four** surfaced only
after review noticed the discovery step could not see modules in one language or
standalone shell scripts at all. The last four are also the argument for
mutation-testing the check itself — the check was wrong in a way that looked
like success.

### C-11 — one slug over three traps
The umbrella trap from C-06 reached **n=24 while already `ruled` seven times in
four documents.** Step 4 reads that as a mechanize signal; step 2 reads it as one
slug stretched over more than one trap. Both were true. Splitting it into three
children is what made any of it writable, because *"verify assertions"* is not
actionable while *"an instance count in a ticket is a lower bound, never a set"*
is.

### C-15 — the trap that recurred inside its own fix
`trap: renumber-breaks-references`. Renaming a section broke a pointer to it —
**from the very check that same batch had just added.** Cheap to mechanize, and
still at n=2 at the time, so under the count rule it earned nothing. It is here
because the count rule held against a case that felt obvious, which is the only
kind of test that rule ever gets.

---

## The argument for verifying an issue's own claims

These are why [`reference/execute-issue.md`](../reference/execute-issue.md)
step 4 treats an issue's factual claims as premises rather than findings.

### C-13 — a guard built to a stale enum
An issue named the members of a set; the guard was built to that list and was
wrong, because a sibling change renamed a member between filing and execution.
`trap: issue-premise-stale`.

### C-14 — an absence audit over the wrong thing
A check encoded **the syntactic form the author happened to delete** rather than
the property being asserted. It passes on every other spelling of the same
mistake, so it fails as a silent **false negative** — the worst shape a guard
can take. Seen three times.
`trap: rule-over-one-syntactic-form`, `trap: guard-cannot-fire`.

---

## The argument for treating a timeout as unanswered

### C-12 — the question nobody saw
An agent posted a blocking question to a chat channel and waited. The post
succeeded; **no human ever saw it**, and the ask tool cannot tell a quiet
channel from a slow one. The run simply waited out its timeout.

Two rules come from this. A timeout is **unanswered**, never an answer and never
grounds to self-answer. And a whole ticket passing with no reply is a **delivery
defect to file**, not a condition to work around each run — working around it is
how it stayed broken.

### C-07 — the PR body that was silently discarded
A headless run opened a pull request whose carefully written body was rebuilt
from commit messages instead, because the convenience flag that fills a body
from commits was used alongside one that supplied it. The brief was simply gone,
and nothing reported an error. This is why
[`reference/git-pr-workflow.md`](../reference/git-pr-workflow.md) requires both
an explicit title and an explicit body file, and forbids the fill flag.
