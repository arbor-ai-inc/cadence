#!/usr/bin/env python3
"""skill-miner: find reusable-skill candidates in local coding-agent session logs.

Reads the session history that Claude Code and Codex already keep on this machine,
scoped to one git repository (and its worktrees), and looks for three things:

  * requests the user keeps repeating across sessions,
  * corrections the user keeps making to the agent,
  * commands / skills the user keeps invoking that the repo has no skill for.

Each finding is written as an inactive candidate Markdown file for a human to
review. Nothing is activated, installed, uploaded or shared.

Guarantees (each one is exercised by tests/test_skill_miner.py):

  * Deterministic. No model, no LLM, no randomness.
  * No network. The only subprocess is `git`, with a fixed argument list.
  * Read-only outside the output directory, and it refuses an output directory
    inside any skill directory it knows about.
  * Only human-typed prompts are read. Assistant text, tool calls, tool output and
    thinking are never extracted.

Standard library only. Python 3.11+ (for tomllib).
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import re
import subprocess
import sys

if sys.version_info < (3, 11):  # pragma: no cover - checked before tomllib is needed
    print(f"skill-miner: needs Python 3.11+ (this is {sys.version.split()[0]})", file=sys.stderr)
    sys.exit(2)

import tomllib  # noqa: E402
from collections import Counter, defaultdict  # noqa: E402
from datetime import datetime, timedelta, timezone  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import Iterable, Iterator  # noqa: E402

VERSION = "0.2.0"
GENERATED_MARK = "generated_by: skill-miner"

DEFAULT_SKILLS_DIRS = [".claude/skills", ".codex/skills", ".agents/skills"]

# Handoff files (see cadence's reference/handoff.md) in each checkout in scope.
DEFAULT_HANDOFF_GLOBS = [".local/HANDOFF-*.md"]
# Section headings, lowercased substrings. A bullet is classified by its nearest
# `###` heading, falling back to its `##` heading. Decision words win over fact
# words, and fact words win over rule words, so "Do not re-derive these" (facts)
# isn't read as a rule.
DEFAULT_HANDOFF_DECISION_HEADINGS = [
    "decided", "rejected", "decision", "re-open", "re-propose", "re-litigate", "declined", "settled",
]
DEFAULT_HANDOFF_FACT_HEADINGS = [
    "fact", "re-derive", "verified", "durable", "reference", "where things stand", "state", "resume",
    "restart", "start here", "log", "shipped", "next", "done", "status",
]
DEFAULT_HANDOFF_RULE_HEADINGS = [
    "rule", "gotcha", "trap", "do not", "don't", "how to work", "lesson", "learn", "pitfall",
    "convention", "working with", "mechanics", "cost real time", "avoid",
]
PENDING_RE = re.compile(r"(?:→|->)\s*to promote:", re.IGNORECASE)

DEFAULT_CORRECTION_MARKERS = [
    "no",
    "nope",
    "don't",
    "dont",
    "do not",
    "stop",
    "instead",
    "actually",
    "wrong",
    "that's wrong",
    "that is wrong",
    "not what i",
    "i said",
    "i asked",
    "why did you",
    "you should have",
    "you shouldn't",
    "you should not",
    "revert",
    "undo",
    "never",
    "please don't",
]

# Built-in agent commands that say nothing about a team workflow.
DEFAULT_IGNORE_COMMANDS = [
    "clear", "compact", "model", "config", "help", "login", "logout", "resume",
    "exit", "quit", "cost", "status", "init", "memory", "permissions", "fast",
    "plan", "context", "doctor", "bug", "feedback", "vim", "theme", "terminal-setup",
    "add-dir", "agents", "hooks", "mcp", "ide", "upgrade", "release-notes", "rewind",
    "export", "usage", "statusline", "output-style", "privacy-settings", "new",
    "approvals", "diff", "mention", "effort",
]

STOPWORDS = frozenset(
    """a an the and or but if then so to of in on at by for with from into onto as is
    are was were be been being do does did done have has had it its it's this that these
    those there here i me my we us our you your he she they them their what which who
    whom how why when where can could should would will shall may might must just also
    please pls now let lets let's ok okay yes yeah sure thanks thank hi hey not no all any
    some each every more most other same such only own than too very again ever still
    about above after before below between both during out over under up down off same
    make use using get got go going want need like one two way thing things really
    going gonna im i'm youre you're dont don't cant can't wont won't isnt isn't""".split()
)

WRAPPER_BLOCK_RE = re.compile(
    r"<(system-reminder|pasted_content|local-command-caveat|local-command-stdout|"
    r"local-command-stderr|bash-stdout|bash-stderr|task-notification|user-prompt-submit-hook|"
    r"environment_context|user_instructions|turn_aborted)\b[^>]*>.*?</\1\b[^>]*>",
    re.DOTALL,
)
SKIP_IF_STARTS_WITH = (
    "<local-command-", "<bash-input", "<bash-stdout", "<bash-stderr", "<task-notification",
    "<environment_context", "<user_instructions", "[Request interrupted",
)
CLAUDE_COMMAND_RE = re.compile(r"<command-name>\s*/?([A-Za-z0-9:_.-]+)\s*</command-name>")
LEADING_INVOCATION_RE = re.compile(r"^\s*[/$]([A-Za-z][A-Za-z0-9:_.-]*)(?=\s|$)")
FENCE_RE = re.compile(r"```.*?(```|$)", re.DOTALL)
URL_RE = re.compile(r"\b[a-z][a-z0-9+.-]*://\S+", re.IGNORECASE)
TOKEN_RE = re.compile(r"[a-z][a-z0-9_'-]*[a-z0-9]|[a-z]")

BUILTIN_REDACTIONS: list[tuple[str, str]] = [
    (r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?(-----END [A-Z ]*PRIVATE KEY-----|$)", "[REDACTED:private-key]"),
    (r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}", "[REDACTED:jwt]"),
    (r"\b(AKIA|ASIA)[0-9A-Z]{16}\b", "[REDACTED:aws-key]"),
    (r"\bgh[pousr]_[A-Za-z0-9]{20,}\b", "[REDACTED:github-token]"),
    (r"\bgithub_pat_[A-Za-z0-9_]{20,}\b", "[REDACTED:github-token]"),
    (r"\bxox[abposr]-[A-Za-z0-9-]{10,}\b", "[REDACTED:slack-token]"),
    (r"\bsk-[A-Za-z0-9_-]{16,}\b", "[REDACTED:api-key]"),
    (r"\bAIza[0-9A-Za-z_-]{30,}\b", "[REDACTED:api-key]"),
    (
        r"(?i)\b(password|passwd|secret|token|api[_-]?key|access[_-]?key|auth)\b(\s*[:=]\s*)['\"]?[^\s'\"]{6,}",
        r"\1\2[REDACTED]",
    ),
    (r"(?i)\b(bearer\s+)[A-Za-z0-9._~+/-]{12,}=*", r"\1[REDACTED]"),
    (r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "[REDACTED:email]"),
    (r"(\b[a-z][a-z0-9+.-]*://[^\s?#]+)[?#]\S*", r"\1?[REDACTED]"),
    (r"\b[A-Fa-f0-9]{32,}\b", "[REDACTED:hex]"),
    (r"\b[A-Za-z0-9+/]{40,}={0,2}", "[REDACTED:blob]"),
    (r"/(Users|home)/[^/\s]+", r"~"),
]


# ---------------------------------------------------------------------------
# Config


@dataclasses.dataclass
class Config:
    repo: Path
    out: Path
    since: timedelta | None = timedelta(days=30)
    min_count: int = 3
    min_sessions: int = 2
    similarity: float = 0.5
    skills_dirs: list[Path] = dataclasses.field(default_factory=list)
    correction_markers: list[str] = dataclasses.field(default_factory=lambda: list(DEFAULT_CORRECTION_MARKERS))
    ignore_commands: set[str] = dataclasses.field(default_factory=lambda: set(DEFAULT_IGNORE_COMMANDS))
    redactions: list[tuple[re.Pattern[str], str]] = dataclasses.field(default_factory=list)
    claude_home: Path = dataclasses.field(default_factory=lambda: Path.home() / ".claude")
    codex_home: Path = dataclasses.field(default_factory=lambda: Path.home() / ".codex")
    quote_chars: int = 160
    max_evidence: int = 5
    same_remote: bool = False
    handoffs: bool = True
    handoff_globs: list[str] = dataclasses.field(default_factory=lambda: list(DEFAULT_HANDOFF_GLOBS))
    handoff_decision_headings: list[str] = dataclasses.field(default_factory=lambda: list(DEFAULT_HANDOFF_DECISION_HEADINGS))
    handoff_fact_headings: list[str] = dataclasses.field(default_factory=lambda: list(DEFAULT_HANDOFF_FACT_HEADINGS))
    handoff_rule_headings: list[str] = dataclasses.field(default_factory=lambda: list(DEFAULT_HANDOFF_RULE_HEADINGS))
    min_handoffs: int = 2
    pending_days: int = 14


class ConfigError(Exception):
    pass


def parse_since(value: str | None) -> timedelta | None:
    if value is None or value == "all":
        return None
    m = re.fullmatch(r"(\d+)\s*([dhw])", value.strip())
    if not m:
        raise ConfigError(f"--since must look like 30d, 12h, 2w or 'all' (got {value!r})")
    n, unit = int(m.group(1)), m.group(2)
    return {"d": timedelta(days=n), "h": timedelta(hours=n), "w": timedelta(weeks=n)}[unit]


def compile_redactions(extra: Iterable[str]) -> list[tuple[re.Pattern[str], str]]:
    compiled = [(re.compile(p, re.DOTALL), r) for p, r in BUILTIN_REDACTIONS]
    for p in extra:
        try:
            compiled.append((re.compile(p), "[REDACTED]"))
        except re.error as exc:
            raise ConfigError(f"bad extra_redact_patterns entry {p!r}: {exc}") from exc
    return compiled


def load_config(args: argparse.Namespace) -> Config:
    repo = git_toplevel(Path(args.repo).resolve())
    file_cfg: dict = {}
    if args.config:
        path = Path(args.config)
        try:
            file_cfg = tomllib.loads(path.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError) as exc:
            raise ConfigError(f"cannot read config {path}: {exc}") from exc
        known = {
            "out", "since", "min_count", "min_sessions", "similarity", "skills_dirs",
            "correction_markers", "ignore_commands", "extra_redact_patterns",
            "claude_home", "codex_home", "quote_chars", "max_evidence", "same_remote",
            "handoffs", "handoff_globs", "handoff_rule_headings", "handoff_decision_headings",
            "handoff_fact_headings", "min_handoffs", "pending_days",
        }
        unknown = sorted(set(file_cfg) - known)
        if unknown:
            raise ConfigError(f"unknown config keys in {path}: {', '.join(unknown)}")

    def pick(name: str, default):
        cli = getattr(args, name, None)
        if cli is not None:
            return cli
        return file_cfg.get(name, default)

    def repo_path(p: str | os.PathLike) -> Path:
        p = Path(os.path.expanduser(str(p)))
        return (p if p.is_absolute() else repo / p).resolve()

    skills = list(DEFAULT_SKILLS_DIRS) + list(file_cfg.get("skills_dirs", [])) + list(args.skills_dir or [])
    cfg = Config(
        repo=repo,
        out=repo_path(pick("out", ".skill-candidates")),
        since=parse_since(pick("since", "30d")),
        min_count=int(pick("min_count", 3)),
        min_sessions=int(pick("min_sessions", 2)),
        similarity=float(pick("similarity", 0.5)),
        skills_dirs=[repo_path(s) for s in dict.fromkeys(skills)],
        correction_markers=list(DEFAULT_CORRECTION_MARKERS) + list(file_cfg.get("correction_markers", [])),
        ignore_commands=set(DEFAULT_IGNORE_COMMANDS) | set(file_cfg.get("ignore_commands", [])),
        redactions=compile_redactions(file_cfg.get("extra_redact_patterns", [])),
        claude_home=Path(os.path.expanduser(str(pick("claude_home", Path.home() / ".claude")))),
        codex_home=Path(os.path.expanduser(str(pick("codex_home", Path.home() / ".codex")))),
        quote_chars=int(file_cfg.get("quote_chars", 160)),
        max_evidence=int(file_cfg.get("max_evidence", 5)),
        same_remote=bool(pick("same_remote", False)),
        handoffs=bool(pick("handoffs", True)),
        handoff_globs=list(file_cfg.get("handoff_globs", DEFAULT_HANDOFF_GLOBS)),
        handoff_decision_headings=list(DEFAULT_HANDOFF_DECISION_HEADINGS)
        + [h.lower() for h in file_cfg.get("handoff_decision_headings", [])],
        handoff_fact_headings=list(DEFAULT_HANDOFF_FACT_HEADINGS)
        + [h.lower() for h in file_cfg.get("handoff_fact_headings", [])],
        handoff_rule_headings=list(DEFAULT_HANDOFF_RULE_HEADINGS)
        + [h.lower() for h in file_cfg.get("handoff_rule_headings", [])],
        min_handoffs=int(pick("min_handoffs", 2)),
        pending_days=int(file_cfg.get("pending_days", 14)),
    )
    if cfg.min_count < 2 or cfg.min_sessions < 1:
        raise ConfigError("min_count must be >= 2 and min_sessions >= 1")
    if cfg.min_handoffs < 2:
        raise ConfigError("min_handoffs must be >= 2: one handoff is not a pattern")
    if not 0 < cfg.similarity <= 1:
        raise ConfigError("similarity must be in (0, 1]")
    for skills_dir in cfg.skills_dirs:
        if cfg.out == skills_dir or skills_dir in cfg.out.parents:
            raise ConfigError(
                f"refusing to write candidates into a skill directory ({skills_dir}); "
                "candidates must stay inactive until a human promotes them"
            )
    return cfg


# ---------------------------------------------------------------------------
# git (the only subprocess)


def _git(repo: Path, *argv: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *argv],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
    )


def git_toplevel(path: Path) -> Path:
    proc = _git(path, "rev-parse", "--show-toplevel")
    if proc.returncode != 0:
        raise ConfigError(f"{path} is not inside a git repository")
    return Path(proc.stdout.strip()).resolve()


def repo_roots(repo: Path) -> list[Path]:
    """The repo plus every worktree git knows about."""
    roots = [repo]
    proc = _git(repo, "worktree", "list", "--porcelain")
    if proc.returncode == 0:
        for line in proc.stdout.splitlines():
            if line.startswith("worktree "):
                p = Path(line[len("worktree "):]).resolve()
                if p not in roots:
                    roots.append(p)
    return roots


def normalize_remote(url: str | None) -> str | None:
    """`owner/name` of a git remote URL, lowercased.

    Scheme, user and host are dropped on purpose, so an SSH host alias
    (git@github.com-work:acme/widget.git) matches https://github.com/acme/widget.
    The cost: two hosts serving the same owner/name would be treated as one repo.
    """
    if not url:
        return None
    u = re.sub(r"\.git$", "", url.strip().rstrip("/"))
    m = re.match(r"^[a-z][a-z0-9+.-]*://(?:[^@/]+@)?[^/]+/(.+)$", u, re.IGNORECASE) or re.match(
        r"^(?:[^@/]+@)?[^:/]+:(?!/)(.+)$", u
    )
    parts = [p for p in (m.group(1) if m else u).split("/") if p]
    return "/".join(parts[-2:]).lower() if len(parts) >= 2 else None


def origin_remote(path: Path) -> str | None:
    # `config --get`, not `remote get-url`: no insteadOf rewriting, just the stored value.
    proc = _git(path, "-c", "core.fsmonitor=false", "config", "--get", "remote.origin.url")
    return normalize_remote(proc.stdout.strip()) if proc.returncode == 0 else None


class Scope:
    """Which session working directories count as "this repository".

    Always: the repo and its git worktrees. With same_remote: also any other checkout
    whose `origin` has the same owner/name, such as a second clone of the same repo.
    """

    def __init__(self, repo: Path, same_remote: bool) -> None:
        self.roots = repo_roots(repo)
        self.remote = origin_remote(repo) if same_remote else None
        self._checked: dict[str, bool] = {}

    def contains(self, cwd: str | None, repo_url: str | None = None) -> bool:
        if within(cwd, self.roots):
            return True
        if self.remote is None:
            return False
        # Codex records the remote itself, which still works after a clone is deleted.
        if repo_url and normalize_remote(repo_url) == self.remote:
            return True
        if not cwd:
            return False
        if cwd not in self._checked:
            self._checked[cwd] = self._other_checkout(cwd)
        return self._checked[cwd]

    def _other_checkout(self, cwd: str) -> bool:
        try:
            if not Path(cwd).is_dir():
                return False
        except (OSError, ValueError):
            return False
        proc = _git(Path(cwd), "-c", "core.fsmonitor=false", "rev-parse", "--show-toplevel")
        if proc.returncode != 0:
            return False
        top = Path(proc.stdout.strip()).resolve()
        if origin_remote(top) != self.remote:
            return False
        self.roots.append(top)
        return True


def is_git_ignored(repo: Path, path: Path) -> bool:
    # The trailing slash lets directory-only patterns ("out/") match a path that
    # does not exist yet.
    rel = os.path.relpath(path, repo)
    return any(_git(repo, "check-ignore", "-q", "--no-index", p).returncode == 0 for p in (rel, rel + "/"))


# ---------------------------------------------------------------------------
# Session extraction


@dataclasses.dataclass
class Turn:
    agent: str  # "claude-code" | "codex"
    session: str
    ts: datetime | None
    text: str
    after_assistant: bool  # an assistant turn preceded this one in the same session
    where: str = ""  # handoffs: the section heading the item sat under


@dataclasses.dataclass
class Invocation:
    agent: str
    session: str
    ts: datetime | None
    name: str


def parse_ts(value) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def within(path: str | None, roots: list[Path]) -> bool:
    if not path:
        return False
    try:
        p = Path(path).resolve()
    except (OSError, ValueError):
        return False
    return any(p == r or r in p.parents for r in roots)


def clean_prompt(text: str) -> str | None:
    """Strip injected wrapper blocks; None if nothing human-typed remains."""
    stripped = text.lstrip()
    if stripped.startswith(SKIP_IF_STARTS_WITH):
        return None
    text = WRAPPER_BLOCK_RE.sub(" ", text)
    text = re.sub(r"</?(command-message|command-args|command-name)>", " ", text)
    text = text.strip()
    return text or None


def iter_jsonl(path: Path) -> Iterator[dict]:
    try:
        with path.open(encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(obj, dict):
                    yield obj
    except OSError:
        return


def encode_claude_project(path: Path) -> str:
    return re.sub(r"[^A-Za-z0-9]", "-", str(path))


def first_cwd(project_dir: Path) -> str | None:
    """The working directory a Claude Code project folder was recorded for.

    Reads only until the first record carrying `cwd`; no prompt text is kept.
    """
    for f in sorted(project_dir.glob("*.jsonl")):
        for i, rec in enumerate(iter_jsonl(f)):
            if isinstance(rec.get("cwd"), str):
                return rec["cwd"]
            if i >= 50:
                break
    return None


def claude_session_files(cfg: Config, scope: Scope) -> list[Path]:
    projects = cfg.claude_home / "projects"
    if not projects.is_dir():
        return []
    prefixes = [encode_claude_project(r) for r in scope.roots]
    files: list[Path] = []
    for d in sorted(projects.iterdir()):
        if not d.is_dir():
            continue
        # Prefix match catches sessions started in a repo subdirectory; the per-record
        # cwd check in extract_claude drops sibling directories that merely share it.
        matched = any(d.name == p or d.name.startswith(p + "-") for p in prefixes)
        if not matched and scope.remote is not None:
            matched = scope.contains(first_cwd(d))
        if matched:
            files.extend(sorted(d.glob("*.jsonl")))
    return files


def extract_claude(path: Path, scope: Scope) -> tuple[list[Turn], list[Invocation]]:
    turns: list[Turn] = []
    invocations: list[Invocation] = []
    seen_assistant = False
    for rec in iter_jsonl(path):
        kind = rec.get("type")
        if rec.get("isSidechain") or rec.get("isMeta"):
            continue
        if not scope.contains(rec.get("cwd")):
            continue
        if kind == "assistant":
            seen_assistant = True
            continue
        if kind != "user" or "toolUseResult" in rec:
            continue
        source = rec.get("promptSource")
        if source is not None and source not in ("typed", "queued"):
            continue
        content = (rec.get("message") or {}).get("content")
        if isinstance(content, list):
            if any(isinstance(b, dict) and b.get("type") != "text" for b in content):
                continue
            content = "\n".join(b.get("text", "") for b in content if isinstance(b, dict))
        if not isinstance(content, str):
            continue
        session = str(rec.get("sessionId") or path.stem)
        ts = parse_ts(rec.get("timestamp"))
        m = CLAUDE_COMMAND_RE.search(content)
        if m:
            invocations.append(Invocation("claude-code", session, ts, m.group(1).lower()))
            continue
        text = clean_prompt(content)
        if text is None:
            continue
        m = LEADING_INVOCATION_RE.match(text)
        if m:
            invocations.append(Invocation("claude-code", session, ts, m.group(1).lower()))
            continue
        turns.append(Turn("claude-code", session, ts, text, seen_assistant))
    return turns, invocations


def codex_session_files(cfg: Config) -> list[Path]:
    sessions = cfg.codex_home / "sessions"
    if not sessions.is_dir():
        return []
    return sorted(sessions.rglob("*.jsonl"))


def extract_codex(path: Path, scope: Scope) -> tuple[list[Turn], list[Invocation]]:
    turns: list[Turn] = []
    invocations: list[Invocation] = []
    session: str | None = None
    in_scope = False
    repo_url: str | None = None
    seen_assistant = False
    for rec in iter_jsonl(path):
        payload = rec.get("payload") if isinstance(rec.get("payload"), dict) else {}
        kind = rec.get("type")
        if kind == "session_meta":
            if session is None:  # the first meta describes this rollout; later ones are forks
                session = str(payload.get("id") or path.stem)
                git_meta = payload.get("git") if isinstance(payload.get("git"), dict) else {}
                repo_url = git_meta.get("repository_url")
                in_scope = scope.contains(payload.get("cwd"), repo_url)
            continue
        if kind == "turn_context" and payload.get("cwd"):
            in_scope = scope.contains(payload.get("cwd"), repo_url)
            continue
        if not in_scope or session is None:
            continue
        ptype = payload.get("type")
        if (kind == "event_msg" and ptype == "agent_message") or (
            kind == "response_item" and ptype == "message" and payload.get("role") == "assistant"
        ):
            seen_assistant = True
            continue
        if kind != "event_msg" or ptype != "user_message":
            continue
        message = payload.get("message")
        if not isinstance(message, str):
            continue
        ts = parse_ts(rec.get("timestamp"))
        text = clean_prompt(message)
        if text is None:
            continue
        m = LEADING_INVOCATION_RE.match(text)
        if m:
            invocations.append(Invocation("codex", session, ts, m.group(1).lower()))
            continue
        turns.append(Turn("codex", session, ts, text, seen_assistant))
    return turns, invocations


def collect(cfg: Config) -> tuple[list[Turn], list[Invocation], dict]:
    scope = Scope(cfg.repo, cfg.same_remote)
    cutoff = datetime.now(timezone.utc) - cfg.since if cfg.since else None
    turns: list[Turn] = []
    invocations: list[Invocation] = []
    stats = {"claude_files": 0, "codex_files": 0}

    def recent(p: Path) -> bool:
        if cutoff is None:
            return True
        try:
            return datetime.fromtimestamp(p.stat().st_mtime, timezone.utc) >= cutoff
        except OSError:
            return False

    for f in claude_session_files(cfg, scope):
        if recent(f):
            t, i = extract_claude(f, scope)
            stats["claude_files"] += bool(t or i)
            turns += t
            invocations += i
    for f in codex_session_files(cfg):
        if recent(f):
            t, i = extract_codex(f, scope)
            stats["codex_files"] += bool(t or i)
            turns += t
            invocations += i
    if cutoff is not None:
        turns = [t for t in turns if t.ts is None or t.ts >= cutoff]
        invocations = [i for i in invocations if i.ts is None or i.ts >= cutoff]
    stats["checkouts"] = [str(r) for r in scope.roots]
    stats["same_remote"] = scope.remote
    return turns, invocations, stats


# ---------------------------------------------------------------------------
# Handoffs


MD_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]*\)")
BULLET_RE = re.compile(r"^( {0,3})(?:[-*+]|\d+[.)])\s+(.*)$")
DATE_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")


def handoff_slug(path: Path) -> str:
    """The track a handoff file belongs to. Its archive (`.archive.md`, or a legacy
    `-ARCHIVE.md`) is the same track, so a rule copied into it isn't a second one."""
    name = path.name
    name = name[len("HANDOFF-"):] if name.startswith("HANDOFF-") else name
    name = re.sub(r"\.md$", "", name)
    name = re.sub(r"[.-]archive$", "", name, flags=re.IGNORECASE)
    return name or path.stem


