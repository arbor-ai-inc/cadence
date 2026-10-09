#!/usr/bin/env python3
"""check_vocab.py - fail if a private repo's names appear in this one.

check_no_leaks.py is a denylist: it catches what someone thought to list, and
nothing else. Spec names, PR numbers and table names reached the public tree
because nobody had listed them. This check derives its list instead: every
distinctive file and directory name in the private repos you point it at
(`spec-h`, `hashes`), minus cadence's own names and the
generic terms in tests/vocab_allow.txt. The list is built at run time and never
written down, so the check publishes nothing.

It needs the private repos on disk, so public CI cannot run it. Run it before
every release, or set CADENCE_PRIVATE_SOURCES and pre-commit runs it on each
commit. With no sources it skips and says so, which keeps it harmless for
outside contributors.

It sees names, not meaning: a customer, a person or a metric that is never a
file name gets through. A human read of examples/ is still part of a release.

Usage:
    check_vocab.py --source ../private-a --source ../private-b
    CADENCE_PRIVATE_SOURCES=../private-a:../private-b check_vocab.py
    check_vocab.py --source ../private-a --history   # also scan every commit
    check_vocab.py --selftest

Exit codes:
    0  clean, or skipped with no sources
    1  a private name found, or a usage error
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ALLOW = Path(__file__).resolve().parent / "vocab_allow.txt"
ENV = "CADENCE_PRIVATE_SOURCES"

# A distinctive name: two or more parts joined by - or _, at least 7 characters.
# A single word (`tools`, `reporting`) is too common to mean anything.
TOKEN = re.compile(r"^[A-Za-z][A-Za-z0-9]*[-_][A-Za-z0-9_-]+$")
MIN_LEN = 7
# A letter or digit continues a name, so `round-2` is not in `round-20`; a hyphen
# does not, so `secret-widget-followup` still carries `secret-widget`.
EDGE = r"A-Za-z0-9"


def git_files(repo: Path) -> list[str]:
    out = subprocess.run(["git", "-C", str(repo), "ls-files"], capture_output=True,
                         text=True, check=True).stdout
    return out.splitlines()


def names(paths: list[str]) -> set[str]:
    """Every path component, without its extensions."""
    return {part.split(".")[0] for p in paths for part in p.split("/") if part}


def load_allow(text: str) -> tuple[list[re.Pattern], set[str]]:
    """Allowed-term patterns (full match), and paths exempt from the scan."""
    terms, paths = [], set()
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("path:"):
            paths.add(line[5:].strip())
        else:
            terms.append(re.compile(line, re.IGNORECASE))
    return terms, paths


def vocabulary(private: list[list[str]], own: list[str], allow: list[re.Pattern]) -> set[str]:
    mine = {n.lower() for n in names(own)}
    found = set()
    for paths in private:
        for n in names(paths):
            if TOKEN.match(n) and len(n) >= MIN_LEN and n.lower() not in mine:
                if not any(a.fullmatch(n) for a in allow):
                    found.add(n)
    return found


def matcher(vocab: set[str]) -> re.Pattern | None:
    if not vocab:
        return None
    alt = "|".join(re.escape(v) for v in sorted(vocab, key=len, reverse=True))
    return re.compile(rf"(?<![{EDGE}])(?:{alt})(?![{EDGE}])", re.IGNORECASE)


def scan_text(text: str, rx: re.Pattern) -> list[tuple[int, str]]:
    return [(i, m.group(0)) for i, line in enumerate(text.splitlines(), 1)
            for m in rx.finditer(line)]


def scan_tree(rx: re.Pattern, skip: set[str]) -> list[str]:
    hits = []
    for rel in git_files(REPO):
        if rel in skip:
            continue
        try:
            text = (REPO / rel).read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        hits += [f"{rel}:{n}: {term}" for n, term in scan_text(text, rx)]
    return hits


def scan_history(rx: re.Pattern) -> list[str]:
    log = subprocess.run(["git", "-C", str(REPO), "log", "--all", "-p", "--format=commit %h"],
                         capture_output=True, text=True, errors="replace", check=True).stdout
    first: dict[str, str] = {}
    commit = "?"
    for line in log.splitlines():
        if line.startswith("commit "):
            commit = line[7:]
        elif line.startswith("+") and not line.startswith("+++"):
            for m in rx.finditer(line):
                first[m.group(0).lower()] = commit  # log is newest first: keep the oldest
    return [f"history: {term} (added in {c})" for term, c in sorted(first.items())]


def sources_from(args_sources: list[str]) -> list[Path]:
    raw = list(args_sources) or [s for s in os.environ.get(ENV, "").split(os.pathsep) if s]
    return [Path(s).expanduser().resolve() for s in raw]


def selftest() -> int:
    failures = []
    check = lambda label, cond: failures.append(label) if not cond else None
    allow, skip = load_allow("round-\\d+   # review rounds\npath: scripts/x.py\n")
    check("allow line parsed", len(allow) == 1 and skip == {"scripts/x.py"})
    private = [["services/secret-widget/main.py", "specs/round-12/a.md", "docs/plain.md",
                "tools/shared-name.py"]]
    vocab = vocabulary(private, ["tools/shared-name.py"], allow)
    check("a distinctive private name is in the list", "secret-widget" in vocab)
    check("an allowed term is not", "round-12" not in vocab)
    check("a name cadence also has is not", "shared-name" not in vocab)
    check("a single word is not", "plain" not in vocab and "services" not in vocab)
    rx = matcher(vocab)
    check("it fires on the name", scan_text("see secret-widget here", rx) == [(1, "secret-widget")])
    check("case does not hide it", len(scan_text("Secret-Widget", rx)) == 1)
    check("a longer word is not a hit", scan_text("secret-widgets", rx) == [])
    check("a name inside a longer name is", len(scan_text("secret-widget-followup", rx)) == 1)
    check("a file name is a hit", len(scan_text("open secret-widget.md", rx)) == 1)
    with tempfile.TemporaryDirectory() as d:
        subprocess.run(["git", "init", "-q", d], check=True)
        (Path(d) / "hidden-thing.txt").write_text("x")
        subprocess.run(["git", "-C", d, "add", "."], check=True)
        check("names come from tracked files", "hidden-thing" in names(git_files(Path(d))))
    check("the allow file parses", isinstance(load_allow(ALLOW.read_text())[0], list))
    for f in failures:
        print(f"selftest: {f}", file=sys.stderr)
    if failures:
        return 1
    print("check_vocab selftest: ok")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", action="append", default=[], help="a private repo to derive names from")
    ap.add_argument("--history", action="store_true", help="also scan every commit in this repo")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        return selftest()

    sources = sources_from(args.source)
    if not sources:
        print(f"check_vocab: skipped, no private sources (--source or {ENV})")
        return 0
    for s in sources:
        if not (s / ".git").exists():
            print(f"check_vocab: {s} is not a git checkout", file=sys.stderr)
            return 1

    allow, skip = load_allow(ALLOW.read_text())
    vocab = vocabulary([git_files(s) for s in sources], git_files(REPO), allow)
    rx = matcher(vocab)
    if rx is None:
        print("check_vocab: no distinctive names in the sources")
        return 0
    hits = scan_tree(rx, skip)
    if args.history:
        hits += scan_history(rx)
    for h in hits:
        print(f"check_vocab: {h}", file=sys.stderr)
    if hits:
        print(f"check_vocab: {len(hits)} private name(s). Rename them, or add a generic term "
              f"to tests/vocab_allow.txt.", file=sys.stderr)
        return 1
    print(f"check_vocab: clean against {len(vocab)} names from {len(sources)} source(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
