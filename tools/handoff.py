#!/usr/bin/env python3
"""handoff.py - create, find, list and lint agent handoff files.

A handoff is the file a coding agent writes so a later session can pick up a
multi-session track. reference/handoff.md is the procedure and the memory model
behind the format. This tool does the mechanical parts, so they come out the
same every time:

    handoff.py new <slug> [--issue ID] [--epic NAME] [--spec PATH] [--owner NAME]
    handoff.py resolve <query>          # which file does "PROJ-34" or "quota" mean?
    handoff.py list [--json]
    handoff.py lint [<query>] [--json] [--strict]
    handoff.py backup <query>           # rotate <file>.prev before a rewrite

Handoffs live in the MAIN worktree's handoff directory, whichever worktree this
runs from, so a handoff saved in one worktree is found from every other. The
header's `Checkout:` still names the worktree the work happens in.

Settings come from the [handoff] table of cadence.toml at the main worktree's
root, or from a standalone TOML file passed with --config. Every key is
optional; see templates/cadence.toml.

Local-only: no network. The only subprocess is `git` (rev-parse, check-ignore,
config, branch). Standard library only; Python 3.11+.
"""

from __future__ import annotations

import sys

if sys.version_info < (3, 11):  # pragma: no cover - checked before tomllib is needed
    print(f"handoff: needs Python 3.11+ (this is {sys.version.split()[0]})", file=sys.stderr)
    sys.exit(2)

import argparse  # noqa: E402
import dataclasses  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
import re  # noqa: E402
import shutil  # noqa: E402
import subprocess  # noqa: E402
import tomllib  # noqa: E402
from datetime import date, datetime  # noqa: E402
from pathlib import Path  # noqa: E402

VERSION = "0.1.0"
PREFIX = "HANDOFF-"
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$|^[A-Z][A-Z0-9]*-[0-9]+(-[a-z0-9-]+)?$")
HEADER_FIELDS = ("Issue", "Repo", "Checkout", "Owner", "Last written", "Status")
STATUSES = ("active", "parked", "closing")
TIMESTAMPED_BACKUP_RE = re.compile(r"\.bak[-_.]?\d{6,}")

EXIT_OK, EXIT_LINT, EXIT_USAGE, EXIT_AMBIGUOUS, EXIT_NOT_FOUND = 0, 1, 2, 3, 4


@dataclasses.dataclass
class Config:
    dir: str = ".local"
    resume_max_lines: int = 40
    file_max_lines: int = 300
    archive_max_lines: int = 300
    log_entry_max_lines: int = 5
    stale_days: int = 14


class UsageError(Exception):
    pass


# ---------------------------------------------------------------------------
# git (the only subprocess)


def _git(cwd: Path, *argv: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(cwd), "-c", "core.fsmonitor=false", *argv],
        capture_output=True, text=True, check=False,
        env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
    )


def repo_root(cwd: Path) -> Path:
    """The worktree `cwd` is in: what a handoff's `Checkout:` names."""
    proc = _git(cwd, "rev-parse", "--show-toplevel")
    if proc.returncode != 0:
        raise UsageError(f"{cwd} is not inside a git repository")
    return Path(proc.stdout.strip()).resolve()


def _git_path(cwd: Path, *argv: str) -> Path:
    """A path git prints, resolved against `cwd` (older git prints it relative)."""
    proc = _git(cwd, "rev-parse", *argv)
    out = proc.stdout.strip()
    if proc.returncode != 0 or not out or "\n" in out:
        raise UsageError(f"{cwd} is not inside a git repository")
    return (cwd / out).resolve()


def main_root(cwd: Path) -> Path:
    """The MAIN worktree's root, even from a linked worktree: where handoffs live.

    From the main worktree (including a submodule's, or one whose git directory
    lives elsewhere) that is simply its top level. From a linked worktree it is
    found through the shared git directory: its parent for an ordinary `.git`,
    else the directory its `core.worktree` names (how a submodule records it).
    """
    if _git(cwd, "rev-parse", "--is-bare-repository").stdout.strip() == "true":
        raise UsageError(f"{cwd} is a bare repository; run from a worktree")
    common = _git_path(cwd, "--git-common-dir")
    if _git_path(cwd, "--absolute-git-dir") == common:
        return repo_root(cwd)
    if common.name == ".git":
        return common.parent
    proc = _git(common, "config", "--file", str(common / "config"), "core.worktree")
    if proc.returncode == 0 and proc.stdout.strip():
        return (common / proc.stdout.strip()).resolve()
    raise UsageError(
        f"cannot find the main worktree from the linked worktree {cwd}; run from the main worktree"
    )