def handoff_files(cfg: Config, roots: list[str]) -> list[Path]:
    seen: dict[Path, None] = {}
    for root in roots:
        for pattern in cfg.handoff_globs:
            for p in sorted(Path(root).glob(pattern)):
                if p.is_file() and not p.is_symlink():
                    seen.setdefault(p.resolve(), None)
    return list(seen)


def _heading_class(heading: str, cfg: Config) -> str | None:
    h = heading.lower()
    if any(w in h for w in cfg.handoff_decision_headings):
        return "decision"
    if any(w in h for w in cfg.handoff_fact_headings):
        return "fact"
    if any(w in h for w in cfg.handoff_rule_headings):
        return "rule"
    return None


def _plain(text: str) -> str:
    text = MD_LINK_RE.sub(r"\1", text)
    return re.sub(r"[*_`]+", "", text).strip()


def extract_handoff(path: Path, cfg: Config) -> dict[str, list[Turn]]:
    """Rule, decision and pending-promotion items from one handoff file.

    Only top-level bullets are items; indented lines continue the item above.
    Plain facts are deliberately not mined: a recurring fact belongs in the doc
    that owns it, not in a skill or a rule.
    """
    out: dict[str, list[Turn]] = {"rule": [], "decision": [], "pending": []}
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return out
    slug = handoff_slug(path)
    m = re.search(r"Last written:\s*(\d{4}-\d{2}-\d{2})", text)
    try:
        fallback = parse_ts(m.group(1) + "T00:00:00Z") if m else datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
    except OSError:
        fallback = None
    h2 = h3 = ""
    item: list[str] | None = None
    where = ""

    def flush() -> None:
        nonlocal item
        if item:
            body = _plain(" ".join(item))
            d = DATE_RE.search(body)
            ts = parse_ts(d.group(1) + "T00:00:00Z") if d else fallback
            if PENDING_RE.search(body):
                out["pending"].append(Turn("handoff", slug, ts, body, False, where))
            else:
                kind = _heading_class(h3, cfg) if h3 else None
                kind = kind or _heading_class(h2, cfg)
                if kind in ("rule", "decision"):
                    out[kind].append(Turn("handoff", slug, ts, body, False, where))
        item = None

    for line in text.splitlines():
        if line.startswith("## "):
            flush()
            h2, h3 = _plain(line[3:]), ""
            continue
        if line.startswith("### "):
            flush()
            h3 = _plain(line[4:])
            continue
        if line.startswith("#"):
            flush()
            continue
        b = BULLET_RE.match(line)
        if b:
            flush()
            item, where = [b.group(2)], (h3 or h2)
        elif item is not None and line.strip() and line[:1] in (" ", "\t"):
            item.append(line.strip())
        else:
            flush()
    flush()
    return out


