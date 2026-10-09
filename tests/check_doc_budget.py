#!/usr/bin/env python3
"""check_doc_budget.py - hold every reference doc to a size budget.

An agent loads a workflow's reference doc in full each time it runs that
workflow, so every byte is paid for on every run, by every adopter. Rules are
added one retro at a time and almost never removed, and nothing noticed: the
source these docs came from grew its PR workflow to over 60 KB, and a repo that
copied it trimmed it to 20 KB by hand.

So each doc has a byte budget in tests/doc_budget.json, and a doc over budget
fails. A new rule has to make room — compress a case write-up into
examples/case-studies.md, or point at the doc that owns the rule — or raise the
budget in the same change, where the raise is visible in review.

A doc with no budget fails too: a new reference doc must declare one.

Usage:
    check_doc_budget.py
    check_doc_budget.py --report     # every doc, its size and headroom
    check_doc_budget.py --selftest
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REFERENCE = ROOT / "reference"
BUDGET = Path(__file__).resolve().parent / "doc_budget.json"


def docs() -> dict[str, int]:
    return {p.relative_to(REFERENCE).as_posix(): p.stat().st_size
            for p in sorted(REFERENCE.rglob("*.md"))}


def problems(sizes: dict[str, int], budget: dict[str, int]) -> list[str]:
    out = []
    for name, size in sizes.items():
        cap = budget.get(name)
        if cap is None:
            out.append(f"{name}: no budget. Add it to tests/doc_budget.json.")
        elif size > cap:
            out.append(f"{name}: {size} bytes, over its {cap}-byte budget by {size - cap}. "
                       f"Make room, or raise the budget in this change and say why.")
    for name in sorted(set(budget) - set(sizes)):
        out.append(f"{name}: budgeted but missing. Remove it from tests/doc_budget.json.")
    return out


def selftest() -> int:
    failures = []
    check = lambda label, cond: failures.append(label) if not cond else None
    check("under budget passes", problems({"a.md": 10}, {"a.md": 10}) == [])
    check("over budget fails", len(problems({"a.md": 11}, {"a.md": 10})) == 1)
    check("an unbudgeted doc fails", len(problems({"a.md": 1}, {})) == 1)
    check("a stale budget entry fails", len(problems({}, {"a.md": 1})) == 1)
    check("the budget file parses", isinstance(json.loads(BUDGET.read_text()), dict))
    check("reference/ has docs", len(docs()) > 0)
    for f in failures:
        print(f"selftest: {f}", file=sys.stderr)
    if failures:
        return 1
    print("check_doc_budget selftest: ok")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        return selftest()

    sizes, budget = docs(), json.loads(BUDGET.read_text())
    if args.report:
        for name, size in sizes.items():
            cap = budget.get(name)
            print(f"{size:7d} / {cap if cap is not None else '-':>7}  {name}")
    found = problems(sizes, budget)
    for p in found:
        print(f"check_doc_budget: {p}", file=sys.stderr)
    if found:
        return 1
    print(f"check_doc_budget: {len(sizes)} docs within budget ({sum(sizes.values())} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
