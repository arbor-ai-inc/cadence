#!/usr/bin/env python3
"""Tests for tools/handoff.py. Stdlib unittest; every fixture is synthetic.

    python3 tests/test_handoff.py
"""

from __future__ import annotations

import contextlib
import io
import json
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
sys.path.insert(0, str(HERE.parent / "tools"))

import handoff  # noqa: E402

TODAY = "2099-01-10"

GOOD = """# Handoff — PROJ-12-widget-cache

Issue: PROJ-12  ·  Epic/project: widgets  ·  Spec: none
Repo: acme/widget  ·  Checkout: {checkout}  ·  Branch(es): proj-12-cache
Owner: sam  ·  Started: 2099-01-01  ·  Last written: 2099-01-09  ·  Status: active

## Resume here — 2099-01-09
Goal: cache widget lookups
State:
- PR #4 open, CI green
Next: address the review comment on #4

## Rules
- run the cache tests with the fake clock — why: real clock flakes (2099-01-05)

## Facts
- cache TTL is 60s — source: config/cache.toml · verified 2099-01-09
### Decided — don't re-open
- LRU over LFU — why: simpler, measured equal · 2099-01-03 · log: 2099-01-03
### Rejected — don't re-propose
- Redis — why not: one more service to run · 2099-01-03

## Log
### 2099-01-09 — review round
- Did: pushed fix · Decided: keep TTL · Promoted: nothing
"""


def git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


class HandoffTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="handoff-test-")).resolve()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.repo = self.tmp / "widget"
        self.repo.mkdir()
        git("init", "-q", "-b", "main", cwd=self.repo)
        git("config", "user.name", "Sam Example", cwd=self.repo)
        git("remote", "add", "origin", "git@github.example-work:acme/widget.git", cwd=self.repo)
        (self.repo / ".gitignore").write_text(".local/\n")
        self.dir = self.repo / ".local"

    def run_cli(self, *argv: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = handoff.main(["--repo", str(self.repo), "--today", TODAY, *argv])
        return rc, out.getvalue(), err.getvalue()

    def write(self, slug: str, text: str) -> Path:
        self.dir.mkdir(exist_ok=True)
        p = self.dir / f"HANDOFF-{slug}.md"
        p.write_text(text)
        return p

    # --- new -------------------------------------------------------------------
    def test_new_creates_dir_and_a_lint_clean_skeleton(self):
        rc, out, _ = self.run_cli("new", "PROJ-12-widget-cache", "--issue", "PROJ-12")
        self.assertEqual(rc, 0)
        p = Path(out.strip())
        self.assertTrue(p.exists())
        self.assertEqual(stat.S_IMODE(p.stat().st_mode), 0o600)
        text = p.read_text()
        self.assertIn("Repo: acme/widget", text)
        self.assertIn(f"Checkout: {self.repo}", text)
        self.assertIn("Owner: Sam Example", text)
        self.assertIn("Issue: PROJ-12", text)
        rc, out, _ = self.run_cli("lint", "PROJ-12")
        self.assertEqual(rc, 0, out)

    def test_new_refuses_when_git_would_track_it(self):
        (self.repo / ".gitignore").write_text("")
        rc, _, err = self.run_cli("new", "theme-quota")
        self.assertEqual(rc, 2)
        self.assertIn("would be tracked by git", err)
        self.assertFalse(self.dir.exists())

    def test_new_refuses_existing_and_bad_slugs(self):
        self.run_cli("new", "theme-quota")
        rc, _, err = self.run_cli("new", "theme-quota")
        self.assertEqual(rc, 2)
        rc, _, err = self.run_cli("new", "My Handoff")
        self.assertEqual(rc, 2)

    # --- resolve -------------------------------------------------------------------
    def test_resolve_exact_then_issue_id_then_fragment(self):
        for s in ("PROJ-12-widget-cache", "PROJ-120-other", "theme-quota"):
            self.write(s, GOOD.format(checkout=self.repo))
        rc, out, _ = self.run_cli("resolve", "PROJ-12")
        self.assertEqual((rc, Path(out.strip()).name), (0, "HANDOFF-PROJ-12-widget-cache.md"))
        rc, out, _ = self.run_cli("resolve", "quota")
        self.assertEqual(rc, 0)
        rc, out, _ = self.run_cli("resolve", "PROJ")  # a non-id fragment hitting two
        self.assertEqual(rc, 3)
        self.assertEqual(len(out.split()), 2)
        rc, _, _ = self.run_cli("resolve", "nothing")
        self.assertEqual(rc, 4)

    def test_issue_id_query_never_matches_a_longer_id(self):
        self.write("PROJ-273-handoff-wiring", GOOD.format(checkout=self.repo))
        for q in ("PROJ-27", "PROJ-2", "proj-27"):
            rc, out, _ = self.run_cli("resolve", q)
            self.assertEqual(rc, 4, (q, out))
        rc, out, _ = self.run_cli("resolve", "PROJ-273")
        self.assertEqual(rc, 0)
        rc, out, _ = self.run_cli("resolve", "wiring")  # a non-id fragment still matches
        self.assertEqual(rc, 0)

    # --- lint --------------------------------------------------------------------
    def test_good_handoff_is_clean(self):
        self.write("PROJ-12-widget-cache", GOOD.format(checkout=self.repo))
        rc, out, _ = self.run_cli("lint", "--json", "--strict")
        self.assertEqual(rc, 0, out)
        self.assertEqual(json.loads(out)["PROJ-12-widget-cache"], [])

    def codes(self, text: str, *extra: str) -> set[str]:
        self.write("PROJ-12-widget-cache", text)
        _, out, _ = self.run_cli("lint", "--json", *extra)
        return {f["code"] for f in json.loads(out)["PROJ-12-widget-cache"]}

    def test_stacked_resume_sections_are_errors(self):
        text = GOOD.format(checkout=self.repo).replace("## Rules", "## RESTART HERE — 2099-01-02\nold\n\n## Rules")
        self.assertIn("stacked-start", self.codes(text))
        text = GOOD.format(checkout=self.repo).replace("## Rules", "## Resume here — 2099-01-02\nold\n\n## Rules")
        self.assertIn("multiple-resume", self.codes(text))
        text = GOOD.format(checkout=self.repo).replace("## Rules", "## ⚡ START HERE — state\nold\n\n## Rules")
        self.assertIn("stacked-start", self.codes(text))
        mention = GOOD.format(checkout=self.repo).replace("## Rules", "## Run plan — the next action is in RESTART HERE\n\n## Rules")
        self.assertNotIn("stacked-start", self.codes(mention))

    def test_dated_slug_warns(self):
        self.write("2099-01-01-proj12-cache", GOOD.format(checkout=self.repo))
        _, out, _ = self.run_cli("lint", "--json")
        self.assertIn("slug-dated", {f["code"] for f in json.loads(out)["2099-01-01-proj12-cache"]})

    def test_caps(self):
        g = GOOD.format(checkout=self.repo)
        long_resume = g.replace("Next:", "\n".join(f"- line {i}" for i in range(45)) + "\nNext:")
        self.assertIn("resume-too-long", self.codes(long_resume))
        long_file = g + "\n".join(f"- filler {i}" for i in range(300))
        self.assertIn("file-too-long", self.codes(long_file))
        long_entry = g + "\n".join(f"- more {i}" for i in range(6))
        self.assertIn("log-entry-long", self.codes(long_entry))

    def test_missing_header_and_bad_status(self):
        g = GOOD.format(checkout=self.repo)
        self.assertIn("header-missing", self.codes(g.replace("Owner: sam  ·  ", "")))
        self.assertIn("bad-status", self.codes(g.replace("Status: active", "Status: done")))

    def test_facts_need_source_and_decisions_need_reasons(self):
        g = GOOD.format(checkout=self.repo)
        c = self.codes(g.replace("- cache TTL is 60s — source: config/cache.toml · verified 2099-01-09", "- cache TTL is 60s"))
        self.assertIn("fact-unsourced", c)
        c = self.codes(g.replace("- LRU over LFU — why: simpler, measured equal", "- LRU over LFU"))
        self.assertIn("decision-no-reason", c)

    def test_hygiene_warnings(self):
        g = GOOD.format(checkout="/definitely/not/here")
        self.assertIn("checkout-missing", self.codes(g))
        stale = GOOD.format(checkout=self.repo).replace("Last written: 2099-01-09", "Last written: 2098-11-01")
        self.assertIn("stale", self.codes(stale))
        pointer = GOOD.format(checkout=self.repo).replace("## Rules\n", "## Rules\n- → promoted to docs/x.md (PR #9)\n")
        self.assertIn("promoted-pointers", self.codes(pointer))
        p = self.write("PROJ-12-widget-cache", GOOD.format(checkout=self.repo))
        (p.parent / (p.name + ".bak-20990101T000000Z")).write_text("x")
        self.assertIn("timestamped-backups", self.codes(p.read_text()))

    def test_archive_cap(self):
        p = self.write("PROJ-12-widget-cache", GOOD.format(checkout=self.repo))
        p.with_name("HANDOFF-PROJ-12-widget-cache.archive.md").write_text("\n".join(f"- old {i}" for i in range(301)))
        self.assertIn("archive-too-long", self.codes(p.read_text()))
        rc, out, _ = self.run_cli("list", "--json")
        self.assertEqual([r["slug"] for r in json.loads(out)], ["PROJ-12-widget-cache"])  # archive is not a handoff

    def test_strict_fails_on_warnings(self):
        g = GOOD.format(checkout="/definitely/not/here")
        self.write("PROJ-12-widget-cache", g)
        self.assertEqual(self.run_cli("lint")[0], 0)
        self.assertEqual(self.run_cli("lint", "--strict")[0], 1)

    # --- list / backup -----------------------------------------------------------------
    def test_list_and_backup(self):
        self.write("PROJ-12-widget-cache", GOOD.format(checkout=self.repo))
        rc, out, _ = self.run_cli("list")
        self.assertEqual(rc, 0)
        self.assertIn("PROJ-12-widget-cache", out)
        self.assertIn("active", out)
        rc, out, _ = self.run_cli("backup", "PROJ-12")
        prev = Path(out.strip())
        self.assertEqual(prev.name, "HANDOFF-PROJ-12-widget-cache.md.prev")
        self.assertEqual(stat.S_IMODE(prev.stat().st_mode), 0o600)

    def test_settings_file_caps_and_unknown_keys(self):
        cfg = self.tmp / "h.toml"
        cfg.write_text("file_max_lines = 10\n")
        self.write("PROJ-12-widget-cache", GOOD.format(checkout=self.repo))
        _, out, _ = self.run_cli("--config", str(cfg), "lint", "--json")
        self.assertIn("file-too-long", {f["code"] for f in json.loads(out)["PROJ-12-widget-cache"]})
        cfg.write_text("typo = 1\n")
        self.assertEqual(self.run_cli("--config", str(cfg), "list")[0], 2)

    def test_cadence_toml_handoff_table(self):
        (self.repo / "cadence.toml").write_text('[paths]\nspecs = "specs"\n\n[handoff]\nfile_max_lines = 10\n')
        self.write("PROJ-12-widget-cache", GOOD.format(checkout=self.repo))
        _, out, _ = self.run_cli("lint", "--json")
        self.assertIn("file-too-long", {f["code"] for f in json.loads(out)["PROJ-12-widget-cache"]})
        (self.repo / "cadence.toml").write_text("[handoff]\ntypo = 1\n")
        self.assertEqual(self.run_cli("list")[0], 2)

    # --- worktrees ----------------------------------------------------------------------
    def test_linked_worktree_uses_the_main_worktrees_handoffs(self):
        git("-c", "user.email=sam@example.com", "commit", "-q", "--allow-empty", "-m", "init", cwd=self.repo)
        wt = self.tmp / "widget-wt"
        git("worktree", "add", "-q", "-b", "feature", str(wt), cwd=self.repo)
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = handoff.main(["--repo", str(wt), "--today", TODAY, "new", "PROJ-7-from-wt", "--issue", "PROJ-7"])
        self.assertEqual(rc, 0, err.getvalue())
        p = Path(out.getvalue().strip())
        self.assertEqual(p.parent, self.dir)
        text = p.read_text()
        self.assertIn(f"Checkout: {wt.resolve()}", text)
        self.assertIn("Branch(es): feature", text)
        rc, out, _ = self.run_cli("resolve", "PROJ-7")
        self.assertEqual((rc, Path(out.strip())), (0, p))

    # --- isolation ----------------------------------------------------------------------
    def test_no_network_and_only_git(self):
        self.write("PROJ-12-widget-cache", GOOD.format(checkout=self.repo))
        spawned = []
        real = subprocess.run

        def rec(argv, *a, **k):
            spawned.append(argv[0])
            return real(argv, *a, **k)

        def boom(*a, **k):
            raise AssertionError("network")

        with mock.patch.object(socket.socket, "connect", boom), mock.patch.object(socket, "create_connection", boom), \
             mock.patch.object(handoff.subprocess, "run", rec):
            for cmd in (["list"], ["lint"], ["resolve", "PROJ-12"], ["new", "theme-x"], ["backup", "PROJ-12"]):
                self.run_cli(*cmd)
        self.assertTrue(spawned)
        self.assertEqual(set(spawned), {"git"})
        src = Path(handoff.__file__).read_text()
        for banned in ("import socket", "urllib", "http.client", "Popen(", "os.system", "shell=True"):
            self.assertNotIn(banned, src)


if __name__ == "__main__":
    unittest.main()