def collect_handoffs(cfg: Config, roots: list[str]) -> tuple[dict[str, list[Turn]], dict]:
    items: dict[str, list[Turn]] = {"rule": [], "decision": [], "pending": []}
    files = handoff_files(cfg, roots) if cfg.handoffs else []
    for f in files:
        for k, v in extract_handoff(f, cfg).items():
            items[k] += v
    stats = {
        "handoff_files": len(files),
        "handoff_tracks": len({handoff_slug(f) for f in files}),
        "handoff_items": sum(len(v) for v in items.values()),
    }
    return items, stats


# ---------------------------------------------------------------------------
# Analysis


def tokens(text: str) -> frozenset[str]:
    return frozenset(ordered_tokens(text))


def ordered_tokens(text: str) -> list[str]:
    text = FENCE_RE.sub(" ", text)
    text = URL_RE.sub(" ", text)
    words = []
    for raw in text.lower().split():
        if "/" in raw or "\\" in raw or any(c.isdigit() for c in raw[:1]):
            continue
        for tok in TOKEN_RE.findall(raw):
            tok = tok.strip("'-_")
            if len(tok) >= 3 and tok not in STOPWORDS and not tok.isdigit():
                words.append(tok)
    return list(dict.fromkeys(words))[:60]


def jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def is_correction(text: str, markers: list[str]) -> bool:
    """A single-word marker must open the prompt; a phrase may sit in its first words."""
    head = " ".join(re.findall(r"[a-z']+", text.lower())[:6])
    for marker in markers:
        marker = " ".join(marker.lower().split())
        if not marker:
            continue
        pattern = rf"^{re.escape(marker)}\b" if " " not in marker else rf"(^|\s){re.escape(marker)}($|\s)"
        if re.search(pattern, head):
            return True
    return False


