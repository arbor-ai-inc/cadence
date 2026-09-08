# execute-issue

Pick up a tracked issue, implement it on a branch, and hand off to code review.
Dead simple by design: the author fires it in a terminal; everything after is autonomous.

## Invocation

`/cadence:execute-issue <issue-id>` — e.g. `/cadence:execute-issue XX-33`. Run from
a clean checkout of main.

## Procedure

0. Read the project's config once: `python3 tools/cadence_config.py --json`. The
   tracker, the lint and test commands, the ask transport, the reviewer, and the
   must-stop boundary all come from there. Nothing below hardcodes any of them.
1. Fetch the issue through `[tracker].provider` (title, description, acceptance
   criteria, linked spec). If the issue cannot be found or has no actionable body,
   fail loud and exit. With `provider = "none"` the issue body is supplied inline —
   an empty one is still a hard stop, not a licence to invent scope.
2. Move the issue to `[tracker].state_started`, where the tracker has one.
3. `git checkout -b <lowercased-issue-id>` from up-to-date main (e.g. `xx-33`).
4. Implement exactly what the issue and its spec describe. Scope discipline: if work
   outside the issue's scope seems necessary, that is a question, not a decision.

   **An issue's factual claims are premises, not findings — verify the ones you are
   about to build on.** Confirming the *problem* is not confirming the *premise*, and
   the two feel identical while you are doing them. Eleven tickets have now built on a
   wrong one ([`C-13`](../examples/case-studies.md), [`C-14`](../examples/case-studies.md)).

   **They fail two ways, and assuming only the first is how most get through.** Some go
   **stale** — true when filed, false by the time they run, because siblings merged in
   between. More were **wrong when written** and never checked against the file at all.
   An agent told the defect is staleness re-verifies only what a merge could have
   changed, and skips a misquoted rule or a filing-time miscount. **Recompute every
   premise from the tree at your own commit, whatever its age:**

   - **A count, or a quoted instance, is a lower bound — never a set.** One issue
     quoted a single forbidden value; there were seven, in three phrasings. Another's
     "10 occurrences" was 2 at every commit in that file's history. Grep the **field or
     identifier** and read every value: the quoted string finds only the phrasing
     someone already saw, and `grep -c` counts *lines*, not occurrences.
   - **A file list is stale the moment a sibling merges.** Six files became twelve when
     three sibling PRs landed between filing and execution. Where a compiler covers the
     edit, let it enumerate — 21 errors across 7 files in one run beats a grep for
     constructors, which is one more premise.
   - **A name the issue uses may not exist yet.** A decomposed epic writes every AC in
     the epic's **end-state** vocabulary, so the issue is routinely ahead of the tree at
     your task's turn, and the same substitution appears in every sibling ticket. One
     grep settles it.
   - **Read a cited rule for the claim it was cited for.** One issue quoted a rule to
     explain why *this* half was hard; the same rule's list contradicted what it said
     about the *other* half. Confirming the part you already believe is not reading it.
   - **Where the issue says to read something is a claim too, and the guard goes where
     the value is produced.** An issue named the field a bad decode arrives through and
     named the wrong one — the real path is screened a module upstream, so a guard
     placed as directed would have left it open, and opening the named file *confirms*
     the issue. Go to the **writers of the destination**, not the file that declares it.
     Same for a set's membership: in [`C-13`](../examples/case-studies.md) a guard was
     built to the issue's enum and was wrong, because the writer renamed a member in
     between.
   - **An observable named together with an environment is a pairing to check.**
     One issue asked for a counter that had never held a value in the environment it
     named — metrics were disabled there, and three files in the repo already said so.
     "Go read X in Y" reads like a task and can be an impossibility.

   **Correct the issue when it is wrong** — on the issue and in the PR body — so the
   next reader does not inherit it. Never fill a gap with a fabricated figure.
