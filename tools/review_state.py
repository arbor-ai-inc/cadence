#!/usr/bin/env python3
"""Report the TRUE automated-review state of a PR, and what to do about it.

`automation-silently-paused` was recorded seven times in nineteen tickets (n=9
cumulative, examples/case-studies.md C-09) with 380 lines of guidance telling
agents how to read it by hand. Four signals render a passing state for a review that never ran:

  1. The check row buckets `Review rate limited`, `Review skipped` and a STALE
     `Review completed` all to `pass`. Read the description, never the bucket.
  2. Every thread reply files a body-less COMMENTED, so the newest review is
     usually not the verdict. Select on `state` -- never on a non-empty body, since
     an APPROVED carries none and such a test is unreachable on a finished PR.
  3. The bot's acknowledgement is EDITED IN PLACE from "Review triggered" to
     "Action not completed" within ~8s. `created_at != updated_at` is the tell.
  4. The stated refill is ORG-WIDE and can move backwards, so a derived one ("last
     review + 1h") is wrong by construction. Only the current body is usable.

Not decided here, and `action == "LANDED"` is ONE THIRD of done: whether every
finding is answered, whether the reviewer's block is cleared, batching, escalation,
the three-round bound. reference/git-pr-workflow.md § *The terminal condition* is three parts; this
reports part 1. The others are judgment and live there.

Usage:
    review_state.py                 # self-test; what pre-commit runs
    review_state.py --pr 686        # report on one PR
    review_state.py --pr 686 --json # machine-readable, for a monitor
"""

from __future__ import annotations

import argparse
import inspect
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cadence_config  # noqa: E402

# The reviewer's login. This module DEFAULT exists only so the self-test and a
# direct function call work without a config; `main()` overrides it from
# [review].bot_login, because which bot reviews a PR is per-project.
#
# Every function below takes the login as an argument with this as its default,
# so nothing reads the global at call time. That matters: a module constant read
# deep in a call stack is exactly how a configured value ends up ignored while
# looking configured.
BOT = "coderabbitai[bot]"
VERDICTS = ("APPROVED", "CHANGES_REQUESTED")

# The bot states its allowance in prose that it is free to reword, so this is a
# hint extractor and never a gate: `stated_refill_minutes` is None whenever the
# phrasing moves, and every caller must still treat the ask itself as the probe.
_REFILL = re.compile(r"next (?:included )?(?:PR )?review (?:will be )?available in (\d+)\s*minute", re.I)
# `not completed` is anchored to the bot's own refusal phrasing ("Action not
# completed") rather than left free-floating: this regex now gates the WAIT branch,
# and a walkthrough comment using those two words in prose would otherwise suppress
# a legitimate WAIT. It fails safe either way -- one extra ask, never an infinite
# wait -- but a loose anchor on a pattern that changes an action is worth closing.
# The bot's own REFUSAL, not any mention of rate limiting. Every genuine refusal
# carries "Action not completed"; a prose reply discussing a rate-limited review does
# not. Measured on one measured PR at 15:28:37Z: the bot quoted "a rate-limited review did not
# evaluate the current changes" back from a comment of mine, the old anchor flipped,
# and the tool printed RATE LIMITED over an approval and would have suppressed WAIT.
_RATE_LIMITED = re.compile(r"action not completed", re.I)
_TRIGGERED = re.compile(r"review triggered|action performed", re.I)


# The bot's acknowledgement of `@coderabbitai approve` / `resolve`. Append-only,
# unlike the status row -- see the note in evaluate(). Anchored to the full phrase:
# "approved" alone appears in `Review approved`, a real description.
_APPROVE_CMD = re.compile(r"comments resolved and changes approved|changes approved", re.I)


def _command_approval_times(comments: list[dict], bot: str = BOT) -> list[str]:
    """Timestamps of the bot's approve/resolve acknowledgements."""
    return [
        c.get("created_at") or ""
        for c in comments
        if (c.get("user") or {}).get("login") == bot and _APPROVE_CMD.search(c.get("body") or "")
    ]


def _paired_with_command(review: dict, cmd_times: list[str], window_s: int = 300) -> bool:
    """True when an approve-command acknowledgement sits beside this review.

    Measured on one measured PR: the review lands at 08:20:25Z and the acknowledgement at
    08:20:28Z -- the comment FOLLOWS the review by seconds, so the window is
    two-sided. 300s is deliberately loose: the cost of a false pair is one extra
    ask, while a missed pair is a false LANDED over unreviewed code.
    """
    when = review.get("submitted_at")
    if not when or not cmd_times:
        return False
    ref = _epoch(when)
    return any(ref is not None and (t := _epoch(c)) is not None and abs(t - ref) <= window_s for c in cmd_times)


