#!/usr/bin/env python3
"""check_version_bumped.py - refuse a content change that leaves the version alone.

Claude Code pins an installed plugin to the `version` string in plugin.json:
users receive an update only when that string changes. So shipping a fix
without bumping it means every existing install stays on the old copy, silently
and indefinitely.

That happened here. `version` sat at 0.1.0 across four content commits, and it
surfaced only when a newly added skill did not appear after a marketplace
update. Nothing reported it, because nothing was wrong from the publisher's
side — the commits were pushed and the repo was correct.

So this runs on commit. If anything a user actually receives is staged and
plugin.json is not, it fails.

Usage:
    check_version_bumped.py            # check the staged change (pre-commit)
    check_version_bumped.py --range A..B   # check a range, for CI
    check_version_bumped.py --selftest

To bypass deliberately (a typo in a comment, say): SKIP=version-bumped git commit
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ".claude-plugin/plugin.json"

# What a user actually receives when they install or update. Everything else in
# the repo -- the tests, the docs directory, CI config, the drift report -- is
# for developing cadence, not for running it, so a change there needs no bump.
SHIPPED_PREFIXES = (
    "skills/",
    "agents/",
    "reference/",
    "tools/",
    "templates/",
    "adapters/",
    "examples/",
    ".claude-plugin/",
)


def changed_files(rng: str | None) -> list[str]:
    cmd = ["git", "-C", str(ROOT), "diff", "--name-only", "--cached"]
    if rng:
        cmd = ["git", "-C", str(ROOT), "diff", "--name-only", rng]
    out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
    return [line for line in out.splitlines() if line.strip()]


def declared_version() -> str | None:
    try:
        return json.loads((ROOT / MANIFEST).read_text()).get("version")
    except (OSError, json.JSONDecodeError):
        return None


def selftest() -> int:
    failures = []

    def check(label, cond):
        if not cond:
            failures.append(label)

    shipped = lambda f: f.startswith(SHIPPED_PREFIXES)
    check("a skill counts as shipped", shipped("skills/retro/SKILL.md"))
    check("a reference doc counts as shipped", shipped("reference/retro.md"))
    check("a tool counts as shipped", shipped("tools/fanout.py"))
    check("a template counts as shipped", shipped("templates/cadence.toml"))
    # These are for developing cadence, not for running it.
    check("a test does not count", not shipped("tests/check_fanout.py"))
    check("a doc does not count", not shipped("docs/configuration.md"))
    check("CI does not count", not shipped(".github/workflows/ci.yml"))
    check("the README does not count", not shipped("README.md"))
    # The manifest itself is how the bump arrives.
    check("the manifest counts as shipped", shipped(MANIFEST))
    check("a version is declared", declared_version() is not None)

    for line in failures:
        print(f"selftest: {line}", file=sys.stderr)
    if failures:
        print(f"\ncheck_version_bumped selftest: {len(failures)} failure(s).", file=sys.stderr)
        return 1
    print(f"check_version_bumped selftest: ok (declared version {declared_version()})")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--range", dest="rng", help="a git range to check instead of the staged change")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        return selftest()

    files = changed_files(args.rng)
    shipped = sorted(f for f in files if f.startswith(SHIPPED_PREFIXES) and f != MANIFEST)
    if not shipped:
        return 0
    if MANIFEST in files:
        print(f"check_version_bumped: ok (version {declared_version()})")
        return 0

    print(
        "check_version_bumped: this change ships to users but does not bump the version.\n",
        file=sys.stderr,
    )
    for f in shipped[:8]:
        print(f"  {f}", file=sys.stderr)
    if len(shipped) > 8:
        print(f"  ... and {len(shipped) - 8} more", file=sys.stderr)
    print(
        f"\nClaude Code pins an install to plugin.json's `version` (now "
        f"{declared_version()}). Users receive an update ONLY when that string\n"
        f"changes, so leaving it means every existing install stays on the old\n"
        f"copy — silently, and with nothing on either side reporting it.\n\n"
        f"Bump {MANIFEST}, or bypass deliberately with:\n"
        f"  SKIP=version-bumped git commit ...",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
