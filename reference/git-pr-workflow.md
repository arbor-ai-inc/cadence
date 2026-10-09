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
alex/xx-5-agent-skill-presubmit
alex/xx-5-git-pr-workflow
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
   commit (T-21 PR U).
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
   [`automated-review`](./automated-review.md) for the terminal condition and the
   commands, and
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
    different history shape. **Before merge, re-run the suites with `main` merged in**:
    two branches green on their own bases can be red composed, and no CI run sees the
    composed state (`merge-order-composition-gap`, 5 times).
12. After merge, switch to `main`, pull, prune, and delete local branches that
    are no longer needed.

## Watching The Automated Review

**Only when `[review].provider` names a PR-time reviewer** (a bot that reviews the
open PR). Then step 8 follows [`automated-review`](./automated-review.md): the terminal
condition, requesting re-reviews, batching fixes and spending the review allowance. With
any other provider, skip it, and say so rather than reporting an unrun review as
settled. It is a separate doc so a project without a PR bot never loads it.

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

**Who must approve what is `[paths].review_standards`, not this doc.** Cadence
describes the review loop; the approval policy — required reviewers, code
owners, which gates block a merge, who may bypass — is per-project and lives
there. Read it before assuming a PR needs an approval, or that it does not.


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
buys nothing durable: the squash collapses it. PR S carried three — `fix(offline):
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
revert to, bisect to, or diff against. Sequence them instead ([`branch-updates`](./branch-updates.md) § *Running siblings
in parallel*), which costs wall-clock and nothing else.

Before merging, confirm the PR includes every commit and file expected. This is
especially important after pushing late follow-up commits.

### Stacked, parallel and out-of-date branches

**Read [`branch-updates`](./branch-updates.md) before you stack a branch on another,
run sibling branches in parallel, or update a branch from `main`.** It covers why a
stacked branch does not survive its parent merging, why file overlap means sequence
rather than parallelize, why being behind `main` is not itself a blocker, and the safe
way to update when one genuinely must be. An ordinary single-branch PR needs none of it.

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
[`branch-updates`](./branch-updates.md) § *A stacked branch does not survive its parent merging* uses.

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