def _epoch(ts: str) -> float | None:
    try:
        return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()
    except (ValueError, TypeError):
        return None


class StateError(RuntimeError):
    """A failure to determine the state, as distinct from a state."""


def _order(review: dict) -> tuple[str, int]:
    """Total order over reviews. `id` breaks the second-granularity ties that
    request-then-approve-in-one-second produces (see review_gate.py)."""
    rid = review.get("id")
    try:
        rid = int(rid)
    except (TypeError, ValueError):
        rid = 0
    return (review.get("submitted_at") or "", rid)


def latest_verdict(reviews: list[dict], login: str = BOT) -> dict | None:
    """The newest APPROVED / CHANGES_REQUESTED from `login`, or None. Signal 2:
    a COMMENTED is never a verdict however new, and an empty body proves nothing."""
    verdicts = [r for r in reviews if r.get("state") in VERDICTS and (r.get("user") or {}).get("login") == login]
    return max(verdicts, key=_order) if verdicts else None


def standing_human_objection(reviews: list[dict], bot: str = BOT) -> dict | None:
    """The newest human CHANGES_REQUESTED not superseded by that human's own later
    verdict. Over the FULL history, not `latestReviews`: that is the latest *review*
    per reviewer, so a later COMMENTED hides a standing verdict (df981d15: merge
    BLOCKED, latestReviews named no block)."""
    by_person: dict[str, dict] = {}
    for r in reviews:
        user = r.get("user") or {}
        login = str(user.get("login", ""))
        if not login or login.endswith("[bot]") or user.get("type") == "Bot" or login == bot:
            continue
        if r.get("state") not in VERDICTS:
            continue
        if login not in by_person or _order(r) > _order(by_person[login]):
            by_person[login] = r
    objections = [r for r in by_person.values() if r["state"] == "CHANGES_REQUESTED"]
    return max(objections, key=_order) if objections else None


def read_bot_notice(comments: list[dict], bot: str = BOT) -> dict:
    """The bot's newest notice, read from its CURRENT body (signals 3 and 4).
    `edited` reports a rewrite since posting, which is what makes "Review
    triggered" unusable as evidence on its own."""
    mine = [c for c in comments if (c.get("user") or {}).get("login") == bot]
    if not mine:
        return {"present": False, "rate_limited": False, "edited": False, "stated_refill_minutes": None}
    newest = max(mine, key=lambda c: (c.get("updated_at") or c.get("created_at") or "", c.get("id") or 0))
    body = newest.get("body") or ""
    created, updated = newest.get("created_at"), newest.get("updated_at")
    refill = _REFILL.search(body)
    return {
        "present": True,
        "id": newest.get("id"),
        "created_at": created,
        "updated_at": updated,
        "edited": bool(created and updated and created != updated),
        "rate_limited": bool(_RATE_LIMITED.search(body)),
        "claims_triggered": bool(_TRIGGERED.search(body)),
        "stated_refill_minutes": int(refill.group(1)) if refill else None,
    }


