# Stacked, parallel and out-of-date branches

Situational detail for [`git-pr-workflow`](./git-pr-workflow.md): read it before
stacking a branch on another, running sibling branches in parallel, or updating a
branch from `main`. The project's merge strategy is in `git-pr-workflow` § *Merge
Strategy*.

## A stacked branch does not survive its parent merging

A squash puts **one new commit with a new SHA** on `main`. A child branch still
carrying its parent's original commits therefore has a merge base *predating* the
squash, and GitHub renders the parent's whole diff inside the child's PR. PR A hit
this exactly: correct content, green CI, and **20 files shown instead of 12** — so
the reviewer would have re-reviewed the parent.

**Check with `gh pr diff <n> --name-only` and count the files.** `git diff main --stat`
does *not* catch it: that is a **2-dot** diff comparing content, and it reads clean
while GitHub's **3-dot** diff from the merge base does not.

**Merging `main` forward fixes it.** An earlier revision of this section said the merge
"would leave the duplicated diff anyway". That is **wrong**, and the error was
load-bearing — it is why PR A was rebuilt at all rather than updated in place. (That the
rebuild then had to become a *new* PR is a separate constraint, the force-push denial;
see the two-endings table below. The two explanations stack, they do not compete.)

Merging `main` into the child moves the merge base to **the merged `main` commit** (not
specifically the parent's squash — whatever tip you merge), which makes `main`'s tip an
ancestor of the child, so the 3-dot diff collapses to the 2-dot one: the child's own
changes.

That last step is a deduction, not an observation: once `main`'s tip is an ancestor of the
child, the 3-dot diff *is* the 2-dot diff, by definition.

**The mechanics are confirmed in production**, by a branch that merged `main` forward as `533c391` on the way to PR B:

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
proposes reverting `main`; that is the hazard [`git-pr-workflow`](./git-pr-workflow.md) § *When rebase and cherry-pick are
unavailable* already names. Where the divergence does not overlap, the merge is clean and
the collapse is complete — a clean merge here is not suspicious.

**Afterwards, check the rendered list, not the count.** Re-run
`gh pr diff <n> --name-only` and confirm it equals the branch's own files. PR B went 36 →
36 on a correct merge-forward, so "the count dropped" is not the invariant.

**What an agent can actually run today.** Local `git merge` is denied by
`.claude/settings.json` — a guard, not a sandbox: branch protection on `main` is the
control that holds. The server-side `gh api -X PUT
repos/:owner/:repo/pulls/<n>/update-branch` is not, and it performs the same merge and the
same merge-base move — see § *If a branch genuinely must be updated*. **But it only
completes a clean merge**: GitHub will not resolve conflicts server-side, so in the
conflicting case above there is no *in-place* update path. The recreate recipe below
still applies — that is what PR A → PR C did — so the fallback is a rebuild, not a dead
end. Lifting the local denial is tracked separately (T-27).

`update-branch` is a push. Whether a push costs an existing approval depends on the
ruleset (`require_last_push_approval`, `dismiss_stale_reviews_on_push`) — check it,
§ *If a branch genuinely must be updated*. In the source project, while
`require_last_push_approval` was on, five PRs in a row needed a second approval after
the push.

Two ways to keep a child from going stale in the first place, in preference order:

1. **Do not stack.** Land one PR, then branch the next off fresh `main`. Sibling
   branches off the same `main` are fine — neither carries the other's commits, so
   neither renders the other's diff. Split by **topic**; if two topics want the
   same file, that is a sequencing decision — see below.
2. **Stack anyway, and merge `main` forward into each child once its parent lands** —
   the remedy above, and the cheap path: the PR keeps its number and its review
   history. Rebuilding the child is the fallback for when the merge conflicts badly
   enough that resolving it is riskier than re-creating the branch, using the recreate
   recipe in [`git-pr-workflow`](./git-pr-workflow.md) § *When rebase and cherry-pick are unavailable*: fresh branch off `main`,
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
   So the second ending is the one available here, and it is why PR A was closed in
   favour of a new PR (PR C) rather than force-updated in place. Naming the supersession
   in the new PR's body is what keeps the closed one from reading as abandoned work.

## Running siblings in parallel: file overlap is a signal to sequence

**Split by topic. That is what makes a PR reviewable**, and it is not negotiable
for the sake of merge mechanics — a reviewer needs the change and its reason in
one place.

Overlap is the constraint to plan around, not a reason to abandon that. Two
branches off the same `main` editing the same file do *not* automatically
conflict — git merges non-overlapping hunks fine. The risk is *overlapping*
edits, which you cannot see in a file list and will not discover until the second
PR is open. The recovery is **merge `main` forward into the second branch and resolve
the conflict there** (§ *A stacked branch does not survive its parent merging*) — PR B
did exactly this. Re-creating the file by hand on a third branch is the fallback for
when that resolution is too risky, not the first move; an earlier revision of this
paragraph said otherwise, on the same wrong premise corrected above.

So when two topics want the same file, the choice is about **parallelism**, in
this order:

1. **Sequence them.** Land the first, branch the second off updated `main`. Costs
   wall-clock and nothing else — both PRs stay coherent. This is usually right.
2. **Run them in parallel anyway** if the edits are in clearly different parts of
   the file, and resolve any conflict by merging `main` forward into the second
   branch — PR B did exactly that, resolving a four-file overlap in place.
   Rebuilding the branch is the fallback for a resolution too risky to trust, not
   the expected cost.
3. **Move the shared file's edits into one PR** only when they are small and
   mechanical enough that a sentence in the PR body restores the context. This
   buys parallelism by spending reviewability, so spend it deliberately.

T-28 took (3) and paid for it: three PRs off one `main`, with every
environment-variable doc edit pulled into PR I even though half described the
service that PR J deploys. The merges were clean — PR I landed and
PR J needed no rebase and no update, then the same for PR K — but PR I's
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
one — on PR L one generated hash file conflicted while
a second generated registry **auto-merged**, leaving a hash map
assembled from two branches and matching neither's source, with no marker to
prompt anyone. `git checkout --theirs` does not even apply to a file that never
conflicted.

So take the list from the merge, not from the conflicts:

```bash
git diff --name-only ORIG_HEAD..            # everything the merge moved
<regenerate each generated file the merge moved>
```

Then **prove it**, which is what separates "regenerated" from "regenerated and
shown to agree with source":

```bash
<each generator's --check>                  # no drift
<the contract check>                        # unchanged
```

Note the generator resolves paths from its own location rather than the cwd, so
invoking it by absolute path from another worktree is safe — worth checking per
generator, because the alternative silently writes to the wrong checkout.

**Forward-merge once, when you are next in the queue.** Total regenerations across
N branches sharing a generated file are N−1 whatever the order — every branch
after the first pays one. What varies is how often *each* branch pays: merge
`main` after every upstream landing and you regenerate per landing, wait until you
are next and you regenerate once. Four PRs shared
two generated files over two days, and the branches that
held off paid once each.

**Order by conflict complexity, not by size.** Put the branches whose conflicts are
*source-level* last, because that is judgment you do not want to repeat, and a
regeneration is not. In that same set PR M went last because its overlap in a source file
and its test was the only conflict needing a decision rather than a
command; PR N went first because it was clean and already approved, not because it
was smallest.

## Being behind `main` is not what blocks you

When several PRs are open at once, the reflex on a red or blocked PR is to bring
the branch up to date. Here that reflex is wrong twice over: it is not required,
and acting on it is how a clean branch acquires a problem it did not have.

**A branch is not required to be up to date with `main`** unless the ruleset sets
`strict_required_status_checks_policy: true`. Check:

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

## If a branch genuinely must be updated

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

**Worth knowing before you reach for it:** `update-branch` is a push, so whether it
costs an approval depends on two parameters of the `pull_request` rule. The command
above filters on `required_status_checks` and cannot see them; select this instead:

```bash
gh api repos/:owner/:repo/rules/branches/main \
  --jq '.[] | select(.type=="pull_request") | .parameters
        | {require_last_push_approval, dismiss_stale_reviews_on_push,
           require_code_owner_review, required_approving_review_count,
           required_review_thread_resolution}'
```

Either `require_last_push_approval` or `dismiss_stale_reviews_on_push` being `true`
means a push costs the approval; plan for a re-review. A ruleset bypass, where someone
has one, is a deliberate `gh pr merge --admin` and is audited — never the agent's.

Two entry conditions to note, because § *A stacked branch does not survive its parent
merging* now routes readers here. First, that section's case is a **rendering** problem,
not a blocking one — PR A was correct content on green CI — so it does not have to fail
the `mergeStateStatus` check above to belong here. Second, for a stacked child this is
the primary agent-runnable remedy rather than a rarity; the "prefer the partition"
advice applies to a branch that is merely *behind*, not to one rendering its parent's
diff.
