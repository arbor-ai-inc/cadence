#!/usr/bin/env python3
"""Validate cadence's canonical workflow docs and its thin adapters.

Three things, each of which failed silently at least once before it was checked:

  1. Every adapter has valid frontmatter, carries "Use when" trigger text, and
     points at its matching canonical doc through ${CLAUDE_PLUGIN_ROOT}.
  2. Adapters stay THIN. An adapter that grows a second copy of the procedure
     is the drift the canonical/adapter split exists to prevent, and the
     duplication check only catches lines copied verbatim -- a paraphrase
     passes, so reviewers still have to read.
  3. Every relative markdown link inside reference/ resolves.

Usage:
    python3 tests/check_agent_skills.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANONICAL_DIR = ROOT / "reference"
CODEX_SKILLS_DIR = ROOT / "adapters" / "codex"
CLAUDE_SKILLS_DIR = ROOT / "skills"
CLAUDE_AGENTS_DIR = ROOT / "agents"
CLAUDE_COMMANDS_DIR = ROOT / "commands"
ACK_TOKEN = "agent-skill-duplication: acknowledged"

# A shipped plugin must NOT pin `model:` anywhere. Two reasons, and the second
# is the one that bites: it silently overrides the model a user chose for a role
# they are paying for, and a plugin agent's model is not conveniently
# overridable from outside. Omitting the key inherits the session model, which
# is what an adopter expects.
#
# This replaces an upstream check that validated the *spelling* of a pin. That
# check existed because a bad value fails open -- the harness falls back to the
# session model and says nothing, so a typo reads as honoured and is not. Here
# the stronger rule is available: no pin at all.
FORBIDDEN_FRONTMATTER_KEYS = ("model",)

# Every canonical doc is ported. PENDING_DOCS is empty and stays that way:
# the guard below still fires, so re-adding a name to hide a broken link means
# the doc must actually be absent.
PENDING_DOCS: set[str] = set()


def check_plugin_manifest(errors: list[str]) -> None:
    """plugin.json's `agents` array must list exactly the files on disk.

    `agents` takes an ARRAY OF FILE PATHS, not a directory -- a directory string
    is rejected by `claude plugin validate`, which is how this was found. The
    consequence of the array form is drift: adding agents/<new>.md without
    touching the manifest ships a subagent the plugin never registers, and
    nothing at runtime says so. Removing one leaves a path to a missing file.
    """
    import json

    manifest = ROOT / ".claude-plugin" / "plugin.json"
    if not manifest.exists():
        errors.append("missing .claude-plugin/plugin.json")
        return
    try:
        declared = json.loads(manifest.read_text(encoding="utf-8")).get("agents", [])
    except json.JSONDecodeError as exc:
        errors.append(f"{rel(manifest)} is not valid JSON: {exc}")
        return

    if isinstance(declared, str):
        errors.append(
            f"{rel(manifest)} declares agents as a string; it must be an array of "
            f"file paths, or `claude plugin validate` rejects it"
        )
        return

    on_disk = sorted(f"./agents/{p.name}" for p in CLAUDE_AGENTS_DIR.glob("*.md"))
    for missing in sorted(set(on_disk) - set(declared)):
        errors.append(
            f"{missing} exists but is not in plugin.json's agents array, so the "
            f"plugin will not register it"
        )
    for absent in sorted(set(declared) - set(on_disk)):
        errors.append(f"plugin.json's agents array names {absent}, which does not exist")


def check_pending_list_is_current(errors: list[str]) -> None:
    """A ported doc must leave PENDING_DOCS, or the list starts hiding real breaks."""
    for name in sorted(PENDING_DOCS):
        for candidate in (CANONICAL_DIR / name, ROOT / "templates" / name):
            if candidate.exists():
                errors.append(
                    f"{rel(candidate)} now exists but is still in PENDING_DOCS in "
                    f"{rel(Path(__file__))}. Remove it from that set — while it is "
                    f"listed, broken links to it are not reported."
                )

CANONICAL_SECTION_HEADINGS = {
    "## Overview",
    "## When To Use",
    "## Workflow",
    "## Common Rationalizations",
    "## Red Flags",
    "## Verification",
}


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def nonblank_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def strip_frontmatter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---\n"):
        return {}, text

    end = text.find("\n---\n", 4)
    if end == -1:
        return {}, text

    raw = text[4:end]
    body = text[end + len("\n---\n") :]
    frontmatter: dict[str, str] = {}

    # Minimal block-scalar support. Every .claude adapter writes its description as
    # a folded scalar ("description: >" plus an indented block), and reading the
    # value as ">" silently defeated any check on it -- which is why the trigger
    # check had to be switched off there rather than fixed. Continuation lines also
    # contain colons, so the naive parser invented keys out of prose.
    lines = raw.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        i += 1
        if ":" not in line or line.startswith((" ", "\t")):
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value in (">", ">-", ">+", "|", "|-", "|+"):
            folded = value.startswith(">")
            block: list[str] = []
            while i < len(lines):
                nxt = lines[i]
                if nxt.strip() and not nxt.startswith((" ", "\t")):
                    break
                block.append(nxt.strip())
                i += 1
            joined = " ".join(b for b in block if b) if folded else "\n".join(block)
            frontmatter[key] = joined.strip()
        else:
            frontmatter[key] = value
    return frontmatter, body


def markdown_links(text: str) -> list[str]:
    return re.findall(r"\[[^\]]+\]\(([^)]+)\)", text)


def local_doc_path(source: Path, target: str) -> Path | None:
    if "://" in target or target.startswith("#"):
        return None
    target = target.split("#", 1)[0]
    if not target:
        return None
    return (source.parent / target).resolve()


def canonical_docs() -> list[Path]:
    """Every canonical doc, including nested ones.

    rglob rather than glob: personas/ sits one level down and a top-level glob
    silently skipped it, so those four docs' outbound links were unchecked. An
    unchecked file and a passing file look identical from the outside.
    """
    return sorted(CANONICAL_DIR.rglob("*.md"))


def adapter_docs() -> list[Path]:
    paths: list[Path] = []
    for skills_dir in (CODEX_SKILLS_DIR, CLAUDE_SKILLS_DIR):
        if skills_dir.exists():
            paths.extend(sorted(skills_dir.glob("*/SKILL.md")))
    for name in ("CLAUDE.md", "AGENTS.md"):
        path = ROOT / name
        if path.exists():
            paths.append(path)
    return paths


def model_bearing_docs() -> list[Path]:
    """Every file whose frontmatter may carry a `model:` pin.

    Wider than adapter_docs(): subagent and slash-command definitions also take the
    key, and they are the two directories the thinness and duplication checks do not
    open. Adding them here is what puts `.claude/agents/` and `.claude/commands/`
    under any check at all.
    """
    paths = list(adapter_docs())
    for extra_dir in (CLAUDE_AGENTS_DIR, CLAUDE_COMMANDS_DIR):
        if extra_dir.exists():
            paths.extend(sorted(extra_dir.glob("*.md")))
    return paths


def check_model_value(path: Path, errors: list[str]) -> None:
    """Refuse a `model:` pin in anything cadence ships.

    Named check_model_value for continuity with the upstream check it replaces,
    which validated the spelling of a pin rather than its presence.
    """
    frontmatter, _ = strip_frontmatter(read(path))
    for key in FORBIDDEN_FRONTMATTER_KEYS:
        if key in frontmatter:
            errors.append(
                f"{rel(path)} pins {key}: {frontmatter[key]!r}. A shipped plugin must not "
                f"pin a model — it silently overrides the model the user chose for this "
                f"role, and a plugin's pin is not conveniently overridable from outside. "
                f"Omit the key to inherit the session model."
            )


def duplicated_canonical_lines() -> dict[str, set[str]]:
    duplicated: dict[str, set[str]] = {}
    for path in canonical_docs():
        if path.name == "README.md":
            continue
        lines = {
            line
            for line in nonblank_lines(read(path))
            if len(line) >= 90
            and not line.startswith("|")
            and not line.startswith("```")
            and not line.startswith("- [ ]")
        }
        duplicated[rel(path)] = lines
    return duplicated


# Minimum length for a canonical paragraph to be worth matching. Short paragraphs
# collide on ordinary phrasing.
#
# Coverage, with an honest denominator: 428 of 544 prose blocks, so 78.7%. An earlier
# version of this comment said "428 of the ~470", which flattered the floor by
# comparing a 120-char filter against an 80-char one -- 470 *is* the count at 80+.
# The floor is still the right trade; the sentence justifying it was not.
MIN_PARAGRAPH = 120


def canonical_paragraphs() -> dict[str, list[str]]:
    """Whitespace-normalized canonical paragraphs, keyed by source doc.

    The line-based check below is nearly useless on its own: it only matches lines
    of 90+ characters, and this repo hard-wraps markdown at ~88, so it reaches 54 of
    3753 nonblank canonical lines. A paragraph copied verbatim and re-wrapped at any
    width is invisible to it -- measured at 0 matchable lines for a real paragraph
    re-wrapped to 70 columns. Normalizing whitespace before comparing removes
    wrapping from the equation entirely.

    This still only catches *verbatim* copying. A paraphrase defeats it, which is
    why the nonblank-line cap remains the only real bound on adapter volume.

    One further escape, found by review: a wrapper that breaks *at hyphens* also
    slips through, because rejoining inserts a space into the broken word
    ("over-generalized" -> "over- generalized"). Python's textwrap does this by
    default; prose written by hand does not. Left unfixed deliberately -- stripping
    spaces around hyphens would start matching genuinely different text.
    """
    paragraphs: dict[str, list[str]] = {}
    for path in canonical_docs():
        if path.name == "README.md":
            continue
        text = re.sub(r"```.*?```", "", read(path), flags=re.S)
        kept = []
        for block in re.split(r"\n\s*\n", text):
            flat = " ".join(block.split())
            # Tables and headings are structure, not prose worth protecting.
            if not flat or flat.startswith("|") or flat.startswith("#"):
                continue
            if len(flat) >= MIN_PARAGRAPH:
                kept.append(flat)
        paragraphs[rel(path)] = kept
    return paragraphs


def check_canonical_links(errors: list[str]) -> None:
    for path in canonical_docs():
        for target in markdown_links(read(path)):
            resolved = local_doc_path(path, target)
            if resolved is None:
                continue
            if resolved.exists():
                continue
            if resolved.name in PENDING_DOCS:
                continue  # not ported yet; check_pending_list_is_current keeps this honest
            errors.append(f"{rel(path)} links to missing file: {target}")


def check_skill_adapter(path: Path, errors: list[str]) -> None:
    text = read(path)
    frontmatter, body = strip_frontmatter(text)
    skill_name = path.parent.name

    if not frontmatter:
        errors.append(f"{rel(path)} must start with YAML frontmatter")
        return

    if frontmatter.get("name") != skill_name:
        errors.append(
            f"{rel(path)} frontmatter name must match directory {skill_name!r}"
        )

    description = frontmatter.get("description", "")
    if "Use when" not in description:
        errors.append(f"{rel(path)} description must include trigger text: 'Use when'")

    expected_doc = CANONICAL_DIR / f"{skill_name}.md"
    if not expected_doc.exists():
        errors.append(
            f"{rel(path)} must point to an existing canonical doc at {rel(expected_doc)}"
        )
        return

    expected_ref = rel(expected_doc)
    if expected_ref not in body:
        errors.append(f"{rel(path)} must reference {expected_ref}")


def check_adapter_thinness(
    path: Path,
    errors: list[str],
    canonical_lines: dict[str, set[str]],
    canonical_paras: dict[str, list[str]],
) -> None:
    text = read(path)
    acknowledged = ACK_TOKEN in text
    _, body = strip_frontmatter(text)

    if acknowledged:
        if "reason=" not in text:
            errors.append(
                f"{rel(path)} uses {ACK_TOKEN!r} but must include reason=\"...\""
            )
        return

    # The cap applies to the AUTHORED set. It used to be off for skills/
    # entirely, which -- once the Codex set became derived -- would have left it
    # unable to fire anywhere at all. A cap that cannot fire is worse than no
    # cap: it reads as a bound on adapter volume and is not one.
    #
    # So: 30 nonblank body lines, measured against a corpus whose median is 7.
    # That is loose enough for the adapters that legitimately carry a refusal
    # condition or a hash gate an agent must honour BEFORE it loads the
    # canonical doc -- moving that substance out puts it somewhere the agent
    # reads too late -- and tight enough to catch an adapter absorbing the
    # procedure. Above the cap, acknowledge it explicitly with a reason.
    #
    # Do NOT read the cap as "covered by the duplication checks". It is not.
    # The line comparison reaches a small fraction of canonical prose, and
    # neither check sees a *paraphrase*. The cap is the only real bound on
    # adapter volume, and it is deliberately coarse.
    #
    # The generated Codex set is exempt for a different and stronger reason: it
    # is DERIVED. It can only ever be as thin as its source, it is not
    # hand-maintained so it cannot drift on its own, and gen_adapters.py
    # --check already fails if it diverges. Capping it would only ever fire as
    # a duplicate of the cap on the authored file.
    if CODEX_SKILLS_DIR not in path.parents:
        max_nonblank = 30 if path.name == "SKILL.md" else 25
        count = len(nonblank_lines(body))
        if count > max_nonblank:
            errors.append(
                f"{rel(path)} has {count} nonblank body lines (cap {max_nonblank}); "
                f"keep adapters thin, or acknowledge it with "
                f"'<!-- {ACK_TOKEN} reason=\"...\" -->'"
            )

    body_headings = set(re.findall(r"^## .+$", body, flags=re.MULTILINE))
    copied_headings = sorted(body_headings & CANONICAL_SECTION_HEADINGS)
    if copied_headings:
        errors.append(
            f"{rel(path)} appears to copy workflow sections {copied_headings}; "
            f"link to canonical docs or add '<!-- {ACK_TOKEN} reason=\"...\" -->'"
        )

    adapter_lines = set(nonblank_lines(body))
    for source, lines in canonical_lines.items():
        copied = sorted(adapter_lines & lines)
        if copied:
            sample = copied[0][:120]
            errors.append(
                f"{rel(path)} duplicates canonical content from {source}: {sample!r}. "
                f"Link instead or add '<!-- {ACK_TOKEN} reason=\"...\" -->'"
            )

    # Wrapping-independent: catches a canonical paragraph pasted and re-wrapped,
    # which the line comparison above cannot see at all.
    flat_body = " ".join(body.split())
    for source, paras in canonical_paras.items():
        for para in paras:
            if para in flat_body:
                errors.append(
                    f"{rel(path)} duplicates a canonical paragraph from {source}: "
                    f"{para[:120]!r}. Link instead or add "
                    f"'<!-- {ACK_TOKEN} reason=\"...\" -->'"
                )
                break


def main() -> int:
    errors: list[str] = []

    if not CANONICAL_DIR.exists():
        errors.append(f"Missing canonical workflow directory: {rel(CANONICAL_DIR)}")
        print("\n".join(errors), file=sys.stderr)
        return 1

    check_plugin_manifest(errors)
    check_pending_list_is_current(errors)
    check_canonical_links(errors)
    canonical_lines = duplicated_canonical_lines()
    canonical_paras = canonical_paragraphs()

    for path in adapter_docs():
        if path.name == "SKILL.md":
            check_skill_adapter(path, errors)
        check_adapter_thinness(path, errors, canonical_lines, canonical_paras)

    for path in model_bearing_docs():
        check_model_value(path, errors)

    if errors:
        print("cadence workflow validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(
        f"check_agent_skills: ok "
        f"({len(canonical_docs())} canonical docs, {len(adapter_docs())} adapters"
        + (f", {len(PENDING_DOCS)} docs pending" if PENDING_DOCS else "")
        + ")"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
