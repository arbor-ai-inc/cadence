#!/usr/bin/env python3
"""Report what changed in the private source tree since cadence forked from it.

Cadence was extracted once and the two now evolve separately. That is a
deliberate choice with a known cost: the retro loop keeps improving the private
copy, and this copy does not hear about it. Two or three batches and the public
docs are quietly behind.

This does not fix that. It makes it visible, which is the difference between
"stale" and "a diff you chose not to take". Run it before a release.

Usage:
    scripts/drift_report.py --source /path/to/private/repo
    scripts/drift_report.py --source /path/to/private/repo --doc retro.md
    scripts/drift_report.py --source /path/to/private/repo --diff retro.md

It reads only. It never writes to either tree.
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "reference"
BASELINE = ROOT / "scripts" / "fork-baseline.json"

# Where each cadence doc came from, relative to the private repo root. Only the
# files that were genuinely forked appear here: reference/README.md and the
# provider notes were written fresh, so they have no upstream and drift cannot
# apply to them.
UPSTREAM = "docs/engineering/agent-skills"
NO_UPSTREAM = {"README.md", "providers/coderabbit.md"}

# Before comparing, both texts are normalized so the report shows CONTENT
# changes rather than the genericization this port already did. Without it every
# file reads as heavily changed and the report means nothing.
#
# The privacy-sensitive half of that vocabulary is NOT written out here. It is
# derived from tests/check_no_leaks.py's own rules, for two reasons: those two
# lists describe the same thing and would drift apart if both were authored, and
# spelling the patterns here a second time would put the private repo's
# vocabulary into a second publishable file.
import importlib.util as _ilu

_spec = _ilu.spec_from_file_location("_leaks", Path(__file__).resolve().parents[1] / "tests" / "check_no_leaks.py")
_leaks = _ilu.module_from_spec(_spec)
sys.modules["_leaks"] = _leaks
_spec.loader.exec_module(_leaks)

# Structural rewrites this port made, which are not leak classes and so have no
# counterpart in the leak rules.
STRUCTURAL = [
    (re.compile(r"docs/engineering/agent-skills/"), ""),
    (re.compile(r"tools/agent-spec/"), "tools/"),
    (re.compile(r"\.github/scripts/"), "tools/"),
    (re.compile(r"\$\{CLAUDE_PLUGIN_ROOT\}/reference/"), ""),
    (re.compile(r"\$\{CLAUDE_PLUGIN_ROOT\}/"), ""),
    (re.compile(r"slack_ask\.py"), "ask.py"),
    (re.compile(r"pr_review_state\.py"), "review_state.py"),
    (re.compile(r"\.claude/"), ".cadence/"),
    (re.compile(r"\bT-\d\d\b"), "<id>"),
    (re.compile(r"\bC-\d\d\b"), "<id>"),
    (re.compile(r"#\d{3,4}\b"), "<pr>"),
    (re.compile(r"\bcross-plane\b"), "cross-boundary"),
    (re.compile(r"\bplane\b"), "boundary"),
]

# Every leak pattern collapses to one token, so a private name and the generic
# phrase that replaced it compare equal.
NORMALIZE = [(r.compiled(), "<x>") for r in (*_leaks.RULES, _leaks.CODERABBIT)] + STRUCTURAL


def normalize(text: str) -> list[str]:
    for pattern, repl in NORMALIZE:
        text = pattern.sub(repl, text)
    # Compare on words, not lines: a rewrap changes every line and no content.
    return [w for w in re.split(r"\s+", text) if w]


def upstream_head(source: Path) -> str:
    try:
        return subprocess.run(
            ["git", "-C", str(source), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "(not a git repo)"


def content_key(text: str) -> str:
    """A hash of the normalized words, stable across rewraps and renamed citations."""
    import hashlib
    return hashlib.sha256(" ".join(normalize(text)).encode()).hexdigest()[:16]


def load_baseline() -> dict:
    if not BASELINE.exists():
        return {}
    return json.loads(BASELINE.read_text())


def record_baseline(source: Path) -> int:
    """Snapshot what upstream looked like at the fork, so drift is measurable.

    Without this the report compares cadence against upstream and calls every
    deliberate genericization "upstream changed" -- which made its first run
    flag 14 of 15 docs and mean nothing. What matters is whether UPSTREAM has
    moved since the fork, and that is a question about upstream alone.
    """
    docs = {}
    for doc in sorted(REFERENCE.rglob("*.md")):
        name = doc.relative_to(REFERENCE).as_posix()
        if name in NO_UPSTREAM or name.startswith("personas/"):
            continue
        up = source / UPSTREAM / name
        if up.exists():
            docs[name] = content_key(up.read_text())
    BASELINE.write_text(json.dumps(
        {"upstream_head": upstream_head(source), "docs": docs}, indent=2, sort_keys=True) + "\n")
    print(f"recorded baseline for {len(docs)} docs at upstream {upstream_head(source)}")
    print(f"  -> {rel(BASELINE)}")
    return 0


def rel(p: Path) -> str:
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return str(p)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", required=True, type=Path, help="the private repo this was forked from")
    ap.add_argument("--record-baseline", action="store_true",
                    help="snapshot upstream as the fork point (run once, at fork)")
    ap.add_argument("--doc", help="report on one doc only")
    ap.add_argument("--diff", help="print a word-level diff of upstream then vs now")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    source = args.source.expanduser().resolve()
    if not (source / UPSTREAM).is_dir():
        print(f"drift_report: {source / UPSTREAM} not found. Is --source the right repo?", file=sys.stderr)
        return 1

    if args.record_baseline:
        return record_baseline(source)

    baseline = load_baseline()
    if not baseline:
        print("drift_report: no fork baseline recorded. Run once with --record-baseline.", file=sys.stderr)
        return 1

    rows = []
    for name, was in sorted(baseline["docs"].items()):
        if args.doc and name != args.doc:
            continue
        up = source / UPSTREAM / name
        if not up.exists():
            rows.append({"doc": name, "status": "REMOVED upstream"})
            continue
        now = content_key(up.read_text())
        rows.append({"doc": name, "status": "moved" if now != was else "in step"})

        if args.diff == name:
            print(f"drift_report: baseline stores a hash, not the text, so a word diff\n"
                  f"needs the fork commit. Run:\n\n"
                  f"  git -C {source} diff {baseline['upstream_head']}..HEAD -- {UPSTREAM}/{name}\n")
            return 0

    if args.json:
        print(json.dumps({"baseline": baseline["upstream_head"],
                          "upstream_head": upstream_head(source), "docs": rows}, indent=2))
        return 0

    moved = [r for r in rows if r["status"] != "in step"]
    print(f"fork baseline : upstream @ {baseline['upstream_head']}")
    print(f"upstream now  : {source} @ {upstream_head(source)}\n")

    if not moved:
        print(f"All {len(rows)} forked docs are unchanged upstream since the fork.")
        return 0

    for r in moved:
        print(f"  {r['status']:<16} {r['doc']}")
    print(f"\n{len(moved)} of {len(rows)} doc(s) have moved upstream since the fork. To read one:\n"
          f"  git -C {source} diff {baseline['upstream_head']}..HEAD -- {UPSTREAM}/<doc>\n\n"
          "Taking an upstream change is a judgement, not a merge. Much of what changes\n"
          "upstream is specific to that codebase, and the genericization here is not\n"
          "reversible by patch. When you do take one, re-record the baseline.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