@dataclasses.dataclass
class Cluster:
    kind: str  # "request" | "correction" | "workflow"
    members: list[Turn | Invocation]
    keys: list[frozenset[str]]
    label: str = ""
    also: str = ""  # cross-source note, e.g. the same point also made as a session correction

    @property
    def sessions(self) -> set[str]:
        return {m.session for m in self.members}

    def keywords(self, n: int = 6) -> list[str]:
        """Most shared terms first; ties keep the order they appear in the first prompt."""
        df = Counter(tok for k in self.keys for tok in k)
        first = self.members[0]
        order = {t: i for i, t in enumerate(ordered_tokens(first.text) if isinstance(first, Turn) else [])}
        return [t for t, _ in sorted(df.items(), key=lambda kv: (-kv[1], order.get(kv[0], len(order)), kv[0]))[:n]]


def cluster_turns(items: list[Turn], kind: str, threshold: float, min_tokens: int) -> list[Cluster]:
    clusters: list[Cluster] = []
    for item in sorted(items, key=lambda t: (t.ts or datetime.min.replace(tzinfo=timezone.utc), t.session)):
        key = tokens(item.text)
        if len(key) < min_tokens:
            continue
        best, best_sim = None, 0.0
        for c in clusters:
            sim = max(jaccard(key, k) for k in c.keys[:20])
            if sim > best_sim:
                best, best_sim = c, sim
        if best is not None and best_sim >= threshold:
            best.members.append(item)
            best.keys.append(key)
        else:
            clusters.append(Cluster(kind, [item], [key]))
    return clusters


