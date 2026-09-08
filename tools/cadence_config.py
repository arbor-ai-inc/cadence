#!/usr/bin/env python3
"""cadence_config.py - load and validate cadence.toml.

SINGLE SOURCE OF TRUTH for configuration and for the must-stop boundary. Every
tool and skill that needs a lint command, a provider name, or a must-stop
decision reads it from here. Nothing re-parses the TOML and nothing keeps its
own copy of the path list.

That last part is the point. In the system cadence was extracted from, the
must-stop boundary was a dict literal inside the fan-out engine, mirrored by
hand into a prose document; the two drifted, and the workflow docs had to carry
a standing instruction to trust the code over the prose. One loader, one
matcher, and the prose can point at the config instead of restating it.

Usage:
    cadence_config.py                    # print the effective config
    cadence_config.py --json             # machine-readable
    cadence_config.py must-stop <path>.. # exit 5 if any path is inside the boundary
    cadence_config.py --selftest

Exit codes:
    0  fine
    1  usage or config error
    5  must-stop: at least one path is inside the boundary
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tomllib
from dataclasses import dataclass, field, asdict
from pathlib import Path

CONFIG_NAME = "cadence.toml"

TRACKER_PROVIDERS = ("linear", "github", "none")
ASK_PROVIDERS = ("harness", "slack", "stdout")
REVIEW_PROVIDERS = ("coderabbit", "codex", "claude", "subagent", "none")


class ConfigError(Exception):
    """A config that cannot be trusted. Always fail loud, never fall back."""


@dataclass(frozen=True)
class MustStop:
    path: str
    reason: str

    @property
    def is_dir(self) -> bool:
        """A trailing slash means the directory and everything under it."""
        return self.path.endswith("/")


@dataclass
class Config:
    root: Path
    source: Path | None = None

    lint: str = "pre-commit run --all-files"
    test: str = "pytest"
    test_fast: str | None = None

    tracker_provider: str = "none"
    issue_key: str = r"^([A-Z]{2,5}-[0-9]+)$"
    state_started: str | None = None
    state_in_review: str | None = None

    ask_provider: str = "harness"
    ask_timeout_seconds: int = 3600

    review_provider: str = "none"
    review_bot_login: str | None = None
    review_max_rounds: int = 3

    specs_dir: str = "specs"
    retros_dir: str = "docs/retros"
    principles_path: str = "docs/architectural-principles.md"
    review_standards_path: str = "docs/code-review-standards.md"

    # ADVISORY ONLY, and the docstring below says why. Cadence cannot force a
    # model. A skill's `model:` pin lasts only the turn that invoked it, and a
    # workflow that stops to ask the author spans many turns -- so from the
    # second prompt onward the session model applies again, silently. There is
    # no hook that can change a model and no per-agent override.
    #
    # So this is what a workflow CHECKS against. It refuses to run on a
    # different model without saying so, which turns a silent degrade into a
    # visible choice. Setting it does not switch anything.
    models_recommended: str | None = None

    synthesis_threshold: int = 15

    max_leaves: int = 8
    max_depth: int = 3
    max_options: int = 3

    must_stop: tuple = ()

    # -- the boundary ------------------------------------------------------

    def must_stop_hits(self, paths) -> list[tuple[str, str]]:
        """Which of `paths` fall inside the must-stop boundary.

        Returns (normalized path, reason) pairs, one per offending path, in the
        order given. A path matches at most once even if several entries cover
        it -- the first reason is enough to stop, and listing three reasons for
        one file reads as three problems.
        """
        hits = []
        for raw in paths:
            norm = str(raw).strip().replace("\\", "/").lstrip("./")
            if not norm:
                continue
            for entry in sorted(self.must_stop, key=lambda e: e.path):
                matched = norm.startswith(entry.path) if entry.is_dir else norm == entry.path
                if matched:
                    hits.append((norm, entry.reason))
                    break
        return hits

    def describe_boundary(self) -> str:
        if not self.must_stop:
            return (
                "No must-stop boundary is configured, so nothing will ever stop for a\n"
                "human. Add [[must_stop]] entries to cadence.toml naming the surfaces\n"
                "where being wrong is expensive and irreversible."
            )
        lines = [f"{len(self.must_stop)} must-stop entr{'y' if len(self.must_stop) == 1 else 'ies'}:"]
        for e in sorted(self.must_stop, key=lambda e: e.path):
            lines.append(f"  {e.path}  — {e.reason}")
        return "\n".join(lines)


def repo_root(start: Path | None = None) -> Path:
    """The MAIN worktree root, even when called from inside a linked worktree.

    Not --show-toplevel, which returns the current worktree: from a fan-out leaf
    that would find a different config than the one the parent run read.
    """
    cwd = Path(start or Path.cwd()).resolve()
    try:
        common = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],
            cwd=cwd, capture_output=True, text=True, check=True,
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return cwd
    git_dir = Path(common)
    if not git_dir.is_absolute():
        git_dir = (cwd / git_dir).resolve()
    return git_dir.parent


def _require(d: dict, section: str, key: str, allowed: tuple, default: str) -> str:
    value = d.get(section, {}).get(key, default)
    if value not in allowed:
        raise ConfigError(
            f"{CONFIG_NAME}: [{section}].{key} is {value!r}; expected one of {', '.join(allowed)}"
        )
    return value


def load(start: Path | None = None) -> Config:
    """Load cadence.toml from the repo root, or return defaults if absent.

    A missing file is fine and documented -- the defaults need no credentials.
    A malformed or invalid file is not: it raises, because silently running on
    defaults when the author wrote a config is how a must-stop boundary
    quietly stops being enforced.
    """
    root = repo_root(start)
    path = root / CONFIG_NAME
    if not path.exists():
        return Config(root=root, source=None)

    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, OSError) as exc:
        raise ConfigError(f"{path}: cannot be read: {exc}") from exc

    known = {"commands", "tracker", "ask", "review", "paths", "models", "retro", "fanout", "must_stop"}
    for section in raw:
        if section not in known:
            raise ConfigError(
                f"{path}: unknown section [{section}]. Known: {', '.join(sorted(known))}"
            )

    cmds = raw.get("commands", {})
    tracker = raw.get("tracker", {})
    ask = raw.get("ask", {})
    review = raw.get("review", {})
    paths = raw.get("paths", {})
    retro = raw.get("retro", {})
    fanout = raw.get("fanout", {})

    entries = []
    for i, item in enumerate(raw.get("must_stop", [])):
        p = str(item.get("path", "")).strip()
        reason = str(item.get("reason", "")).strip()
        if not p:
            raise ConfigError(f"{path}: [[must_stop]] #{i + 1} has no path")
        if not reason:
            # An unexplained boundary gets argued with. The reason is what the
            # agent shows the human when it stops, so it is required.
            raise ConfigError(
                f"{path}: [[must_stop]] {p!r} has no reason. The reason is what an agent "
                f"shows a human when it stops, so it is not optional."
            )
        entries.append(MustStop(path=p.replace("\\", "/").lstrip("./"), reason=reason))

    cfg = Config(
        root=root,
        source=path,
        lint=cmds.get("lint", Config.lint),
        test=cmds.get("test", Config.test),
        test_fast=cmds.get("test_fast"),
        tracker_provider=_require(raw, "tracker", "provider", TRACKER_PROVIDERS, "none"),
        issue_key=tracker.get("issue_key", Config.issue_key),
        state_started=tracker.get("state_started"),
        state_in_review=tracker.get("state_in_review"),
        ask_provider=_require(raw, "ask", "provider", ASK_PROVIDERS, "harness"),
        ask_timeout_seconds=int(ask.get("timeout_seconds", Config.ask_timeout_seconds)),
        review_provider=_require(raw, "review", "provider", REVIEW_PROVIDERS, "none"),
        review_bot_login=review.get("bot_login"),
        review_max_rounds=int(review.get("max_rounds", Config.review_max_rounds)),
        specs_dir=paths.get("specs", Config.specs_dir),
        retros_dir=paths.get("retros", Config.retros_dir),
        principles_path=paths.get("principles", Config.principles_path),
        review_standards_path=paths.get("review_standards", Config.review_standards_path),
        models_recommended=raw.get("models", {}).get("recommended"),
        synthesis_threshold=int(retro.get("synthesis_threshold", Config.synthesis_threshold)),
        max_leaves=int(fanout.get("max_leaves", Config.max_leaves)),
        max_depth=int(fanout.get("max_depth", Config.max_depth)),
        max_options=int(fanout.get("max_options", Config.max_options)),
        must_stop=tuple(entries),
    )

    unknown_model_keys = set(raw.get("models", {})) - {"recommended"}
    if unknown_model_keys:
        raise ConfigError(
            f"{path}: [models] only reads `recommended`; found "
            f"{', '.join(sorted(unknown_model_keys))}. Cadence cannot set a model "
            f"per role — a skill's pin lasts one turn — so a key here that looks "
            f"like it assigns one would be doing nothing."
        )

    if cfg.review_provider == "coderabbit" and not cfg.review_bot_login:
        cfg.review_bot_login = "coderabbitai[bot]"
    if cfg.synthesis_threshold < 1:
        raise ConfigError(f"{path}: [retro].synthesis_threshold must be at least 1")
    for name, value in (("max_leaves", cfg.max_leaves), ("max_depth", cfg.max_depth), ("max_options", cfg.max_options)):
        if value < 1:
            raise ConfigError(f"{path}: [fanout].{name} must be at least 1")
    return cfg


def as_dict(cfg: Config) -> dict:
    d = asdict(cfg)
    d["root"] = str(cfg.root)
    d["source"] = str(cfg.source) if cfg.source else None
    d["must_stop"] = [{"path": e.path, "reason": e.reason} for e in cfg.must_stop]
    return d


# -- selftest --------------------------------------------------------------

def selftest() -> int:
    import tempfile

    failures = []

    def check(label, cond):
        if not cond:
            failures.append(label)

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)

        # No config at all: defaults, and an empty boundary that says so.
        cfg = Config(root=root)
        check("default boundary must be empty", cfg.must_stop == ())
        check("empty boundary must warn", "No must-stop boundary" in cfg.describe_boundary())
        check("empty boundary matches nothing", cfg.must_stop_hits(["db/migrations/001.sql"]) == [])
        # An unconfigured boundary and a genuinely clean path both produce no
        # hits, and must NOT report the same thing.
        check("empty boundary is distinguishable from clean",
              Config(root=root).must_stop == () and
              Config(root=root, must_stop=(MustStop("x/", "y"),)).must_stop != ())

        cfg = Config(root=root, must_stop=(
            MustStop("db/migrations/", "a schema migration"),
            MustStop("api/models.py", "the published schema"),
            MustStop("src/billing/", "money-bearing logic"),
        ))

        # Directory entries cover everything beneath them.
        check("dir entry matches a file under it",
              cfg.must_stop_hits(["db/migrations/001.sql"]) == [("db/migrations/001.sql", "a schema migration")])
        # A file entry is exact. Prefix-matching it would refuse models.py.bak
        # too, which is the bug the trailing-slash convention exists to avoid.
        check("file entry is exact", cfg.must_stop_hits(["api/models.py"]) != [])
        check("file entry does not prefix-match", cfg.must_stop_hits(["api/models.py.bak"]) == [])
        # A sibling directory sharing a name prefix must not match.
        check("dir entry does not prefix-match a sibling",
              cfg.must_stop_hits(["db/migrations-old/001.sql"]) == [])
        # Leading ./ and backslashes are normalized, since callers pass git output.
        check("./ prefix normalized", cfg.must_stop_hits(["./src/billing/rate.py"]) != [])
        check("backslashes normalized", cfg.must_stop_hits([r"src\billing\rate.py"]) != [])
        # Clean paths stay clean.
        check("unrelated path is clean", cfg.must_stop_hits(["src/ui/button.tsx"]) == [])
        # One path, one reason, even when two entries could cover it.
        two = Config(root=root, must_stop=(MustStop("src/", "the tree"), MustStop("src/billing/", "money")))
        check("one hit per path", len(two.must_stop_hits(["src/billing/x.py"])) == 1)
        # Order and count are preserved across a mixed batch.
        mixed = cfg.must_stop_hits(["src/ui/a.tsx", "db/migrations/2.sql", "src/billing/b.py"])
        check("mixed batch keeps order and drops clean paths",
              [p for p, _ in mixed] == ["db/migrations/2.sql", "src/billing/b.py"])

        # A written config round-trips, and an invalid one raises rather than
        # silently reverting to defaults -- the failure that would quietly
        # disable the boundary.
        (root / CONFIG_NAME).write_text(
            '[commands]\nlint = "make lint"\n'
            '[review]\nprovider = "coderabbit"\n'
            '[[must_stop]]\npath = "db/migrations/"\nreason = "a schema migration"\n'
        )
        loaded = load(root)
        check("config file is read", loaded.lint == "make lint")
        check("coderabbit implies a default bot login", loaded.review_bot_login == "coderabbitai[bot]")
        check("must_stop entries load", len(loaded.must_stop) == 1)

        (root / CONFIG_NAME).write_text('[models]\nrecommended = "opus"\n')
        check("recommended model loads", load(root).models_recommended == "opus")
        check("no [models] means no recommendation", Config(root=root).models_recommended is None)

        for bad, label in (
            ('[ask]\nprovider = "carrier-pigeon"\n', "unknown ask provider"),
            ('[nope]\nx = 1\n', "unknown section"),
            ('[[must_stop]]\npath = "db/"\n', "must_stop without a reason"),
            ('[[must_stop]]\nreason = "x"\n', "must_stop without a path"),
            ('[retro]\nsynthesis_threshold = 0\n', "zero synthesis threshold"),
            ('[models]\ndefault = "sonnet"\n', "a [models] key that cannot do anything"),
        ):
            (root / CONFIG_NAME).write_text(bad)
            try:
                load(root)
                failures.append(f"{label} should have raised ConfigError")
            except ConfigError:
                pass

    for line in failures:
        print(f"selftest: {line}", file=sys.stderr)
    if failures:
        print(f"\ncadence_config selftest: {len(failures)} failure(s).", file=sys.stderr)
        return 1
    print("cadence_config selftest: ok")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", nargs="?", default="show", choices=["show", "must-stop"])
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        return selftest()

    try:
        cfg = load()
    except ConfigError as exc:
        print(f"cadence_config: {exc}", file=sys.stderr)
        return 1

    if args.command == "must-stop":
        if not args.paths:
            print("cadence_config: must-stop needs at least one path", file=sys.stderr)
            return 1
        hits = cfg.must_stop_hits(args.paths)
        if not hits:
            if not cfg.must_stop:
                # "clear" would be a true statement about a check that did not
                # happen. With no boundary configured every path is clear, and
                # that reads as safe rather than as unconfigured -- which is the
                # exact confusion [[must_stop]] exists to prevent.
                print(
                    f"NOT CHECKED: no [[must_stop]] boundary is configured, so all "
                    f"{len(args.paths)} path(s) pass trivially.\n"
                    f"This is not the same as safe. Add entries to "
                    f"{cfg.source or 'cadence.toml'} naming the surfaces where\n"
                    f"being wrong is expensive and irreversible."
                )
                return 0
            print(f"clear: none of {len(args.paths)} path(s) are inside the must-stop boundary")
            return 0
        print("must-stop boundary crossed. Ask a human; do not decide and do not fan out.\n")
        for p, reason in hits:
            print(f"  {p}\n      {reason}")
        return 5

    if args.json:
        print(json.dumps(as_dict(cfg), indent=2, sort_keys=True))
        return 0

    where = cfg.source if cfg.source else f"(no {CONFIG_NAME}; defaults)"
    print(f"root:   {cfg.root}\nconfig: {where}\n")
    print(f"lint:     {cfg.lint}\ntest:     {cfg.test}")
    print(f"tracker:  {cfg.tracker_provider}\nask:      {cfg.ask_provider}\nreview:   {cfg.review_provider}")
    if cfg.models_recommended:
        print(f"model:    {cfg.models_recommended} (recommended; advisory, not enforced)")
    print(f"specs:    {cfg.specs_dir}\nretros:   {cfg.retros_dir}\n")
    print(cfg.describe_boundary())
    return 0


if __name__ == "__main__":
    sys.exit(main())