def normalize_remote(url: str) -> str | None:
    """`owner/name` of a git remote, dropping scheme, user and host."""
    u = re.sub(r"\.git$", "", url.strip().rstrip("/"))
    m = re.match(r"^[a-z][a-z0-9+.-]*://(?:[^@/]+@)?[^/]+/(.+)$", u, re.IGNORECASE) or re.match(
        r"^(?:[^@/]+@)?[^:/]+:(?!/)(.+)$", u
    )
    parts = [p for p in (m.group(1) if m else u).split("/") if p]
    return "/".join(parts[-2:]) if len(parts) >= 2 else None


def repo_name(root: Path) -> str:
    proc = _git(root, "config", "--get", "remote.origin.url")
    return (normalize_remote(proc.stdout) if proc.returncode == 0 else None) or root.name


def current_branch(root: Path) -> str:
    proc = _git(root, "branch", "--show-current")
    return proc.stdout.strip() or "none"


def git_user(root: Path) -> str:
    proc = _git(root, "config", "--get", "user.name")
    return proc.stdout.strip() or "unknown"


def enclosing_repo(d: Path) -> Path | None:
    """The worktree holding `d` (or its nearest existing parent), if any."""
    probe = next((p for p in (d, *d.parents) if p.is_dir()), None)
    if probe is None:
        return None
    proc = _git(probe, "rev-parse", "--show-toplevel")
    return Path(proc.stdout.strip()).resolve() if proc.returncode == 0 else None


def is_ignored(root: Path, path: Path) -> bool:
    return _git(root, "check-ignore", "-q", "--no-index", os.path.relpath(path, root)).returncode == 0


# ---------------------------------------------------------------------------
# Files


CONFIG_NAME = "cadence.toml"


def config_errors(raw: object) -> list[str]:
    """What is wrong with a [handoff] table. cadence_config.py uses this too."""
    if not isinstance(raw, dict):
        return ["[handoff] must be a table"]
    known = [f.name for f in dataclasses.fields(Config)]
    errors = []
    for key, value in raw.items():
        if key not in known:
            errors.append(f"unknown key [handoff].{key}. Known: {', '.join(sorted(known))}")
        elif key == "dir":
            if not (isinstance(value, str) and value.strip()):
                errors.append("[handoff].dir must be a non-empty path")
        elif not (isinstance(value, int) and not isinstance(value, bool) and value >= 1):
            errors.append(f"[handoff].{key} must be a whole number of at least 1")
    return errors


def load_config(path: str | None, root: Path) -> Config:
    """The [handoff] table of --config FILE or of root/cadence.toml.

    A --config file may also hold the keys at its top level, with no table.
    """
    source = Path(path) if path else root / CONFIG_NAME
    if not path and not source.exists():
        return Config()
    try:
        raw = tomllib.loads(source.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise UsageError(f"cannot read config {source}: {exc}") from exc
    if "handoff" in raw or not path:
        raw = raw.get("handoff", {})
    errors = config_errors(raw)
    if errors:
        raise UsageError(f"{source}: " + "; ".join(errors))
    return Config(**raw)


def handoff_dir(root: Path, cfg: Config) -> Path:
    d = Path(cfg.dir)
    return (d if d.is_absolute() else root / d).resolve()


def slug_of(path: Path) -> str:
    return path.name[len(PREFIX):-len(".md")]


def handoff_files(d: Path) -> list[Path]:
    if not d.is_dir():
        return []
    return sorted(p for p in d.glob(f"{PREFIX}*.md") if not p.name.endswith(".archive.md"))


ISSUE_ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9]*-[0-9]+$")


def resolve(d: Path, query: str) -> list[Path]:
    """Exact slug, then issue-id prefix, then case-insensitive substring.

    A query shaped like an issue id (`PROJ-12`) never falls through to substring
    matching: `PROJ-1` must not find `PROJ-12-…`, or one issue's run would pick up
    another issue's handoff.
    """
    files = handoff_files(d)
    exact = [p for p in files if slug_of(p) == query]
    if exact:
        return exact
    q = query.lower()
    by_id = [p for p in files if slug_of(p).lower() == q or slug_of(p).lower().startswith(q + "-")]
    if by_id or ISSUE_ID_RE.match(query):
        return by_id
    return [p for p in files if q in slug_of(p).lower()]


def resolve_one(d: Path, query: str) -> Path:
    hits = resolve(d, query)
    if len(hits) == 1:
        return hits[0]
    if not hits:
        raise LookupError(f"no handoff matches {query!r} in {d}")
    raise LookupError(f"{query!r} matches {len(hits)} handoffs: " + ", ".join(slug_of(p) for p in hits))


