# execute-issue

Pick up a tracked issue, implement it on a branch, and hand off to code review. The
author fires it in a terminal; everything after is autonomous.

## Invocation

`/cadence:execute-issue <issue-id>` — e.g. `/cadence:execute-issue XX-33`. Run from
a clean checkout of main.

## Procedure

0. Read the project's config once: `python3 tools/cadence_config.py --json` — tracker,
   lint and test commands, ask transport, reviewer, must-stop boundary. Nothing below
   hardcodes any of them.
1. Fetch the issue through `[tracker].provider` (title, description, acceptance
   criteria, linked spec). If the issue cannot be found or has no actionable body,
   fail loud and exit. With `provider = "none"` the issue body is supplied inline —
   an empty one is still a hard stop, not a licence to invent scope.
2. Move the issue to `[tracker].state_started`, where the tracker has one.
3. `git checkout -b <lowercased-issue-id>` from up-to-date main (e.g. `xx-33`).
4. Implement exactly what the issue and its spec describe. Scope discipline: if work
   outside the issue's scope seems necessary, that is a question, not a decision.

   **An issue's factual claims are premises, not findings — verify the ones you build
   on.** Confirming the *problem* is not confirming the *premise*
   ([`C-13`](../examples/case-studies.md), [`C-14`](../examples/case-studies.md)).
   Premises go **stale** (siblings merged since filing) and, more often, were **wrong
   when written** — which checking only what a merge could change misses. **Recompute
   every premise from the tree at your own commit, whatever its age — including one you
   are only quoting into a doc:**

   - **A count, or a quoted instance, is a lower bound — never a set.** Grep the
     **field or identifier** and read every value: the quoted string finds only the
     phrasing someone already saw, and `grep -c` counts *lines*, not occurrences.
   - **A file list is stale the moment a sibling merges.** Where a compiler covers the
     edit, let it enumerate — a grep for constructors is one more premise.
   - **A name the issue uses may not exist yet** — a decomposed epic writes ACs in its
     **end-state** vocabulary. One grep settles it.
   - **"What calls this" is a reachability question.** A claim that something is or is
     not called, or a change other code depends on, needs its callers' callers too:
     grep the name in every form it travels under, or use a call-graph tool if the
     project has one (source wins over a stale map).
   - **Read a cited rule for the claim it was cited for.** Confirming the part you
     already believe is not reading it.
   - **Where the issue says to read something is a claim too; the guard goes where the
     value is produced.** Go to the **writers of the destination**, not the file that
     declares it — set membership included ([`C-13`](../examples/case-studies.md)).
   - **An observable named together with an environment is a pairing to check** — e.g.
     a metric in an environment where metrics are disabled. "Go read X in Y" can be an
     impossibility.

   **Correct the issue when it is wrong** — on the issue and in the PR body. Never fill a gap with a fabricated figure.

   Follow [`test-authoring`](./test-authoring.md) whenever its § *When To Use*
   applies. If the issue owns a P0 row of the spec's `testing-plan.md`, record a
   break-it result or *not audited* in the PR.
