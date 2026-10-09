#!/usr/bin/env python3
"""check_spec_pipeline.py - the spec pipeline's mechanical guarantees.

Three things the spec pipeline relies on that are prose everywhere except here:

  1. `spec_hash.py design` covers a split design exactly: every file under
     design/ moves the digest, nothing outside it does, and the ways content
     could leave its reach fail loudly instead of hashing.
  2. Every file that decides whether a spec may skip Gate 1 carries the same
     literal test, so none drifts to a looser wording.
  3. The design template's section lists match its own headings.

Usage:
    python3 tests/check_spec_pipeline.py
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESIGN_TEMPLATE = ROOT / "templates" / "_design_template.md"
# The template's always-present / optional split, pinned: a section that moves
# between the lists changes what Gate 2 does with its absence.
ALWAYS_PRESENT_COUNT = 14
OPTIONAL_SECTIONS = {
    "Sub-designs",
    "Failure Modes & Operational Behavior",
    "Security, Privacy & Abuse",
    "Scale, Performance & Cost",
    "Observability",
    "Rollout, Migration & Compatibility",
}


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def check_spec_hash_design_mode(errors: list[str]) -> None:
    """Exercise `spec_hash.py design` against a constructed tree.

    This lives beside the design-template check because the same commit that gave
    a design more than one file gave `design_hash` the job of covering them, and
    neither had an assertion behind it: `grep -rl spec_hash tests/` found nothing,
    and nothing else exercises the mode, so every rule it enforces could be deleted
    with a green tree. Each case below is a way an
    artifact could stop being what its digest says it is.
    """
    script = ROOT / "tools" / "spec_hash.py"
    if not script.exists():
        errors.append(f"Missing {rel(script)}")
        return

    def run(mode, path):
        return subprocess.run(
            [sys.executable, str(script), mode, str(path)],
            capture_output=True,
            text=True,
        )

    with tempfile.TemporaryDirectory() as tmp:
        spec = Path(tmp) / "slug"
        (spec / "design").mkdir(parents=True)
        design = spec / "design.md"
        design.write_text("# HLD\n\nbody\n", encoding="utf-8")

        unsplit = run("design", design)
        plain = run("spec", design)

        # Coverage is design/ only. testing-plan.md and product.md sit beside it,
        # and every doc says the testing plan is outside design_hash.
        for sibling in ("testing-plan.md", "product.md", "notes.md"):
            (spec / sibling).write_text("# " + sibling + "\n", encoding="utf-8")
        if run("design", design).stdout != unsplit.stdout:
            errors.append(
                "spec_hash: a file beside design/ (testing-plan.md, product.md) "
                "must not move design_hash"
            )
        if unsplit.stdout != plain.stdout:
            errors.append(
                "spec_hash: design mode must reduce to spec mode with no "
                "sub-designs, or every recorded design_hash stops reproducing"
            )

        sub = spec / "design" / "storage.md"
        sub.write_text("# Storage\n\nv1\n", encoding="utf-8")
        split = run("design", design)
        if split.stdout == plain.stdout:
            errors.append("spec_hash: a sub-design must move design_hash")
        sub.write_text("# Storage\n\nv2\n", encoding="utf-8")
        if run("design", design).stdout == split.stdout:
            errors.append("spec_hash: editing a sub-design must move design_hash")
        edited = run("design", design).stdout
        sub.rename(spec / "design" / "renamed.md")
        if run("design", design).stdout == edited:
            errors.append("spec_hash: a rename must move design_hash")
        renamed = run("design", design).stdout

        # Content must not be able to spell the record separator.
        forge = spec / "design" / "a.md"
        forge.write_text("A\n## FILE b.md\nB\n", encoding="utf-8")
        one_file = run("design", design).stdout
        forge.write_text("A\n", encoding="utf-8")
        (spec / "design" / "b.md").write_text("B\n", encoding="utf-8")
        if run("design", design).stdout == one_file:
            errors.append(
                "spec_hash: one file spelling the separator must not hash the "
                "same as the two files it names"
            )
        (spec / "design" / "a.md").unlink()
        (spec / "design" / "b.md").unlink()

        # Editor droppings must not re-open the gate.
        (spec / "design" / ".DS_Store").write_text("junk\n", encoding="utf-8")
        if run("design", design).stdout != renamed:
            errors.append("spec_hash: a dot-prefixed file must not move design_hash")
        (spec / "design" / ".DS_Store").unlink()

        # Coverage: a nested file is as much the artifact as a top-level one.
        nested = spec / "design" / "deep"
        nested.mkdir()
        (nested / "detail.md").write_text("d\n", encoding="utf-8")
        if run("design", design).stdout == renamed:
            errors.append("spec_hash: a nested file must be part of the artifact")

        # The refusals, each a way for content to leave the digest's reach.
        if os.geteuid() != 0:
            # Root bypasses the permission bit, so the case would invert and
            # report a spurious failure in a container that runs as root.
            nested.chmod(0o000)
            try:
                if run("design", design).returncode == 0:
                    errors.append(
                        "spec_hash: an unreadable directory must fail, not yield "
                        "a digest for content it never read"
                    )
            finally:
                nested.chmod(0o755)

        unreadable_file = nested / "detail.md"
        if os.geteuid() != 0:
            unreadable_file.chmod(0o000)
            try:
                if run("design", design).returncode == 0:
                    errors.append("spec_hash: an unreadable file must fail")
            finally:
                unreadable_file.chmod(0o644)

        link = spec / "design" / "linked.md"
        link.symlink_to(design)
        if run("design", design).returncode == 0:
            errors.append("spec_hash: a symlinked file under design/ must fail")
        link.unlink()

        # The two directory symlinks: one inside design/, and design/ itself.
        # Either one moves a whole subtree out of the spec.
        sibling = Path(tmp) / "other"
        sibling.mkdir()
        (sibling / "x.md").write_text("x\n", encoding="utf-8")
        dir_link = spec / "design" / "linked_dir"
        dir_link.symlink_to(sibling, target_is_directory=True)
        if run("design", design).returncode == 0:
            errors.append("spec_hash: a symlinked directory under design/ must fail")
        dir_link.unlink()

        # design/ itself as a symlink, one case per target type. isdir() follows
        # the link, so the broken and file-target cases look like "no design/ at
        # all" unless islink is asked first — each would silently print an
        # HLD-only digest for a spec that has a committed design entry.
        for case, target, is_dir in (
            ("a directory", "real", True),
            ("a regular file", "loose.md", False),
            ("nothing", "missing", False),
        ):
            aliased = Path(tmp) / ("aliased-" + case.replace(" ", "-"))
            (aliased / "real").mkdir(parents=True)
            (aliased / "design.md").write_text("# HLD\n", encoding="utf-8")
            (aliased / "real" / "storage.md").write_text("s\n", encoding="utf-8")
            (aliased / "loose.md").write_text("l\n", encoding="utf-8")
            (aliased / "design").symlink_to(
                aliased / target, target_is_directory=is_dir
            )
            if run("design", aliased / "design.md").returncode == 0:
                errors.append(
                    f"spec_hash: design/ symlinked to {case} must fail, not "
                    f"fall through to the unsplit digest"
                )

        # The basename guard, against a file that exists: otherwise this passes
        # on 'cannot read' and asserts nothing.
        (spec / "product.md").write_text("# Product\n", encoding="utf-8")
        if run("design", spec / "product.md").returncode == 0:
            errors.append("spec_hash: design mode must refuse a non-design.md path")

        weird = spec / "design" / "with\nnewline.md"
        try:
            weird.write_text("x\n", encoding="utf-8")
        except OSError:
            weird = None
        if weird is not None:
            if run("design", design).returncode == 0:
                errors.append(
                    "spec_hash: a control character in a path must fail — the "
                    "digest separates records by newline"
                )
            weird.unlink()


DESIGN_ONLY_TEST = re.compile(
    r"could see,?\s+be billed for,?\s+or complain about"
)
# Every file that decides, or describes, whether a spec may skip Gate 1. The
# rule is prose in each, so nothing but this list stops one of them drifting to
# a looser wording — which happened five times across one review cycle, twice in
# a frontmatter `description:` that a model reads before the procedure below it.
DESIGN_ONLY_SITES = (
    "templates/_design_template.md",
    "agents/eng-design-reviewer.md",
    "skills/draft-plan/SKILL.md",
    "skills/spec-pipeline/SKILL.md",
    "adapters/codex/draft-plan/SKILL.md",
    "reference/draft-plan.md",
    "reference/spec-pipeline.md",
)


DESIGN_ONLY_DESCRIPTIONS = ("skills/draft-plan/SKILL.md", "adapters/codex/draft-plan/SKILL.md")


def check_design_only_test(errors: list[str]) -> None:
    """Every site that mentions design-only must carry the literal test.

    Normalizes whitespace and strips blockquote markers before matching: a
    line-based grep misses a wrapped occurrence and a `> ` quoted one, so the
    check that was meant to prove the phrase identical everywhere could not.
    """
    for rel_path in DESIGN_ONLY_SITES:
        path = ROOT / rel_path
        if not path.exists():
            errors.append(f"Missing {rel_path}")
            continue
        text = read(path)

        def carries(chunk: str) -> bool:
            flat = " ".join(re.sub(r"^\s*>\s?", "", chunk, flags=re.M).split())
            return bool(DESIGN_ONLY_TEST.search(flat))

        # Unconditional: gating on a trigger word like "design-only" would let a
        # file drop the term and the literal together and still pass, which is
        # the drift this exists to stop. Every listed file must carry it.
        if not carries(text):
            errors.append(
                f"{rel_path} is a design-only decision point but does not carry "
                f"the literal test 'nothing a customer could see, be billed for, "
                f"or complain about'. A looser wording here lets billable work "
                f"skip Gate 1. If this file no longer decides eligibility, drop "
                f"it from DESIGN_ONLY_SITES in {rel(Path(__file__))}"
            )

        # The frontmatter `description:` is graded on its own: a model picks a
        # skill from it and can act on a looser rule before ever reading the
        # procedure beneath it. A body that carries the test does not cover this.
        match = re.search(r"^description:\s*(.+?)(?=^\w+:|^---)", text, re.M | re.S)
        # The drafter's description decides eligibility, so it is checked whatever
        # its wording; gating it on a trigger word would let it drop both. Other
        # sites are checked when their description raises the subject at all.
        decides = rel_path in DESIGN_ONLY_DESCRIPTIONS
        if match and (decides or re.search(r"ungated|design-only|no product gate|with none",
                                           match.group(1))):
            if not carries(match.group(1)):
                errors.append(
                    f"{rel_path}: the frontmatter description states when the "
                    f"product gate is skipped but not the literal test. A model "
                    f"selects the skill from this line without reading the body"
                )


def check_design_template(errors: list[str]) -> None:
    """The Gate 2 design template's section lists must match its own headings.

    The drafter, the Gate 2 reviewer and `/cadence:spec-pipeline` all key off the template's
    always-present / optional split. Nothing else reads this file, so a heading
    renamed on one side of it and not the other is invisible until a design is
    drafted against the drift — which is how three defects reached a second
    review round. The check is deliberately narrow: names only, no length rule.
    """
    if not DESIGN_TEMPLATE.exists():
        errors.append(f"Missing {rel(DESIGN_TEMPLATE)}")
        return
    text = read(DESIGN_TEMPLATE)
    # Split at the instructions block's own terminator. Splitting on the file's
    # first "\n---\n" would land on YAML front matter if one is ever added, and
    # then every heading reads as "missing" — 29 errors for one added line.
    start = text.find("\n## How to use this template")
    body = text[start:].split("\n---\n", 1) if start != -1 else [text]
    if len(body) != 2:
        errors.append(
            f"{rel(DESIGN_TEMPLATE)}: no '---' separating the instructions block "
            f"from the template body; the drafter deletes from "
            f"'## How to use this template' down to that line"
        )
        return
    instructions, template = body

    headings = re.findall(r"^## (.+)$", template, flags=re.M)
    listed: dict[str, set[str]] = {}
    for label, pattern in (
        ("always-present", r"\*\*Always present:\*\*(.+?)(?=\n\n)"),
        ("optional", r"\*\*Present only when they materially apply:\*\*(.+?)(?=\n\n)"),
    ):
        match = re.search(pattern, instructions, flags=re.S)
        if not match:
            errors.append(
                f"{rel(DESIGN_TEMPLATE)}: no '{label}' section list in the "
                f"instructions block"
            )
            listed[label] = set()
            continue
        # Names wrap across lines in the source; compare on collapsed whitespace.
        listed[label] = {
            " ".join(name.split())
            for name in re.findall(r"\*([^*]+)\*", match.group(1))
        }

    named = listed["always-present"] | listed["optional"]
    for heading in headings:
        if heading not in named:
            errors.append(
                f"{rel(DESIGN_TEMPLATE)}: section '## {heading}' is in neither the "
                f"always-present nor the optional list"
            )
    for name in sorted(named):
        if name not in headings:
            errors.append(
                f"{rel(DESIGN_TEMPLATE)}: '{name}' is listed in the instructions "
                f"block but no '## {name}' heading exists"
            )

    # After the drafter deletes the instructions block, an optional section's
    # "> *Include only ...*" marker is the only thing in the shipped file saying
    # it may be left out. Nothing else would notice that drifting.
    for heading in headings:
        section = re.search(
            r"^## " + re.escape(heading) + r"\n(.*?)(?=^## |\Z)",
            template,
            flags=re.M | re.S,
        )
        if not section:
            continue
        marked = "> *Include only" in section.group(1)
        if heading in listed["optional"] and not marked:
            errors.append(
                f"{rel(DESIGN_TEMPLATE)}: optional section '## {heading}' has no "
                f"'> *Include only ...*' marker; once the instructions block is "
                f"deleted that marker is all a drafter has"
            )
        if heading in listed["always-present"] and marked:
            errors.append(
                f"{rel(DESIGN_TEMPLATE)}: always-present section '## {heading}' "
                f"carries an '> *Include only ...*' marker, which tells a drafter "
                f"to delete a section Gate 2 blocks on when it is absent"
            )

    words = {14: "fourteen"}
    reviewer = ROOT / "agents" / "eng-design-reviewer.md"
    word = words.get(ALWAYS_PRESENT_COUNT)
    if word is None or not re.search(rf"\b{word}\b", read(reviewer)):
        errors.append(
            f"{rel(reviewer)} must state the always-present count as "
            f"'{word or ALWAYS_PRESENT_COUNT}' — it tells the reviewer how many "
            f"absent sections are BLOCKERs. Update the word, or `words` here"
        )

    if len(listed["always-present"]) != ALWAYS_PRESENT_COUNT:
        errors.append(
            f"{rel(DESIGN_TEMPLATE)}: {len(listed['always-present'])} always-present "
            f"sections, but {rel(Path(__file__))} and "
            f"`agents/eng-design-reviewer.md` say "
            f"{ALWAYS_PRESENT_COUNT}. Update all three or none"
        )

    both = listed["always-present"] & listed["optional"]
    for name in sorted(both):
        errors.append(
            f"{rel(DESIGN_TEMPLATE)}: '{name}' is in both the always-present and "
            f"the optional list; the drafter and the Gate 2 reviewer branch on "
            f"which one it is"
        )

    # Which list a section is in is the load-bearing bit: an optional section
    # correctly omitted is never a finding, while a missing always-present one is
    # a BLOCKER (`agents/eng-design-reviewer.md`, § *Inputs you MUST
    # read*, item 1 — "absent from the whole artifact"). A
    # section that moves between the lists changes what the gate does, so the
    # split is pinned here rather than left to the union check above.
    if listed["optional"] != OPTIONAL_SECTIONS:
        for name in sorted(listed["optional"] - OPTIONAL_SECTIONS):
            errors.append(
                f"{rel(DESIGN_TEMPLATE)}: '{name}' was moved into the optional "
                f"list; an optional section omitted from a design is never a "
                f"finding. Intended? Update OPTIONAL_SECTIONS in {rel(Path(__file__))}"
            )
        for name in sorted(OPTIONAL_SECTIONS - listed["optional"]):
            errors.append(
                f"{rel(DESIGN_TEMPLATE)}: '{name}' is no longer optional; Gate 2 "
                f"will now block on its absence. Intended? Update "
                f"OPTIONAL_SECTIONS in {rel(Path(__file__))}"
            )


def main() -> int:
    errors: list[str] = []
    check_spec_hash_design_mode(errors)
    check_design_only_test(errors)
    check_design_template(errors)
    for e in errors:
        print(f"check_spec_pipeline: {e}", file=sys.stderr)
    if errors:
        print(f"\ncheck_spec_pipeline: {len(errors)} problem(s).", file=sys.stderr)
        return 1
    print("check_spec_pipeline: ok (design hash, design-only test, design template)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
