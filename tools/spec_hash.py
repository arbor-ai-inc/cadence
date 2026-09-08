#!/usr/bin/env python3
"""Canonical hash helper for the spec pipeline.

SINGLE SOURCE OF TRUTH for spec_hash and product_hash. Both the review-spec
and draft-plan skills MUST compute hashes by running this script and using its
stdout verbatim. Never compute, describe, or placeholder a hash any other way —
that is what broke before, and a placeholder hash is worse than none: it makes
a frozen artifact look verified.

What the hash is for: the spec pipeline freezes an artifact at the first READY
verdict, and the recorded hash is what detects an edit afterwards. A spec edited
after its gate closed has re-opened that gate, and nothing else notices.

Usage:
  python3 tools/spec_hash.py spec    <path>   # whole-file hash
  python3 tools/spec_hash.py product <path>   # single-file layout, section slice

Two-file layout (recommended): a spec is <specs>/<slug>/product.md plus
<specs>/<slug>/design.md, where <specs> is [paths].specs from cadence.toml.
Both gate hashes use whole-file "spec" mode:
  product_hash = spec_hash.py spec <specs>/<slug>/product.md
  design_hash  = spec_hash.py spec <specs>/<slug>/design.md

Single-file layout: <specs>/<slug>.md with '## Section 1' / '## Section 2'
headings. There, product_hash is the Section 1 slice:
  product_hash = spec_hash.py product <specs>/<slug>.md
The "product" (slice) mode exists only for that layout.

Canonical normalization (identical for both modes):
  - read file as UTF-8
  - normalize all line endings (\\r\\n and \\r) to \\n
  - strip trailing whitespace from every line
  - drop trailing blank lines (so a trailing newline never changes the hash)
  - join remaining lines with \\n
  - sha256 of the UTF-8 bytes; print the hex digest

Product extraction:
  - the lines from the first line beginning '## Section 1'
    up to (but NOT including) the first later line beginning '## Section 2'
  - the '## Section 1' heading line itself IS included, so editing that
    heading changes product_hash (this is intended).
"""
import sys
import hashlib

PRODUCT_START = "## Section 1"
PRODUCT_END = "## Section 2"


def normalized_lines(text):
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [ln.rstrip() for ln in text.split("\n")]
    while lines and lines[-1] == "":
        lines.pop()
    return lines


def canonical_hash(lines):
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def product_slice(lines):
    start = end = None
    for i, ln in enumerate(lines):
        s = ln.strip()
        if start is None and s.startswith(PRODUCT_START):
            start = i
        elif start is not None and s.startswith(PRODUCT_END):
            end = i
            break
    if start is None:
        sys.exit("ERROR: no '## Section 1' heading found")
    if end is None:
        end = len(lines)
    return lines[start:end]


def selftest():
    """Pin the normalization contract.

    Every rule below exists so that two readings of an unchanged file cannot
    disagree. A hash that moves when nothing meaningful changed re-opens a
    closed gate for no reason; one that fails to move when the text changed is
    the far worse direction, and the last two cases guard it.
    """
    failures = []

    def eq(label, a, b):
        if a != b:
            failures.append(label)

    def ne(label, a, b):
        if a == b:
            failures.append(label)

    h = lambda t: canonical_hash(normalized_lines(t))

    eq("CRLF must not change the hash", h("a\r\nb"), h("a\nb"))
    eq("lone CR must not change the hash", h("a\rb"), h("a\nb"))
    eq("trailing spaces on a line are stripped", h("a   \nb"), h("a\nb"))
    eq("trailing blank lines are dropped", h("a\nb\n\n\n"), h("a\nb"))
    eq("a final newline is not a change", h("a\nb\n"), h("a\nb"))
    eq("an empty file and a blank one agree", h(""), h("\n\n"))
    # The direction that matters: real edits must move the hash.
    ne("changed text must change the hash", h("a\nb"), h("a\nc"))
    ne("interior blank lines are significant", h("a\n\nb"), h("a\nb"))
    ne("leading whitespace is significant", h("  a"), h("a"))
    ne("line order is significant", h("a\nb"), h("b\na"))

    # The section slice includes its own heading, so editing the heading
    # changes product_hash. That is intended and load-bearing.
    doc = normalized_lines("intro\n## Section 1\nP\n## Section 2\nD")
    eq("slice starts at the heading and excludes the next", product_slice(doc),
       ["## Section 1", "P"])
    doc2 = normalized_lines("## Section 1 (product)\nP")
    eq("slice runs to EOF when there is no Section 2", product_slice(doc2),
       ["## Section 1 (product)", "P"])
    ne("editing the Section 1 heading changes product_hash",
       canonical_hash(product_slice(doc)),
       canonical_hash(product_slice(normalized_lines("## Section 1 — v2\nP\n## Section 2\nD"))))

    for line in failures:
        print("selftest: " + line, file=sys.stderr)
    if failures:
        print("\nspec_hash selftest: %d failure(s)." % len(failures), file=sys.stderr)
        return 1
    print("spec_hash selftest: normalization contract holds")
    return 0


def main():
    if len(sys.argv) == 2 and sys.argv[1] == "--selftest":
        sys.exit(selftest())
    if len(sys.argv) != 3 or sys.argv[1] not in ("spec", "product"):
        sys.exit("usage: spec_hash.py {spec|product} <path>\n       spec_hash.py --selftest")
    mode, path = sys.argv[1], sys.argv[2]
    try:
        with open(path, encoding="utf-8") as fh:
            lines = normalized_lines(fh.read())
    except OSError as exc:
        sys.exit("ERROR: cannot read %s: %s" % (path, exc))
    if mode == "spec":
        print(canonical_hash(lines))
    else:
        print(canonical_hash(product_slice(lines)))


if __name__ == "__main__":
    main()
