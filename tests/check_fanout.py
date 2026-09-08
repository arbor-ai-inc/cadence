#!/usr/bin/env python3
"""Verify tools/fanout.py against real git worktrees.

Stdlib `unittest` rather than pytest, deliberately. CI runs the hook set on a
bare `setup-python` runner with no pytest installed, so a pytest-only file
would never run in CI at all — an unrun suite and a passing suite look
identical from outside, which is exactly the trap in
examples/case-studies.md C-10. This file runs two ways:

    python3 tests/check_fanout.py     # commit hook + CI
    pytest tests/check_fanout.py      # locally, if you prefer

Every test builds a throwaway git repo in a tempdir and drives the real CLI as
a subprocess, because the things worth testing here are git side effects:
whether a worktree exists, whether a branch was deleted, whether a refusal left
the tree untouched. Mocking git would test none of that.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FANOUT = ROOT / "tools" / "fanout.py"

ISSUE = "XX-999"


def digest_limit():
    """Read DIGEST_LIMIT from the tool so the test tracks the constant."""
    import re
    src = FANOUT.read_text(encoding="utf-8")
    return int(re.search(r"^DIGEST_LIMIT = (\d+)", src, re.M).group(1))


# The boundary is configuration now, so the suite DECLARES one in each
# throwaway repo instead of reading a constant out of the tool. That is a
# stronger test: it exercises the config path an adopter actually uses, and it
# covers the shapes that matter rather than one project's particular paths.
#
# Both trailing-slash forms are here on purpose -- a directory entry and an
# exact-file entry have different matching rules, and the near-miss tests below
# depend on both being present.
MUST_STOP_FIXTURE = [
    ("db/migrations/", "a schema migration"),
    ("api/contracts/", "a durable published contract"),
    ("api/models.py", "the API schema"),
    ("src/serving/", "the serving critical path"),
    ("src/events/", "billable event publish"),
    ("src/billing/rollup/", "the money-bearing reporting tables"),
    ("static/runtime/", "the runtime shipped to third parties"),
    ("static/tag.js", "the tag shipped to third parties"),
]


def must_stop_entries():
    """The paths the fixture config declares."""
    return [path for path, _reason in MUST_STOP_FIXTURE]


def cadence_toml() -> str:
    """The fixture config each throwaway repo gets."""
    lines = []
    for path, reason in MUST_STOP_FIXTURE:
        lines.append("[[must_stop]]")
        lines.append(f'path = "{path}"')
        lines.append(f'reason = "{reason}"')
        lines.append("")
    return "\n".join(lines)


def load_fanout_module():
    """Import fanout.py by path, for the one test that inspects its parser."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("_fanout_under_test", FANOUT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def subparser_map(parser):
    """{subcommand name: its parser}, from an argparse parser with subparsers."""
    import argparse
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return dict(action.choices)
    raise AssertionError("fanout.py's parser has no subparsers")


# Mirrors STATE_DIR in fanout.py. Read from the tool rather than duplicated,
# so a rename there fails here loudly instead of silently testing the old path.
def _state_dir():
    import re
    src = FANOUT.read_text(encoding="utf-8")
    return re.search(r'^STATE_DIR = "([^"]+)"', src, re.M).group(1)


STATE_DIR = _state_dir()


# Throwaway repos must not inherit the developer's global git config.
# `commit.gpgsign=true` makes every commit here fail; `core.hooksPath` or
# `init.templateDir` would hand these repos somebody else's hooks, which is a
# poor foundation for a suite whose whole subject is hook enforcement. Since this
# file is the only gate on fanout.py, a false red trains people to reach for
# --no-verify.
GIT_ENV = {
    **os.environ,
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_SYSTEM": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
}


def git(*args, cwd):
    proc = subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True, text=True, check=False,
        env=GIT_ENV,
    )
    if proc.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed: {proc.stderr}")
    return proc.stdout.strip()