5. Questions: any genuine ambiguity → a Shape A decision brief
   ([`human-brief`](./human-brief.md)) sent via
   `python3 tools/ask.py ask "<question>" --context "<issue-id> execute"`.
   Use the reply, then mirror question + answer onto the issue as a comment. Never guess on product behavior; never self-answer.

   **A posted question is not a delivered one.** `ask.py` exits 0 on a reply, 2 on
   timeout, and 4 when the configured transport cannot ask on its own; none can tell
   you nobody is reading
   ([`C-12`](../examples/case-studies.md#c-12--the-question-nobody-saw)). So: do every
   part of the task that does not depend on the answer while the ask is out, treat
   exit **2** as *unanswered* rather than as an answer, and never self-answer either way.

   On exit **4** — and after a **2** — put the question to the author in the session
   that invoked the skill: the same Shape A brief, through `AskUserQuestion` where the
   harness offers it and as the identical table as text where it does not. Record it
   on the issue whatever happens — mirrored Q+A if the session answers it, an open
   question if not. A question that expired unrecorded is indistinguishable from one
   never asked.

   **A whole ticket with no reply is a delivery defect — file it**, do not work around
   it each run.
6. Run the project's `[commands].lint` and `[commands].test`. Fix failures before
   proceeding. Commit in logical units with issue-id-prefixed messages.
7. Invoke the code-review skill ([`code-review`](./code-review.md)) and drive it to
   LGTM.
8. Push the branch, write the Shape B change brief the code-review step produced to a
   file, and open a PR with
   `gh pr create --title "<issue-id>: <summary>" --body-file <brief>`. Both flags are
   required: `--fill` would rebuild the body from commit messages and drop the brief,
   while `--body-file` without `--title` prompts for a title and therefore fails
   headless. Do NOT merge — squash-merge is a human decision, always.
9. `python3 tools/ask.py notify "PR ready: <url>" --context "<issue-id>"` and move
   the issue to `[tracker].state_in_review`. **This announces the PR; it does not end the invocation.**
10. **Then follow [`git-pr-workflow`](./git-pr-workflow.md) § Workflow steps 8-10 and
    § [Watching the automated review](./automated-review.md)**: wait for the automated
    review to land, address it, write this issue's retro fragment, then add human
    reviewers where § *Review Process* says one is needed. The post-PR sequence has
    one definition; do not copy it here.

## When this skill is done

**Not at `gh pr create`.** The automated review is asynchronous and blocking, and
catches what survived the adversarial pass; step 9 precedes step 10 so the
announcement is not mistaken for the finish.

Done means all of:

- The PR is open, and `[commands].lint` and `[commands].test` are green on it.
- `python3 tools/review_state.py --pr <n>` prints the verdict line as `AT HEAD`
  (`--json` gives the `review_landed_at_head` field a monitor reads).
  **Never read the check row instead**
  ([`C-09`](../examples/case-studies.md#c-09--a-reviewer-that-reports-success-without-running)).
  Absence of findings on a freshly-opened PR is "not yet", never "nothing to do".

  With `[review].provider = "none"` this bullet and the watch loop do not apply; the
  invocation ends at a green PR — say so rather than reporting an unconfigured review
  as settled.
- Every finding is fixed or answered with a reply stating why it is declined —
  review **body** included (see `code-review-and-quality.md` § *Working With Automated
  Reviewers*).
- Either the review has settled, or the separate `[review].max_rounds` post-PR bound
  was reached, the open findings were announced through `tools/ask.py notify`, and
  the PR says which commit went un-re-reviewed.
- **Any standing human `CHANGES_REQUESTED` is reported, not silently left** (the same
  command shows it). Clearing it is not this skill's job.

If the review has not landed, the invocation is **not** finished: wait with the
harness's background or monitor facility — and **that monitor acts; it does not only
observe** (a poll-only loop waits on a review nobody requested). A green row whose
newest review is rate-limited or stale is no reason to finish or stop. What to ask
for, when, and what counts as an answer:
[`git-pr-workflow`](./git-pr-workflow.md#requesting-the-re-review) — do not re-derive
it, or the state reading.

**Stop earlier only when termination is imposed from outside the agent** — the user
halts the run; the harness or runtime hits a deadline; auth, network, or tooling breaks
polling; or the PR is ineligible for review by deliberate config. **"The session is
ending" is not a reason when the agent is the one ending it**, and lacking a background
facility is not one while foreground polling works. Then the final message names the
PR number, the last review state observed, and what remains unwatched, and says the
issue is **not** complete.

## Hard rules

- Never commit to main. Never merge. Never force-push.
- Classify every decision before asking or guessing: see § *Decisions* below.
- One issue per invocation. No drive-by fixes; file follow-up issues instead.
- If lint or tests cannot be made green within the issue's scope, stop and ask
  rather than weakening tests or hooks.

## Decisions: classify before you guess or block

Applies throughout step 4, and decides whether step 5 is reached at all.

Reversal cost and blast radius decide, not how hard the question feels. Full table
and `must-stop` list: [`decision-fanout`](./decision-fanout.md) § *Classify Before
You Fork*. Short form:

- `mechanical` (one defensible answer), or a **two-way door** (wrong is cheap
  to undo): decide it, record what reversing would cost, and keep going.
  Scope discipline is unchanged — work outside the issue's scope is a
  question, not a decision.
- **A one-way door whose effects stay inside this diff**: **only when
  `[fanout].enabled = true`**, fan out instead of stalling — build each defensible
  option in its own worktree per [`decision-fanout`](./decision-fanout.md), and run
  step 6 in every leaf. **With fan-out off (the default), ask**, per step 5.
- **`must-stop`**, **or a fan-out `fanout.py` refused for a cap**: ask,
  per step 5 — not variants, and not re-shaping a refused fan-out until it fits.

  **Work the boundary from the config, never from a description of it.**
  `python3 tools/cadence_config.py must-stop <path>...` exits 5 when a path is
  inside. Typical entries — schema and migrations, published contracts, serving or
  payment critical paths, money and ranking logic, audit trails, anything shipped to
  third parties — are a description; `[[must_stop]]` in `cadence.toml` is enforced.

  **An empty boundary is a real answer, and a dangerous one:** nothing routes here.
  Say so once in the PR body rather than concluding no decision was one-way.

**Exit 3 on its own does not mean ask** — it is every `fork` refusal; read the printed
reason. A cap
(`max_options` / `max_depth` / `max_leaves`), `must-stop boundary:` or `fan-out is
off` is the ask above. But `only N surviving option(s)` means there was never a fork to build, so
it belongs to the first branch: decide it and `record` — do not escalate it.

`fanout.py` prints `Ask the author ... instead` under **every** refusal, including
that one, whose reason says `decide it and \`record\` instead`. The reason is right and
the remedy line is not; this doc is the tie-breaker until the tool is fixed.

Only the ask branch reaches step 5 — `must-stop`, a `fork` refused for a cap, and any
one-way door when fan-out is off.
A decision you make and a decision you fan out are both answered without a question.
A fanned decision is deferred, not answered, so it is still mirrored onto the issue.