5. Questions: any genuine ambiguity → a Shape A decision brief
   ([`human-brief`](./human-brief.md)) sent via
   `python3 tools/ask.py ask "<question>" --context "<issue-id> execute"`.
   A question with no options and no recommendation puts the whole framing cost on
   the reader, which is part of why they go unanswered. Use the reply, then mirror
   question + answer onto the issue as a comment. Never guess on product
   behavior; never self-answer.

   **A posted question is not a delivered one, and the difference is invisible from
   here.** `ask.py` exits 0 on a reply, 2 on timeout, and 4 when the configured
   transport cannot ask on its own; all three are honest, and none of them can tell
   you the channel is empty and nobody is reading. In
   [`C-12`](../examples/case-studies.md#c-12--the-question-nobody-saw) the question
   posted fine, no human ever saw it, and the run simply waited. So: do every part of
   the task that does not depend on the answer while the ask is out, treat exit **2**
   as *unanswered* rather than as an answer, and never self-answer either way.

   On exit **4** — and after a **2** — put the question to the author in the session
   that invoked the skill: the same Shape A brief, through `AskUserQuestion` where the
   harness offers it and as the identical table as text where it does not, because a
   numbered option is answerable in one token where a wall of prose is not. Record it
   on the issue whatever happens — mirrored Q+A if the session answers it, an open
   question if not. A question that expired unrecorded is indistinguishable from one
   never asked.

   **And if a whole ticket goes by with no reply, that is a delivery defect — file it.**
   Working around it each run is how it stays broken.
6. Run the project's `[commands].lint` and `[commands].test`. Fix failures before
   proceeding. Commit in logical units with issue-id-prefixed messages.
7. Invoke the code-review skill ([`code-review`](./code-review.md)) and drive it to
   LGTM.
8. Push the branch, write the Shape B change brief the code-review step produced to a
   file, and open a PR with
   `gh pr create --title "<issue-id>: <summary>" --body-file <brief>`. Both flags are
   required: `--fill` would rebuild the body from commit messages and drop the brief,
   while `--body-file` without `--title` prompts for a title and therefore fails
   headless. Do NOT merge — squash-merge
   is a human decision, always.
9. `python3 tools/ask.py notify "PR ready: <url>" --context "<issue-id>"` and move
   the issue to `[tracker].state_in_review`. **This announces the PR; it does not end the invocation.**
10. **Then follow [`git-pr-workflow`](./git-pr-workflow.md) § Workflow steps 8-10 and
    § [Watching the automated review](./git-pr-workflow.md#watching-the-automated-review)**:
    wait for the automated review to land, address it, write this issue's retro fragment,
    then add human reviewers where § *Review Process* says one is needed. Deliberately
    a pointer rather than a copy — the post-PR sequence has one definition, and a second
    copy here would be one more place to correct when it changes.

## When this skill is done

**Not at `gh pr create`.** The PR existing is the middle of the procedure, not the end.
The automated review is asynchronous and blocking, and it is where defects that survived
the adversarial pass get caught — so an invocation that returns at PR-open has skipped
the step most likely to find a real bug. Announcing the PR (step 9) is deliberately
ordered *before* step 10 so that the announcement cannot be mistaken for the finish.

Done means all of:

- The PR is open, and `[commands].lint` and `[commands].test` are green on it.
- `python3 tools/review_state.py --pr <n>` prints the verdict line as `AT HEAD`
  (`--json` gives the `review_landed_at_head` field a monitor reads).
  **Never read the check row instead** — it renders
  `pass` for a paused review, a rate-limited one and a stale `CHANGES_REQUESTED`
  alike ([`C-09`](../examples/case-studies.md#c-09--a-reviewer-that-reports-success-without-running)).
  Absence of findings on a freshly-opened PR is "not yet", never "nothing to do".

  With `[review].provider = "none"` this bullet and the whole watch loop do not
  apply, and the invocation ends at a green PR. Say so explicitly rather than
  reporting a review that was never configured as settled.
- Every finding is fixed or answered with a reply stating why it is declined —
  including findings in the review **body**, which is where anything outside the diff
  lands and which no thread count reflects.
- Either the review has settled, or the separate `[review].max_rounds` post-PR bound
  was reached,
  the open findings were announced through `tools/ask.py notify`, and the PR says
  which commit went un-re-reviewed.
- **Any standing human `CHANGES_REQUESTED` is reported, not silently left** — the same
  command reports it. Clearing it is not this skill's job, but ending the invocation
  while one stands, without saying so, reports the work as further along than it is.

If the review has not landed, the invocation is **not** finished: wait on it with the
harness's background or monitor facility — and **that monitor acts; it does not only
observe.** A loop that only polls is waiting on a review nobody requested. A green row
whose newest review is rate-limited or stale is neither a reason to finish nor a reason
to stop. What to ask for, when, and what counts as an answer are defined once in
[`git-pr-workflow`](./git-pr-workflow.md#requesting-the-re-review); do not re-derive
them here, and do not re-derive the state reading either.

**Stopping before that is permitted only when termination is imposed from outside the
agent** — the user halts the run; the harness or runtime hits a deadline; auth,
network, or tooling breaks polling; or the PR is ineligible for review by deliberate
config. Everything else is waiting, including a session that would only end because
the agent chose to return: **"the session is ending" is not a reason when the agent is
the one ending it**, and if foreground polling is available, lacking a background
facility is not enough either. When the exception does apply, the final message must
name the PR number, the last review state observed, and what remains unwatched, and
must say the issue is **not** complete.

## Hard rules

- Never commit to main. Never merge. Never force-push.
- Classify every decision before asking or guessing: see § *Decisions* below.
- One issue per invocation. No drive-by fixes; file follow-up issues instead.
- If lint or tests cannot be made green within the issue's scope, stop and ask
  rather than weakening tests or hooks.

## Decisions: classify before you guess or block

Applies throughout step 4, and decides whether step 5 is reached at all.

Reversal cost and blast radius decide what happens next, not how hard the
question feels. The full table and the `must-stop` list are in
[`decision-fanout`](./decision-fanout.md) § *Classify Before You Fork*. The
short form:

- `mechanical` (one defensible answer), or a **two-way door** (wrong is cheap
  to undo): decide it, record what reversing would cost, and keep going.
  Scope discipline is unchanged — work outside the issue's scope is a
  question, not a decision.
- **A one-way door whose effects stay inside this diff**: fan out instead of
  stalling. Build each defensible option in its own worktree per
  [`decision-fanout`](./decision-fanout.md), and run step 6 in every leaf.
- **`must-stop`**, **or a fan-out `fanout.py` refused for a cap**: ask,
  per step 5. Variants of those are worse than one question, and a refused cap is
  a question rather than a decision to re-shape until it fits.

  **Work the boundary from the config, never from a description of it.**
  `python3 tools/cadence_config.py must-stop <path>...` answers it and exits 5
  when a path is inside. Typical entries are schema and migrations, published
  contracts, a serving or payment critical path, money and ranking logic, audit
  trails, and anything shipped to third parties — but that sentence is a
  description, and `[[must_stop]]` in `cadence.toml` is what is enforced.

  **An empty boundary is a real answer, and a dangerous one.** If the project
  configured none, nothing will ever route to this branch. Say so once, in the
  PR body, rather than concluding that no decision in the diff was one-way.

**Exit 3 on its own does not mean ask.** It is every `fork` refusal, and the
reasons do not share a remedy — read the reason the command printed. A cap
(`max_options` / `max_depth` / `max_leaves`) or `must-stop boundary:` is the ask
above. But `only N surviving option(s)` means there was never a fork to build, so
it belongs to the first branch: decide it and `record`. Escalating that one puts a
question to a human that the run had already answered by finding one option.

Note that `fanout.py` prints `Ask the author ... instead` under **every**
refusal, including that one, where its own reason text says `decide it and
\`record\` instead`. The reason is right and the remedy line is not; this doc is
the tie-breaker until the tool is fixed.

Only the ask branch reaches step 5 — `must-stop`, and a `fork` refused for a cap.
The other two never do: a decision you make and a decision you fan out are both
answered without a question. Nothing about step 5 itself changes: a fanned decision
is deferred, not answered, so it is still mirrored onto the issue.