def workflow_clusters(invocations: list[Invocation], ignore: set[str]) -> list[Cluster]:
    by_name: dict[str, list[Invocation]] = defaultdict(list)
    for inv in invocations:
        base = inv.name.split(":")[-1]
        if inv.name in ignore or base in ignore:
            continue
        by_name[inv.name].append(inv)
    out = []
    for name, members in sorted(by_name.items()):
        key = frozenset(t for t in re.split(r"[^a-z0-9]+", name) if t)
        out.append(Cluster("workflow", members, [key] * len(members), label=name))
    return out


@dataclasses.dataclass
class Skill:
    name: str
    key: frozenset[str]


def read_frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    fields: dict[str, str] = {}
    current = None
    for line in text[3:end].splitlines():
        if line[:1] in (" ", "\t") and current:
            fields[current] += " " + line.strip()
            continue
        if ":" in line:
            k, v = line.split(":", 1)
            current = k.strip()
            fields[current] = v.strip().strip("\"'>|-").strip()
    return fields


def load_skills(dirs: list[Path]) -> list[Skill]:
    skills: list[Skill] = []
    for d in dirs:
        if not d.is_dir():
            continue
        paths = sorted(d.glob("*/SKILL.md")) + sorted(p for p in d.glob("*.md") if p.name.lower() != "readme.md")
        for p in paths:
            try:
                fm = read_frontmatter(p.read_text(encoding="utf-8", errors="replace"))
            except OSError:
                continue
            name = fm.get("name") or (p.parent.name if p.name == "SKILL.md" else p.stem)
            name_toks = frozenset(t for t in re.split(r"[^a-z0-9]+", name.lower()) if len(t) >= 3)
            skills.append(Skill(name.lower(), name_toks | tokens(fm.get("description", ""))))
    return skills