# ---------------------------------------------------------------------------
# Parsing


def parse_header(text: str) -> dict[str, str]:
    """Fields from the `Key: value · Key: value` lines between the title and the first `## `."""
    fields: dict[str, str] = {}
    for line in text.splitlines()[1:]:
        if line.startswith("## "):
            break
        for part in line.split("·"):
            if ":" in part:
                k, v = part.split(":", 1)
                k = k.strip()
                if k and len(k) <= 24:
                    fields[k] = v.strip()
    return fields


def sections(text: str) -> dict[str, list[str]]:
    """`## ` heading → its lines (headings keep their suffix, e.g. `Resume here — 2026-01-02`)."""
    out: dict[str, list[str]] = {}
    current = None
    for line in text.splitlines():
        if line.startswith("## "):
            current = line[3:].strip()
            out.setdefault(current, [])
        elif current is not None:
            out[current].append(line)
    return out


def find_section(secs: dict[str, list[str]], name: str) -> list[tuple[str, list[str]]]:
    return [(k, v) for k, v in secs.items() if k.lower().startswith(name.lower())]


def nonblank(lines: list[str]) -> int:
    return sum(1 for ln in lines if ln.strip())


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    m = re.search(r"\d{4}-\d{2}-\d{2}", value)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(0), "%Y-%m-%d").date()
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Lint


@dataclasses.dataclass
class Finding:
    severity: str  # "error" | "warning"
    code: str
    message: str


def lint_file(path: Path, cfg: Config, today: date) -> list[Finding]:
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    out: list[Finding] = []

    def err(code: str, msg: str) -> None:
        out.append(Finding("error", code, msg))

    def warn(code: str, msg: str) -> None:
        out.append(Finding("warning", code, msg))

    if not lines or not lines[0].startswith("# "):
        err("no-title", "first line must be a `# Handoff — <slug>` title")
    header = parse_header(text)
    missing = [f for f in HEADER_FIELDS if f not in header]
    if missing:
        err("header-missing", f"header lacks: {', '.join(missing)}")
    status = header.get("Status", "").split()[0].lower() if header.get("Status") else ""
    if header.get("Status") and status not in STATUSES:
        err("bad-status", f"Status must start with one of {', '.join(STATUSES)}")
    checkout = header.get("Checkout")
    if checkout and checkout.lower() != "none" and not Path(os.path.expanduser(checkout)).is_dir():
        warn("checkout-missing", f"Checkout {checkout} does not exist on this machine")
    written = parse_date(header.get("Last written"))
    if status == "active" and written and (today - written).days > cfg.stale_days:
        warn("stale", f"active but last written {(today - written).days} days ago")
    if not SLUG_RE.match(slug_of(path)):
        warn("slug-shape", "slug should be an issue id (PROJ-12-topic) or lowercase-hyphen (epic-…, spec-…, theme-…)")
    if re.search(r"\d{4}-\d{2}-\d{2}", slug_of(path)):
        warn("slug-dated", "dates belong in the header, not the slug")

    secs = sections(text)
    resumes = find_section(secs, "Resume here")
    if not resumes:
        err("no-resume", "missing `## Resume here`")
    elif len(resumes) > 1:
        err("multiple-resume", f"{len(resumes)} `## Resume here` sections; rewrite one, don't stack")
    # A heading that *opens* with a resume phrase (after emoji / numbering), not one that mentions it.
    starts = ("start here", "restart here", "resume point", "resume here")
    extra = [
        k for k in secs
        if re.sub(r"^[^A-Za-z]+", "", k).lower().startswith(starts) and not k.lower().startswith("resume here")
    ]
    if extra:
        err("stacked-start", f"extra resume-style section(s): {'; '.join(e[:50] for e in extra)}")
    for name, body in resumes[:1]:
        n = nonblank(body)
        if n > cfg.resume_max_lines:
            err("resume-too-long", f"`## Resume here` is {n} lines (cap {cfg.resume_max_lines})")
        if not any(re.match(r"\s*(\*\*)?next(\*\*)?\s*:", ln, re.IGNORECASE) for ln in body):
            warn("no-next", "`## Resume here` has no `Next:` line")
    for sec in ("Rules", "Facts", "Log"):
        if not find_section(secs, sec):
            warn("section-missing", f"missing `## {sec}`")

    total = nonblank(lines)
    if total > cfg.file_max_lines:
        err("file-too-long", f"{total} lines (cap {cfg.file_max_lines}); prune, or learn from it")

    sub = None
    for ln in next((v for _, v in find_section(secs, "Facts")), []):
        if ln.startswith("### "):
            sub = ln[4:].lower()
            continue
        if not ln.lstrip().startswith("- ") or "→ promoted to" in ln:
            continue
        if sub is None and not ("source:" in ln.lower() and "verified" in ln.lower()):
            warn("fact-unsourced", f"fact without `source:` and `verified <date>`: {ln.strip()[:80]}")
        elif sub and sub.startswith("decided") and "why" not in ln.lower():
            warn("decision-no-reason", f"decision without `why:`: {ln.strip()[:80]}")
        elif sub and sub.startswith("rejected") and "why" not in ln.lower():
            warn("rejection-no-reason", f"rejection without `why not:`: {ln.strip()[:80]}")

    entry, count = None, 0
    for ln in next((v for _, v in find_section(secs, "Log")), []) + ["### end"]:
        if ln.startswith("### "):
            if entry and count > cfg.log_entry_max_lines:
                warn("log-entry-long", f"log entry `{entry}` is {count} lines (cap {cfg.log_entry_max_lines})")
            entry, count = ln[4:].strip(), 0
        elif ln.strip():
            count += 1

    for ln in (ln for ln in lines if "→ to promote:" in ln):
        seen = parse_date(m.group(1)) if (m := re.search(r"verified (\d{4}-\d{2}-\d{2})", ln)) else None
        if seen is None or (today - seen).days > cfg.stale_days:
            warn("promotion-pending", f"`→ to promote:` older than {cfg.stale_days} days or undated; "
                 f"promote it or drop it: {ln.strip()[:80]}")

    pointers = [ln.strip() for ln in lines if "→ promoted to" in ln]
    if pointers:
        warn("promoted-pointers", f"{len(pointers)} promoted pointer(s); delete each once its PR merges")

    archive = path.with_name(path.name[:-3] + ".archive.md")
    if archive.exists():
        n = nonblank(archive.read_text(encoding="utf-8", errors="replace").splitlines())
        if n > cfg.archive_max_lines:
            err("archive-too-long", f"{archive.name} is {n} lines (cap {cfg.archive_max_lines})")
    baks = [p.name for p in path.parent.glob(path.name + "*") if TIMESTAMPED_BACKUP_RE.search(p.name)]
    if baks:
        warn("timestamped-backups", f"{len(baks)} timestamped backups; keep only `{path.name}.prev`")
    return out


