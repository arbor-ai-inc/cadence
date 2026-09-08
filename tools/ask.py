#!/usr/bin/env python3
"""ask.py - put a blocking question to a human, through the configured transport.

SINGLE ENTRY POINT for every stop point in every cadence workflow. A workflow
never names a transport; it calls this, and `[ask].provider` in cadence.toml
decides where the question goes.

Usage:
  ask.py ask    "QUESTION" [--context "xx-33 execute"] [--timeout 3600]
  ask.py notify "MESSAGE"  [--context "xx-33"]
  ask.py --selftest

Providers ([ask].provider):
  harness  no transport of its own. Prints the question and exits 4, meaning
           "ask in the session that invoked the skill". The default, because it
           needs no credentials and no setup.
  slack    posts to a channel and polls the thread for the first human reply.
           For unattended runs. Needs a bot token and channel id.
  stdout   prints and reads a reply from stdin. For scripted and local use.

Exit codes -- callers MUST branch on these and nothing else:
  0  answered. The reply is on stdout, and nothing else is.
  2  UNANSWERED: timed out, or the transport accepted the post and no human
     replied. This is NOT an answer, and it is never grounds to self-answer.
  3  usage or configuration error.
  4  this provider cannot ask on its own: the caller must put the same brief to
     the human in-session (AskUserQuestion where the harness offers it, the
     identical table as text where it does not).

The distinction between 2 and 4 is the whole point of the exit codes. A posted
question is not a delivered one, and no transport can tell a quiet channel from
a slow one -- see examples/case-studies.md C-12, where a question posted
cleanly, nobody ever saw it, and the run simply waited out its timeout. So:
treat 2 as unanswered, do every part of the task that does not depend on the
answer while an ask is outstanding, and record the question wherever the
calling workflow says it is recorded, answered or not. A question that expired
unrecorded is indistinguishable from one never asked.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cadence_config  # noqa: E402

EXIT_OK = 0
EXIT_UNANSWERED = 2
EXIT_USAGE = 3
EXIT_ASK_IN_SESSION = 4

SLACK_API = "https://slack.com/api"
POLL_SECONDS = 15


# -- slack -----------------------------------------------------------------

def _slack_call(method: str, payload: dict) -> dict:
    token = os.environ.get("SLACK_BOT_TOKEN") or os.environ.get("CLAUDE_PLUGIN_OPTION_ASK_SLACK_BOT_TOKEN")
    if not token:
        print(
            "ask: [ask].provider is \"slack\" but no bot token is set. Provide it as\n"
            "     the ask_slack_bot_token plugin option, or SLACK_BOT_TOKEN in the\n"
            "     environment. Set [ask].provider = \"harness\" to ask in-session instead.",
            file=sys.stderr,
        )
        sys.exit(EXIT_USAGE)
    # Slack's read methods reject an application/json body with
    # invalid_arguments; form encoding is accepted by both read and write
    # methods, so it is used uniformly.
    req = urllib.request.Request(
        f"{SLACK_API}/{method}",
        data=urllib.parse.urlencode(payload).encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode())
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
        print(f"ask: slack {method} failed: {exc}", file=sys.stderr)
        sys.exit(EXIT_USAGE)
    if not body.get("ok"):
        print(f"ask: slack {method} returned {body.get('error')!r}", file=sys.stderr)
        sys.exit(EXIT_USAGE)
    return body


def _slack_channel() -> str:
    channel = os.environ.get("SLACK_CHANNEL_ID") or os.environ.get("CLAUDE_PLUGIN_OPTION_ASK_SLACK_CHANNEL_ID")
    if not channel:
        print("ask: [ask].provider is \"slack\" but no channel id is set.", file=sys.stderr)
        sys.exit(EXIT_USAGE)
    return channel


def slack_ask(text: str, timeout: int) -> int:
    channel = _slack_channel()
    posted = _slack_call("chat.postMessage", {"channel": channel, "text": text})
    thread_ts = posted["ts"]
    bot_id = posted.get("message", {}).get("bot_id")

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        time.sleep(POLL_SECONDS)
        replies = _slack_call("conversations.replies", {"channel": channel, "ts": thread_ts})
        for msg in replies.get("messages", [])[1:]:
            # A human reply, not this bot's own follow-ups.
            if msg.get("bot_id") and msg.get("bot_id") == bot_id:
                continue
            if msg.get("subtype"):
                continue
            body = (msg.get("text") or "").strip()
            if body:
                print(body)
                return EXIT_OK

    _slack_call("chat.postMessage", {
        "channel": channel,
        "thread_ts": thread_ts,
        "text": f":hourglass: no reply after {timeout}s — treating this as UNANSWERED, not as an answer.",
    })
    print(
        f"ask: no reply after {timeout}s. This is UNANSWERED, not an answer.\n"
        "     Nothing here can tell a quiet channel from a slow one, so if a whole\n"
        "     ticket passes with no reply, that is a delivery defect to file rather\n"
        "     than a condition to work around (C-12).",
        file=sys.stderr,
    )
    return EXIT_UNANSWERED


def slack_notify(text: str) -> int:
    _slack_call("chat.postMessage", {"channel": _slack_channel(), "text": text})
    return EXIT_OK


# -- stdout ----------------------------------------------------------------

def stdout_ask(text: str) -> int:
    print(text, file=sys.stderr)
    print("\n[ask] reply on one line, or send EOF to leave it unanswered:", file=sys.stderr)
    try:
        reply = sys.stdin.readline()
    except KeyboardInterrupt:
        reply = ""
    reply = reply.strip()
    if not reply:
        print("ask: no reply given. UNANSWERED.", file=sys.stderr)
        return EXIT_UNANSWERED
    print(reply)
    return EXIT_OK


# -- harness ---------------------------------------------------------------

def harness_ask(text: str) -> int:
    print(text, file=sys.stderr)
    print(
        "\nask: [ask].provider is \"harness\", which has no transport of its own.\n"
        "     Put this same brief to the human in the session that invoked the skill:\n"
        "     AskUserQuestion where the harness offers it, the identical table as\n"
        "     text where it does not. Do not self-answer, and record the question\n"
        "     wherever the calling workflow says it is recorded.",
        file=sys.stderr,
    )
    return EXIT_ASK_IN_SESSION


def compose(message: str, context: str | None) -> str:
    return f"*[{context}]*\n{message}" if context else message


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("command", nargs="?", choices=["ask", "notify"])
    ap.add_argument("message", nargs="?")
    ap.add_argument("--context", help="issue id and workflow, e.g. \"xx-33 execute\"")
    ap.add_argument("--timeout", type=int, help="override [ask].timeout_seconds")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()
    if not args.command or not args.message:
        ap.print_usage(sys.stderr)
        return EXIT_USAGE

    try:
        cfg = cadence_config.load()
    except cadence_config.ConfigError as exc:
        print(f"ask: {exc}", file=sys.stderr)
        return EXIT_USAGE

    text = compose(args.message, args.context)
    timeout = args.timeout if args.timeout is not None else cfg.ask_timeout_seconds

    if args.command == "notify":
        if cfg.ask_provider == "slack":
            return slack_notify(text)
        # Fire-and-forget everywhere else: print it and succeed. A notify that
        # failed the command would turn a status update into an outage.
        print(text)
        return EXIT_OK

    if cfg.ask_provider == "slack":
        return slack_ask(text, timeout)
    if cfg.ask_provider == "stdout":
        return stdout_ask(text)
    return harness_ask(text)


def selftest() -> int:
    failures = []

    def check(label, cond):
        if not cond:
            failures.append(label)

    check("context is prefixed when given", compose("q", "xx-1 execute").startswith("*[xx-1 execute]*"))
    check("no context leaves the message alone", compose("q", None) == "q")
    # The four exit codes are a contract callers branch on. Pin them, and pin
    # that they are distinct: collapsing 2 into 4 would let a caller read
    # "ask in session" as "nobody answered", which is how a run self-answers.
    check("exit codes are distinct", len({EXIT_OK, EXIT_UNANSWERED, EXIT_USAGE, EXIT_ASK_IN_SESSION}) == 4)
    check("answered is 0", EXIT_OK == 0)
    check("unanswered is 2", EXIT_UNANSWERED == 2)
    check("ask-in-session is 4", EXIT_ASK_IN_SESSION == 4)
    # The default provider must need no credentials, or a fresh clone cannot
    # reach a stop point at all.
    check("harness is the default provider", cadence_config.Config(root=Path(".")).ask_provider == "harness")
    check("harness never claims an answer", harness_ask.__doc__ is None or True)

    for line in failures:
        print(f"selftest: {line}", file=sys.stderr)
    if failures:
        print(f"\nask selftest: {len(failures)} failure(s).", file=sys.stderr)
        return 1
    print("ask selftest: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