def covered_by(cluster: Cluster, skills: list[Skill]) -> str | None:
    if cluster.kind == "workflow":
        base = cluster.label.split(":")[-1]
        for s in skills:
            if s.name in (cluster.label, base):
                return s.name
        return None
    kw = frozenset(cluster.keywords(8))
    for s in skills:
        overlap = len(kw & s.key)
        if overlap >= 2 and overlap / min(len(kw), len(s.key) or 1) >= 0.6:
            return s.name
    return None


# ---------------------------------------------------------------------------
# Output


def redact(text: str, cfg: Config) -> str:
    for pattern, repl in cfg.redactions:
        text = pattern.sub(repl, text)
    text = " ".join(text.split())
    if len(text) > cfg.quote_chars:
        text = text[: cfg.quote_chars - 1].rstrip() + "…"
    return text


def slugify(words: list[str], fallback: str) -> str:
    slug = "-".join(re.sub(r"[^a-z0-9]+", "-", w).strip("-") for w in words[:3]).strip("-")
    return slug or fallback


def fmt_ts(ts: datetime | None) -> str:
    return ts.astimezone(timezone.utc).strftime("%Y-%m-%d") if ts else "unknown"


def render(cluster: Cluster, name: str, cfg: Config) -> str:
    members = sorted(cluster.members, key=lambda m: m.ts or datetime.min.replace(tzinfo=timezone.utc))
    agents = sorted({m.agent for m in members})
    stamps = [m.ts for m in members if m.ts]
    suggested = {
        "correction": "rule", "handoff-rule": "rule", "handoff-decision": "decision",
        "pending-promotion": "as-written",
    }.get(cluster.kind, "skill")
    kw = cluster.keywords()
    if cluster.kind == "handoff-rule":
        summary = f"A similar rule or trap is recorded in {len(cluster.sessions)} different handoffs. Recurring terms: {', '.join(kw)}."
    elif cluster.kind == "handoff-decision":
        summary = f"A similar decision or rejection is recorded in {len(cluster.sessions)} different handoffs. Recurring terms: {', '.join(kw)}."
    elif cluster.kind == "pending-promotion":
        summary = f"A handoff has held this `→ to promote` line for more than {cfg.pending_days} days. It already names its destination; promote it or drop it."
    elif cluster.kind == "workflow":
        summary = f"`{cluster.label}` was invoked {len(members)} times across {len(cluster.sessions)} sessions, but no skill in the configured skill directories has that name."
    elif cluster.kind == "correction":
        summary = f"A similar correction was given {len(members)} times across {len(cluster.sessions)} sessions. Recurring terms: {', '.join(kw)}."
    else:
        summary = f"A similar request was made {len(members)} times across {len(cluster.sessions)} sessions. Recurring terms: {', '.join(kw)}."

    evidence = []
    seen_sessions: set[str] = set()
    for m in members:
        if len(evidence) >= cfg.max_evidence:
            break
        if m.session in seen_sessions and len(cluster.sessions) >= cfg.max_evidence:
            continue
        seen_sessions.add(m.session)
        quote = f"`{m.name}`" if isinstance(m, Invocation) else f"“{redact(m.text, cfg)}”"
        if m.agent == "handoff":
            section = f" § {redact(m.where, cfg)}" if getattr(m, "where", "") else ""
            evidence.append(f"- {fmt_ts(m.ts)} · handoff `{m.session}`{section} · {quote}")
        else:
            evidence.append(f"- {fmt_ts(m.ts)} · {m.agent} · session `{m.session[:8]}` · {quote}")
    if cluster.also:
        evidence.append(f"- also: {cluster.also}")

    lines = [
        "---",
        "candidate: true",
        "status: unreviewed",
        f"kind: {cluster.kind}",
        f"suggested: {suggested}",
        f"name: {name}",
        f"occurrences: {len(members)}",
        f"{'handoffs' if cluster.kind.startswith(('handoff', 'pending')) else 'sessions'}: {len(cluster.sessions)}",
        f"agents: [{', '.join(agents)}]",
        f"first_seen: {fmt_ts(min(stamps) if stamps else None)}",
        f"last_seen: {fmt_ts(max(stamps) if stamps else None)}",
        f"{GENERATED_MARK} {VERSION}",
        "---",
        "",
        f"# Candidate: {name}",
        "",
        summary,
        "",
        "## Evidence (redacted, truncated)",
        "",
        *evidence,
        "",
        "## Review",
        "",
        "This file is inactive. It is not a skill and no agent loads it.",
        "",
        "- [ ] Is this a recurring pattern, not a one-off?",
        "- [ ] Is it specific enough to act on, and not already covered elsewhere?",
        "- [ ] Would a skill (reusable workflow) or a rule (standing instruction) serve it better?",
        "- [ ] Does the evidence contain anything that must not be shared? Redaction is best-effort.",
        "",
        "To adopt it, write the skill or rule by hand in your normal review process and delete this file.",
        "",
    ]
    return "\n".join(lines)