# ---------------------------------------------------------------------------
# Commands


def skeleton(slug: str, root: Path, args: argparse.Namespace, today: date) -> str:
    here = repo_root(Path(args.repo).resolve())
    return f"""# Handoff — {slug}

Issue: {args.issue or "none — theme"}  ·  Epic/project: {args.epic or "none"}  ·  Spec: {args.spec or "none"}
Repo: {repo_name(root)}  ·  Checkout: {here}  ·  Branch(es): {current_branch(here)}
Owner: {args.owner or git_user(root)}  ·  Started: {today}  ·  Last written: {today}  ·  Status: active

## Resume here — {today}
Goal: <one line: what done looks like>
State:
- <what is true now, with PR / branch / issue ids and their states>
Next: <the single next action, concrete enough to start without asking>

## Rules

## Facts
### Decided — don't re-open
### Rejected — don't re-propose

## Log
### {today} — started
- Did: created this handoff.
"""


def cmd_new(args: argparse.Namespace, root: Path, cfg: Config, today: date) -> int:
    slug = args.slug
    if not SLUG_RE.match(slug):
        raise UsageError(f"slug {slug!r} should be an issue id (PROJ-12-topic) or lowercase-hyphen words")
    d = handoff_dir(root, cfg)
    path = d / f"{PREFIX}{slug}.md"
    if path.exists():
        raise UsageError(f"{path} already exists; update it instead")
    if d == root:
        raise UsageError(f"[handoff].dir {cfg.dir!r} is the repository root; use a folder inside it, such as .local")
    holder = root if root in d.parents else enclosing_repo(d)
    if holder and not is_ignored(holder, path):
        raise UsageError(f"{path} would be tracked by git; add `{os.path.relpath(d, holder)}/` to .gitignore first")
    d.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(skeleton(slug, root, args, today))
    print(path)
    return EXIT_OK


def summary(path: Path, cfg: Config, today: date) -> dict:
    text = path.read_text(encoding="utf-8", errors="replace")
    h = parse_header(text)
    findings = lint_file(path, cfg, today)
    return {
        "slug": slug_of(path),
        "path": str(path),
        "status": h.get("Status", "?"),
        "last_written": h.get("Last written", "?"),
        "issue": h.get("Issue", "?"),
        "lines": nonblank(text.splitlines()),
        "errors": sum(f.severity == "error" for f in findings),
        "warnings": sum(f.severity == "warning" for f in findings),
    }


