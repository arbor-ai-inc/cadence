#!/usr/bin/env python3
"""Tests for skill_miner.py. Stdlib unittest; every fixture is synthetic.

    python3 -m unittest discover -s contrib/skill-miner/tests -v
    python3 contrib/skill-miner/tests/test_skill_miner.py

Each test builds a throwaway git repo plus fake Claude Code / Codex data dirs in a
tempdir, writes invented session logs into them, and runs the real CLI entry point.
"""

from __future__ import annotations

import builtins
import contextlib
import io
import json
import os
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import skill_miner  # noqa: E402

NOW = "2099-01-01T00:00:00Z"  # far future so --since never filters fixtures by timestamp

# Sentinels that must never reach a candidate file.
ASSISTANT_SENTINEL = "ZZASSISTANTTEXTZZ"
TOOL_SENTINEL = "ZZTOOLOUTPUTZZ"
THINKING_SENTINEL = "ZZTHINKINGZZ"
REMINDER_SENTINEL = "ZZREMINDERZZ"
PASTED_SENTINEL = "ZZPASTEDZZ"
SIDECHAIN_SENTINEL = "ZZSIDECHAINZZ"

REQUEST = "regenerate the changelog from merged pull requests and group entries by component"
REQUEST_VARIANTS = [
    REQUEST,
    "regenerate the changelog from merged pull requests, group entries by component",
    "please regenerate changelog from the merged pull requests and group the entries by component",
]
CORRECTION = "no, run the formatter before committing the changes"


def git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