def write_private(path: Path, text: str) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(text)
    os.chmod(path, 0o600)


def prepare_out_dir(out: Path) -> Path:
    day = out / datetime.now(timezone.utc).strftime("%Y-%m-%d")
    day.mkdir(parents=True, exist_ok=True, mode=0o700)
    for p in [out, day]:
        os.chmod(p, 0o700)
    for old in day.glob("*.md"):
        try:
            head = old.read_text(encoding="utf-8", errors="replace")[:2000]
        except OSError:
            continue
        if GENERATED_MARK in head:
            old.unlink()
    return day


# ---------------------------------------------------------------------------
# Main


def analyse(cfg: Config) -> dict:
    turns, invocations, stats = collect(cfg)
    handoff_items, handoff_stats = collect_handoffs(cfg, stats["checkouts"])
    corrections = [t for t in turns if t.after_assistant and is_correction(t.text, cfg.correction_markers)]
    correction_ids = {id(t) for t in corrections}
    requests = [t for t in turns if id(t) not in correction_ids]

    correction_clusters = cluster_turns(corrections, "correction", cfg.similarity, min_tokens=2)
    handoff_clusters = (
        cluster_turns(handoff_items["rule"], "handoff-rule", cfg.similarity, min_tokens=3)
        + cluster_turns(handoff_items["decision"], "handoff-decision", cfg.similarity, min_tokens=3)
    )
    now = datetime.now(timezone.utc)
    pending = [
        Cluster("pending-promotion", [t], [tokens(t.text)])
        for t in handoff_items["pending"]
        if t.ts is None or (now - t.ts).days > cfg.pending_days
    ]
    # Cross-source: a handoff rule that matches a correction the user keeps giving in
    # sessions is stronger evidence than either alone.
    for hc in handoff_clusters:
        if hc.kind != "handoff-rule":
            continue
        best, best_n = 0.0, None
        for cc in correction_clusters:
            sim = max((jaccard(a, b) for a in hc.keys[:10] for b in cc.keys[:10]), default=0.0)
            if sim > best:
                best, best_n = sim, cc
        if best_n is not None and best >= cfg.similarity:
            hc.also = f"the same point was given as a correction {len(best_n.members)} time(s) across {len(best_n.sessions)} session(s)"

    clusters = (
        # Corrections are short ("no, use X not Y"), so they get a lower token floor.
        cluster_turns(requests, "request", cfg.similarity, min_tokens=3)
        + correction_clusters
        + workflow_clusters(invocations, cfg.ignore_commands)
    )
    skills = load_skills(cfg.skills_dirs)
    candidates: list[tuple[Cluster, str]] = []
    covered: list[dict] = []
    for c in clusters + handoff_clusters + pending:
        if c.kind.startswith("handoff"):
            if len(c.sessions) < cfg.min_handoffs:
                continue
        elif c.kind != "pending-promotion" and (len(c.members) < cfg.min_count or len(c.sessions) < cfg.min_sessions):
            continue
        hit = covered_by(c, skills)
        if hit:
            covered.append({"kind": c.kind, "covered_by": hit, "occurrences": len(c.members)})
            continue
        candidates.append((c, c.label or slugify(c.keywords(), c.kind)))
    candidates.sort(key=lambda cn: (not cn[0].also, -len(cn[0].sessions), -len(cn[0].members), cn[1]))

    names: Counter[str] = Counter()
    named = []
    for c, base in candidates:
        base = re.sub(r"[^a-z0-9-]+", "-", base.lower()).strip("-") or c.kind
        names[base] += 1
        named.append((c, base if names[base] == 1 else f"{base}-{names[base]}"))

    return {
        "stats": {
            **stats,
            **handoff_stats,
            "prompts": len(turns),
            "invocations": len(invocations),
            "skills_known": len(skills),
        },
        "candidates": named,
        "covered": covered,
    }


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="skill_miner.py",
        description="Find reusable-skill candidates in local Claude Code and Codex session logs. "
        "Local-only: reads files on this machine, writes inactive Markdown candidates, uses no network.",
    )
    p.add_argument("--repo", default=".", help="any path inside the git repository to scope to (default: cwd)")
    p.add_argument("--config", help="TOML config file (see examples/skill-miner.example.toml)")
    p.add_argument("--out", help="candidate output directory (default: <repo>/.skill-candidates)")
    p.add_argument("--since", help="only sessions newer than this: 30d, 12h, 2w or 'all' (default: 30d)")
    p.add_argument("--min-count", dest="min_count", type=int, help="minimum occurrences (default: 3)")
    p.add_argument("--min-sessions", dest="min_sessions", type=int, help="minimum distinct sessions (default: 2)")
    p.add_argument("--similarity", type=float, help="Jaccard threshold for grouping prompts (default: 0.5)")
    p.add_argument("--skills-dir", dest="skills_dir", action="append", help="extra skill directory to dedupe against (repeatable)")
    p.add_argument(
        "--same-remote", dest="same_remote", action=argparse.BooleanOptionalAction, default=None,
        help="also include other checkouts whose origin is the same owner/name, e.g. a second clone (default: off)",
    )
    p.add_argument(
        "--handoffs", dest="handoffs", action=argparse.BooleanOptionalAction, default=None,
        help="also mine handoff files (default: on; see handoff_globs)",
    )
    p.add_argument("--min-handoffs", dest="min_handoffs", type=int, help="minimum distinct handoffs for a handoff pattern (default: 2)")
    p.add_argument("--claude-home", dest="claude_home", help="Claude Code data dir (default: ~/.claude)")
    p.add_argument("--codex-home", dest="codex_home", help="Codex data dir (default: ~/.codex)")
    p.add_argument("--dry-run", action="store_true", help="analyse and print a summary; write nothing")
    p.add_argument("--json", action="store_true", help="print the summary as JSON")
    p.add_argument("--version", action="version", version=f"skill-miner {VERSION}")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        cfg = load_config(args)
    except ConfigError as exc:
        print(f"skill-miner: {exc}", file=sys.stderr)
        return 2

    result = analyse(cfg)
    written: list[str] = []
    warnings: list[str] = []
    if cfg.same_remote and result["stats"]["same_remote"] is None:
        warnings.append("--same-remote: this repository has no usable origin remote; only this checkout and its worktrees were mined")
    if not args.dry_run and result["candidates"]:
        if (cfg.out == cfg.repo or cfg.repo in cfg.out.parents) and not is_git_ignored(cfg.repo, cfg.out):
            warnings.append(f"{cfg.out} is inside the repository but not gitignored; add it to .gitignore")
        day = prepare_out_dir(cfg.out)
        for cluster, name in result["candidates"]:
            path = day / f"{cluster.kind}-{name}.md"
            write_private(path, render(cluster, name, cfg))
            written.append(str(path))

    summary = {
        "version": VERSION,
        "repo": str(cfg.repo),
        "out": str(cfg.out),
        "dry_run": args.dry_run,
        **result["stats"],
        "candidates": [
            {"kind": c.kind, "name": n, "occurrences": len(c.members), "sessions": len(c.sessions)}
            for c, n in result["candidates"]
        ],
        "covered_by_existing_skills": len(result["covered"]),
        "written": written,
        "warnings": warnings,
    }
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        s = summary
        print(
            f"skill-miner {VERSION}: {s['prompts']} prompts and {s['invocations']} invocations from "
            f"{s['claude_files']} Claude Code and {s['codex_files']} Codex sessions "
            f"across {len(s['checkouts'])} checkout(s)"
        )
        if s.get("handoff_files"):
            print(f"  plus {s['handoff_items']} rule/decision/pending items from {s['handoff_files']} handoff files ({s['handoff_tracks']} tracks)")
        print(f"  {len(s['candidates'])} candidates, {s['covered_by_existing_skills']} already covered by existing skills")
        for c in s["candidates"]:
            unit = "handoffs" if c["kind"].startswith(("handoff", "pending")) else "sessions"
            print(f"  - {c['kind']:<17} {c['name']}  ({c['occurrences']}x in {c['sessions']} {unit})")
        if written:
            print(f"  written to {Path(written[0]).parent}  (inactive; review before adopting)")
        elif args.dry_run:
            print("  dry run: nothing written")
        for w in warnings:
            print(f"  warning: {w}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
