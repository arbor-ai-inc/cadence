# retro-synthesis

## Overview

Turn a batch of accumulated retro fragments into guidance changes, once per ~15
tickets, as a single reviewed PR.

This is the judgment half of [`retro`](./retro.md). The capture half is a step in
[`git-pr-workflow`](./git-pr-workflow.md) § *Workflow* that costs no extra PR and
writes one fragment per issue into `<[paths].retros>/pending/`.

The split exists because a single ticket cannot tell a recurring trap from an
anecdote. Writing rules one ticket at a time produced two measurable failures over
twelve consecutive retros ([`C-01`](../examples/case-studies.md)):

- **Rules from n=1.** Reviewers had to argue generalizations back. One retro's own
  commit trailers record dropping a false claim; the reviewer's objection was that
  the rule as written would not have caught the bug that produced it
  ([`C-03`](../examples/case-studies.md)).
- **Monotonic growth.** Those twelve retros were ~+687/−18 lines, and over ten weeks
  two guidance docs roughly tripled ([`C-04`](../examples/case-studies.md)). A rule
  nobody finishes reading is not enforced, so accretion defeats the purpose.

A batch is the only point at which frequency is visible and consolidation is
possible. Both are the job.

## When To Use

- `<[paths].retros>/pending/` holds at least `[retro].synthesis_threshold`
  fragments, which defaults to **15**. The check lives in `git-pr-workflow`
  § *Post-Merge Cleanup*; wire a CI job to report the count on every PR and warn at
  the threshold, so that reaching it is announced rather than remembered.

  **The trigger is exact — at or above the threshold, not "about" it.** Elsewhere
  these docs say "~15 tickets", which describes the *batch*, not the trigger: a batch
  is whatever has accumulated by the time someone runs it, so it is usually a little
  over the threshold. Exact trigger, approximate batch.

  The number itself is configuration rather than doctrine, but lowering it costs the
  mechanism its whole point: below roughly a dozen fragments the counts cannot
  distinguish a recurring trap from an anecdote, which is the judgment this step
  exists to make.
- Or on request, to consolidate a doc that has grown past being read.

Do **not** use this to harvest a single ticket. That is the capture step, or — when
a mistake would genuinely recur before the next batch — [`retro`](./retro.md)'s
escape hatch.

## Repo Context To Load

- Every `<[paths].retros>/pending/*.md`, and the shape they follow in
  `_fragment_template.md` ([template](../templates/_fragment_template.md)).
- `<[paths].retros>/TRAPS.md` — cumulative counts from prior batches. Load this
  before deciding anything; it is what makes cross-batch frequency visible.
- Only the destination docs the surviving clusters actually touch.

## Workflow

1. **Start clean and get on a branch, before any edit.** `git status --short --branch`,
   then `git checkout -b retro/batch-NN` from an up-to-date `main`. Steps 6-8 below edit
   guidance docs and delete fragments; doing that on `main`, or on somebody else's
   feature branch, is the failure this step exists to prevent. Never commit to `main`.

2. **Cluster.** Group fragments by `trap` slug. A fragment may name several, and counts
   once in each cluster — one ticket can hit three traps and is evidence for all three.
   Re-cluster where slugs differ but the trap is the same, and where one slug has been
   stretched over two different traps. Fragment authors guess slugs from one ticket;
   correcting that is this step's job.

3. **Add prior counts** from `TRAPS.md` to each cluster. A trap seen once last batch
   and twice this batch is n=3, and no single batch could have seen that.

4. **Let the count set the response.** This is the rule that stops n=1 anecdotes from
   becoming universal rules:

   | Count | Response |
   |---|---|
   | n = 1 | Record the count in `TRAPS.md`. **Touch no guidance doc.** |
   | n = 2 | A rule only if `cost: high` on both fragments. |
   | n >= 3 | A normative rule is justified. |
   | n >= 3 *and already `ruled`* | The rule is not firing. **Mechanize it** — a hook or a test, not more prose. See step 5. |
   | n = 1, *subsystem-local* | Exempt from the counts above: one occurrence earns a § *Traps* entry in that subsystem's own doc, because it warns the next task in that area rather than legislating for everyone. |

   This table is the single normative statement of the rule. `TRAPS.md` used to carry
   its own copy and the two had already diverged, so it now points here instead.