class FanoutCase(unittest.TestCase):
    """A throwaway repo per test, with the CLI driven as a subprocess."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name).resolve() / "repo"
        self.repo.mkdir()
        git("init", "-b", "main", cwd=self.repo)
        git("config", "user.email", "test@example.com", cwd=self.repo)
        git("config", "user.name", "Test", cwd=self.repo)
        # Mirror the real repo: fan-out state and worktrees are gitignored, so
        # `git status` in the root worktree stays clean.
        (self.repo / ".gitignore").write_text(".cadence/\n", encoding="utf-8")
        (self.repo / "cadence.toml").write_text(cadence_toml(), encoding="utf-8")
        (self.repo / "app.py").write_text("print('trunk')\n", encoding="utf-8")
        git("add", "-A", cwd=self.repo)
        git("commit", "-m", "trunk", cwd=self.repo)
        git("checkout", "-b", "xx-999", cwd=self.repo)

    def tearDown(self):
        self._tmp.cleanup()

    # -- helpers ---------------------------------------------------------

    def run_cli(self, *args, cwd=None):
        proc = subprocess.run(
            [sys.executable, str(FANOUT), *args],
            cwd=str(cwd or self.repo),
            capture_output=True,
            text=True,
            check=False,
            env=GIT_ENV,
        )
        return proc.returncode, proc.stdout, proc.stderr

    def ok(self, *args, cwd=None):
        code, out, err = self.run_cli(*args, cwd=cwd)
        self.assertEqual(code, 0, f"expected success, got {code}\nstdout:{out}\nstderr:{err}")
        return out

    def state(self):
        path = self.repo / STATE_DIR / "fanout" / "xx-999" / "tree.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def worktree_paths(self):
        listing = git("worktree", "list", "--porcelain", cwd=self.repo)
        return [
            line.split(" ", 1)[1]
            for line in listing.splitlines()
            if line.startswith("worktree ")
        ]

    def branches(self):
        return git("branch", "--format=%(refname:short)", cwd=self.repo).splitlines()

    def init(self, **caps):
        args = ["init", ISSUE]
        for key, value in caps.items():
            args += [f"--{key.replace('_', '-')}", str(value)]
        return self.ok(*args)

    def fork_two(self, decision="Cache in-process or in Redis?"):
        return self.ok(
            "fork",
            ISSUE,
            "--decision",
            decision,
            "--why-you",
            "either is defensible and the operational cost is yours to carry",
            "--source",
            "app.py:1",
            "--option",
            "inline:dict in the module:no new dependency to operate",
            "--option",
            "redis:shared Redis cache:survives a restart, shared across pods",
        )

    def commit_in(self, path, message, filename="leaf.txt"):
        (Path(path) / filename).write_text(message, encoding="utf-8")
        git("add", "-A", cwd=path)
        git("commit", "-m", message, cwd=path)


class TestFork(FanoutCase):
    def test_init_pins_base_and_creates_root(self):
        self.init()
        state = self.state()
        self.assertEqual(state["base_branch"], "xx-999")
        self.assertEqual(state["root"], "n0")
        self.assertEqual(state["base_sha"], git("rev-parse", "HEAD", cwd=self.repo))
        self.assertEqual(state["nodes"]["n0"]["worktree"], None)

    def test_init_warns_when_hooks_are_missing(self):
        """The must-stop gate IS the pre-commit hook; absent hooks look identical."""
        _code, _out, err = self.run_cli("init", ISSUE)
        self.assertIn("must-stop boundary is NOT enforced", err)
        self.assertIn("fanout-scope hook", err)

    def test_init_refuses_to_clobber_without_force(self):
        self.init()
        code, _out, err = self.run_cli("init", ISSUE)
        self.assertEqual(code, 1)
        self.assertIn("already exists", err)

    def test_fork_creates_one_worktree_per_option(self):
        self.init()
        out = self.fork_two()
        self.assertIn("d1", out)
        state = self.state()
        self.assertEqual(len(state["decisions"]), 1)
        leaves = [n for n, node in state["nodes"].items() if not node["children"]]
        self.assertEqual(len(leaves), 2)
        for slug in ("inline", "redis"):
            path = self.repo / STATE_DIR / "worktrees" / "xx-999" / slug
            self.assertTrue(path.is_dir(), f"missing worktree for {slug}")
            self.assertIn(f"fan/xx-999/{slug}", self.branches())
        # The root node keeps the trunk branch; it is not a fan branch.
        self.assertIn("xx-999", self.branches())

    def test_fork_requires_a_reason_per_option(self):
        self.init()
        code, _out, err = self.run_cli(
            "fork", ISSUE,
            "--decision", "Q", "--why-you", "the tradeoff is the author\'s", "--source", "app.py:1",
            "--option", "inline:only two fields",
            "--option", "redis:shared:survives restart",
        )
        self.assertEqual(code, 1)
        self.assertIn("colon-separated", err)
        self.assertEqual(self.worktree_paths(), [str(self.repo)])

    def test_child_branches_from_parent_head_not_base(self):
        """The prefix tree shares the trunk: work done on a leaf reaches its children."""
        self.init()
        self.fork_two()
        leaf = self.repo / STATE_DIR / "worktrees" / "xx-999" / "inline"
        self.commit_in(leaf, "inline-progress")
        self.ok(
            "fork", ISSUE, "--parent", "n1",
            "--decision", "Strict or lenient parsing?", "--why-you", "the tradeoff is the author\'s", "--source", "app.py:9",
            "--option", "strict:reject unknown keys:fails loudly on drift",
            "--option", "lenient:ignore unknown keys:tolerates older payloads",
        )
        grandchild = self.repo / STATE_DIR / "worktrees" / "xx-999" / "inline-strict"
        self.assertTrue((grandchild / "leaf.txt").exists(),
                        "grandchild did not inherit its parent's commit")

    def test_fork_resolves_parent_from_cwd(self):
        self.init()
        self.fork_two()
        leaf = self.repo / STATE_DIR / "worktrees" / "xx-999" / "redis"
        self.ok(
            "fork", ISSUE,
            "--decision", "TTL fixed or configurable?", "--why-you", "the tradeoff is the author\'s", "--source", "app.py:12",
            "--option", "fixed:hardcode 60s:one less knob to misconfigure",
            "--option", "configurable:env var:tunable per environment",
            cwd=leaf,
        )
        state = self.state()
        self.assertEqual(state["decisions"]["d2"]["node"], "n2")

    def test_a_blocked_second_option_leaves_no_orphan(self):
        """CodeRabbit, outside-diff: the exists() check ran between side effects.

        A second option whose directory already exists used to exit AFTER the
        first option's worktree and branch were created, with nothing in
        tree.json to find them by — so `abandon` could not clean up, and the
        error message told the operator to run exactly that.
        """
        self.init()
        squatter = self.repo / STATE_DIR / "worktrees" / "xx-999" / "redis"
        squatter.mkdir(parents=True)
        (squatter / "in-the-way.txt").write_text("x\n", encoding="utf-8")

        code, _out, err = self.run_cli(
            "fork", ISSUE,
            "--decision", "Cache where?", "--why-you", "the tradeoff is the author's",
            "--source", "app.py:1",
            "--option", "inline:dict in the module:no new dependency",
            "--option", "redis:shared Redis cache:survives a restart",
        )
        self.assertEqual(code, 1)
        self.assertIn("already exists", err)
        # The first option must not have been created and left behind.
        self.assertEqual(self.worktree_paths(), [str(self.repo)])
        self.assertNotIn("fan/xx-999/inline", self.branches())
        self.assertFalse((self.repo / STATE_DIR / "worktrees" / "xx-999" / "inline").exists())
        # And the tree records nothing, so there is nothing to be inconsistent.
        self.assertEqual(self.state()["decisions"], {})

    def test_forking_an_already_forked_node_is_rejected(self):
        self.init()
        self.fork_two()
        code, _out, err = self.run_cli(
            "fork", ISSUE, "--parent", "n0",
            "--decision", "Q", "--why-you", "the tradeoff is the author\'s", "--source", "app.py:1",
            "--option", "a:does a:reason a",
            "--option", "b:does b:reason b",
        )
        self.assertEqual(code, 1)
        self.assertIn("already forked", err)


class TestCaps(FanoutCase):
    """Caps must refuse loudly and leave the tree buildable. Never truncate."""

    def assert_refused(self, code, err, needle):
        self.assertEqual(code, 3, f"expected the cap-refusal exit code 3, got {code}")
        self.assertIn("REFUSED", err)
        self.assertIn(needle, err)
        self.assertIn("ask tool", err)

    def test_too_many_options_is_refused(self):
        self.init(max_options=2)
        code, _out, err = self.run_cli(
            "fork", ISSUE,
            "--decision", "Q", "--why-you", "the tradeoff is the author\'s", "--source", "app.py:1",
            "--option", "a:does a:reason a",
            "--option", "b:does b:reason b",
            "--option", "c:does c:reason c",
        )
        self.assert_refused(code, err, "max_options=2")
        self.assertEqual(self.worktree_paths(), [str(self.repo)])
        self.assertEqual(len(self.state()["refusals"]), 1)

    def test_single_surviving_option_is_refused(self):
        self.init()
        code, _out, err = self.run_cli(
            "fork", ISSUE,
            "--decision", "Q", "--why-you", "the tradeoff is the author\'s", "--source", "app.py:1",
            "--option", "a:does a:reason a",
        )
        self.assert_refused(code, err, "record` instead")

    def test_max_depth_is_refused(self):
        self.init(max_depth=1)
        self.fork_two()
        code, _out, err = self.run_cli(
            "fork", ISSUE, "--parent", "n1",
            "--decision", "Q", "--why-you", "the tradeoff is the author\'s", "--source", "app.py:1",
            "--option", "a:does a:reason a",
            "--option", "b:does b:reason b",
        )
        self.assert_refused(code, err, "max_depth=1")

    def test_max_leaves_is_refused(self):
        self.init(max_leaves=3)
        self.fork_two()
        self.ok(
            "fork", ISSUE, "--parent", "n1",
            "--decision", "Second", "--why-you", "the tradeoff is the author\'s", "--source", "app.py:2",
            "--option", "a:does a:reason a",
            "--option", "b:does b:reason b",
        )  # 3 leaves: n2, n3, n4
        code, _out, err = self.run_cli(
            "fork", ISSUE, "--parent", "n2",
            "--decision", "Third", "--why-you", "the tradeoff is the author\'s", "--source", "app.py:3",
            "--option", "c:does c:reason c",
            "--option", "d:does d:reason d",
        )
        self.assert_refused(code, err, "max_leaves=3")

    def test_refusal_is_rendered_in_the_ledger(self):
        self.init(max_options=2)
        self.run_cli(
            "fork", ISSUE,
            "--decision", "Which queue?", "--why-you", "the tradeoff is the author\'s", "--source", "app.py:4",
            "--option", "a:does a:reason a",
            "--option", "b:does b:reason b",
            "--option", "c:does c:reason c",
        )
        self.ok("ledger", ISSUE)
        text = (self.repo / STATE_DIR / "fanout" / "xx-999" / "LEDGER.md").read_text()
        self.assertIn("Refused to fan out", text)
        self.assertIn("Which queue?", text)
        self.assertIn("Not built:", text)

    def test_max_leaves_is_clamped_to_the_ceiling(self):
        code, _out, err = self.run_cli("init", ISSUE, "--max-leaves", "999")
        self.assertEqual(code, 0)
        self.assertIn("clamped", err)
        self.assertEqual(self.state()["caps"]["max_leaves"], 16)


class TestEvidence(FanoutCase):
    def test_result_attaches_to_a_leaf(self):
        self.init()
        self.fork_two()
        self.ok(
            "result", ISSUE, "--node", "n1", "--tests", "pass",
            "--evidence", "pytest -q: 12 passed",
            "--notice", "nothing visible until a pod restarts",
            "--reversible", "yes",
            "--lost", "cannot share cache across pods",
            "--switch-cost", "swap one module; no data to migrate",
        )
        self.assertEqual(self.state()["nodes"]["n1"]["result"]["tests"], "pass")

    def test_result_rejects_a_non_leaf(self):
        self.init()
        self.fork_two()
        code, _out, err = self.run_cli(
            "result", ISSUE, "--node", "n0", "--tests", "pass",
            "--evidence", "pytest -q: 12 passed", "--notice", "nothing visible",
            "--reversible", "yes", "--lost", "nothing",
            "--switch-cost", "none",
        )
        self.assertEqual(code, 1)
        self.assertIn("not a leaf", err)

    def test_two_way_record_requires_a_reversal_cost(self):
        self.init()
        code, _out, err = self.run_cli(
            "record", ISSUE, "--kind", "two-way",
            "--question", "Module layout?", "--answer", "one file for now",
        )
        self.assertEqual(code, 1)
        self.assertIn("--reversal", err)

    def test_ledger_surfaces_missing_results_and_failures(self):
        self.init()
        self.fork_two()
        self.ok(
            "result", ISSUE, "--node", "n1", "--tests", "fail",
            "--evidence", "pytest -q: 1 failed, 11 passed",
            "--failure", "AssertionError: expected 2 retries, saw 3",
            "--notice", "retries fire at unpredictable times",
            "--reversible", "yes",
            "--lost", "needs a lock we do not have",
            "--switch-cost", "rip out the lock plumbing",
        )
        self.ok("recommend", ISSUE, "--decision", "d1", "--option", "redis",
                "--reason", "inline cannot survive a restart",
                "--wrong-if", "somebody already reads the cross-pod aggregate",
                "--if-silent", "nothing ships; the tree waits")
        self.ok("ledger", ISSUE)
        text = (self.repo / STATE_DIR / "fanout" / "xx-999" / "LEDGER.md").read_text()
        # Shape A: the brief a human decides from (`human-brief`, PR #624).
        self.assertIn("**DECISION:**", text)
        self.assertIn("**WHY YOU:**", text)
        self.assertIn("| Option | In plain English | What you would notice |", text)
        self.assertIn("**RECOMMEND:** `redis`", text)
        self.assertIn("**WRONG IF:** somebody already reads", text)
        self.assertIn("**IF SILENT:** nothing ships", text)
        # file:line stays out of the plain-English cells and lives in evidence.
        self.assertIn("*Evidence: came up at `app.py:1`", text)
        self.assertIn("No result recorded", text)   # n2 never ran the evidence gate
        self.assertIn("is evidence against", text)  # n1 failed, and that is an answer
        self.assertIn("--choose d1=inline   # n1", text)
        # Deciding must not require the audit trail.
        self.assertLess(text.index("## Choose a path"),
                        text.index("## Detail (not needed to decide)"))
        self.assertIn("--choose d1=redis   # n2", text)

    def test_recommend_rejects_an_unknown_option(self):
        self.init()
        self.fork_two()
        code, _out, err = self.run_cli(
            "recommend", ISSUE, "--decision", "d1", "--option", "memcached",
            "--reason", "no",
                "--wrong-if", "somebody already reads the cross-pod aggregate",
                "--if-silent", "nothing ships; the tree waits",
        )
        self.assertEqual(code, 1)
        self.assertIn("not an option", err)


class TestCollapse(FanoutCase):
    def setUp(self):
        super().setUp()
        self.init()
        self.fork_two()
        self.ok(
            "fork", ISSUE, "--parent", "n1",
            "--decision", "Strict or lenient?", "--why-you", "the tradeoff is the author\'s", "--source", "app.py:9",
            "--option", "strict:reject unknown keys:fails loudly on drift",
            "--option", "lenient:ignore unknown keys:tolerates older payloads",
        )
        # leaves: n2 (redis), n3 (inline-strict), n4 (inline-lenient).
        # 5 worktrees, not 4: the intermediate `inline` node keeps its worktree
        # because its children were branched from its HEAD - it is the shared
        # trunk for that subtree, and `collapse` removes it like any non-survivor.
        self.assertEqual(len(self.worktree_paths()), 5)

    def test_ambiguous_choice_is_rejected(self):
        """d1=inline still matches two leaves; the author has to answer d2 too."""
        code, _out, err = self.run_cli("collapse", ISSUE, "--choose", "d1=inline")
        self.assertEqual(code, 4)
        self.assertIn("2 leaves", err)
        self.assertIn("narrow it to one leaf", err)
        self.assertEqual(len(self.worktree_paths()), 5)  # nothing removed

    def test_a_leaf_that_skipped_a_decision_is_still_selectable(self):
        """The prefix-tree case: `redis` never reached d2, so d1 alone picks it.

        Requiring an answer for every fanned decision would make this path
        unreachable, which is the bug the one real ledger ledger surfaced.
        """
        out = self.ok("collapse", ISSUE, "--choose", "d1=redis")
        self.assertIn("fan/xx-999/redis", out)
        paths = self.worktree_paths()
        self.assertEqual(len(paths), 2, f"expected root + survivor, got {paths}")

    def test_unmatched_choice_is_rejected(self):
        code, _out, err = self.run_cli(
            "collapse", ISSUE, "--choose", "d1=redis,d2=strict"
        )
        self.assertEqual(code, 4)
        self.assertIn("0 leaves", err)
        self.assertIn("never reached a decision", err)
        self.assertEqual(len(self.worktree_paths()), 5)

    def test_unknown_decision_id_is_rejected(self):
        code, _out, err = self.run_cli("collapse", ISSUE, "--choose", "d9=inline")
        self.assertEqual(code, 1)
        self.assertIn("unknown decision", err)

    def test_valid_choice_leaves_exactly_one_survivor(self):
        out = self.ok("collapse", ISSUE, "--choose", "d1=inline,d2=strict")
        self.assertIn("fan/xx-999/inline-strict", out)
        paths = self.worktree_paths()
        self.assertEqual(len(paths), 2, f"expected root + survivor, got {paths}")
        self.assertTrue(any(p.endswith("inline-strict") for p in paths))
        branches = self.branches()
        self.assertIn("fan/xx-999/inline-strict", branches)
        self.assertNotIn("fan/xx-999/redis", branches)
        self.assertNotIn("fan/xx-999/inline", branches)
        self.assertNotIn("fan/xx-999/inline-lenient", branches)
        self.assertIn("xx-999", branches)  # the trunk survives

    def test_dirty_worktree_is_kept_without_force(self):
        doomed = self.repo / STATE_DIR / "worktrees" / "xx-999" / "redis"
        (doomed / "scratch.txt").write_text("uncommitted\n", encoding="utf-8")
        _code, _out, err = self.run_cli(
            "collapse", ISSUE, "--choose", "d1=inline,d2=strict"
        )
        self.assertIn("NOT fully collapsed", err)
        self.assertTrue(doomed.is_dir(), "a dirty worktree must not be silently dropped")

    def test_a_partial_collapse_does_not_report_success(self):
        """Murty's MINOR: exit 0 while the output says it did not fully collapse.

        Deliberately 6 rather than 4. Exit 4 means "the choice did not name
        exactly one leaf"; here the choice was unambiguous and the survivor is
        right — the cleanup is what failed. One code, one meaning.
        """
        doomed = self.repo / STATE_DIR / "worktrees" / "xx-999" / "redis"
        (doomed / "scratch.txt").write_text("uncommitted\n", encoding="utf-8")
        code, out, err = self.run_cli("collapse", ISSUE, "--choose", "d1=inline,d2=strict")
        self.assertEqual(code, 6, "a partial collapse must not report success")
        self.assertIn("NOT fully collapsed", err)
        self.assertIn("survivor", out)

    def test_a_clean_collapse_still_reports_success(self):
        out = self.ok("collapse", ISSUE, "--choose", "d1=inline,d2=strict")
        self.assertIn("survivor", out)

    def test_force_drops_a_dirty_worktree(self):
        doomed = self.repo / STATE_DIR / "worktrees" / "xx-999" / "redis"
        (doomed / "scratch.txt").write_text("uncommitted\n", encoding="utf-8")
        self.ok("collapse", ISSUE, "--choose", "d1=inline,d2=strict", "--force")
        self.assertFalse(doomed.exists())

    def test_refuses_when_cwd_is_inside_a_doomed_worktree(self):
        doomed = self.repo / STATE_DIR / "worktrees" / "xx-999" / "redis"
        code, _out, err = self.run_cli(
            "collapse", ISSUE, "--choose", "d1=inline,d2=strict", cwd=doomed
        )
        self.assertEqual(code, 1)
        self.assertIn("cwd is inside", err)
        self.assertEqual(len(self.worktree_paths()), 5)

    def test_a_manually_deleted_worktree_still_gets_its_branch_removed(self):
        """Codex round 1: the stale worktree registration blocked `git branch -D`.

        `check=False` on that delete meant the failure was swallowed while the
        command still reported the branch as removed.
        """
        doomed = self.repo / STATE_DIR / "worktrees" / "xx-999" / "redis"
        shutil.rmtree(doomed)
        out = self.ok("collapse", ISSUE, "--choose", "d1=inline,d2=strict")
        self.assertNotIn("fan/xx-999/redis", self.branches())
        self.assertIn("removed 3 branch(es)", out)

    def test_a_dirty_leftover_is_reported_by_status_not_hidden(self):
        doomed = self.repo / STATE_DIR / "worktrees" / "xx-999" / "redis"
        (doomed / "scratch.txt").write_text("uncommitted\n", encoding="utf-8")
        self.run_cli("collapse", ISSUE, "--choose", "d1=inline,d2=strict")
        out = self.ok("status", ISSUE)
        self.assertIn("NOT fully collapsed", out)
        self.assertIn("redis", out)

    def test_abandon_removes_everything(self):
        self.ok("abandon", ISSUE)
        self.assertEqual(self.worktree_paths(), [str(self.repo)])
        self.assertFalse((self.repo / STATE_DIR / "fanout" / "xx-999").exists())
        for branch in self.branches():
            self.assertFalse(branch.startswith("fan/xx-999/"))


class TestEvidenceDetail(FanoutCase):
    """The ledger has to carry enough to decide on, not just pass/fail."""

    def test_failing_leaf_must_supply_the_failure_text(self):
        self.init()
        self.fork_two()
        code, _out, err = self.run_cli(
            "result", ISSUE, "--node", "n1", "--tests", "fail",
            "--evidence", "pytest -q: 1 failed", "--notice", "n", "--reversible", "yes",
            "--lost", "x", "--switch-cost", "y",
        )
        self.assertEqual(code, 1)
        self.assertIn("--failure", err)

    def test_diff_is_measured_from_git_not_supplied(self):
        self.init()
        self.fork_two()
        leaf = self.repo / STATE_DIR / "worktrees" / "xx-999" / "inline"
        (leaf / "cache.py").write_text("a = 1\nb = 2\nc = 3\n", encoding="utf-8")
        git("add", "-A", cwd=leaf)
        git("commit", "-m", "add cache", cwd=leaf)
        out = self.ok(
            "result", ISSUE, "--node", "n1", "--tests", "pass",
            "--evidence", "pytest -q: 12 passed", "--notice", "nothing visible",
            "--reversible", "yes", "--lost", "no cross-pod view",
            "--switch-cost", "swap one module",
        )
        self.assertIn("+3/-0", out)
        result = self.state()["nodes"]["n1"]["result"]
        self.assertEqual(result["contribution"]["added"], 3)
        self.assertEqual(result["contribution"]["names"], ["cache.py"])

    def test_dependency_manifests_are_flagged(self):
        self.init()
        self.fork_two()
        leaf = self.repo / STATE_DIR / "worktrees" / "xx-999" / "redis"
        (leaf / "requirements.txt").write_text("redis==5.0.0\n", encoding="utf-8")
        git("add", "-A", cwd=leaf)
        git("commit", "-m", "add redis dep", cwd=leaf)
        out = self.ok(
            "result", ISSUE, "--node", "n2", "--tests", "pass",
            "--evidence", "pytest -q: 12 passed", "--notice", "nothing visible",
            "--reversible", "yes", "--lost", "operational cost",
            "--switch-cost", "drop the dep and the client module",
        )
        self.assertIn("requirements.txt", out)

    def test_ledger_carries_evidence_switch_cost_and_open_questions(self):
        self.init()
        self.fork_two()
        self.ok(
            "result", ISSUE, "--node", "n1", "--tests", "pass",
            "--evidence", "pytest -q: 412 passed",
            "--notice", "the counter resets when a pod restarts",
            "--reversible", "yes",
            "--lost", "no cross-pod view",
            "--switch-cost", "swap one module; no data to migrate",
            "--risk", "a restart loses the counter",
            "--open-question", "does anyone read the aggregate today?",
            "--note", "smallest diff",
        )
        self.ok("ledger", ISSUE)
        text = (self.repo / STATE_DIR / "fanout" / "xx-999" / "LEDGER.md").read_text()
        self.assertIn("412 passed", text)
        self.assertIn("cost to switch off this option later", text)
        self.assertIn("swap one module", text)
        self.assertIn("open question: does anyone read", text)
        self.assertIn("risk: a restart loses the counter", text)
        # A leaf with no result must read as unbuilt, not as neutral.
        self.assertIn("No result recorded", text)


class TestMustStop(FanoutCase):
    """The boundary is enforced by a path check, not by remembering a rule."""

    def stage_in(self, path, relpath, body="x\n"):
        target = Path(path) / relpath
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")
        git("add", "-A", cwd=path)

    def test_check_scope_is_a_noop_off_a_fan_branch(self):
        self.stage_in(self.repo, "api/contracts/event-schema.yaml")
        code, _out, _err = self.run_cli("check-scope")
        self.assertEqual(code, 0, "must not police ordinary branches")

    def test_check_scope_refuses_a_contract_change_on_a_fan_branch(self):
        self.init()
        self.fork_two()
        leaf = self.repo / STATE_DIR / "worktrees" / "xx-999" / "inline"
        self.stage_in(leaf, "api/contracts/event-schema.yaml")
        code, _out, err = self.run_cli("check-scope", cwd=leaf)
        self.assertEqual(code, 5)
        self.assertIn("api/contracts/event-schema.yaml", err)
        self.assertIn("a durable published contract", err)
        self.assertIn("abandon", err)

    def test_check_scope_refuses_a_migration_and_the_serving_path(self):
        self.init()
        self.fork_two()
        leaf = self.repo / STATE_DIR / "worktrees" / "xx-999" / "redis"
        self.stage_in(leaf, "db/migrations/001_x.py")
        self.stage_in(leaf, "src/serving/bid.go")
        code, _out, err = self.run_cli("check-scope", cwd=leaf)
        self.assertEqual(code, 5)
        self.assertIn("schema migration", err)
        self.assertIn("serving critical path", err)

    def test_check_scope_allows_ordinary_files_on_a_fan_branch(self):
        self.init()
        self.fork_two()
        leaf = self.repo / STATE_DIR / "worktrees" / "xx-999" / "inline"
        self.stage_in(leaf, "src/crawler/fetch.go")
        code, _out, err = self.run_cli("check-scope", cwd=leaf)
        self.assertEqual(code, 0, f"false positive: {err}")

    def test_fork_refuses_when_the_trunk_already_crossed_the_line(self):
        self.init()
        target = self.repo / "api" / "contracts" / "event-schema.yaml"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("v: 1\n", encoding="utf-8")
        git("add", "-A", cwd=self.repo)
        git("commit", "-m", "touch a contract", cwd=self.repo)
        code, _out, err = self.run_cli(
            "fork", ISSUE,
            "--decision", "Q", "--why-you", "the tradeoff is the author\'s", "--source", "app.py:1",
            "--option", "a:does a:reason a",
            "--option", "b:does b:reason b",
        )
        self.assertEqual(code, 3)
        self.assertIn("must-stop boundary", err)
        self.assertEqual(self.worktree_paths(), [str(self.repo)])

    def test_fork_refuses_a_declared_must_stop_path(self):
        self.init()
        code, _out, err = self.run_cli(
            "fork", ISSUE,
            "--decision", "Q", "--why-you", "the tradeoff is the author\'s", "--source", "app.py:1",
            "--touches", "api/models.py",
            "--option", "a:does a:reason a",
            "--option", "b:does b:reason b",
        )
        self.assertEqual(code, 3)
        self.assertIn("schema", err)


class TestMustStopBypasses(FanoutCase):
    """The ways a protected path can reach a commit without looking like one."""

    def test_moving_a_protected_file_out_is_refused(self):
        """`git mv` of a contract reports only the destination without --no-renames.

        This is the most destructive way to touch a protected file and it was the
        one shape the gate could not see: rename detection collapses the delete
        and the add into one entry named by the DESTINATION, which is unprotected.
        """
        self.init()
        self.fork_two()
        leaf = self.repo / STATE_DIR / "worktrees" / "xx-999" / "inline"
        target = leaf / "api" / "contracts" / "event-schema.yaml"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("v: 1\nx: 2\ny: 3\nz: 4\nw: 5\n", encoding="utf-8")
        git("add", "-A", cwd=leaf)
        git("commit", "-m", "add a contract", cwd=leaf)

        git("mv", "api/contracts/event-schema.yaml", "moved.yaml", cwd=leaf)
        code, _out, err = self.run_cli("check-scope", cwd=leaf)
        self.assertEqual(code, 5, "a rename out of the boundary must still be refused")
        self.assertIn("api/contracts/event-schema.yaml", err)

    def test_deleting_a_protected_file_is_refused(self):
        self.init()
        self.fork_two()
        leaf = self.repo / STATE_DIR / "worktrees" / "xx-999" / "inline"
        target = leaf / "api" / "contracts" / "event-schema.yaml"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("v: 1\n", encoding="utf-8")
        git("add", "-A", cwd=leaf)
        git("commit", "-m", "add a contract", cwd=leaf)
        git("rm", "-q", "api/contracts/event-schema.yaml", cwd=leaf)
        code, _out, err = self.run_cli("check-scope", cwd=leaf)
        self.assertEqual(code, 5)
        self.assertIn("api/contracts/event-schema.yaml", err)

    def test_every_declared_must_stop_entry_is_actually_refused(self):
        """Covers the whole boundary, not the three entries someone thought of.

        The doc summarises MUST_STOP_PATHS in a table; without this, the two can
        drift and the table would keep promising protection the tool dropped.
        """
        entries = must_stop_entries()
        self.assertGreaterEqual(len(entries), 8, "boundary fixture looks unexpectedly small")
        self.init()
        self.fork_two()
        leaf = self.repo / STATE_DIR / "worktrees" / "xx-999" / "inline"
        for entry in entries:
            relative = entry + "probe.txt" if entry.endswith("/") else entry
            target = leaf / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("x\n", encoding="utf-8")
            git("add", "-A", cwd=leaf)
            code, _out, err = self.run_cli("check-scope", cwd=leaf)
            self.assertEqual(code, 5, f"{relative} was NOT refused")
            self.assertIn(relative, err)
            git("reset", "-q", cwd=leaf)
            target.unlink()

    def test_the_usage_block_names_every_required_flag(self):
        """The docstring drifted from argparse once; this is why it cannot again.

        Three subcommands had acquired required flags -- the Shape A brief
        fields -- that the module docstring never gained, so anyone reading
        `--help`-by-docstring wrote a command that argparse rejected. A
        docstring is documentation until something checks it, at which point it
        is a contract.
        """
        src = FANOUT.read_text(encoding="utf-8")
        usage = src[src.index("Usage:"):src.index("State lives in")]

        parser = load_fanout_module().build_parser()
        missing = []
        for name, sub_parser in subparser_map(parser).items():
            for action in sub_parser._actions:
                if not action.option_strings or not action.required:
                    continue
                flag = action.option_strings[0]
                if flag not in usage:
                    missing.append(f"{name} {flag}")
        self.assertEqual(
            missing, [],
            "these required flags are missing from the module docstring's Usage "
            "block: " + ", ".join(missing),
        )

    def test_a_near_miss_path_is_not_a_false_positive(self):
        """`db/migrations/` must not match `db/migrations_utils.py`."""
        self.init()
        self.fork_two()
        leaf = self.repo / STATE_DIR / "worktrees" / "xx-999" / "inline"
        target = leaf / "db" / "migrations_utils.py"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("x = 1\n", encoding="utf-8")
        git("add", "-A", cwd=leaf)
        code, _out, err = self.run_cli("check-scope", cwd=leaf)
        self.assertEqual(code, 0, f"false positive on a near-miss path: {err}")


class TestGateBypasses(FanoutCase):
    """Codex round 1 findings: the ways the gate could be walked around."""

    def test_detached_head_in_a_leaf_still_enforces(self):
        """`git checkout --detach` used to be a one-command bypass.

        --abbrev-ref prints "HEAD" when detached, so the branch-name check exited
        0. The worktree's location cannot be detached from.
        """
        self.init()
        self.fork_two()
        leaf = self.repo / STATE_DIR / "worktrees" / "xx-999" / "inline"
        git("checkout", "--detach", cwd=leaf)
        target = leaf / "api" / "contracts" / "event-schema.yaml"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("v: 1\n", encoding="utf-8")
        git("add", "-A", cwd=leaf)
        code, _out, err = self.run_cli("check-scope", cwd=leaf)
        self.assertEqual(code, 5, "detached HEAD must not bypass the boundary")
        self.assertIn("detached or moved", err)

    def test_a_moved_and_detached_leaf_still_enforces(self):
        """Codex round 2 BLOCKER: move + detach defeated branch AND path checks.

        `git worktree move` erases the `.claude/worktrees/` path and
        `git checkout --detach` erases the `fan/` branch name, so together they
        were a complete bypass. The worktree-local config marker survives both.
        """
        self.init()
        self.fork_two()
        moved = Path(self._tmp.name).resolve() / "external-inline"
        git("worktree", "move", f"{STATE_DIR}/worktrees/xx-999/inline", str(moved),
            cwd=self.repo)
        git("checkout", "--detach", cwd=moved)
        target = moved / "api" / "contracts" / "event-schema.yaml"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("v: 1\n", encoding="utf-8")
        git("add", "-A", cwd=moved)

        self.assertEqual(git("rev-parse", "--abbrev-ref", "HEAD", cwd=moved), "HEAD")
        self.assertNotIn(f"{STATE_DIR}/worktrees", str(moved))
        code, _out, err = self.run_cli("check-scope", cwd=moved)
        self.assertEqual(code, 5, "move + detach must not bypass the boundary")
        self.assertIn("XX-999", err)
        self.assertIn("api/contracts/event-schema.yaml", err)

    def test_removing_the_marker_after_move_and_detach_still_enforces(self):
        """Codex round 3 BLOCKER: the marker is a setting, and settings are editable.

        move + detach + `extensions.worktreeConfig false` + unset put the leaf back
        out of scope. The fallback keys on the run's own records instead, which is
        the one identifier the thing being checked cannot rewrite.
        """
        self.init()
        self.fork_two()
        moved = Path(self._tmp.name).resolve() / "ext-inline"
        git("worktree", "move", f"{STATE_DIR}/worktrees/xx-999/inline", str(moved),
            cwd=self.repo)
        git("config", "extensions.worktreeConfig", "false", cwd=self.repo)
        git("checkout", "--detach", cwd=moved)
        subprocess.run(["git", "config", "--worktree", "--unset", "fanout.issue"],
                       cwd=str(moved), capture_output=True, text=True, check=False,
                       env=GIT_ENV)
        target = moved / "api" / "contracts" / "event-schema.yaml"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("v: 1\n", encoding="utf-8")
        git("add", "-A", cwd=moved)

        code, _out, err = self.run_cli("check-scope", cwd=moved)
        self.assertEqual(code, 5, "an erased marker must not bypass the boundary")
        self.assertIn("marker removed", err)

    def test_an_unrelated_worktree_is_not_policed(self):
        """The fallback must not start refusing commits in worktrees we do not own."""
        self.init()
        self.fork_two()
        other = Path(self._tmp.name).resolve() / "unrelated"
        git("worktree", "add", "-b", "feature/x", str(other), cwd=self.repo)
        target = other / "api" / "contracts" / "event-schema.yaml"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("v: 1\n", encoding="utf-8")
        git("add", "-A", cwd=other)
        code, _out, err = self.run_cli("check-scope", cwd=other)
        self.assertEqual(code, 0, f"policed a worktree outside the fan tree: {err}")

    # Murty mutation-tested the four-signal disjunct at check-scope and found
    # three of four survived deletion against all 66 tests. Each of these
    # isolates one signal so that removing that disjunct kills its test. The
    # survivors were `marked`, the branch prefix and the path check - all three
    # added because a real bypass was found, hardening with no regression test.

    def stage_contract(self, path):
        target = Path(path) / "api" / "contracts" / "event-schema.yaml"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("v: 1\n", encoding="utf-8")
        git("add", "-A", cwd=path)

    def test_the_branch_prefix_alone_is_enough(self):
        """Only `branch.startswith("fan/")` fires: hand-made, outside the dir, unmarked."""
        self.init()
        outside = Path(self._tmp.name).resolve() / "handmade-fan"
        git("worktree", "add", "-b", "fan/handmade/x", str(outside), cwd=self.repo)
        self.stage_contract(outside)
        # `git config --get` exits nonzero when unset, so ask without raising.
        probe = subprocess.run(
            ["git", "config", "--worktree", "--get", "fanout.issue"],
            cwd=str(outside), capture_output=True, text=True, check=False, env=GIT_ENV,
        )
        self.assertEqual(probe.stdout.strip(), "",
                         "precondition: this worktree must carry no marker")
        code, _out, err = self.run_cli("check-scope", cwd=outside)
        self.assertEqual(code, 5, "the fan/ branch prefix alone must still enforce")
        self.assertIn("event-schema.yaml", err)

    def test_the_worktree_location_alone_is_enough(self):
        """Only `in_fan_worktree` fires: inside the dir, non-fan branch, unmarked."""
        self.init()
        inside = self.repo / STATE_DIR / "worktrees" / "xx-999" / "handmade"
        git("worktree", "add", "-b", "feature/ordinary", str(inside), cwd=self.repo)
        self.stage_contract(inside)
        branch = git("rev-parse", "--abbrev-ref", "HEAD", cwd=inside)
        self.assertFalse(branch.startswith("fan/"), "precondition: not a fan/ branch")
        code, _out, err = self.run_cli("check-scope", cwd=inside)
        self.assertEqual(code, 5, "living under .claude/worktrees must still enforce")
        self.assertIn("event-schema.yaml", err)

    def test_the_marker_alone_is_enough(self):
        """Only `marked` fires: outside the dir, detached, unregistered, marked."""
        self.init()
        outside = Path(self._tmp.name).resolve() / "marked-only"
        git("worktree", "add", "-b", "feature/plain", str(outside), cwd=self.repo)
        git("config", "extensions.worktreeConfig", "true", cwd=self.repo)
        git("config", "--worktree", "fanout.issue", ISSUE, cwd=outside)
        git("checkout", "--detach", cwd=outside)
        self.stage_contract(outside)
        self.assertEqual(git("rev-parse", "--abbrev-ref", "HEAD", cwd=outside), "HEAD")
        self.assertNotIn(f"{STATE_DIR}/worktrees", str(outside))
        code, _out, err = self.run_cli("check-scope", cwd=outside)
        self.assertEqual(code, 5, "the worktree marker alone must still enforce")
        self.assertIn("event-schema.yaml", err)

    def test_exact_file_entries_do_not_prefix_match(self):
        """`api/models.py` must not also refuse `models.py.bak`."""
        self.init()
        self.fork_two()
        leaf = self.repo / STATE_DIR / "worktrees" / "xx-999" / "inline"
        target = leaf / "api" / "models.py.bak"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("x = 1\n", encoding="utf-8")
        git("add", "-A", cwd=leaf)
        code, _out, err = self.run_cli("check-scope", cwd=leaf)
        self.assertEqual(code, 0, f"over-refusal on an exact-file near miss: {err}")

    def test_the_real_exact_file_is_still_refused(self):
        self.init()
        self.fork_two()
        leaf = self.repo / STATE_DIR / "worktrees" / "xx-999" / "inline"
        target = leaf / "api" / "models.py"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("x = 1\n", encoding="utf-8")
        git("add", "-A", cwd=leaf)
        code, _out, err = self.run_cli("check-scope", cwd=leaf)
        self.assertEqual(code, 5)
        self.assertIn("schema", err)

    def test_a_bad_base_ref_fails_loudly_rather_than_measuring_zero(self):
        """A measurement of +0/-0 must never stand in for "not measured"."""
        self.init()
        self.fork_two()
        state_file = self.repo / STATE_DIR / "fanout" / "xx-999" / "tree.json"
        blob = json.loads(state_file.read_text())
        blob["nodes"]["n1"]["fork_sha"] = "0" * 40
        state_file.write_text(json.dumps(blob))
        code, _out, err = self.run_cli(
            "result", ISSUE, "--node", "n1", "--tests", "pass",
            "--evidence", "pytest -q: 12 passed", "--notice", "n",
            "--reversible", "yes", "--lost", "x", "--switch-cost", "y",
        )
        self.assertNotEqual(code, 0, "an unmeasurable diff must not report success")
        self.assertIn("git diff", err)


class TestConcurrency(FanoutCase):
    """Leaves build in parallel by design, so state writes must not lose each other."""

    def _result_proc(self, node, slug):
        import subprocess as sp
        return sp.Popen(
            [sys.executable, str(FANOUT), "result", ISSUE, "--node", node,
             "--tests", "pass", "--evidence", "pytest -q: 12 passed",
             "--notice", f"{slug} behaviour", "--reversible", "yes",
             "--lost", f"{slug} tradeoff", "--switch-cost", "one module"],
            cwd=str(self.repo), stdout=sp.PIPE, stderr=sp.PIPE, text=True, env=GIT_ENV,
        )

    def test_a_result_call_blocks_while_the_lock_is_held(self):
        """Tests the lock itself, rather than hoping two fast calls interleave.

        Timing-based concurrency tests are a coverage claim, not coverage. This
        one holds the lock from the test process, proves the child cannot proceed,
        then releases and proves it does — so deleting the lock fails it
        deterministically rather than probabilistically.
        """
        import fcntl

        self.init()
        self.fork_two()
        lock_path = self.repo / STATE_DIR / "fanout" / "xx-999" / ".lock"
        with open(lock_path, "w") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            proc = self._result_proc("n1", "inline")
            with self.assertRaises(Exception):
                # Still blocked on the lock, so it cannot have exited.
                proc.wait(timeout=2)
            self.assertIsNone(proc.poll(), "child did not wait for the lock")
            fcntl.flock(handle, fcntl.LOCK_UN)
        self.assertEqual(proc.wait(timeout=30), 0, proc.communicate()[1])
        self.assertIsNotNone(self.state()["nodes"]["n1"]["result"])

    def test_concurrent_results_do_not_lose_each_other(self):
        """Contention across a wider tree: every node must keep its result."""
        self.init()
        self.fork_two()
        self.ok(
            "fork", ISSUE, "--parent", "n1",
            "--decision", "Strict or lenient?",
            "--why-you", "the tradeoff is the author's",
            "--source", "app.py:9",
            "--option", "strict:reject unknown keys:fails loudly",
            "--option", "lenient:ignore unknown keys:tolerates old payloads",
        )
        leaves = [("n2", "redis"), ("n3", "strict"), ("n4", "lenient")]
        procs = [self._result_proc(node, slug) for node, slug in leaves]
        for proc in procs:
            self.assertEqual(proc.wait(), 0, proc.communicate()[1])
        nodes = self.state()["nodes"]
        for node, _slug in leaves:
            self.assertIsNotNone(nodes[node]["result"], f"{node}'s result was lost")


class TestHandoff(FanoutCase):
    """A fresh session must be able to pick the tree up from state alone."""

    def test_status_walks_building_then_awaiting_then_collapsed(self):
        self.init()
        self.fork_two()
        out = self.ok("status", ISSUE)
        self.assertIn("state: building", out)
        self.assertIn("leaves with no result yet", out)

        for node, slug in (("n1", "inline"), ("n2", "redis")):
            self.ok(
                "result", ISSUE, "--node", node, "--tests", "pass",
                "--evidence", "pytest -q: 12 passed", "--notice", "nothing visible",
            "--reversible", "yes", "--lost", f"{slug} tradeoff",
                "--switch-cost", "one module",
            )
        out = self.ok("status", ISSUE)
        self.assertIn("no recommendation", out)

        self.ok("recommend", ISSUE, "--decision", "d1", "--option", "inline",
                "--reason", "no new dependency",
                "--wrong-if", "somebody already reads the cross-pod aggregate",
                "--if-silent", "nothing ships; the tree waits")
        out = self.ok("status", ISSUE)
        self.assertIn("state: awaiting-decision", out)
        self.assertIn("the author picks a path", out)
        self.assertIn("--choose d1=inline", out)

        self.ok("collapse", ISSUE, "--choose", "d1=inline")
        out = self.ok("status", ISSUE)
        self.assertIn("state: collapsed", out)
        self.assertIn("fan/xx-999/inline", out)
        self.assertIn("execute-issue from step 6", out)

    def test_notify_survives_a_launch_failure(self):
        """`notify` promises a transport problem never fails the command.

        The launch itself can fail before the child runs — no python3 on PATH, or
        an argv over ARG_MAX — and an uncaught OSError there would fail the last
        step of an unattended run.
        """
        self.init()
        self.fork_two()
        script = self.repo / "tools" / "ask.py"
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_text("raise SystemExit(0)\n", encoding="utf-8")
        # A PATH with git but no python3: the tool's own git calls keep working,
        # so the run reaches the notify launch, and only that launch fails.
        # Emptying PATH outright would break `git rev-parse` first and test
        # nothing about notify.
        fake_bin = Path(self._tmp.name).resolve() / "bin"
        fake_bin.mkdir(exist_ok=True)
        (fake_bin / "git").symlink_to(shutil.which("git"))
        broken = {**GIT_ENV, "PATH": str(fake_bin)}
        proc = subprocess.run(
            [sys.executable, str(FANOUT), "notify", ISSUE],
            cwd=str(self.repo), capture_output=True, text=True, check=False,
            env=broken,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("could not launch ask-tool notify", proc.stderr)

    def test_the_digest_is_bounded_not_merely_shortened(self):
        """Pads the fields compact mode KEEPS, and asserts the real limit.

        The first version of this test padded `--notice` and `--risk`, which
        compact rendering drops — so it proved the compact path shrinks output and
        said nothing about whether the limit is enforced. Everything padded here
        survives compaction: the question, why-you, the option summaries, the
        recommendation reason, WRONG IF and IF SILENT.
        """
        limit = digest_limit()
        self.init(max_leaves=9, max_depth=3, max_options=3)
        self.ok(
            "fork", ISSUE,
            "--decision", "Where does it live? " + "q" * 900,
            "--why-you", "the tradeoff is the author's " + "w" * 900,
            "--source", "app.py:1",
            "--option", "a:" + "x" * 900 + ":why a",
            "--option", "b:" + "x" * 900 + ":why b",
            "--option", "c:" + "x" * 900 + ":why c",
        )
        for node in ("n1", "n2", "n3"):
            self.ok(
                "result", ISSUE, "--node", node, "--tests", "pass",
                "--evidence", "pytest -q: 12 passed",
                "--notice", "n" * 200, "--reversible", "yes",
                "--lost", "l" * 200, "--switch-cost", "s" * 200,
            )
        self.ok("recommend", ISSUE, "--decision", "d1", "--option", "a",
                "--reason", "r" * 900, "--wrong-if", "f" * 900,
                "--if-silent", "s" * 900)

        out = self.ok("notify", ISSUE, "--print-only").rstrip("\n")
        self.assertLessEqual(
            len(out), limit,
            f"digest is {len(out)} chars, over the {limit} limit — shortened but not bounded",
        )
        # Whatever is trimmed, the actionable tail survives whole.
        self.assertIn("--choose d1=a", out)
        self.assertIn("--choose d1=b", out)
        self.assertIn("Full ledger:", out)
        self.assertIn("trimmed for chat", out)

    def test_status_without_an_issue_lists_every_tree(self):
        """Murty's MAJOR: every other command needs an issue id you may not have.

        Worktrees are gitignored, so `git status` stays clean while hundreds of
        MB sit on disk. A run that died between fork and collapse leaves a tree
        nothing points at.
        """
        self.init()
        self.fork_two()
        out = self.ok("status")
        self.assertIn("XX-999", out)
        self.assertIn("building", out)
        self.assertIn("2 leaves", out)
        self.assertIn("last touched", out)
        self.assertIn("abandon", out)

    def test_status_says_so_when_there_are_no_trees(self):
        out = self.ok("status")
        self.assertIn("no fan-out trees on disk", out)

    def test_status_listing_reports_each_state(self):
        self.init()
        self.fork_two()
        self.ok("status")
        for node, slug in (("n1", "inline"), ("n2", "redis")):
            self.ok(
                "result", ISSUE, "--node", node, "--tests", "pass",
                "--evidence", "pytest -q: 12 passed", "--notice", f"{slug} thing",
                "--reversible", "yes", "--lost", "x", "--switch-cost", "y",
            )
        self.assertIn("awaiting-decision", self.ok("status"))
        self.ok("collapse", ISSUE, "--choose", "d1=inline")
        self.assertIn("collapsed", self.ok("status"))

    def test_init_notes_other_trees_left_on_disk(self):
        """The moment a person is present is the moment to mention the leftovers."""
        self.init()
        self.fork_two()
        code, _out, err = self.run_cli("init", "XX-998")
        self.assertEqual(code, 0)
        self.assertIn("other tree(s) still on disk", err)
        self.assertIn("XX-999", err)

    def test_init_does_not_note_a_collapsed_tree(self):
        self.init()
        self.fork_two()
        self.ok("collapse", ISSUE, "--choose", "d1=inline")
        _code, _out, err = self.run_cli("init", "XX-998")
        self.assertNotIn("other tree(s) still on disk", err)

    def test_notify_print_only_renders_without_the_ask_tool(self):
        self.init()
        self.fork_two()
        self.ok(
            "result", ISSUE, "--node", "n1", "--tests", "pass",
            "--evidence", "pytest -q: 12 passed", "--notice", "nothing visible",
            "--reversible", "yes", "--lost", "no cross-pod view",
            "--switch-cost", "one module",
        )
        self.ok("recommend", ISSUE, "--decision", "d1", "--option", "inline",
                "--reason", "no new dependency",
                "--wrong-if", "somebody already reads the cross-pod aggregate",
                "--if-silent", "nothing ships; the tree waits")
        out = self.ok("notify", ISSUE, "--print-only")
        self.assertIn("*XX-999*", out)
        self.assertIn("RECOMMEND `inline`", out)
        self.assertIn("WRONG IF:", out)
        self.assertIn("IF SILENT:", out)
        # Numbered, so a chat reply can be one token (human-brief, chat path).
        self.assertIn("*1. inline*", out)
        self.assertIn("*2. redis*", out)
        self.assertIn("you would notice:", out)
        self.assertIn("--choose d1=inline", out)
        self.assertNotIn("|---|", out)  # chat transports do not render markdown tables


if __name__ == "__main__":
    unittest.main(verbosity=2 if "-v" in sys.argv else 1)