def evaluate(
    head: str,
    reviews: list[dict],
    comments: list[dict],
    row_description: str | None = None,
    row_state: str | None = None,
    bot: str = BOT,
) -> dict:
    """Pure state reduction. Every fetcher below feeds this; the self-test drives it directly."""
    verdict = latest_verdict(reviews, bot)
    at_head = bool(verdict and verdict.get("commit_id") == head)
    desc = (row_description or "").lower()
    notice = read_bot_notice(comments, bot)
    human = standing_human_objection(reviews, bot)
    # `pending` is trusted because it makes ONE claim -- a review is coming. A
    # FINISHED row's state is not (signal 1). Do NOT also
    # require the description to be absent -- "Review queued" is a real pending row.
    in_progress = (row_state or "").upper() == "PENDING" or "in progress" in desc or "queued" in desc

    # `@coderabbitai approve`/`resolve` produces an APPROVED that reviewed nothing.
    # Discriminated on the bot's append-only "changes approved" comment -- measured
    # across 60 PRs: exactly 3, matching the 3 command approvals, 0 against 44
    # genuine ones. NOT the check row: the row is one mutable slot that the prescribed ASK overwrites
    # within ~11s, so a row-based guard defeats itself in one step.
    # Per-VERDICT, not per-PR: a command approval can sit on a head a real review
    # DID read (the documented way to clear a declined finding).
    approved_at_head = [
        r
        for r in reviews
        if r.get("commit_id") == head and r.get("state") == "APPROVED" and (r.get("user") or {}).get("login") == bot
    ]
    cmd_times = _command_approval_times(comments, bot)
    genuine_approvals = [r for r in approved_at_head if not _paired_with_command(r, cmd_times)]
    command_approval = bool(approved_at_head) and not genuine_approvals
    if command_approval and verdict and verdict.get("state") == "APPROVED":
        at_head = False

    if at_head:
        if verdict["state"] == "CHANGES_REQUESTED":
            action = "READ_FINDINGS"
        elif human:
            # The BOT landed; the PR did not. A monitor dispatches on `action`, so
            # this must not read LANDED with the block only in a sibling field.
            action = "REPORT_HUMAN_BLOCK"
        else:
            action = "LANDED"
    elif "review skipped" in desc:
        # `Review skipped: …` means ineligible by config (draft, an ignored title
        # keyword, or every changed file under a path_filter). Anchored to that
        # phrase, not a bare "skipped": "Review completed: 2 files skipped" is a
        # NORMAL completion, and unlike the rate-limit anchor this one does not fail
        # safe -- a false positive halts the loop and sends a human to remove a cause
        # from a PR that is perfectly eligible. Re-asking does nothing
        # -- git-pr-workflow.md § *When no check row appears* is
        # remove-the-cause-then-retrigger -- so a monitor dispatching ASK here would
        # loop forever against a PR nothing will review. Only visible at all once the
        # description started reaching this function.
        action = "INELIGIBLE"
    elif in_progress and not notice["rate_limited"]:
        # A review already running is an outstanding ask, not an unmet condition:
        # asking inside that window spends a second allowance unit for a review
        # that was already coming. But `in_progress` comes from the check row's
        # DESCRIPTION, and signal 1 is that the description itself stays wrong for
        # hours. When the bot's current notice is an explicit refusal, the ask was
        # dropped -- so the refusal outranks the row, or a monitor waits forever on
        # a review nobody is running.
        action = "WAIT"
    else:
        action = "ASK"

    return {
        "head": head,
        "verdict": None
        if not verdict
        else {
            "state": verdict["state"],
            "commit_id": verdict.get("commit_id"),
            "submitted_at": verdict.get("submitted_at"),
            "at_head": at_head,
            # Not just AT HEAD / STALE: a command approval IS at the head commit, so
            # calling it STALE would send the reader looking for a newer commit.
            # Gated on the same condition as the `at_head` override above, not on
            # `command_approval` alone. They differ: a command approval followed by a
            # REAL CHANGES_REQUESTED at the same head keeps command_approval True
            # while the verdict is no longer an approval, and the label then read
            # "CHANGES_REQUESTED at HEAD (COMMAND APPROVAL, not a review)" -- calling
            # a review that did happen one that did not.
            "at_head_label": (
                "COMMAND APPROVAL, not a review"
                if command_approval and verdict.get("state") == "APPROVED"
                else ("AT HEAD" if at_head else "STALE")
            ),
        },
        "review_landed_at_head": at_head,
        "command_approval": command_approval,
        "review_in_progress": in_progress,
        "row_description": row_description,
        "row_state": row_state,
        "notice": notice,
        "standing_human_objection": None
        if not human
        else {"login": (human.get("user") or {}).get("login"), "submitted_at": human.get("submitted_at")},
        "action": action,
    }


def render(state: dict) -> str:
    out = [f"head            {state['head']}"]
    v = state["verdict"]
    out.append(
        "verdict         none yet"
        if not v
        else f"verdict         {v['state']} at {v['commit_id']} ({v['at_head_label']}) {v['submitted_at']}"
    )
    if state["row_description"] is not None:
        # Printed as the description, never as the bucket: `pass` covers four
        # different states and three of them mean no review ran.
        out.append(f"check row       {state['row_description']!r}  (bucket deliberately not shown)")
    n = state["notice"]
    if n["present"]:
        flags = []
        if n["rate_limited"]:
            flags.append("RATE LIMITED")
        if n["claims_triggered"] and not n["rate_limited"]:
            flags.append("claims triggered")
        if n["edited"]:
            flags.append(f"EDITED IN PLACE since posting ({n['created_at']} -> {n['updated_at']})")
        out.append(f"bot notice      {', '.join(flags) or 'no rate-limit language'}")
        if n["stated_refill_minutes"] is not None:
            out.append(
                f"stated refill   {n['stated_refill_minutes']} min -- org-wide and non-monotonic; "
                "ask ~90s AFTER it, never before, and re-read rather than deriving"
            )
    if state["standing_human_objection"]:
        h = state["standing_human_objection"]
        out.append(
            f"HUMAN BLOCK     {h['login']} CHANGES_REQUESTED at {h['submitted_at']} -- report it, never ask the bot about it"
        )
    out.append(f"action          {state['action']}")
    if state["action"] == "INELIGIBLE":
        out.append(
            "                ineligible by config — remove the cause, then re-trigger; asking again does nothing"
        )
    return "\n".join(out)