5. **Before writing a rule, check whether one already exists** that should have caught
   it. Search the destination doc first. If a rule is there, the finding is *not* "add
   a rule" — it is "the existing rule did not fire", which has better fixes:

   - make it enforceable as written (the objection a reviewer raised in
     [`C-03`](../examples/case-studies.md)),
   - move it earlier in the workflow, where it would actually be read, or
   - **mechanize it** — a commit hook or a test.

   Prefer mechanizing whenever the rule is checkable. Prose added to a 578-line doc
   gets skimmed; a failing hook does not. A trap that is already `ruled` in `TRAPS.md`
   and recurs anyway is a mechanization candidate by definition, not a re-wording one.
   [`C-09`](../examples/case-studies.md#c-09--a-reviewer-that-reports-success-without-running)
   is that case exactly: nine occurrences and 380 lines of prose explaining how to
   work around it by hand, before anyone wrote the check.

   **Mutation-test the check you just wrote.** A guard placed where the harness never
   reaches, or permissive enough to pass anything, reports success and is worse than
   the prose it replaced. Break the thing deliberately, watch the check fail, restore
   it. [`C-10`](../examples/case-studies.md#c-10--suites-nobody-run) is why: that
   check was wrong in a way that looked exactly like working.

6. **Route surviving rules** to exactly one destination. Cadence's own reference
   docs are read-only for you — a lesson about *your* project does not belong in the
   plugin — so the destinations are all in your repository:

   | Destination | For a lesson about |
   |---|---|
   | `CLAUDE.md` / `AGENTS.md` | how agents should work in this repo, in one or two lines |
   | your project conventions doc | a durable convention every ticket must follow |
   | the spec templates in `[paths].specs` | something every future spec must state |
   | `[paths].principles` | an architectural guardrail a design should be graded against |
   | a subsystem doc § *Traps* | a constraint true of one area only |
   | your decision log | a choice that was made and should not be silently revisited |
   | your current-state doc | what is now *true*, rather than what to do differently |
   | a `cadence.toml` value, or a check | anything mechanizable — always prefer this |

   One destination, not two. A rule in two places is the drift this mechanism exists
   to catch.

   If the lesson is genuinely about a cadence workflow rather than about your project,
   that is an upstream issue on cadence, not an edit to a vendored file — a local edit
   is silently reverted by the next plugin update.

7. **Consolidate every doc you touch.** Not optional, and the reason this skill is
   batched: merge rules that overlap, collapse repeated instances of one trap into a
   single statement, and delete rules that a later decision superseded or that never
   recurred. Report the net line delta per doc. A batch that only adds has failed at
   half its job.

8. **Archive.** Concatenate the consumed fragments into
   `<[paths].retros>/archive/batch-NN.md`, then delete them from `pending/`.
   Consume `pending/*.md` only — the `.gitkeep` keeps the directory tracked. Update
   `TRAPS.md` counts and statuses (`observed` / `ruled` / `mechanized`).

9. **One PR** from the step 1 branch, opened as
   `gh pr create --title "retro(batch-NN): <summary>" --body-file <brief>` — see
   [`retro`](./retro.md) § *Opening the PR* for why both flags are mandatory and why the
   body is a Shape B brief. A human reviewer is required — see
   `git-pr-workflow` § *Review Process*, which already puts retro PRs in that set,
   because this writes the guidance other agents then follow. Never merge.

   The PR body must carry, inline: each rule's citations, the cluster histogram with
   counts, the net lines added and removed per doc, and how many rules became checks.
   **Inline matters.** Automated reviewers commonly read a sparse checkout driven by
   path filters, and a fragments directory is exactly the sort of path a project
   excludes from review — so evidence quoted only by path is invisible to the reviewer
   you are asking to check it.

## Common Rationalizations

| Rationalization | Reality |
|---|---|
| "Only one fragment mentions it, but it is clearly a general rule." | That judgment is exactly what step 3 exists to overrule. It felt general the last seven times too, and four docs carry the scars. |
| "This trap already has a rule, so I will sharpen the wording." | Re-wording a rule that did not fire is the failure mode, not the fix. Mechanize it or move it. |
| "Consolidating is a separate cleanup; I will just add the new rules." | Then nothing ever consolidates, which is how these docs tripled. The batch is the only moment this is possible. |
| "The fragments are unreviewed, so I should review them." | Fragments are observations. Judge the *pattern* across them, not the prose of each. |
| "15 fragments is a lot to hold; I will do the clearest five." | Silent truncation reads as full coverage. Cover all of them or say in the PR body which you dropped and why. |
| "This one is obviously general, so the count rule can bend once." | The count rule only ever gets tested by a case that feels obvious. [`C-15`](../examples/case-studies.md) felt obvious, was cheap to mechanize, and still earned nothing at n=2 — which is what makes the rule worth anything. |

## Red Flags

- A rule written from one fragment.
- A net-positive line delta across every touched doc, with no deletions anywhere.
- A new prose bullet for a trap already marked `ruled` in `TRAPS.md`.
- Fragments deleted from `pending/` without an `archive/batch-NN.md` holding them.
- Editing a file outside the step 5 destination list.
- A PR body that cites evidence by path instead of inline.

## Verification

- `find <[paths].retros>/pending -maxdepth 1 -type f -name '*.md' | wc -l` returns
  `0`, and `archive/batch-NN.md` contains every fragment consumed.
- Every cluster in the batch appears in `TRAPS.md` with an updated count — including
  the n=1 ones, which is the only trace they leave.
- `git diff --stat main` shows deletions, not only insertions.
- Any rule that became a check has a failing-then-passing demonstration: break the
  thing deliberately, confirm the hook or test fails, restore it.
- The project's `[commands].lint` and `[commands].test` both pass.