def cmd_list(args: argparse.Namespace, root: Path, cfg: Config, today: date) -> int:
    rows = [summary(p, cfg, today) for p in handoff_files(handoff_dir(root, cfg))]
    if args.json:
        print(json.dumps(rows, indent=2))
        return EXIT_OK
    if not rows:
        print(f"no handoffs in {handoff_dir(root, cfg)}")
    for r in rows:
        flags = f"  [{r['errors']} error(s), {r['warnings']} warning(s)]" if r["errors"] or r["warnings"] else ""
        print(f"{r['slug']:<40} {r['status']:<10} {r['last_written']:<12} {r['issue']:<18} {r['lines']:>5} lines{flags}")
    return EXIT_OK


def cmd_lint(args: argparse.Namespace, root: Path, cfg: Config, today: date) -> int:
    d = handoff_dir(root, cfg)
    paths = [resolve_one(d, args.query)] if args.query else handoff_files(d)
    report = {slug_of(p): [dataclasses.asdict(f) for f in lint_file(p, cfg, today)] for p in paths}
    if not paths and not args.json:
        print(f"no handoffs in {d}")
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        for slug, findings in report.items():
            print(f"{slug}: {'ok' if not findings else ''}")
            for f in findings:
                print(f"  {f['severity']:<7} {f['code']:<22} {f['message']}")
    flat = [f for fs in report.values() for f in fs]
    failing = [f for f in flat if f["severity"] == "error" or (args.strict and f["severity"] == "warning")]
    return EXIT_LINT if failing else EXIT_OK


def cmd_resolve(args: argparse.Namespace, root: Path, cfg: Config, today: date) -> int:
    hits = resolve(handoff_dir(root, cfg), args.query)
    for p in hits:
        print(p)
    if not hits:
        print(f"handoff: no handoff matches {args.query!r}", file=sys.stderr)
        return EXIT_NOT_FOUND
    return EXIT_OK if len(hits) == 1 else EXIT_AMBIGUOUS


def cmd_backup(args: argparse.Namespace, root: Path, cfg: Config, today: date) -> int:
    path = resolve_one(handoff_dir(root, cfg), args.query)
    prev = path.with_name(path.name + ".prev")
    shutil.copy2(path, prev)
    os.chmod(prev, 0o600)
    print(prev)
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="handoff.py", description="Create, find, list and lint agent handoff files.")
    p.add_argument("--repo", default=".", help="any path inside the git repository (default: cwd)")
    p.add_argument("--config", help="TOML file with a [handoff] table (or its keys at top level); "
                   "default: cadence.toml in the main worktree")
    p.add_argument("--today", help=argparse.SUPPRESS)  # tests pin the date
    p.add_argument("--version", action="version", version=f"handoff {VERSION}")
    sub = p.add_subparsers(dest="cmd", required=True)
    n = sub.add_parser("new", help="create a handoff skeleton")
    n.add_argument("slug")
    n.add_argument("--issue")
    n.add_argument("--epic")
    n.add_argument("--spec")
    n.add_argument("--owner")
    r = sub.add_parser("resolve", help="print the handoff(s) a slug, issue id or fragment refers to")
    r.add_argument("query")
    li = sub.add_parser("list", help="one line per handoff")
    li.add_argument("--json", action="store_true")
    lt = sub.add_parser("lint", help="check format, caps and hygiene")
    lt.add_argument("query", nargs="?")
    lt.add_argument("--json", action="store_true")
    lt.add_argument("--strict", action="store_true", help="fail on warnings too")
    b = sub.add_parser("backup", help="copy a handoff to <file>.prev before a rewrite")
    b.add_argument("query")
    return p


COMMANDS = {"new": cmd_new, "list": cmd_list, "lint": cmd_lint, "resolve": cmd_resolve, "backup": cmd_backup}


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        today = datetime.strptime(args.today, "%Y-%m-%d").date() if args.today else date.today()
        root = main_root(Path(args.repo).resolve())
        cfg = load_config(args.config, root)
        return COMMANDS[args.cmd](args, root, cfg, today)
    except UsageError as exc:
        print(f"handoff: {exc}", file=sys.stderr)
        return EXIT_USAGE
    except LookupError as exc:
        print(f"handoff: {exc}", file=sys.stderr)
        return EXIT_AMBIGUOUS if "matches" in str(exc) and "no handoff" not in str(exc) else EXIT_NOT_FOUND


if __name__ == "__main__":
    sys.exit(main())
