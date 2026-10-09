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
  python3 tools/spec_hash.py design  <path>   # design.md + its sub-designs
  python3 tools/spec_hash.py product <path>   # single-file layout, section slice

Two-file layout (recommended): a spec is <specs>/<slug>/product.md plus
<specs>/<slug>/design.md, where <specs> is [paths].specs from cadence.toml.
  product_hash = spec_hash.py spec   <specs>/<slug>/product.md
  design_hash  = spec_hash.py design <specs>/<slug>/design.md

"design" mode exists because a large design splits into an HLD (design.md) plus
sub-designs under <specs>/<slug>/design/, and those files are one Gate 2 artifact:
a verdict that named only design.md's bytes would leave a sub-design edit
invisible to the freeze rule. It covers every file on disk under design/, at any
depth and whatever the extension — a .json fixture or design/storage/detail.md
is as much part of the artifact as design/storage.md, and omitting it would
leave a hole exactly where someone would put content to keep it out.

Four things are refused rather than silently included or skipped, because each
one is a way for the artifact to stop being what the digest says it is: a
symlink, including design/ itself (its target is outside the spec, so edits
there would be invisible, and a relative link to a sibling spec would make this
hash move when that one is edited); a path containing a control character (the
record separator below is a newline, so such a name can spell a second record);
an unreadable file; and an unreadable directory, which os.walk would otherwise
drop silently, yielding a valid-looking digest for content it never read.

Dot-prefixed entries ARE skipped, silently and deliberately: .DS_Store and
editor swap files would otherwise re-open the gate whenever someone opened the
folder in Finder. Note what this trades — a committed design/.notes.md is
skipped here and by the reviewer's glob, so it is content in the directory that
neither the freeze rule nor the unindexed-file rule can see. That is accepted as
the lesser cost, not as a claim that no hole exists: .gitignore covers
.DS_Store and *.swp, not dotfiles in general.

The digest composes per-file digests rather than concatenating file contents:

    design_hash = sha256(
        <canonical design.md digest> + "\n" +
        "".join("%s %s\n" % (relative path, that file's canonical digest))
    )

Composing digests rather than bytes is what keeps the file set itself part of
the hash. An earlier form appended each file's lines behind a "## FILE <name>"
separator, and a sub-design whose body contained that literal line could forge
the boundary: one file holding "A\n## FILE b.md\nB" hashed the same as two files
holding "A" and "B". A digest cannot be spelled by the content it summarizes.

**Unsplit designs hash identically in both modes.** With no design/ directory
there is nothing to compose, so "design" mode returns the plain "spec" digest
and every design_hash already recorded in a round file stays reproducible.

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
import os
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


def sub_design_paths(design_path):
    """Every file on disk under the sibling design/ directory, at any depth.

    On disk, not committed: an untracked stray (an editor backup, a draft) moves
    the digest too, so keep design/ to the files the design PR will carry.

    Sorted by POSIX relative path (codepoint order, locale-independent) and
    returned as (relative path, absolute path) pairs, because the path is part
    of what is hashed: a rename has to move the digest as much as an edit does.
    Dot-prefixed names are skipped; symlinks and control characters in a path
    are errors. See the module docstring for why each.
    """
    directory = os.path.join(os.path.dirname(design_path) or ".", "design")
    # islink BEFORE isdir: isdir() follows the link, so it is false for a broken
    # link and for one pointing at a regular file. Asking isdir() first would
    # send both down the "no sub-designs" path and print an HLD-only digest for
    # a spec that has a committed design entry.
    if os.path.islink(directory):
        sys.exit(
            "ERROR: %s is a symlink; design_hash covers a directory inside the "
            "spec, not a link to one elsewhere" % directory
        )
    if not os.path.isdir(directory):
        return []

    def unreadable(exc):
        # os.walk swallows listing errors by default, which would drop a whole
        # subtree and still print a digest. Fail instead.
        sys.exit("ERROR: cannot list %s: %s" % (exc.filename, exc))

    found = []
    for root, dirs, names in os.walk(directory, onerror=unreadable):
        dirs[:] = sorted(d for d in dirs if not d.startswith("."))
        for name in dirs:
            if os.path.islink(os.path.join(root, name)):
                sys.exit(
                    "ERROR: %s is a symlinked directory; design_hash cannot "
                    "cover a target outside the spec" % os.path.join(root, name)
                )
        for name in sorted(names):
            if name.startswith("."):
                continue
            absolute = os.path.join(root, name)
            if os.path.islink(absolute):
                sys.exit(
                    "ERROR: %s is a symlink; design_hash covers files, not "
                    "aliases to them" % absolute
                )
            relative = os.path.relpath(absolute, directory).replace(os.sep, "/")
            if any(ord(ch) < 32 for ch in relative):
                sys.exit(
                    "ERROR: %s contains a control character; the digest "
                    "separates records by newline" % absolute
                )
            found.append((relative, absolute))
    return sorted(found)


def design_hash(design_path, lines):
    """design.md's digest, then one (path, digest) line per sub-design."""
    own = canonical_hash(lines)
    parts = sub_design_paths(design_path)
    if not parts:
        return own
    composed = [own]
    for relative, absolute in parts:
        try:
            with open(absolute, "rb") as fh:
                raw = fh.read()
        except OSError as exc:
            sys.exit("ERROR: cannot read %s: %s" % (absolute, exc))
        try:
            digest = canonical_hash(normalized_lines(raw.decode("utf-8")))
        except UnicodeDecodeError:
            # A non-text artifact under design/ still belongs to the set.
            digest = hashlib.sha256(raw).hexdigest()
        composed.append("%s %s" % (relative, digest))
    return hashlib.sha256(("\n".join(composed) + "\n").encode("utf-8")).hexdigest()


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
    if len(sys.argv) != 3 or sys.argv[1] not in ("spec", "design", "product"):
        sys.exit("usage: spec_hash.py {spec|design|product} <path>\n       spec_hash.py --selftest")
    mode, path = sys.argv[1], sys.argv[2]
    if mode == "design" and os.path.basename(path) != "design.md":
        sys.exit(
            "ERROR: design mode hashes a spec's design.md together with its "
            "design/ sub-designs; got %s" % path
        )
    try:
        with open(path, encoding="utf-8") as fh:
            lines = normalized_lines(fh.read())
    except OSError as exc:
        sys.exit("ERROR: cannot read %s: %s" % (path, exc))
    except UnicodeDecodeError as exc:
        sys.exit("ERROR: %s is not valid UTF-8: %s" % (path, exc))
    if mode == "spec":
        print(canonical_hash(lines))
    elif mode == "design":
        print(design_hash(path, lines))
    else:
        print(canonical_hash(product_slice(lines)))


if __name__ == "__main__":
    main()
