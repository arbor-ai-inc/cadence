#!/usr/bin/env python3
"""check_user_docs.py - refuse a doc command an adopter cannot run.

The docs are read by two audiences from two different working directories, and
conflating them produced eight broken commands before anyone noticed:

  - A CONTRIBUTOR works inside a clone of this repo. `python3 tools/x.py` is
    correct for them.
  - An ADOPTER works inside THEIR project, where `tools/` does not exist. The
    same command fails immediately.

Neither audience gets an error message that explains which one the doc meant.
The adopter just sees "No such file or directory" on step two of setup.

So: user-facing docs must call the shim `/cadence:init` writes into the
project, and must not name a plugin-relative path. Contributor sections opt out
with a marker, which also forces the doc to say which audience it is addressing.

Usage:
    check_user_docs.py
    check_user_docs.py --selftest
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Read by adopters: the README and everything in docs/. Discovered rather than
# listed, because a hardcoded list is one more thing to forget -- the first
# version of this file named four files, a fifth was added, and it went
# unchecked silently. Coverage is opt-OUT, so a new doc is covered by default.
#
# reference/ is excluded on purpose: those docs are loaded BY a skill, where
# ${CLAUDE_PLUGIN_ROOT} does expand, so a plugin-relative path is correct there.
def user_docs() -> list[str]:
    docs = [p.relative_to(ROOT).as_posix() for p in sorted((ROOT / "docs").glob("*.md"))]
    return ["README.md", *docs]


# A command that only works with this repo as the working directory.
PLUGIN_RELATIVE = re.compile(r"python3\s+(?:tools|tests|scripts)/[\w/.]+\.py")

# A section may opt out by naming its audience. The marker is prose a reader
# sees, not a comment they do not — the point is that the doc SAYS which
# working directory it assumes.
CONTRIBUTOR_MARKER = "run from a clone of this repo"

# What an adopter should be told to call instead.
SHIM = "./.cadence/cadence"


def offending_lines(text: str) -> list[tuple[int, str]]:
    """Lines with a plugin-relative command, outside a contributor section.

    A contributor section runs from its marker to the next heading of the same
    or higher level, which is why the marker has to sit inside the section it
    covers rather than at the top of the file.
    """
    out, in_contrib, contrib_depth = [], False, 0
    for i, line in enumerate(text.splitlines(), start=1):
        heading = re.match(r"^(#+)\s", line)
        if heading:
            depth = len(heading.group(1))
            if in_contrib and depth <= contrib_depth:
                in_contrib = False
        if CONTRIBUTOR_MARKER in line.lower():
            in_contrib = True
            # Attribute the marker to the most recent heading.
            contrib_depth = 6
            for prev in reversed(text.splitlines()[:i]):
                h = re.match(r"^(#+)\s", prev)
                if h:
                    contrib_depth = len(h.group(1))
                    break
        if in_contrib:
            continue
        if PLUGIN_RELATIVE.search(line):
            out.append((i, line.strip()))
    return out


def selftest() -> int:
    failures = []

    def check(label, cond):
        if not cond:
            failures.append(label)

    plain = "Run this:\n\n```bash\npython3 tools/cadence_config.py\n```\n"
    check("a bare plugin-relative command is caught", len(offending_lines(plain)) == 1)

    marked = (
        "## Verifying it\n\n**For contributors, run from a clone of this repo.**\n\n"
        "```bash\npython3 tools/cadence_config.py --selftest\n```\n"
    )
    check("a marked contributor section is allowed", offending_lines(marked) == [])

    # The marker must not leak past its own section.
    leaked = marked + "\n## Setup\n\n```bash\npython3 tools/cadence_config.py\n```\n"
    check("the marker does not cover a later section", len(offending_lines(leaked)) == 1)

    shim = "```bash\n./.cadence/cadence config\n```\n"
    check("the shim form is fine", offending_lines(shim) == [])

    # Coverage must be discovered, not listed, or a new doc is silently unchecked.
    found = user_docs()
    check("the README is covered", "README.md" in found)
    check("every docs/*.md is covered",
          all(f"docs/{p.name}" in found for p in (ROOT / "docs").glob("*.md")))
    check("reference/ is not treated as user-facing",
          not any(f.startswith("reference/") for f in found))

    for line in failures:
        print(f"selftest: {line}", file=sys.stderr)
    if failures:
        print(f"\ncheck_user_docs selftest: {len(failures)} failure(s).", file=sys.stderr)
        return 1
    print("check_user_docs selftest: ok")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        return selftest()

    problems = []
    for name in user_docs():
        path = ROOT / name
        if not path.exists():
            problems.append(f"{name}: missing")
            continue
        for lineno, line in offending_lines(path.read_text(encoding="utf-8")):
            problems.append(f"{name}:{lineno}: {line}")

    if problems:
        print("check_user_docs: these commands assume this repo is the working directory,\n"
              "but the reader is in THEIR project, where tools/ does not exist:\n", file=sys.stderr)
        for p in problems:
            print(f"  {p}", file=sys.stderr)
        print(f"\nUse {SHIM} <command> instead, which /cadence:init writes into their\n"
              f"repo. Or, if the section really is for contributors, say so in it with\n"
              f'the phrase "{CONTRIBUTOR_MARKER}" — which also tells the reader which\n'
              f"working directory it assumes.", file=sys.stderr)
        return 1

    print(f"check_user_docs: ok ({len(user_docs())} user-facing docs: "
          f"{', '.join(user_docs())})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