def statuses_args(prefix: str, sha: str) -> list[str]:
    """argv for the commit-statuses read.

    Extracted so `--paginate` is assertable. It is the whole of CodeRabbit's round-2
    finding, and reverting it left the self-test green -- a resolution nothing
    asserts is one that can be silently reverted.
    """
    return ["api", "--paginate", f"{prefix}/commits/{sha}/statuses?per_page=100"]


def coderabbit_row(statuses: list[dict]) -> tuple[str | None, str | None]:
    """(description, state) of the newest CodeRabbit commit status, or (None, None).

    Newest first: the endpoint is documented reverse-chronological, so the first
    match is current.

    `--paginate` at the call site because a busy commit could push the row past the
    first page. Not reachable today, but the margin is smaller than it looks and it
    grows with WALL-CLOCK time rather than with repo size: this repo posts two status
    contexts, and the busiest commit carries **15** rows, all of them CodeRabbit's,
    accruing about two per rate-limit cycle while a PR sits paused. So 15/100, not
    5/100 -- that is the branch's own maximum, not the repo's. It is a cliff rather
    than a slope, since the row is missed only if 100+ statuses are NEWER than it.
    No `--slurp`:
    `gh api --paginate` merges an array endpoint into a single array (measured
    across 9-, 40- and 52-page results); `--slurp` is needed only with gh's own
    `--jq`, which this script never uses.

    Pure, so the past-the-first-page case is assertable at all -- the merged array
    hides the page boundary, so nothing at the fetch level could express it.
    """
    # Substring, not equality: the context has to survive a rename by the bot
    # ("coderabbitai", "CodeRabbit / incremental"). Tightening it to `==` returns
    # (None, None), which reads as "no row" -- the green-over-a-review-that-never-ran
    # failure this whole file exists to prevent.
    for row in statuses:
        if "coderabbit" in str(row.get("context", "")).lower():
            return row.get("description"), row.get("state")
    return None, None


def _gh_json(args: list[str]) -> object:
    """Run `gh` and parse stdout directly. Never via a shell `echo`: zsh decodes
    backslash escapes, corrupting JSON bodies into invalid control characters, and
    under 2>/dev/null that reads as "no reviews found" rather than as an error."""
    try:
        out = subprocess.run(["gh"] + args, capture_output=True, text=True, check=True).stdout
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        detail = getattr(exc, "stderr", "") or str(exc)
        raise StateError(f"`gh {' '.join(args)}` failed: {detail.strip()[:300]}") from exc
    try:
        return json.loads(out)
    except json.JSONDecodeError as exc:
        raise StateError(f"unparseable output from `gh {' '.join(args)}`: {exc}") from exc


def fetch(pr: int, repo: str | None = None, bot: str = BOT) -> dict:
    prefix = f"repos/{repo}" if repo else "repos/:owner/:repo"
    # Deliberately NOT `--jq .headRefOid`: that prints a BARE SHA, which is not
    # JSON, so the parse raises and the whole report dies on the one field it
    # cannot work without. Ask for the object and index it.
    head_obj = _gh_json(["pr", "view", str(pr), "--json", "headRefOid"] + (["--repo", repo] if repo else []))
    head_sha = (head_obj or {}).get("headRefOid") if isinstance(head_obj, dict) else None
    if not head_sha:
        raise StateError(f"no headRefOid for #{pr}")
    reviews = _gh_json(["api", "--paginate", f"{prefix}/pulls/{pr}/reviews"])
    comments = _gh_json(["api", "--paginate", f"{prefix}/issues/{pr}/comments"])
    # The commit-statuses API, NOT `gh pr view --json statusCheckRollup`. gh (2.96.0)
    # asks GraphQL for `description` and then drops it from its output for every
    # StatusContext, in every state -- so the rollup route made `row_description`
    # unconditionally None, which left signal 1 ("read the description, never the
    # bucket") UNIMPLEMENTED on the live path while the docstring claimed it. The
    # check-row line in render() could never fire either. Verified on one measured PR: the
    # rollup yields `{"context":"CodeRabbit","state":"SUCCESS"}` with no description,
    # while this endpoint yields `success / "Review completed"` for the same row.
    statuses = _gh_json(statuses_args(prefix, head_sha))
    desc, state = coderabbit_row(statuses if isinstance(statuses, list) else [])
    if not isinstance(reviews, list) or not isinstance(comments, list):
        raise StateError(f"expected JSON arrays for #{pr}")
    return evaluate(head_sha, reviews, comments, desc, state, bot=bot)