class Fixture:
    """A temp repo plus fake agent homes, with helpers to write session logs."""

    def __init__(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="skill-miner-test-")).resolve()
        self.repo = self.tmp / "proj"
        self.repo.mkdir()
        git("init", "-q", "-b", "main", cwd=self.repo)
        git("-c", "user.email=t@example.invalid", "-c", "user.name=t", "commit", "-q", "--allow-empty", "-m", "init", cwd=self.repo)
        (self.repo / ".gitignore").write_text(".skill-candidates/\n")
        self.claude = self.tmp / "claude-home"
        self.codex = self.tmp / "codex-home"
        self._n = 0

    def cleanup(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    # --- Claude Code -------------------------------------------------------
    def claude_session(self, prompts: list[str], cwd: Path | None = None, extra: list[dict] | None = None) -> str:
        cwd = cwd or self.repo
        self._n += 1
        sid = f"c{self._n:07d}-0000-0000-0000-000000000000"
        d = self.claude / "projects" / skill_miner.encode_claude_project(cwd)
        d.mkdir(parents=True, exist_ok=True)
        base = {"cwd": str(cwd), "sessionId": sid, "timestamp": NOW, "isSidechain": False}
        recs: list[dict] = []
        for p in prompts:
            recs.append({**base, "type": "user", "promptSource": "typed", "message": {"role": "user", "content": p}})
            recs.append({
                **base, "type": "assistant",
                "message": {"role": "assistant", "content": [
                    {"type": "thinking", "thinking": THINKING_SENTINEL},
                    {"type": "text", "text": ASSISTANT_SENTINEL},
                    {"type": "tool_use", "name": "Bash", "input": {"command": "echo hi"}},
                ]},
            })
            recs.append({
                **base, "type": "user", "toolUseResult": {"stdout": TOOL_SENTINEL},
                "message": {"role": "user", "content": [{"type": "tool_result", "content": TOOL_SENTINEL}]},
            })
        recs.extend({**r, "sessionId": sid} for r in (extra or []))
        (d / f"{sid}.jsonl").write_text("\n".join(json.dumps(r) for r in recs) + "\n")
        return sid

    def claude_command(self, name: str, cwd: Path | None = None) -> str:
        cwd = cwd or self.repo
        return self.claude_session([], cwd=cwd, extra=[{
            "type": "user", "cwd": str(cwd), "sessionId": "x", "timestamp": NOW,
            "message": {"role": "user", "content": f"<command-name>/{name}</command-name>\n<command-args></command-args>"},
        }])

    # --- Codex ---------------------------------------------------------------
    def codex_session(self, prompts: list[str], cwd: Path | None = None, repo_url: str | None = None) -> str:
        cwd = cwd or self.repo
        self._n += 1
        sid = f"x{self._n:07d}-0000-0000-0000-000000000000"
        d = self.codex / "sessions" / "2099" / "01" / "01"
        d.mkdir(parents=True, exist_ok=True)
        meta = {"id": sid, "cwd": str(cwd)}
        if repo_url:
            meta["git"] = {"repository_url": repo_url}
        recs: list[dict] = [{"timestamp": NOW, "type": "session_meta", "payload": meta}]
        for p in prompts:
            recs.append({"timestamp": NOW, "type": "event_msg", "payload": {"type": "user_message", "message": p}})
            recs.append({"timestamp": NOW, "type": "response_item", "payload": {"type": "function_call_output", "output": TOOL_SENTINEL}})
            recs.append({"timestamp": NOW, "type": "event_msg", "payload": {"type": "agent_message", "message": ASSISTANT_SENTINEL}})
        (d / f"rollout-{sid}.jsonl").write_text("\n".join(json.dumps(r) for r in recs) + "\n")
        return sid

    # --- running -------------------------------------------------------------
    def run(self, *extra: str) -> tuple[int, dict, str]:
        argv = [
            "--repo", str(self.repo), "--claude-home", str(self.claude), "--codex-home", str(self.codex),
            "--since", "all", "--json", *extra,
        ]
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = skill_miner.main(argv)
        summary = json.loads(out.getvalue()) if rc == 0 else {}
        return rc, summary, err.getvalue()

    def written_text(self, summary: dict) -> str:
        return "\n".join(Path(p).read_text() for p in summary["written"])


class SkillMinerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.f = Fixture()
        self.addCleanup(self.f.cleanup)

    def kinds(self, summary: dict) -> dict[str, list[str]]:
        out: dict[str, list[str]] = {}
        for c in summary["candidates"]:
            out.setdefault(c["kind"], []).append(c["name"])
        return out

    # --- detection -------------------------------------------------------------
    def test_repeated_request_across_agents_becomes_one_candidate(self):
        self.f.claude_session([REQUEST_VARIANTS[0]])
        self.f.claude_session([REQUEST_VARIANTS[1]])
        self.f.codex_session([REQUEST_VARIANTS[2]])
        rc, s, _ = self.f.run()
        self.assertEqual(rc, 0)
        requests = [c for c in s["candidates"] if c["kind"] == "request"]
        self.assertEqual(len(requests), 1, s)
        self.assertEqual(requests[0]["occurrences"], 3)
        self.assertEqual(requests[0]["sessions"], 3)
        text = self.f.written_text(s)
        self.assertIn("agents: [claude-code, codex]", text)
        self.assertIn("status: unreviewed", text)

    def test_below_threshold_is_not_a_candidate(self):
        self.f.claude_session([REQUEST_VARIANTS[0]])
        self.f.claude_session([REQUEST_VARIANTS[1]])
        rc, s, _ = self.f.run()
        self.assertEqual(rc, 0)
        self.assertEqual(s["candidates"], [])

    def test_min_sessions_counts_distinct_sessions(self):
        self.f.claude_session(REQUEST_VARIANTS)  # three times, one session
        rc, s, _ = self.f.run()
        self.assertEqual([c for c in s["candidates"] if c["kind"] == "request"], [])

    def test_correction_needs_a_preceding_assistant_turn(self):
        # First prompt of a session cannot correct anything.
        for _ in range(3):
            self.f.claude_session([CORRECTION])
        rc, s, _ = self.f.run()
        self.assertNotIn("correction", self.kinds(s))
        # After an assistant turn it can.
        for _ in range(3):
            self.f.claude_session(["tidy up the module layout for the parser", CORRECTION])
        rc, s, _ = self.f.run()
        self.assertIn("correction", self.kinds(s))
        text = self.f.written_text(s)
        self.assertIn("suggested: rule", text)

    def test_single_word_marker_must_open_the_prompt(self):
        self.assertTrue(skill_miner.is_correction("No, use the other flag", skill_miner.DEFAULT_CORRECTION_MARKERS))
        self.assertFalse(skill_miner.is_correction("is there no faster way", skill_miner.DEFAULT_CORRECTION_MARKERS))
        self.assertTrue(skill_miner.is_correction("hmm, why did you delete it", skill_miner.DEFAULT_CORRECTION_MARKERS))

    def test_repeated_command_invocation_is_a_workflow_candidate(self):
        for _ in range(3):
            self.f.claude_command("release-notes-draft")
        for _ in range(3):
            self.f.claude_command("clear")  # built-in: ignored
        rc, s, _ = self.f.run()
        self.assertEqual(self.kinds(s).get("workflow"), ["release-notes-draft"])

    def test_codex_leading_invocation(self):
        for _ in range(3):
            self.f.codex_session(["$triage-flaky-test for the nightly job"])
        rc, s, _ = self.f.run()
        self.assertEqual(self.kinds(s).get("workflow"), ["triage-flaky-test"])

    # --- dedupe ------------------------------------------------------------------
    def test_existing_skill_suppresses_workflow_and_request(self):
        skill = self.f.repo / ".claude" / "skills" / "release-notes-draft"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text(
            "---\nname: release-notes-draft\ndescription: Regenerate the changelog from merged pull requests grouped by component.\n---\n"
        )
        for _ in range(3):
            self.f.claude_command("release-notes-draft")
        for v in REQUEST_VARIANTS:
            self.f.claude_session([v])
        rc, s, _ = self.f.run()
        self.assertEqual(s["candidates"], [], s)
        self.assertEqual(s["covered_by_existing_skills"], 2)

    def test_extra_skills_dir_from_config(self):
        docs = self.f.repo / "handbook" / "workflows"
        docs.mkdir(parents=True)
        (docs / "changelog.md").write_text(
            "---\nname: changelog\ndescription: regenerate changelog from merged pull requests, grouped by component\n---\n"
        )
        cfg = self.f.tmp / "cfg.toml"
        cfg.write_text('skills_dirs = ["handbook/workflows"]\n')
        for v in REQUEST_VARIANTS:
            self.f.claude_session([v])
        rc, s, _ = self.f.run("--config", str(cfg))
        self.assertEqual(s["candidates"], [])

    # --- scoping -----------------------------------------------------------------
    def test_other_repos_and_prefix_siblings_are_ignored(self):
        sibling = self.f.tmp / "proj2"  # shares the encoded-name prefix
        other = self.f.tmp / "elsewhere"
        for d in (sibling, other):
            d.mkdir()
            for v in REQUEST_VARIANTS:
                self.f.claude_session([v], cwd=d)
                self.f.codex_session([v], cwd=d)
        rc, s, _ = self.f.run()
        self.assertEqual(s["prompts"], 0)
        self.assertEqual(s["candidates"], [])

    def test_subdirectory_and_worktree_sessions_count(self):
        sub = self.f.repo / "pkg" / "core"
        sub.mkdir(parents=True)
        wt = self.f.tmp / "proj-wt"
        git("worktree", "add", "-q", str(wt), cwd=self.f.repo)
        self.f.claude_session([REQUEST_VARIANTS[0]], cwd=sub)
        self.f.claude_session([REQUEST_VARIANTS[1]], cwd=wt)
        self.f.codex_session([REQUEST_VARIANTS[2]], cwd=wt)
        rc, s, _ = self.f.run()
        self.assertEqual(s["prompts"], 3)
        self.assertEqual(len(s["candidates"]), 1)

    # --- same remote -------------------------------------------------------------
    def clone(self, name: str, origin: str | None) -> Path:
        d = self.f.tmp / name
        d.mkdir()
        git("init", "-q", cwd=d)
        if origin:
            git("remote", "add", "origin", origin, cwd=d)
        return d

    def test_same_remote_includes_other_clones_of_the_same_repo(self):
        git("remote", "add", "origin", "git@github.example-work:Acme/widget.git", cwd=self.f.repo)
        second = self.clone("proj2", "https://github.example/acme/widget.git")  # also shares the name prefix
        other = self.clone("other", "https://github.example/acme/gadget.git")
        self.f.claude_session([REQUEST_VARIANTS[0]])
        self.f.claude_session([REQUEST_VARIANTS[1]], cwd=second)
        self.f.codex_session([REQUEST_VARIANTS[2]], cwd=second)
        for v in REQUEST_VARIANTS:
            self.f.claude_session([v], cwd=other)

        _, off, _ = self.f.run()
        self.assertEqual(off["prompts"], 1)
        self.assertEqual(off["candidates"], [])

        _, on, _ = self.f.run("--same-remote")
        self.assertEqual(on["prompts"], 3)
        self.assertEqual(len(on["candidates"]), 1)
        self.assertIn(str(second), on["checkouts"])
        self.assertNotIn(str(other), on["checkouts"])
        self.assertEqual(on["same_remote"], "acme/widget")

    def test_same_remote_from_config_and_cli_override(self):
        git("remote", "add", "origin", "https://github.example/acme/widget.git", cwd=self.f.repo)
        second = self.clone("second", "git@github.example:acme/widget.git")
        for v in REQUEST_VARIANTS:
            self.f.claude_session([v], cwd=second)
        cfg = self.f.tmp / "cfg.toml"
        cfg.write_text("same_remote = true\n")
        _, s, _ = self.f.run("--config", str(cfg))
        self.assertEqual(s["prompts"], 3)
        _, s, _ = self.f.run("--config", str(cfg), "--no-same-remote")
        self.assertEqual(s["prompts"], 0)

    def test_codex_repository_url_counts_after_the_clone_is_gone(self):
        git("remote", "add", "origin", "https://github.example/acme/widget.git", cwd=self.f.repo)
        gone = self.f.tmp / "deleted-clone"
        for v in REQUEST_VARIANTS:
            self.f.codex_session([v], cwd=gone, repo_url="git@github.example:acme/widget.git")
        _, s, _ = self.f.run("--same-remote")
        self.assertEqual(s["prompts"], 3)

    def test_same_remote_without_origin_warns_and_stays_local(self):
        second = self.clone("second", "https://github.example/acme/widget.git")
        for v in REQUEST_VARIANTS:
            self.f.claude_session([v], cwd=second)
        _, s, _ = self.f.run("--same-remote")
        self.assertEqual(s["prompts"], 0)
        self.assertTrue(any("no usable origin" in w for w in s["warnings"]))

    def test_normalize_remote(self):
        n = skill_miner.normalize_remote
        self.assertEqual(n("git@github.com-work:Acme/Widget.git"), "acme/widget")
        self.assertEqual(n("https://user:secret@github.com/acme/widget.git/"), "acme/widget")
        self.assertEqual(n("ssh://git@host:2222/group/sub/widget.git"), "sub/widget")
        self.assertEqual(n("/srv/git/acme/widget.git"), "acme/widget")
        self.assertIsNone(n("widget"))
        self.assertIsNone(n(None))

    # --- handoffs ----------------------------------------------------------------
    def handoff(self, slug: str, body: str, root: Path | None = None, name: str | None = None) -> Path:
        d = (root or self.f.repo) / ".local"
        d.mkdir(exist_ok=True)
        (self.f.repo / ".gitignore").write_text(".skill-candidates/\n.local/\n")
        p = d / (name or f"HANDOFF-{slug}.md")
        p.write_text(f"# Handoff — {slug}\n\nLast written: 2099-01-05\n\n{body}")
        return p

    RULE_A = "## Rules\n- rebuild the fixture index before running the widget tests, or they read stale rows\n"
    RULE_B = "## Gotchas that cost real time\n- rebuild the fixture index before the widget tests run; otherwise stale rows are read\n"

    def test_rule_repeated_across_handoffs_is_a_candidate(self):
        self.handoff("PROJ-1-cache", self.RULE_A)
        self.handoff("theme-quota", self.RULE_B)
        _, s, _ = self.f.run()
        kinds = self.kinds(s)
        self.assertEqual(len(kinds.get("handoff-rule", [])), 1, s)
        self.assertEqual(s["handoff_tracks"], 2)
        text = self.f.written_text(s)
        self.assertIn("handoffs: 2", text)
        self.assertIn("suggested: rule", text)
        self.assertIn("handoff `PROJ-1-cache` § Rules", text)

    def test_one_handoff_and_its_archive_are_one_track(self):
        self.handoff("PROJ-1-cache", self.RULE_A)
        self.handoff("PROJ-1-cache", self.RULE_B, name="HANDOFF-PROJ-1-cache.archive.md")
        self.handoff("legacy", self.RULE_A)
        self.handoff("legacy", self.RULE_B, name="HANDOFF-legacy-ARCHIVE.md")
        _, s, _ = self.f.run()
        self.assertEqual(s["handoff_tracks"], 2)
        self.assertEqual(len(self.kinds(s).get("handoff-rule", [])), 1)  # PROJ-1-cache + legacy, not four

    def test_decisions_mined_and_facts_ignored(self):
        body = (
            "## Facts\n- the cache TTL is sixty seconds per the config file\n"
            "### Decided — don't re-open\n- use LRU eviction over LFU because it measured equal and simpler\n"
            "## Do not re-derive these\n- the widget service listens on the internal port only\n"
        )
        self.handoff("PROJ-1-cache", body)
        self.handoff("PROJ-2-store", body.replace("sixty", "ninety"))
        _, s, _ = self.f.run()
        kinds = self.kinds(s)
        self.assertEqual(len(kinds.get("handoff-decision", [])), 1, s)
        self.assertNotIn("handoff-rule", kinds)
        text = self.f.written_text(s)
        self.assertNotIn("TTL", text)
        self.assertNotIn("internal port", text)
        self.assertIn("suggested: decision", text)

    def test_single_handoff_is_not_a_pattern(self):
        self.handoff("PROJ-1-cache", self.RULE_A + self.RULE_B.replace("## Gotchas that cost real time\n", ""))
        _, s, _ = self.f.run()
        self.assertNotIn("handoff-rule", self.kinds(s))

    def test_old_pending_promotion_is_listed_and_new_one_is_not(self):
        self.handoff("PROJ-1-cache", "## Rules\n- → to promote: widget retry budget → docs/widgets.md — source: PR 4 · verified 2099-01-01\n")
        old = self.handoff("PROJ-2-store", "## Rules\n- → to promote: store backup cadence → docs/store.md — source: PR 9 · verified 2000-01-01\n")
        _, s, _ = self.f.run()
        pend = [c for c in s["candidates"] if c["kind"] == "pending-promotion"]
        self.assertEqual(len(pend), 1, s)
        self.assertIn("store backup cadence", self.f.written_text(s))
        self.assertTrue(old.exists())  # the miner never edits handoffs

    def test_handoff_rule_matching_a_session_correction_ranks_first(self):
        for _ in range(2):
            self.f.claude_session(["tidy the widget module", "no, rebuild the fixture index before running the widget tests"])
        self.handoff("PROJ-1-cache", self.RULE_A)
        self.handoff("theme-quota", self.RULE_B)
        for v in REQUEST_VARIANTS:
            self.f.claude_session([v])
        _, s, _ = self.f.run()
        self.assertEqual(s["candidates"][0]["kind"], "handoff-rule", s["candidates"])
        self.assertIn("also: the same point was given as a correction", self.f.written_text(s))

    def test_no_handoffs_flag_and_config(self):
        self.handoff("PROJ-1-cache", self.RULE_A)
        self.handoff("theme-quota", self.RULE_B)
        _, s, _ = self.f.run("--no-handoffs")
        self.assertEqual(s["handoff_files"], 0)
        cfg = self.f.tmp / "cfg.toml"
        cfg.write_text('handoff_globs = ["notes/*.handoff.md"]\n')
        _, s, _ = self.f.run("--config", str(cfg))
        self.assertEqual(s["handoff_files"], 0)
        cfg.write_text("min_handoffs = 1\n")
        rc, _, err = self.f.run("--config", str(cfg))
        self.assertEqual(rc, 2)

    def test_handoffs_in_same_remote_clones_count(self):
        git("remote", "add", "origin", "https://github.example/acme/widget.git", cwd=self.f.repo)
        second = self.clone("proj2", "git@github.example:acme/widget.git")
        self.handoff("PROJ-1-cache", self.RULE_A)
        self.handoff("theme-quota", self.RULE_B, root=second)
        # Clones are discovered through their session logs, so this one needs a session.
        self.f.claude_session(["look at the widget cache layout"], cwd=second)
        _, off, _ = self.f.run()
        self.assertEqual(off["handoff_files"], 1)
        _, on, _ = self.f.run("--same-remote")
        self.assertEqual(on["handoff_files"], 2)
        self.assertEqual(len(self.kinds(on).get("handoff-rule", [])), 1)

    def test_handoff_evidence_is_redacted(self):
        secret = "ghp_" + "Z" * 36
        self.handoff("PROJ-1-cache", self.RULE_A.replace("stale rows", f"stale rows token={secret}"))
        self.handoff("theme-quota", self.RULE_B)
        _, s, _ = self.f.run()
        self.assertNotIn(secret, self.f.written_text(s))

    # --- privacy -----------------------------------------------------------------
    def test_only_human_prompts_are_extracted(self):
        extra = lambda sid_cwd: [  # noqa: E731
            {"type": "user", "cwd": str(self.f.repo), "sessionId": "s", "timestamp": NOW, "promptSource": "system",
             "message": {"content": f"{REQUEST} {REMINDER_SENTINEL}"}},
            {"type": "user", "cwd": str(self.f.repo), "sessionId": "s", "timestamp": NOW, "isSidechain": True,
             "message": {"content": f"{REQUEST} {SIDECHAIN_SENTINEL}"}},
        ]
        for v in REQUEST_VARIANTS:
            self.f.claude_session(
                [f"{v}\n<system-reminder>{REMINDER_SENTINEL}</system-reminder>\n<pasted_content id=\"1\">{PASTED_SENTINEL}</pasted_content id=\"1\">"],
                extra=extra(None),
            )
        rc, s, _ = self.f.run()
        self.assertEqual(len(s["candidates"]), 1)
        text = self.f.written_text(s)
        for sentinel in (ASSISTANT_SENTINEL, TOOL_SENTINEL, THINKING_SENTINEL, REMINDER_SENTINEL, PASTED_SENTINEL, SIDECHAIN_SENTINEL):
            self.assertNotIn(sentinel, text)

    def test_secrets_are_redacted_in_evidence(self):
        secrets = [
            "ghp_" + "A" * 36,
            "AKIA" + "B" * 16,
            "sk-" + "c" * 32,
            "someone@example.com",
            "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abcdefghijklmnop",
        ]
        for i, v in enumerate(REQUEST_VARIANTS):
            self.f.claude_session([f"{v} token={secrets[i]} {secrets[3]} {secrets[4]} /Users/alice/x"])
        cfg = self.f.tmp / "cfg.toml"
        cfg.write_text("quote_chars = 1000\n")
        rc, s, _ = self.f.run("--config", str(cfg))
        text = self.f.written_text(s)
        for secret in secrets[:3] + secrets[3:]:
            self.assertNotIn(secret, text)
        self.assertNotIn("alice", text)
        self.assertIn("[REDACTED", text)

    def test_extra_redaction_pattern(self):
        cfg = self.f.tmp / "cfg.toml"
        cfg.write_text('extra_redact_patterns = ["PROJECT-[0-9]+"]\nquote_chars = 1000\n')
        for v in REQUEST_VARIANTS:
            self.f.claude_session([f"{v} for PROJECT-4242"])
        rc, s, _ = self.f.run("--config", str(cfg))
        self.assertNotIn("PROJECT-4242", self.f.written_text(s))

    def test_quotes_are_truncated(self):
        long_tail = " lorem" * 200
        for v in REQUEST_VARIANTS:
            self.f.claude_session([v + long_tail])
        rc, s, _ = self.f.run()
        for line in self.f.written_text(s).splitlines():
            if line.startswith("- ") and "session" in line:
                self.assertLess(len(line), 260)

    # --- output safety -------------------------------------------------------------
    def test_output_is_private_and_inside_out_dir(self):
        for v in REQUEST_VARIANTS:
            self.f.claude_session([v])
        rc, s, err = self.f.run()
        self.assertEqual(err, "")
        out = Path(s["out"])
        self.assertTrue(s["written"])
        for p in s["written"]:
            p = Path(p)
            self.assertIn(out, p.parents)
            self.assertFalse(p.name == "SKILL.md")
            self.assertEqual(stat.S_IMODE(p.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(out.stat().st_mode), 0o700)

    def test_refuses_output_inside_a_skill_dir(self):
        rc, s, _ = self.f.run("--out", str(self.f.repo / ".claude" / "skills" / "x"))
        self.assertEqual(rc, 2)

    def test_warns_when_output_not_gitignored(self):
        (self.f.repo / ".gitignore").write_text("")
        for v in REQUEST_VARIANTS:
            self.f.claude_session([v])
        rc, s, _ = self.f.run()
        self.assertTrue(any("not gitignored" in w for w in s["warnings"]))

    def test_dry_run_writes_nothing(self):
        for v in REQUEST_VARIANTS:
            self.f.claude_session([v])
        rc, s, _ = self.f.run("--dry-run")
        self.assertEqual(len(s["candidates"]), 1)
        self.assertEqual(s["written"], [])
        self.assertFalse((self.f.repo / ".skill-candidates").exists())

    def test_rerun_replaces_generated_files_but_keeps_user_files(self):
        for v in REQUEST_VARIANTS:
            self.f.claude_session([v])
        _, s1, _ = self.f.run()
        day = Path(s1["written"][0]).parent
        notes = day / "my-notes.md"
        notes.write_text("keep me\n")
        _, s2, _ = self.f.run()
        self.assertEqual(s1["written"], s2["written"])
        self.assertTrue(notes.exists())

    def test_deterministic(self):
        for v in REQUEST_VARIANTS:
            self.f.claude_session([v])
        for _ in range(3):
            self.f.claude_command("release-notes-draft")
        _, s1, _ = self.f.run()
        t1 = self.f.written_text(s1)
        _, s2, _ = self.f.run()
        self.assertEqual(t1, self.f.written_text(s2))

    # --- isolation guarantees ------------------------------------------------------
    def test_no_network_and_only_git_subprocess_and_scoped_reads(self):
        for v in REQUEST_VARIANTS:
            self.f.claude_session([v])
            self.f.codex_session([v])

        def no_network(*a, **k):
            raise AssertionError("network access attempted")

        spawned: list[list[str]] = []
        real_run = subprocess.run

        def record_run(argv, *a, **k):
            spawned.append(list(argv))
            return real_run(argv, *a, **k)

        opened: list[str] = []
        real_open, real_io_open, real_os_open = builtins.open, io.open, os.open

        def rec(fn):
            def wrapper(file, *a, **k):
                if isinstance(file, (str, os.PathLike)):
                    opened.append(os.fspath(file))
                return fn(file, *a, **k)
            return wrapper

        with mock.patch.object(socket.socket, "connect", no_network), \
             mock.patch.object(socket.socket, "connect_ex", no_network), \
             mock.patch.object(socket, "create_connection", no_network), \
             mock.patch.object(socket, "getaddrinfo", no_network), \
             mock.patch.object(skill_miner.subprocess, "run", record_run), \
             mock.patch.object(builtins, "open", rec(real_open)), \
             mock.patch.object(io, "open", rec(real_io_open)), \
             mock.patch.object(os, "open", rec(real_os_open)):
            rc, s, _ = self.f.run()
        self.assertEqual(rc, 0)
        self.assertTrue(spawned)
        self.assertTrue(all(argv[0] == "git" for argv in spawned), spawned)
        self.assertTrue(opened)
        for path in opened:
            resolved = Path(path).resolve()
            self.assertTrue(resolved == self.f.tmp or self.f.tmp in resolved.parents, f"read outside sandbox: {path}")

    # --- config ----------------------------------------------------------------------
    def test_unknown_config_key_is_an_error(self):
        cfg = self.f.tmp / "cfg.toml"
        cfg.write_text("outt = 'typo'\n")
        rc, _, err = self.f.run("--config", str(cfg))
        self.assertEqual(rc, 2)
        self.assertIn("unknown config keys", err)

    def test_not_a_git_repo(self):
        plain = self.f.tmp / "plain"
        plain.mkdir()
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = skill_miner.main(["--repo", str(plain)])
        # tmp may itself sit inside a git checkout on some machines; only assert when not.
        if subprocess.run(["git", "-C", str(plain), "rev-parse"], capture_output=True).returncode != 0:
            self.assertEqual(rc, 2)

    def test_parse_since(self):
        self.assertIsNone(skill_miner.parse_since("all"))
        self.assertEqual(skill_miner.parse_since("2w").days, 14)
        with self.assertRaises(skill_miner.ConfigError):
            skill_miner.parse_since("soon")

    def test_source_has_no_network_or_extra_process_primitives(self):
        src = Path(skill_miner.__file__).read_text()
        for banned in ("import socket", "urllib", "http.client", "import http", "import requests", "Popen(",
                       "os.system", "os.exec", "os.spawn", "shell=True", "import ssl", "ftplib", "smtplib"):
            self.assertNotIn(banned, src)
        self.assertEqual(src.count("subprocess.run("), 1)


if __name__ == "__main__":
    unittest.main()
