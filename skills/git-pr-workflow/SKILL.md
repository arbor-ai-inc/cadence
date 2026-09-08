---
name: git-pr-workflow
description: >
  Use when creating a branch, committing, opening a pull request, driving an
  automated review through to settled, choosing a merge strategy, or cleaning up
  after a merge. The post-PR sequence has one definition and this is it.
allowed-tools: Read, Grep, Glob, Write, Edit, Bash
---

Follow the canonical procedure in `${CLAUDE_PLUGIN_ROOT}/reference/git-pr-workflow.md` exactly.

Never commit to main. Never merge — that is a human decision. Never force-push.

Open with `gh pr create --title "..." --body-file <brief>`. **Both flags are required**: `--fill` rebuilds the body from commit messages and discards the brief, and `--body-file` alone prompts for a title and so fails headless.

**`gh pr create` is the middle of the procedure, not the end.** Where `[review].provider` names a PR reviewer, the review is asynchronous and blocking, and it is where defects that survived the pre-PR pass get caught.

Read the review state with `python3 ${CLAUDE_PLUGIN_ROOT}/tools/review_state.py --pr <n>` — **never the check row**, which renders `pass` for a skipped, rate-limited, paused and stale review alike.

**Ask for every re-review explicitly.** A loop that only polls is waiting on a review nobody requested. Bound it at `[review].max_rounds`, then report what went un-re-reviewed.

Capture a retro fragment as step 9 — per PR, no extra PR.

With `[review].provider = "none"`, skip the watch loop and say so; an unrun review is not a settled one.