def selfcheck() -> list[str]:
    """One case per signal, plus the two the fixes for those signals reintroduced.

    Every case is drawn from a fragment in `docs/engineering/retros/archive/batch-01.md`
    and named for it, so a simplification that reopens one fails here by name.
    """
    seq = [0]

    def rv(state, commit, when, login=BOT, rid=None):
        seq[0] += 1
        return {
            "id": rid if rid is not None else seq[0],
            "user": {"login": login, "type": "Bot" if login.endswith("[bot]") else "User"},
            "state": state,
            "submitted_at": when,
            "commit_id": commit,
        }

    def cm(body, created, updated=None, login=BOT):
        seq[0] += 1
        return {
            "id": seq[0],
            "user": {"login": login, "type": "Bot"},
            "body": body,
            "created_at": created,
            "updated_at": updated or created,
        }

    ACK = "Action performed: Review triggered"
    LIMIT = "⚠️ Action not completed -- Review rate limited. Next included review available in 54 minutes."

    cases = [
        (
            # T-06: a `pass` row over a two-commit-stale verdict.
            "stale verdict behind a green row is not landed",
            ("HEAD", [rv("CHANGES_REQUESTED", "older", "2026-08-27T01:00:00Z")], [], "Review rate limited"),
            # `standing_human_objection` is asserted here: without it, deleting the
            # bot exclusion survives.
            {"review_landed_at_head": False, "action": "ASK", "standing_human_objection": None},
        ),
        (
            # T-29/-365: signal 2 -- a reply-borne COMMENTED at head must not
            # displace the CHANGES_REQUESTED that still holds the gate.
            "a COMMENTED at head does not become the verdict",
            (
                "HEAD",
                [
                    rv("CHANGES_REQUESTED", "HEAD", "2026-08-27T01:00:00Z"),
                    rv("COMMENTED", "HEAD", "2026-08-27T02:00:00Z"),
                ],
                [],
                None,
            ),
            {"review_landed_at_head": True, "action": "READ_FINDINGS"},
        ),
        (
            # A command approval SUPERSEDED by a real review at the same head.
            "a real CHANGES_REQUESTED after a command approval is not mislabelled",
            (
                "HEAD",
                [
                    rv("APPROVED", "HEAD", "2026-09-01T08:00:00Z"),
                    rv("CHANGES_REQUESTED", "HEAD", "2026-09-01T09:00:00Z"),
                ],
                [cm("Comments resolved and changes approved.", "2026-09-01T08:00:03Z")],
                "Review completed",
            ),
            {"action": "READ_FINDINGS", "verdict.at_head_label": "AT HEAD"},
        ),
        (
            # Measured on one measured PR: `resolve` produced a body-less APPROVED at head over
            # five commits no review had read.
            "a command-produced approval is not a landed review",
            (
                "HEAD",
                [rv("APPROVED", "HEAD", "2026-09-01T08:20:25Z")],
                [
                    cm(
                        "<details><summary>✅ Action performed</summary>Comments resolved and changes approved.</details>",
                        "2026-09-01T08:20:28Z",
                    )
                ],
                # Row deliberately NOT the approve-command string: the discriminator
                # must not depend on it, because the prescribed ASK overwrites it.
                "Review rate limited",
            ),
            {"action": "ASK", "review_landed_at_head": False, "command_approval": True},
        ),
        (
            # F1's self-defeat, pinned: the SAME command approval after the row has been
            # overwritten by the ask this tool prescribes.
            "a command approval still fails to land once the row has moved on",
            (
                "HEAD",
                [rv("APPROVED", "HEAD", "2026-09-01T08:20:25Z")],
                [cm("Comments resolved and changes approved.", "2026-09-01T08:20:28Z")],
                "Review queued",
            ),
            {"review_landed_at_head": False, "command_approval": True},
        ),
        (
            # Without the APPROVED conjunct, a CHANGES_REQUESTED beside a marker
            # comment reads as a command approval and open findings are skipped.
            "a CHANGES_REQUESTED at head is not a command approval",
            (
                "HEAD",
                [rv("CHANGES_REQUESTED", "HEAD", "2026-09-01T08:20:25Z")],
                [cm("Comments resolved and changes approved.", "2026-09-01T08:20:28Z")],
                None,
            ),
            {"action": "READ_FINDINGS", "command_approval": False},
        ),
        (
            # The sole guard on the marker anchor: delete this case and loosening
            # `_APPROVE_CMD` to a bare "approved" survives.
            "a bot comment merely mentioning approval is not the marker",
            (
                "HEAD",
                [rv("APPROVED", "HEAD", "2026-09-01T08:20:25Z")],
                [cm("This PR has not been approved by a human yet.", "2026-09-01T08:20:28Z")],
                "Review completed",
            ),
            {"action": "LANDED", "command_approval": False},
        ),
        (
            # The documented clear path: a real review approved this head, THEN the
            # author ran `@coderabbitai approve` to clear a declined finding.
            "a command approval over a head a real review approved still lands",
            (
                "HEAD",
                [
                    rv("APPROVED", "HEAD", "2026-09-01T07:00:00Z"),
                    rv("APPROVED", "HEAD", "2026-09-01T08:20:25Z"),
                ],
                [cm("Comments resolved and changes approved.", "2026-09-01T08:20:28Z")],
                "Review completed",
            ),
            {"action": "LANDED", "command_approval": False},
        ),
        (
            # The same verdict with a real review behind it MUST still land, or the
            # guard above would make the terminal condition unreachable.
            "a review-produced approval at head still lands",
            ("HEAD", [rv("APPROVED", "HEAD", "2026-09-01T08:20:25Z")], [], "Review completed"),
            {"action": "LANDED", "review_landed_at_head": True, "command_approval": False},
        ),
        (
            # "Review approved" is a REAL description -- 8 of the shapes in an 18-PR
            # sample.
            # `command_approval` derives from `comments`, which is empty here, so the
            # description is INERT in this case -- it documents the shape, it does not
            # test the anchor. The anchor's guard is the marker case above.
            "a genuine 'Review approved' is not a command approval",
            ("HEAD", [rv("APPROVED", "HEAD", "2026-09-01T08:20:25Z")], [], "Review approved"),
            {"action": "LANDED", "command_approval": False},
        ),
        (
            # a measured PR: an APPROVED carries no body; a body-length test never fires.
            "a body-less APPROVED at head is terminal",
            ("HEAD", [rv("APPROVED", "HEAD", "2026-08-27T03:00:00Z")], [], "Review completed"),
            {"review_landed_at_head": True, "action": "LANDED"},
        ),
        (
            # T-29: created 05:26:04Z, updated 05:26:12Z -- read inside the window
            # and reported as accepted.
            "an acknowledgement edited in place is flagged, and does not suppress the ask",
            ("HEAD", [], [cm(LIMIT, "2026-08-27T05:26:04Z", "2026-08-27T05:26:12Z")], "Review rate limited"),
            {"action": "ASK", "notice.edited": True, "notice.rate_limited": True, "notice.stated_refill_minutes": 54},
        ),
        (
            # The same comment read BEFORE the edit: still an ask, never a wait.
            "an unedited 'Review triggered' is still not evidence a review is coming",
            ("HEAD", [], [cm(ACK, "2026-08-27T05:26:04Z")], None),
            {"action": "ASK", "notice.edited": False, "notice.rate_limited": False},
        ),
        (
            # An accepted ask mid-run: asking again spends a second unit.
            "a review in progress is an outstanding ask, not an unmet condition",
            ("HEAD", [], [], "Review in progress"),
            {"action": "WAIT"},
        ),
        (
            # df981d15: latestReviews showed one bot COMMENTED and named no block.
            "a human CHANGES_REQUESTED behind a later COMMENTED is still standing",
            (
                "HEAD",
                [
                    rv("CHANGES_REQUESTED", "older", "2026-08-27T01:00:00Z", login="a-human"),
                    rv("COMMENTED", "HEAD", "2026-08-27T02:00:00Z", login="a-human"),
                    rv("APPROVED", "HEAD", "2026-08-27T03:00:00Z"),
                ],
                [],
                None,
            ),
            {"action": "REPORT_HUMAN_BLOCK", "standing_human_objection.login": "a-human"},
        ),
        (
            # That human's own later APPROVED does clear it -- the guard must not be
            # permanent, or it would report a block nobody holds.
            "a human's own later APPROVED clears their objection",
            (
                "HEAD",
                [
                    rv("CHANGES_REQUESTED", "older", "2026-08-27T01:00:00Z", login="a-human"),
                    rv("APPROVED", "HEAD", "2026-08-27T02:00:00Z", login="a-human"),
                ],
                [],
                None,
            ),
            {"standing_human_objection": None},
        ),
        (
            # Must tie two VERDICTS: `latest_verdict` filters before `max()` sees the
            # tie, so an earlier draft tying a COMMENTED against a verdict was vacuous
            # and dropping the `id` ordinal stayed green.
            "a same-second APPROVED after CHANGES_REQUESTED wins on id",
            (
                "HEAD",
                [
                    rv("CHANGES_REQUESTED", "HEAD", "2026-08-27T01:00:00Z", rid=10),
                    rv("APPROVED", "HEAD", "2026-08-27T01:00:00Z", rid=11),
                ],
                [],
                None,
            ),
            {"action": "LANDED"},
        ),
        (
            # Signal 3, ordering: read the most recently UPDATED notice, not the
            # newest created. Needs TWO comments with the older-created one edited --
            # with a single comment, sorting on `created_at` survives.
            "the newest notice is the most recently UPDATED, not the newest created",
            (
                "HEAD",
                [],
                [
                    cm(LIMIT, "2026-08-27T05:00:00Z", "2026-08-27T06:00:00Z"),
                    cm("Review triggered", "2026-08-27T05:30:00Z"),
                ],
                None,
            ),
            {"notice.rate_limited": True, "notice.edited": True, "notice.stated_refill_minutes": 54},
        ),
        (
            # A review actually RUNNING.
            "a PENDING row with no description is a review in progress",
            ("HEAD", [], [], None, "PENDING"),
            {"action": "WAIT"},
        ),
        (
            # REST spells it lowercase; gh spells it PENDING. The description MUST
            # NOT say "queued" or "in progress" -- that clause would satisfy the case
            # on its own and dropping `.upper()` survives. It did, once.
            "a lowercase pending state is normalised",
            ("HEAD", [], [], "Some other wording", "pending"),
            {"action": "WAIT"},
        ),
        (
            # A queued review is a review that is coming.
            "a queued review with a description is still in progress",
            ("HEAD", [], [], "Review queued", None),
            {"action": "WAIT"},
        ),
        (
            # Ineligible by config: asking again cannot help, so it must not read as
            # ASK.
            "a skipped review is ineligible, not an unmet condition",
            ("HEAD", [], [], "Review skipped: draft pull request", "success"),
            {"action": "INELIGIBLE"},
        ),
        (
            # Description CONSTRUCTED, not observed -- a false positive that never fired
            # leaves no measurement to copy.
            "a completed review mentioning skipped files is not ineligible",
            ("HEAD", [], [], "Review completed: 2 files skipped", "success"),
            {"action": "ASK"},
        ),
        (
            # A prose reply DISCUSSING rate limiting is not a refusal -- measured on
            # one measured PR at 15:28:37Z, where the bot quoted the phrase back from a comment.
            "a reply that merely mentions a rate-limited review is not a refusal",
            (
                "HEAD",
                [],
                [
                    cm(
                        "Review completed, no new findings. A rate-limited review did not evaluate them.",
                        "2026-09-01T15:28:37Z",
                    )
                ],
                "Review in progress",
            ),
            {"action": "WAIT", "notice.rate_limited": False},
        ),
        (
            # T-07/T-06: the row description stays wrong for hours.
            "a rate-limit refusal outranks an 'in progress' row",
            ("HEAD", [], [cm(LIMIT, "2026-08-27T05:00:00Z")], "Review in progress"),
            {"action": "ASK"},
        ),
        (
            # Signal 4: a reworded notice must yield None, not a wrong number.
            "an unrecognised refill phrasing degrades to None rather than guessing",
            # "rate limited", not a bare "rate limit": a walkthrough saying "add a
            # rate limit" must not flip this.
            ("HEAD", [], [cm("Action not completed. Review rate limited. Try later.", "2026-08-27T05:00:00Z")], None),
            {"notice.stated_refill_minutes": None, "notice.rate_limited": True, "action": "ASK"},
        ),
    ]

    def dig(state, path):
        cur = state
        for part in path.split("."):
            if cur is None:
                return None
            cur = cur.get(part)
        return cur

    bad = []

    # The scan, driven past a page boundary. `--paginate` merges pages into one
    # array, so "a row on page 2" is only expressible as a row at a high index --
    # which is why this asserts the pure function rather than a fixture above.
    far = [{"context": "review-gate", "state": "success", "description": f"r{i}"} for i in range(120)]
    far.append({"context": "CodeRabbit", "state": "success", "description": "Review completed"})
    if coderabbit_row(far) != ("Review completed", "success"):
        bad.append(f"  coderabbit_row: missed a row past the first page -> {coderabbit_row(far)}")
    # The call site, not only the builder: reverting `fetch()` to an inline argv
    # would drop --paginate with a green self-test, which is the same
    # separately-revertible shape as check_suites' workflow glob.
    # inspect.getsource(fetch), not a file read: a whole-file search matches the
    # literal in this assertion and can never fail.
    if "statuses_args(" not in inspect.getsource(fetch):
        bad.append("  fetch(): must build its argv via statuses_args(), or --paginate is bypassed")

    args = statuses_args("repos/:owner/:repo", "abc123")
    if "--paginate" not in args:
        bad.append("  statuses_args: --paginate is the round-2 fix; without it a busy commit hides the row")
    if not any("/commits/abc123/statuses" in a for a in args):
        bad.append(f"  statuses_args: wrong endpoint -> {args}")
    if coderabbit_row([{"context": "CodeRabbit / incremental", "state": "success", "description": "d"}]) != (
        "d",
        "success",
    ):
        bad.append("  coderabbit_row: the context match must be a substring, not equality")
    if coderabbit_row([]) != (None, None):
        bad.append("  coderabbit_row: an empty status list must yield (None, None)")
    # Reverse-chronological: the FIRST match wins, not the last.
    two = [
        {"context": "CodeRabbit", "state": "pending", "description": "Review in progress"},
        {"context": "CodeRabbit", "state": "success", "description": "Review completed"},
    ]
    if coderabbit_row(two) != ("Review in progress", "pending"):
        bad.append("  coderabbit_row: must take the NEWEST row, which this endpoint lists first")

    for name, args, expected in cases:
        got = evaluate(*args)
        # render() every case. It hard-depends on keys evaluate() must supply, so
        # without this a deleted key raises KeyError in production behind a green
        # self-test and a green hook -- and the at_head_label branches were
        # asserted by nothing at all.
        try:
            rendered = render(got)
        except Exception as exc:  # noqa: BLE001 - any render failure is the finding
            bad.append(f"  {name}: render() raised {type(exc).__name__}: {exc}")
            continue
        # Only when the command approval is still the operative verdict. A later
        # real CHANGES_REQUESTED at the same head supersedes it, and the line must
        # then describe the review that happened.
        v = got.get("verdict") or {}
        if got.get("command_approval") and v.get("state") == "APPROVED" and "COMMAND APPROVAL" not in rendered:
            bad.append(f"  {name}: a command approval must say so in the rendered verdict line")
        if got["review_landed_at_head"] and "AT HEAD" not in rendered:
            bad.append(f"  {name}: a landed review must render AT HEAD")
        for path, want in expected.items():
            have = dig(got, path)
            if have != want:
                bad.append(f"  {name}: {path} == {have!r}, expected {want!r}")
    return bad


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pr", type=int, help="report on this PR number")
    ap.add_argument("--repo", help="owner/name; defaults to the current repo")
    ap.add_argument("--json", action="store_true", dest="as_json", help="machine-readable output for a monitor")
    args = ap.parse_args()

    try:
        cfg = cadence_config.load()
    except cadence_config.ConfigError as exc:
        print(f"review_state: {exc}", file=sys.stderr)
        return 1

    # `none` means the project configured no automated reviewer. Report that
    # plainly rather than fetching and finding nothing, which reads the same as
    # a reviewer that has not run yet.
    if cfg.review_provider == "none" and args.pr is not None:
        print("review_state: [review].provider is \"none\" — no automated reviewer is "
              "configured for this project, so there is no review state to read. "
              "This is not the same as a review that has not landed yet.")
        return 0

    bot = cfg.review_bot_login or BOT

    bad = selfcheck()
    if bad:
        print("review_state self-test FAILED:", file=sys.stderr)
        print("\n".join(bad), file=sys.stderr)
        return 1

    if args.pr is None:
        print("review_state: OK (self-test passed)")
        return 0

    state = fetch(args.pr, args.repo, bot=bot)
    print(json.dumps(state, indent=2) if args.as_json else render(state))
    # Exit 0 whatever the state: this REPORTS, it does not gate. A non-zero exit
    # for "not landed yet" would make every polling loop treat a normal wait as
    # an error, which is how the last one ended up with `2>/dev/null` on the
    # fetch and read a broken query as a quiet PR.
    return 0


if __name__ == "__main__":
    sys.exit(main())
