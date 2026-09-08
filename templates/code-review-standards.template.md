# Code Review Standards

<!--
  Cadence's `code-review` and `git-pr-workflow` workflows describe HOW to review
  and how to get a change merged. They deliberately do not decide WHO must
  approve what, or which gates block a merge — that is policy, it differs per
  project, and a plugin that shipped an answer would be wrong everywhere.

  This is the template for that policy. Point `[paths].review_standards` at it
  once you have filled it in.

  Everything below is real, measured reasoning from the codebase cadence came
  from, with the project-specific names removed. The **reasoning** is what is
  worth keeping; the numbers are examples of the shape a measurement takes, not
  targets. Delete any section that does not apply to you rather than filling it
  in with a guess — an unenforced policy teaches an agent the whole file is
  advisory.
-->

## TL;DR

<!-- Three lines an author needs before opening a PR. -->

- Every change goes through a pull request. <!-- or: except <named exception> -->
- <what CI must be green>
- <who must approve, if anyone>

## What automation handles, and what it does not

**Enumerate what each gate actually proves.** This is the section most worth
writing precisely, because the gap between what a gate is named and what it
checks is where defects live.

<!--
| Gate | What it actually proves | What it does NOT |
|---|---|---|
| <lint/format hook> | style is consistent | nothing about behaviour |
| <contract hash gate> | a declared artifact did not change unnoticed | that a change is COMPATIBLE — refreshing a golden turns it green |
| <schema dump check> | the dump matches the models | that a migration was ever run |
| <automated PR reviewer> | a fresh adversarial pass ran | that it ran on THIS commit — read its state, not the check row |
-->

**Every drift detector answers "did the declared artifact change without anyone
acknowledging it?" and never "is this change safe for the consumer?"** Producer-
side shape drift — a new key, a nested object where a scalar is declared —
touches no gated file and passes every gate. That is a reviewer responsibility,
and naming it here is what stops it being nobody's.

## What humans should focus on

<!-- Keep this short and keep it to what automation cannot see. -->

- Whether the change sits on the right boundary. A wrong boundary is cheap to fix
  before merge and expensive after, and no gate detects one.
- Whether a deferral is genuinely unimplemented, or whether an existing consumer
  already runs and silently does the wrong thing.
- Whether the tests would fail if the fix were removed.

## PR sizing

<!-- e.g. under 400 lines of diff; larger needs a stated reason. -->

## Author responsibilities

<!--
- <what the PR description must carry>
- <what must be green before requesting review>
- <how to respond to a declined finding: state which decision it would reverse>
-->

## Reviewer responsibilities

<!--
- <turnaround expectation>
- <what a blocking finding must include: consequence, and something checkable>
-->

## Disagreement

<!-- How a contested finding gets settled, and by whom. -->

## Merging

<!--
- Merge method: <squash | merge | rebase>, and why.
- Who merges: <the author after approval | a maintainer>.
-->

**If your history must stay linear, squash is the only method that preserves
it** — which also means a branch stacked on an unmerged branch cannot survive
its parent merging. Say so here, once, rather than letting each author discover
it.

## Branch protection

Two rules and one piece of reasoning are worth copying whatever your tooling:

**Split protection into two rulesets, and let only one be escapable.**

<!--
| Ruleset | Rules | Bypass |
|---|---|---|
| `<name> — integrity` | no force-push, no deletion, linear history, required status checks | **nobody** |
| `<name> — review` | pull-request required, code-owner review, thread resolution | `<team>`, PR-scoped |
-->

**Why the split.** Integrity binds everyone, administrators included. Review
stays escapable — because **with few effective reviewers a review requirement is
unsatisfiable, and an unsatisfiable rule fails to a bypass that then covers CI
and history too.** Keeping them separate means the escape hatch you actually
need does not silently open the two you do not.

**Refuse direct pushes twice over.** A pull-request requirement forces changes
through a PR; a required-status-check rule refuses a direct push independently.
With both, a mistaken flip of the review bypass to *always* still does not reopen
direct pushes to the trunk. Verify it by trying: a fast-forward push should be
rejected citing **both** rules.

**Make review requirements path-aware.** A required-approval count of `0` plus
code-owner review means a PR touching only unowned paths merges on green CI,
while a PR touching an owned path needs that path's owner.

**The author-is-owner exemption is narrow, and is the intended shape.** Most
forges never request review from a PR's own author, so ownership binds *other
people's* changes to a path, not the owner's. It removes the code-owner
approval and nothing else — required checks and thread resolution still apply.

**Beware a rule that the author can satisfy themselves.** A "last push must be
approved" rule sounds like oversight and is not, if a bot approval satisfies it
and the author can summon that approval on demand. Measured over one month in one
repository, a bot was the *sole* approver on roughly half of all clean merges,
and where no bot approval arrived the rule produced **exceptions rather than
reviews**. It was also path-independent, firing where no approval was otherwise
required. Check whether each rule you add can be satisfied by the person it is
meant to constrain.

## Code owners

**Own only what carries real risk.** Most of the tree should be unowned and
merge on green CI. A broad ownership map produces rubber-stamps, which is worse
than no ownership because it looks like review.

<!--
| Tier | Paths | Owner |
|---|---|---|
| **Critical path** | <paths where latency or correctness is load-bearing> | <role> |
| **Published interfaces** | <contract dirs, and the tests that gate them> | <role> |
| **Security / infra** | CI config, deploy scripts, `**/auth/`, `**/migrations/`, dependency manifests | <role> |
-->

**Own the gate's own rules as well as the thing it gates.** If a contract
directory is code-owned, own the tests that enforce it too — otherwise the gate's
rules can be weakened without review, which is a quieter way to achieve the same
thing.

## Bypass

<!--
  If anyone can bypass, say who, when, and what they must record. An
  undocumented bypass is used more often and explained less.
-->

## The review gate

Consider a check that reports whether a PR would merge **over a standing
objection** — the automated reviewer's latest verdict is *changes requested* and
no human has approved since.

Three things learned building one:

- **Read a commit status, not a job result**, if the job always exits 0. Check
  runs accumulate a row per event and a stale row cannot clear itself; a status
  context is overwritten by the newest run.
- **`error` is not a verdict.** `success` means no standing objection, `failure`
  means there is one, and `error` means the gate could not answer. Reading
  `error` as "the gate says no" is the mistake it exists to prevent — it says
  nothing about the reviews. Resolve the gate, then re-read.
- **Land it unrequired first.** Observe what it would have blocked before it
  blocks anything, and do not describe it as enforcing until it is on a ruleset.
  In one repository 17% of merges had gone in over an objection before such a
  gate existed, and it blocked none of the following forty merges — a ratchet,
  not new friction.

## Updating this doc

<!-- Who may change review policy, and where the decision gets recorded. -->
