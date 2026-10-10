#!/usr/bin/env python3
"""check_install.py - run an adopter's whole first hour, from a clean clone.

Every gate in this repo tests a piece in place. None of them tested the thing
an adopter actually does: receive the plugin, scaffold a project, and run the
commands the docs tell them to. Two real bugs lived in that gap and both reached
a user:

  - Eight doc commands assumed this repo as the working directory. In an
    adopter's project `tools/` does not exist, and they hit it on step two.
  - A content change shipped without bumping plugin.json's version, so the
    install stayed on the old copy indefinitely with nothing reporting it.

Neither was visible from inside the repo. Both are obvious the moment you clone
into a temp directory and follow the README, which is what this does.

By default it copies the WORKING TREE, so it tests the code you are about to
commit. The first version of this file cloned git HEAD instead, on the reasoning
that HEAD is what an adopter receives -- and a mutation test showed that made it
unable to fire at all: breaking the shim in the working tree left the check
green, because the clone never saw the break. A gate that cannot see your edit
is not a gate.

`--committed` clones HEAD, which answers the other question: is what people can
already download sound? Useful in CI after a merge, useless before a commit.

Usage:
    check_install.py             # the working tree (what you are about to ship)
    check_install.py --committed # git HEAD (what an adopter can download now)
    check_install.py --keep      # leave the temp dir for inspection
    check_install.py --selftest  # cheap structural checks only

Exit codes:
    0  an adopter's first hour works
    1  something an adopter would hit is broken
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run(cmd: list[str], cwd: Path, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True,
                          env={**os.environ, **(env or {})})


def git(*args: str, cwd: Path) -> None:
    proc = run(["git", *args], cwd)
    if proc.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--committed", action="store_true",
                    help="test git HEAD instead of the working tree")
    ap.add_argument("--keep", action="store_true", help="leave the temp directory in place")
    ap.add_argument("--selftest", action="store_true", help="structural checks only, no clone")
    args = ap.parse_args()

    failures: list[str] = []

    def check(label: str, cond: bool, detail: str = "") -> None:
        if not cond:
            failures.append(f"{label}{(': ' + detail) if detail else ''}")

    # -- cheap structural checks, also the --selftest path ----------------
    manifest = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())
    check("plugin.json declares a version", bool(manifest.get("version")))
    check("plugin.json declares agents as a list", isinstance(manifest.get("agents"), list))
    check("an init skill exists", (ROOT / "skills" / "init" / "SKILL.md").exists())

    if args.selftest:
        for f in failures:
            print(f"selftest: {f}", file=sys.stderr)
        if failures:
            return 1
        print("check_install selftest: ok")
        return 0

    tmp = Path(tempfile.mkdtemp(prefix="cadence-install-"))
    try:
        plugin = tmp / "plugin"
        proj = tmp / "proj"

        if args.committed:
            proc = run(["git", "clone", "--quiet", str(ROOT), str(plugin)], tmp)
            check("the repo clones", proc.returncode == 0, proc.stderr.strip())
            if proc.returncode != 0:
                raise SystemExit(1)
        else:
            # Copy the working tree. Skip .git so the copy is not a repo (an
            # adopter's plugin directory is not one either), and skip the noise
            # that would make this slow.
            shutil.copytree(
                ROOT, plugin,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc",
                                              ".venv", "venv", "node_modules"),
            )
            check("the working tree copies", (plugin / "tools").is_dir())

        version = json.loads((plugin / ".claude-plugin" / "plugin.json").read_text())["version"]
        check("the clone carries a version", bool(version))

        # A project with nothing cadence-aware about it.
        proj.mkdir()
        # -b main explicitly: init.defaultBranch is per-machine, and a test
        # that assumes `main` fails on a laptop configured for `master`.
        git("init", "--quiet", "-b", "main", cwd=proj)
        git("config", "user.email", "t@example.com", cwd=proj)
        git("config", "user.name", "T", cwd=proj)
        (proj / "src").mkdir()
        (proj / "src" / "a.ts").write_text("export const x = 1\n")
        (proj / "db" / "migrations").mkdir(parents=True)
        (proj / "db" / "migrations" / "001.sql").write_text("-- s\n")
        git("add", "-A", cwd=proj)
        git("commit", "--quiet", "-m", "init", cwd=proj)

        env = {"CADENCE_PLUGIN_ROOT": str(plugin)}
        init = ["python3", str(plugin / "tools" / "init_project.py")]

        # -- README step 2 ------------------------------------------------
        p = run([*init, "--retros", "--hook"], proj, env)
        check("init runs", p.returncode == 0, p.stderr.strip()[:200])
        for rel in ("cadence.toml", ".cadence/cadence", ".cadence/check-scope",
                    "docs/retros/TRAPS.md", "docs/retros/_fragment_template.md",
                    "docs/retros/pending/.gitkeep", "docs/retros/archive/.gitkeep"):
            check(f"init creates {rel}", (proj / rel).exists())

        shim = proj / ".cadence" / "cadence"
        if not shim.exists():
            failures.append("no shim, so none of the adopter commands can be tested")
            raise SystemExit(1)
        check("the shim is executable", os.access(shim, os.X_OK))

        # -- every command the docs tell an adopter to run -----------------
        cases = [
            ("config", ["config"], 0),
            ("config --json", ["config", "--json"], 0),
            ("must-stop, unconfigured", ["must-stop", "db/migrations/002.sql"], 0),
            ("check-scope off a fan branch", ["check-scope"], 0),
            ("review-state, provider none", ["review-state", "--pr", "1"], 0),
            ("help", ["--help"], 0),
        ]
        for label, argv, want in cases:
            r = run([str(shim), *argv], proj, env)
            check(f"`cadence {' '.join(argv)}` exits {want}", r.returncode == want,
                  f"got {r.returncode}: {(r.stderr or r.stdout).strip()[:160]}")

        # An unconfigured boundary must not report as clear.
        r = run([str(shim), "must-stop", "db/migrations/002.sql"], proj, env)
        check("unconfigured boundary says NOT CHECKED", "NOT CHECKED" in r.stdout,
              r.stdout.strip()[:120])

        # -- README step 4: the boundary, and that it bites ----------------
        (proj / "cadence.toml").write_text(
            (proj / "cadence.toml").read_text()
            + '\n[[must_stop]]\npath = "db/migrations/"\nreason = "a schema migration"\n'
        )
        r = run([str(shim), "must-stop", "db/migrations/002.sql"], proj, env)
        check("a configured boundary refuses with exit 5", r.returncode == 5,
              f"got {r.returncode}")
        r = run([str(shim), "must-stop", "src/a.ts"], proj, env)
        check("a clean path passes", r.returncode == 0, f"got {r.returncode}")

        # The hook only bites inside a fan-out leaf; prove both directions,
        # because "it passed" on main is the state that misleads.
        git("checkout", "--quiet", "-b", "fan/xx-1/opt", cwd=proj)
        (proj / "db" / "migrations" / "002.sql").write_text("-- new\n")
        git("add", "db/migrations/002.sql", cwd=proj)
        r = run([str(shim), "check-scope"], proj, env)
        check("check-scope refuses on a fan branch (exit 5)", r.returncode == 5,
              f"got {r.returncode}")
        git("reset", "--quiet", cwd=proj)
        git("checkout", "--quiet", "main", cwd=proj)
        (proj / "db" / "migrations" / "003.sql").write_text("-- x\n")
        git("add", "db/migrations/003.sql", cwd=proj)
        r = run([str(shim), "check-scope"], proj, env)
        check("check-scope is a no-op on main (exit 0)", r.returncode == 0,
              f"got {r.returncode}")

        # -- init must be safe to re-run ----------------------------------
        (proj / "cadence.toml").write_text((proj / "cadence.toml").read_text() + "\n# MINE\n")
        p = run([*init, "--retros", "--hook"], proj, env)
        check("re-running init succeeds", p.returncode == 0)
        check("re-running init does not overwrite",
              "# MINE" in (proj / "cadence.toml").read_text())

        # -- the shim must prefer the INSTALLED version over a clone -------
        # A single find over the whole plugins tree also matched the marketplace
        # clone, and "marketplaces" sorts after "cache", so the clone always
        # won. The clone advances on a marketplace update while the installed
        # plugin only advances on a plugin update -- so the loser was the version
        # the SKILLS come from, and nothing reported the mismatch.
        #
        # Asked of the SHIM, via its `root` subcommand. An earlier version of
        # this check asserted on the shim's source text and reimplemented the
        # search itself, and passed while the shim was broken -- because it was
        # testing neither the shim nor its behaviour.
        fake_home = tmp / "home"
        installed = fake_home / ".claude" / "plugins" / "cache" / "cadence" / "cadence" / "0.9.0"
        clone = fake_home / ".claude" / "plugins" / "marketplaces" / "cadence"
        for d in (installed, clone):
            (d / "tools").mkdir(parents=True)

        r = run([str(shim), "root"], proj, {"HOME": str(fake_home), "CADENCE_PLUGIN_ROOT": ""})
        check("the shim resolves the installed version, not the clone",
              r.stdout.strip() == str(installed),
              f"resolved {r.stdout.strip()!r}, wanted the cache copy")

        # With nothing installed it may fall back to the clone, but must say so.
        shutil.rmtree(installed.parent.parent.parent)
        r = run([str(shim), "root"], proj, {"HOME": str(fake_home), "CADENCE_PLUGIN_ROOT": ""})
        check("with nothing installed it falls back to the clone",
              r.stdout.strip() == str(clone), f"resolved {r.stdout.strip()!r}")
        check("and warns that the skills are probably inactive",
              "plugin install" in r.stderr, r.stderr.strip()[:120])

        # -- the shim must fail LOUD, never pass, without the plugin -------
        r = run([str(shim), "check-scope"], proj, {"CADENCE_PLUGIN_ROOT": "/nonexistent"})
        check("the shim fails loudly with no plugin", r.returncode != 0, f"got {r.returncode}")
        check("and says how to fix it", "install" in r.stderr.lower())

        # -- vendored: cadence as a git submodule at .cadence/ ---------------
        # No plugin at all. The dispatcher must resolve the copy it sits in,
        # and the generated wrappers must point at files that exist.
        vendored_first_hour(tmp, plugin, check)

    finally:
        if args.keep:
            print(f"\ntemp dir kept: {tmp}")
        else:
            shutil.rmtree(tmp, ignore_errors=True)

    for f in failures:
        print(f"  FAIL  {f}", file=sys.stderr)
    if failures:
        print(f"\ncheck_install: {len(failures)} failure(s). An adopter would hit these.",
              file=sys.stderr)
        return 1
    print(f"check_install: an adopter's first hour works (plugin {manifest['version']})")
    return 0


def vendored_first_hour(tmp: Path, plugin: Path, check) -> None:
    """A project that vendors cadence as a submodule, with no plugin installed."""
    src = tmp / "vendor-src"
    shutil.copytree(plugin, src, ignore=shutil.ignore_patterns(".git"))
    git("init", "--quiet", "-b", "main", cwd=src)
    git("-c", "user.email=t@example.com", "-c", "user.name=T", "add", "-A", cwd=src)
    git("-c", "user.email=t@example.com", "-c", "user.name=T", "commit", "--quiet", "-m", "v", cwd=src)

    proj = tmp / "vproj"
    proj.mkdir()
    git("init", "--quiet", "-b", "main", cwd=proj)
    git("config", "user.email", "t@example.com", cwd=proj)
    git("config", "user.name", "T", cwd=proj)
    # A file:// URL, not a path: a path clone hardlinks objects, which fails
    # intermittently ("hardlink different from source") on some runners.
    git("-c", "protocol.file.allow=always", "submodule", "add", "--quiet", src.as_uri(), ".cadence", cwd=proj)
    git("commit", "--quiet", "-m", "vendor cadence", cwd=proj)

    # An empty HOME, so the plugin cache cannot be what makes this pass.
    env = {"HOME": str(tmp / "empty-home"), "CADENCE_PLUGIN_ROOT": ""}
    disp = proj / ".cadence" / "cadence"
    r = run([str(disp), "root"], proj, env)
    check("vendored: the dispatcher resolves the copy it sits in",
          Path(r.stdout.strip() or "/nonexistent").resolve() == (proj / ".cadence").resolve(),
          f"resolved {r.stdout.strip()!r} {r.stderr.strip()[:120]}")
    r = run([str(disp), "config"], proj, env)
    check("vendored: `cadence config` runs", r.returncode == 0, r.stderr.strip()[:160])

    p = run(["python3", ".cadence/tools/init_project.py", "--retros", "--hook"], proj, env)
    check("vendored: init runs", p.returncode == 0, p.stderr.strip()[:200])
    check("vendored: init writes cadence.toml", (proj / "cadence.toml").exists())
    check("vendored: init leaves the submodule clean",
          ".cadence" not in run(["git", "status", "--porcelain"], proj).stdout)

    (proj / "cadence.toml").write_text(
        (proj / "cadence.toml").read_text() + '\n[paths]\noverlays = "docs/overlays"\n'
        if "[paths]" not in (proj / "cadence.toml").read_text()
        else (proj / "cadence.toml").read_text().replace("[paths]\n", '[paths]\noverlays = "docs/overlays"\n', 1)
    )
    wrap = ["python3", ".cadence/tools/wrappers.py", "--targets", "claude,codex"]
    p = run(wrap, proj, env)
    check("vendored: wrappers generate", p.returncode == 0, p.stderr.strip()[:200])

    claude = proj / ".claude" / "skills" / "code-review" / "SKILL.md"
    codex = proj / ".codex" / "skills" / "code-review" / "SKILL.md"
    check("vendored: a Claude wrapper exists, unprefixed", claude.exists())
    check("vendored: a Codex wrapper exists", codex.exists())
    check("vendored: agents are generated", (proj / ".claude" / "agents" / "code-reviewer.md").exists())
    check("vendored: no `init` wrapper to shadow the built-in /init",
          not (proj / ".claude" / "skills" / "init").exists())
    import re
    for f in sorted([*(proj / ".claude").rglob("*.md"), *(proj / ".codex").rglob("*.md")]):
        text = f.read_text()
        rel = f.relative_to(proj).as_posix()
        # The trailing slash: skill-anatomy names the variable in prose, which
        # is fine. A PATH through it resolves to nothing outside a plugin.
        check(f"vendored: {rel} has no plugin-root path", "${CLAUDE_PLUGIN_ROOT}/" not in text)
        check(f"vendored: {rel} has no /cadence: prefix", "/cadence:" not in text)
        check(f"vendored: {rel} names its overlay", "docs/overlays/" in text)
        check(f"vendored: {rel} extends overlays to the docs it links to",
              "docs/overlays/<name>.md" in text and "reference/personas/<name>.md" in text)
        for target in set(re.findall(r"\.cadence/[\w./-]+[\w/]", text)):
            check(f"vendored: {rel} points at {target}, which exists",
                  (proj / target.split("#")[0]).exists())
    check("vendored: Codex wrappers drop allowed-tools", "allowed-tools:" not in codex.read_text())

    p = run([*wrap, "--check"], proj, env)
    check("vendored: --check passes when fresh", p.returncode == 0, p.stderr.strip()[:160])
    claude.write_text(claude.read_text() + "hand edit\n")
    p = run([*wrap, "--check"], proj, env)
    check("vendored: --check fails on a hand edit", p.returncode == 1)
    run(wrap, proj, env)

    orphan = proj / ".claude" / "skills" / "gone" / "SKILL.md"
    orphan.parent.mkdir(parents=True)
    orphan.write_text("---\nname: gone\n---\n<!-- GENERATED by cadence from .cadence/skills/gone/SKILL.md.\n-->\n")
    p = run([*wrap, "--check"], proj, env)
    check("vendored: --check fails on an orphaned wrapper", p.returncode == 1)
    run(wrap, proj, env)
    check("vendored: regenerating removes the orphan", not orphan.exists())

    # A project file that merely MENTIONS the marker phrase is still its own.
    mention = proj / ".claude" / "agents" / "notes.md"
    mention.write_text("---\nname: notes\n---\nOur wrappers say GENERATED by cadence from .cadence/.\n")
    run(wrap, proj, env)
    check("vendored: a project file that mentions the marker is not deleted", mention.exists())
    mention.unlink(missing_ok=True)

    # Dropping a target removes that target's wrappers rather than stranding them.
    run(["python3", ".cadence/tools/wrappers.py", "--targets", "claude"], proj, env)
    check("vendored: dropping codex removes the codex wrappers", not codex.exists())
    run(wrap, proj, env)

    own = proj / ".codex" / "skills" / "retro" / "SKILL.md"
    own.write_text("---\nname: retro\n---\nthe project's own\n")
    p = run(wrap, proj, env)
    check("vendored: a project's own file at a wrapper path fails the run", p.returncode == 1)
    check("vendored: ...and is never overwritten", "the project's own" in own.read_text())
    own.unlink()

    p = run(["python3", str(plugin / "tools" / "wrappers.py")], proj, env)
    check("vendored: wrappers refuse to run from a copy that is not .cadence/", p.returncode == 1)

    # [models.pins]: a pin lands in the Claude wrapper's frontmatter, never in Codex's.
    base = (proj / "cadence.toml").read_text()
    (proj / "cadence.toml").write_text(base + '\n[models.pins]\ncode-review = "opus"\nspec-editor = "fable"\n')
    p = run(wrap, proj, env)
    check("vendored: wrappers generate with pins", p.returncode == 0, p.stderr.strip()[:200])
    fm = lambda f: f.read_text().split("\n---\n", 1)[0]
    check("vendored: a skill pin lands in the Claude wrapper", "model: opus" in fm(claude))
    check("vendored: an agent pin lands in the agent wrapper",
          "model: fable" in fm(proj / ".claude" / "agents" / "spec-editor.md"))
    check("vendored: an unpinned wrapper gets no model", "model:" not in fm(proj / ".claude" / "agents" / "code-reviewer.md"))
    check("vendored: Codex wrappers never carry a pin", "model:" not in fm(codex))
    (proj / "cadence.toml").write_text(base + '\n[models.pins]\ncode-reveiw = "opus"\n')
    p = run(wrap, proj, env)
    check("vendored: a pin naming no skill or agent fails", p.returncode == 1 and "code-reveiw" in p.stderr)
    (proj / "cadence.toml").write_text(base)

    # A linked worktree checks its own wrappers against its own .cadence/, so the
    # pre-commit gate passes there too, not only in the main checkout.
    run(wrap, proj, env)
    git("add", "-A", cwd=proj)
    git("commit", "--quiet", "-m", "wrappers", cwd=proj)
    wt = tmp / "vproj-wt"
    git("worktree", "add", "--quiet", "-b", "wt", str(wt), cwd=proj)
    git("-c", "protocol.file.allow=always", "submodule", "update", "--init", "--quiet", cwd=wt)
    p = run([*wrap, "--check"], wt, env)
    check("vendored: --check passes in a linked worktree", p.returncode == 0, p.stderr.strip()[:200])
    wt_claude = wt / ".claude" / "skills" / "code-review" / "SKILL.md"
    wt_claude.write_text(wt_claude.read_text() + "hand edit\n")
    p = run([*wrap, "--check"], wt, env)
    check("vendored: --check in a worktree reads the worktree's files", p.returncode == 1)
    p = run([*wrap, "--check"], proj, env)
    check("vendored: ...not the main checkout's", p.returncode == 0, p.stderr.strip()[:200])


if __name__ == "__main__":
    sys.exit(main())
