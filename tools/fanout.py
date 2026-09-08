#!/usr/bin/env python3
"""fanout.py - decision fan-out tree for autonomous execution.

SINGLE SOURCE OF TRUTH for fan-out tree state, the way spec_hash.py is for
gate hashes. The decision-fanout skill MUST create, grow, and collapse trees by
running this script. Never hand-manage worktrees, branch names, or the ledger:
`collapse` can only be exact if this file is the only thing that ever wrote the
tree.

Usage:
  fanout.py init     <issue> [--base <sha>]
  fanout.py fork     <issue> --decision "Q" --why-you "why you cannot settle it"
                             --source "file:line"
                             --option "slug:what it does:why you would pick it" ...
                             [--parent <node>] [--drop "slug:why it is dominated"]
                             [--touches <path> ...]
  fanout.py record   <issue> --kind mechanical|two-way --question "Q" --answer "A"
                             [--reversal "cost to undo"] [--node <node>]
  fanout.py result   <issue> [--node <node>] --tests pass|fail|skipped
                             --evidence "cmd: what it reported"
                             --notice "what a user or operator notices"
                             --reversible yes|one-way
                             --lost "..." --switch-cost "..."
                             [--failure "..."] [--risk "..."]
                             [--open-question "..."] [--note "..."]
  fanout.py recommend <issue> --decision <id> --option <slug> --reason "..."
                             --wrong-if "the fact that would flip this"
                             --if-silent "what happens with no answer"
  fanout.py leaves   <issue>
  fanout.py ledger   <issue>
  fanout.py collapse <issue> --choose d1=slug,d2=slug [--force]
  fanout.py status   <issue>
  fanout.py notify   <issue> [--print-only]
  fanout.py check-scope                     # commit hook; no issue argument
  fanout.py abandon  <issue> [--force]

The --why-you / --notice / --reversible / --wrong-if / --if-silent flags are the
Shape A decision-brief fields (reference/human-brief.md). They are required
because a fan-out that cannot say what a human would notice, or what would flip
the recommendation, has not produced a decidable brief -- it has produced N
branches and left the framing cost with the reader. `check_fanout.py` asserts
that every required flag appears in this block, because it drifted once already.

State lives in .cadence/fanout/<issue>/tree.json (gitignored). Worktrees live in
.cadence/worktrees/<issue>/<path> (gitignored) on branches named
fan/<issue>/<option-trail>. Both are local-only: a leaf is
never pushed and never becomes a PR. Only the `collapse` survivor continues
into the normal execute-issue tail.

Exit codes (the skill branches on these):
  0  success
  1  usage or state error
  3  cap or must-stop refusal - the fan-out was REFUSED, ask instead
  4  collapse did not resolve to exactly one leaf
  5  check-scope: a fan/* commit crosses the must-stop boundary
  6  collapse chose a survivor but could not remove every other leaf

Caps exist because the combinatorics, not the token cost, are what break this:
max 8 leaves, max depth 3, max 3 options per decision. A refusal is always
recorded in the tree and printed. Nothing is ever silently truncated.
"""
import argparse
import fcntl
import json
import os
import subprocess
import time
import sys
from contextlib import contextmanager
from pathlib import Path

# Same directory, whether run as `python3 tools/fanout.py` from anywhere or via
# an absolute path out of an installed plugin.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import cadence_config  # noqa: E402

# Fallbacks only. The effective caps are [fanout] in cadence.toml; these apply
# when there is no config at all. CEILING_MAX_LEAVES is NOT configurable: it is
# the point past which a human cannot review the tree, and a project raising it
# is usually reaching for a decision it should be asking about instead.
DEFAULT_MAX_LEAVES = 8
CEILING_MAX_LEAVES = 16
DEFAULT_MAX_DEPTH = 3
DEFAULT_MAX_OPTIONS = 3
DEFAULT_MAX_PARALLEL = 3

STATE_VERSION = 1
TESTS_CHOICES = ("pass", "fail", "skipped")
RECORD_KINDS = ("mechanical", "two-way")

LEDGER_NAME = "LEDGER.md"

# Where local fan-out state and leaf worktrees live, relative to the repo root.
# Both are gitignored and neither is ever pushed. Named once because it was
# previously spelled out at seven call sites, and a rename reached the
# docstrings without reaching the code.
STATE_DIR = ".cadence"

ASK_TOOL = "tools/ask.py"
# Worktree-local config key stamped on every leaf. See cmd_check_scope.
MARKER_KEY = "fanout.issue"
# Slack renders a very long message poorly and argv is not unbounded, so a big
# tree degrades to a compact digest rather than pushing an ever-growing payload
# through a command line. Well under both Slack's text limit and any ARG_MAX.
DIGEST_LIMIT = 3500
FANOUT_TOOL = "tools/fanout.py"

# The must-stop boundary is CONFIGURATION, not a constant here. It lives in
# [[must_stop]] in the project's cadence.toml, and tools/cadence_config.py is
# the only thing that parses it and the only thing that matches against it.
#
# It used to be a dict literal in this file, mirrored by hand into a prose
# document. The two drifted, and the workflow docs had to carry a standing
# instruction to trust the code over the prose. One definition, one matcher, and
# the prose can point at the config instead of restating it.
#
# Enforced two ways, and the second is the one that matters:
#   fork        - refuses if the work leading up to the decision already touches
#                 the boundary (the tree would be illegitimate from the start)
#   check-scope - a commit hook that refuses ANY commit on a fan/* branch
#                 touching it. Git-derived, so no amount of reasoning inside a
#                 leaf can talk its way past it.
#
# Prose in CLAUDE.md or a skill doc is a prompt, not a gate. A rule that holds
# only while someone remembers it is the same as no rule by the fourth element.


_CONFIG = None


def config(start=None):
    """The project's cadence config, loaded once.

    Loaded lazily rather than at import so `--help` does not depend on a
    well-formed config, and so a test can inject one.
    """
    global _CONFIG
    if _CONFIG is None:
        _CONFIG = cadence_config.load(start)
    return _CONFIG


def set_config(cfg):
    """Inject a config. For tests, and for callers that already loaded one."""
    global _CONFIG
    _CONFIG = cfg


def must_stop_hits(paths):
    """Which given repo-relative paths fall inside the must-stop boundary.

    Delegates to the config's matcher, which owns the trailing-slash
    convention: a directory entry covers everything under it, while an entry
    without one is an exact file, so `models.py` does not also refuse
    `models.py.bak`.

    There is deliberately no fallback list here. A project that configured no
    boundary has an empty one, and inventing paths on its behalf would refuse
    commits it never asked to protect.
    """
    return config().must_stop_hits(paths)


# --------------------------------------------------------------------------
# git plumbing
# --------------------------------------------------------------------------


def git(*args, cwd=None, check=True):
    """Run git with list args (never a shell) and return stripped stdout."""
    proc = subprocess.run(
        ["git", *args],
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
    )
    if check and proc.returncode != 0:
        die(f"git {' '.join(args)} failed: {proc.stderr.strip() or proc.stdout.strip()}")
    return proc.stdout.strip()


def repo_root(start=None):
    """The MAIN worktree root, even when called from inside a leaf worktree.

    Not `--show-toplevel`, which returns the *current* worktree: called from a
    leaf, that would put a second tree.json inside the leaf and `collapse`
    would then be reading a different tree than `fork` wrote. `--git-common-dir`
    always points at the main checkout's .git, so its parent is the one place
    state can live.
    """
    cwd = Path(start or Path.cwd())
    if git("rev-parse", "--is-inside-work-tree", cwd=cwd, check=False) != "true":
        die("fanout needs a normal work tree; bare repositories are not supported")
    # `git worktree list` names the MAIN worktree first, for the main checkout and
    # every linked one alike. Deriving it from --git-common-dir's parent is only
    # right for an ordinary .git directory: inside a submodule the common dir is
    # <super>/.git/modules/<name>, whose parent is .git/modules, and state would
    # land somewhere nobody looks.
    listing = git("worktree", "list", "--porcelain", cwd=cwd)
    for line in listing.splitlines():
        if line.startswith("worktree "):
            return Path(line[len("worktree "):]).resolve()
    die("could not determine the main worktree from `git worktree list`")


def shortstat(cwd, ref_from, ref_to="HEAD"):
    """Measure a diff with git rather than trusting a hand-typed number.

    The tool measures, the agent judges. A `--diff-lines` the agent typed is
    exactly the kind of number that drifts from the code it describes, and the
    author is reading the ledger precisely because they have not read the diff.
    """
    # check=True on purpose. With check=False an invalid or pruned ref exits
    # nonzero with empty stdout, and this returned "+0/-0" - a measurement that
    # reads as "this option changed nothing" when it actually means "nothing was
    # measured". That is the exact failure the "tool measures, agent judges"
    # split exists to prevent, so a bad ref has to be loud.
    raw = git("diff", "--numstat", f"{ref_from}..{ref_to}", cwd=cwd)
    files, added, removed = 0, 0, 0
    names = []
    for line in raw.splitlines():
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        files += 1
        names.append(parts[2])
        # "-" appears for binary files.
        added += int(parts[0]) if parts[0].isdigit() else 0
        removed += int(parts[1]) if parts[1].isdigit() else 0
    return {"files": files, "added": added, "removed": removed, "names": sorted(names)}


DEPENDENCY_FILES = (
    "requirements.txt", "package.json", "package-lock.json", "go.mod", "go.sum",
    "pyproject.toml", "Pipfile",
)


def dependency_changes(names):
    """Dependency manifests touched. A new dependency is a cost the author is owed."""
    return sorted({n for n in names if Path(n).name in DEPENDENCY_FILES})


def die(message, code=1):
    print(f"fanout: {message}", file=sys.stderr)
    raise SystemExit(code)


# --------------------------------------------------------------------------
# state
# --------------------------------------------------------------------------


def issue_slug(issue):
    return issue.strip().lower()


def state_dir(root, issue):
    return root / STATE_DIR / "fanout" / issue_slug(issue)


def state_path(root, issue):
    return state_dir(root, issue) / "tree.json"


def load(root, issue):
    path = state_path(root, issue)
    if not path.exists():
        die(f"no fan-out tree for {issue}; run `fanout.py init {issue}` first")
    state = json.loads(path.read_text(encoding="utf-8"))
    if state.get("version") != STATE_VERSION:
        die(f"{path} has unsupported version {state.get('version')!r}")
    return state


def save(root, issue, state):
    """Write tree.json atomically.

    `write_text` truncates before it writes, so a reader arriving mid-write sees
    a partial file and dies on a JSON parse error. The read-only commands
    (`leaves`, `ledger`, `status`, `notify`) deliberately do NOT take the lock - a
    human running `ledger` while leaves are still building is the normal case,
    not a race to prevent - so the write is the side that has to be safe.
    os.replace is atomic within a filesystem: a reader sees the old file or the
    new one, never a torn one.
    """
    path = state_path(root, issue)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Unique per writer. A shared `tree.json.tmp` is not an atomic write, it is a
    # second shared mutable file: two writers race on the temp path and one
    # os.replace pulls it out from under the other, which fails with
    # FileNotFoundError instead of losing an update. Found by mutation-testing
    # the lock (removing it turned a lost update into that crash).
    tmp = path.with_suffix(f".json.tmp.{os.getpid()}")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


@contextmanager
def state_lock(root, issue):
    """Serialise read-modify-write of tree.json.

    The workflow builds leaves in parallel subagents by design (`max_parallel`),
    and each one calls `result` when it finishes. Every command loads the whole
    tree, mutates it, and writes it back, so two `result` calls that overlap lose
    one of the two results — and the ledger would then report "No result
    recorded" for a leaf that actually ran, which is the one failure mode that
    looks like an honest gap instead of a bug.

    flock is POSIX-only. This repo runs on macOS and Linux; a Windows port would
    need a different primitive here.
    """
    directory = state_dir(root, issue)
    directory.mkdir(parents=True, exist_ok=True)
    with open(directory / ".lock", "w") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def next_id(prefix, existing):
    n = 1
    while f"{prefix}{n}" in existing:
        n += 1
    return f"{prefix}{n}"


# --------------------------------------------------------------------------
# tree helpers
# --------------------------------------------------------------------------


def node_abs_path(root, node):
    """Absolute working directory for a node. The root node is the primary checkout."""
    return root if node["worktree"] is None else (root / node["worktree"]).resolve()


def depth(state, node_id):
    return len(state["nodes"][node_id]["choices"])


def caps_of(state):
    """Caps with defaults filled in, so a tree written by an older run still reads."""
    caps = dict(state["caps"])
    caps.setdefault("max_parallel", DEFAULT_MAX_PARALLEL)
    return caps


def leaf_ids(state):
    return [nid for nid, node in state["nodes"].items() if not node["children"]]


def resolve_node(state, root, explicit):
    """Pick the node to act on: --node, else the node owning cwd, else the root."""
    if explicit:
        if explicit not in state["nodes"]:
            die(f"unknown node {explicit!r}; try `fanout.py leaves`")
        return explicit
    cwd = Path.cwd().resolve()
    best = None
    for nid, node in state["nodes"].items():
        path = node_abs_path(root, node)
        if cwd == path or path in cwd.parents:
            # Deepest match wins: a worktree path is never a parent of the repo root.
            if best is None or len(str(path)) > len(str(node_abs_path(root, state["nodes"][best]))):
                best = nid
    return best or state["root"]


def choices_expr(node):
    return ",".join(f"{c['decision']}={c['option']}" for c in node["choices"]) or "-"


def descendant_leaves(state, node_id):
    node = state["nodes"][node_id]
    if not node["children"]:
        return [node_id]
    out = []
    for child in node["children"]:
        out.extend(descendant_leaves(state, child))
    return out


def parse_pairs(values, field_count, what):
    """Parse 'a:b' or 'a:b:c' option strings without splitting the prose tail."""
    parsed = []
    for raw in values or []:
        parts = raw.split(":", field_count - 1)
        if len(parts) != field_count:
            die(f"{what} must have {field_count} colon-separated fields: {raw!r}")
        parsed.append([p.strip() for p in parts])
    return parsed


# --------------------------------------------------------------------------
# commands
# --------------------------------------------------------------------------


def cmd_init(args):
    root = repo_root()
    path = state_path(root, args.issue)
    if path.exists() and not args.force:
        die(f"{rel(root, path)} already exists; use --force to start over")

    base = args.base or git("rev-parse", "HEAD", cwd=root)
    base = git("rev-parse", base, cwd=root)
    branch = git("rev-parse", "--abbrev-ref", "HEAD", cwd=root)

    max_leaves = min(args.max_leaves, CEILING_MAX_LEAVES)
    if args.max_leaves > CEILING_MAX_LEAVES:
        print(
            f"fanout: --max-leaves {args.max_leaves} exceeds the ceiling; "
            f"clamped to {CEILING_MAX_LEAVES}",
            file=sys.stderr,
        )

    state = {
        "version": STATE_VERSION,
        "issue": args.issue,
        "base_sha": base,
        "base_branch": branch,
        "caps": {
            "max_leaves": max_leaves,
            "max_depth": args.max_depth,
            "max_options": args.max_options,
            # How many leaf subagents may build at once. Not a safety cap like
            # the others - a calendar-time dial. Local, the binding constraint
            # is Docker (the Python suites each start Postgres via
            # testcontainers), so 2-3. In a cloud run each leaf gets its own
            # container and this can go to the leaf count: same wall clock as
            # one leaf, N times the spend. Recorded in state so a resumed
            # session honours the same number.
            "max_parallel": args.max_parallel,
        },
        "root": "n0",
        "nodes": {
            "n0": {
                "id": "n0",
                "parent": None,
                "branch": branch,
                "worktree": None,
                "choices": [],
                "children": [],
                "result": None,
            }
        },
        "decisions": {},
        "records": [],
        "refusals": [],
    }
    save(root, args.issue, state)
    print(f"initialized {args.issue} at {base[:12]} on branch {branch}")
    print(f"state: {rel(root, path)}")

    # The must-stop boundary is enforced by the `fanout-scope` commit hook.
    # Without installed hooks that enforcement is absent, and the run would look
    # identical - so say so here rather than discovering it from a leaf that
    # committed a migration.
    common = Path(git("rev-parse", "--git-common-dir", cwd=root))
    if not common.is_absolute():
        common = root / common
    if not (common / "hooks" / "pre-commit").exists():
        print(
            "fanout: WARNING - no commit hook installed, so the must-stop "
            "boundary is NOT enforced for this tree. Install the fanout-scope hook (see reference/decision-fanout.md).",
            file=sys.stderr,
        )

    # Same shape as the hook warning: say it at the moment someone is present.
    # A tree left behind by a run that died is invisible - gitignored, so
    # `git status` stays clean - and starting a new one is the likeliest time
    # anybody is looking.
    others = []
    for other in sorted((root / STATE_DIR / "fanout").glob("*/tree.json")):
        if other.parent.name == issue_slug(args.issue):
            continue
        try:
            blob = json.loads(other.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not blob.get("collapsed"):
            others.append(blob.get("issue", other.parent.name))
    if others:
        print(
            f"fanout: NOTE - {len(others)} other tree(s) still on disk: "
            f"{', '.join(others)}. `fanout.py status` lists them with size; "
            f"`abandon <issue>` removes one.",
            file=sys.stderr,
        )
    return 0


def cmd_fork(args):
    root = repo_root()
    with state_lock(root, args.issue):
        state = load(root, args.issue)
        caps = state["caps"]

        options = parse_pairs(args.option, 3, "--option 'slug:what it does:why you would pick it'")
        dropped = parse_pairs(args.drop, 2, "--drop 'slug:why it is dominated'")

        parent_id = resolve_node(state, root, args.parent)
        parent = state["nodes"][parent_id]

        if parent["children"]:
            die(f"node {parent_id} already forked; fork from one of its children instead")

        # --- refusals: cap checks happen before anything is created -------------
        refusal = None
        if len(options) < 2:
            refusal = f"only {len(options)} surviving option(s) - decide it and `record` instead"
        elif len(options) > caps["max_options"]:
            refusal = (
                f"{len(options)} options exceeds max_options={caps['max_options']}; "
                f"drop dominated options first"
            )
        elif depth(state, parent_id) + 1 > caps["max_depth"]:
            refusal = (
                f"depth would be {depth(state, parent_id) + 1}, "
                f"exceeding max_depth={caps['max_depth']}"
            )
        else:
            projected = len(leaf_ids(state)) - 1 + len(options)
            if projected > caps["max_leaves"]:
                refusal = (
                    f"would reach {projected} leaves, exceeding max_leaves={caps['max_leaves']}"
                )

        # A path check the model cannot reason its way around. If the work leading
        # up to this decision already crossed the boundary, the tree is illegitimate
        # before it exists, and forking would multiply a change that needed one
        # considered answer.
        if not refusal:
            parent_dir = node_abs_path(root, parent)
            touched = shortstat(parent_dir, state["base_sha"])["names"]
            touched += [
                line for line in
                git("diff", "--name-only", "--no-renames", state["base_sha"],
                    cwd=parent_dir, check=False).splitlines()
                if line.strip()
            ]
            touched += [
                line[3:].strip()
                for line in git("status", "--porcelain", cwd=parent_dir, check=False).splitlines()
            ]
            declared = list(args.touches or [])
            hits = must_stop_hits(touched + declared)
            if hits:
                listed = "; ".join(f"{path} ({reason})" for path, reason in hits[:4])
                refusal = f"must-stop boundary: {listed}"

        if refusal:
            state["refusals"].append(
                {
                    "node": parent_id,
                    "question": args.decision,
                    "source": args.source,
                    "options": [o[0] for o in options],
                    "reason": refusal,
                }
            )
            save(root, args.issue, state)
            print(f"fanout: REFUSED fan-out: {refusal}", file=sys.stderr)
            print(
                "fanout: recorded in the tree and rendered in the ledger. "
                "Ask the author via the ask tool instead.",
                file=sys.stderr,
            )
            return 3

        slugs = [o[0] for o in options]
        if len(set(slugs)) != len(slugs):
            die(f"duplicate option slugs: {slugs}")

        decision_id = next_id("d", state["decisions"])
        parent_dir = node_abs_path(root, parent)
        parent_head = git("rev-parse", "HEAD", cwd=parent_dir)
        # The parent stops being a leaf here, so it will never get a `result`. Its
        # own contribution is only measurable now, and the ledger needs it: an option
        # that forks again has to be described by what IT changed, not by summing the
        # leaves underneath it.
        parent["contribution"] = shortstat(parent_dir, parent.get("fork_sha") or state["base_sha"])

        # Preflight EVERY planned path before creating anything. This check used
        # to sit inside the creation loop, so a second option whose directory
        # already existed exited after the first had been created — orphaning it,
        # with nothing in tree.json for `abandon` to find it by. A check that can
        # fail belongs before the first side effect, not between them.
        planned = []
        for slug, what, why in options:
            trail = "-".join([*(c["option"] for c in parent["choices"]), slug])
            # `fan/<issue>/<trail>` and NOT `<issue>/fan/<trail>`: git refs are a
            # path hierarchy, so `refs/heads/alt-341` (the trunk branch, which the
            # repo convention already owns) makes `refs/heads/alt-341/fan/...`
            # unlockable. Putting `fan/` first keeps the whole tree in its own
            # namespace, groups every leaf under `git branch --list 'fan/*'`, and
            # can never collide with the branch the issue itself is on.
            branch = f"fan/{issue_slug(args.issue)}/{trail}"
            worktree_rel = Path(STATE_DIR) / "worktrees" / issue_slug(args.issue) / trail
            if (root / worktree_rel).exists():
                die(f"{worktree_rel} already exists; run `abandon` or clean it up first")
            planned.append((slug, what, why, branch, worktree_rel))

        created = []
        rollback = []
        # ONE rollback path for the whole level, rather than one guard per failure
        # mode. Creating a worktree, stamping its marker and recording it in state
        # are three steps that can each fail, and every partial level is an orphan
        # `abandon` cannot see. Catching BaseException covers the SystemExit that
        # `die()` raises as well as anything unanticipated, then re-raises so the
        # exit code and message are unchanged.
        try:
            for slug, what, why, branch, worktree_rel in planned:
                node_id = next_id("n", state["nodes"])
                choices = parent["choices"] + [{"decision": decision_id, "option": slug}]
                worktree_abs = root / worktree_rel

                add = subprocess.run(
                    ["git", "worktree", "add", "-b", branch, str(worktree_abs), parent_head],
                    cwd=str(root), capture_output=True, text=True,
                )
                if add.returncode != 0:
                    die(f"git worktree add {branch} failed: {add.stderr.strip()}")
                rollback.append((worktree_abs, branch))

                # Stamp the leaf with worktree-local config. Neither the branch
                # name nor the directory path is a reliable marker: `git checkout
                # --detach` erases the first and `git worktree move` erases the
                # second, and together they walked straight through the must-stop
                # gate. This lives in .git/worktrees/<name>/config.worktree,
                # which survives both.
                git("config", "extensions.worktreeConfig", "true", cwd=root)
                git("config", "--worktree", MARKER_KEY, args.issue, cwd=worktree_abs)

                state["nodes"][node_id] = {
                    "id": node_id,
                    "parent": parent_id,
                    "branch": branch,
                    "worktree": str(worktree_rel),
                    "choices": choices,
                    "children": [],
                    "result": None,
                    # The commit this option started from. Its diff against the
                    # leaf's HEAD is the option's own CONTRIBUTION, which is the
                    # number that actually discriminates between siblings — a diff
                    # against the base would include the shared trunk and make
                    # every option look alike.
                    "fork_sha": parent_head,
                }
                parent["children"].append(node_id)
                created.append((node_id, slug, what, why, branch, worktree_rel))
        except BaseException:
            for done_abs, done_branch in rollback:
                git("worktree", "remove", "--force", str(done_abs), cwd=root, check=False)
                git("branch", "-D", done_branch, cwd=root, check=False)
            git("worktree", "prune", cwd=root)
            raise

        state["decisions"][decision_id] = {
            "id": decision_id,
            "question": args.decision,
            "why_you": args.why_you,
            "source": args.source,
            "node": parent_id,
            "options": [
                {"slug": slug, "what": what, "why": why, "node": node_id}
                for node_id, slug, what, why, _, _ in created
            ],
            "dropped": [{"slug": slug, "reason": reason} for slug, reason in dropped],
            "recommend": None,
        }
        save(root, args.issue, state)

        print(f"{decision_id}: {args.decision}")
        for node_id, slug, _what, _why, branch, worktree_rel in created:
            print(f"  {node_id}  {slug:<16} {branch}")
            print(f"      cd {worktree_rel}")
        print(f"leaves now: {len(leaf_ids(state))}/{caps['max_leaves']}")
        return 0


def cmd_record(args):
    root = repo_root()
    with state_lock(root, args.issue):
        state = load(root, args.issue)
        node_id = resolve_node(state, root, args.node)
        if args.kind == "two-way" and not args.reversal:
            die("--kind two-way requires --reversal (the cost to undo it later)")
        state["records"].append(
            {
                "node": node_id,
                "kind": args.kind,
                "question": args.question,
                "answer": args.answer,
                "reversal": args.reversal or "",
                "source": args.source or "",
            }
        )
        save(root, args.issue, state)
        print(f"recorded {args.kind} decision on {node_id}")
        return 0


def cmd_result(args):
    root = repo_root()
    with state_lock(root, args.issue):
        state = load(root, args.issue)
        node_id = resolve_node(state, root, args.node)
        node = state["nodes"][node_id]
        if node["children"]:
            die(f"{node_id} is not a leaf; attach results to leaves only")
        if args.tests == "fail" and not args.failure:
            die("--tests fail requires --failure (the assertion or error, not a summary)")

        leaf_dir = node_abs_path(root, node)
        contribution = shortstat(leaf_dir, node.get("fork_sha") or state["base_sha"])
        total = shortstat(leaf_dir, state["base_sha"])

        node["result"] = {
            "tests": args.tests,
            "evidence": args.evidence,
            # Shape A's consequence test: an option described only as a code change
            # is not decidable by the person who has to live with it.
            "notice": args.notice,
            "reversible": args.reversible,
            "failure": args.failure or "",
            "lost": args.lost,
            "switch_cost": args.switch_cost,
            "risk": args.risk or "",
            "open_questions": list(args.open_question or []),
            "note": args.note or "",
            # Measured, not asserted.
            "contribution": contribution,
            "total": total,
            "dependencies": dependency_changes(total["names"]),
        }
        save(root, args.issue, state)
        print(
            f"{node_id} ({choices_expr(node)}): tests={args.tests} "
            f"contribution=+{contribution['added']}/-{contribution['removed']} "
            f"in {contribution['files']} file(s)"
        )
        if node["result"]["dependencies"]:
            print(f"  dependency manifests touched: {', '.join(node['result']['dependencies'])}")
        return 0


def cmd_recommend(args):
    root = repo_root()
    with state_lock(root, args.issue):
        state = load(root, args.issue)
        decision = state["decisions"].get(args.decision)
        if decision is None:
            die(f"unknown decision {args.decision!r}")
        slugs = [o["slug"] for o in decision["options"]]
        if args.option not in slugs:
            die(f"{args.option!r} is not an option of {args.decision}; have {slugs}")
        decision["recommend"] = {
            "slug": args.option,
            "reason": args.reason,
            # WRONG IF is what turns agreeing into a check rather than a shrug: a
            # recommendation with no stated falsifier is the one that gets
            # rubber-stamped. Required for that reason, not for completeness.
            "wrong_if": args.wrong_if,
            "if_silent": args.if_silent,
        }
        save(root, args.issue, state)
        print(f"{args.decision}: recommending {args.option}")
        return 0


def cmd_leaves(args):
    root = repo_root()
    state = load(root, args.issue)
    for node_id in sorted(leaf_ids(state)):
        node = state["nodes"][node_id]
        result = node["result"] or {}
        print(
            "\t".join(
                [
                    node_id,
                    choices_expr(node),
                    node["branch"],
                    result.get("tests", "no-result"),
                ]
            )
        )
    return 0


def cmd_ledger(args):
    root = repo_root()
    state = load(root, args.issue)
    text = render_ledger(state)
    out = state_dir(root, args.issue) / LEDGER_NAME
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(rel(root, out))
    return 0


def cmd_collapse(args):
    root = repo_root()
    with state_lock(root, args.issue):
        state = load(root, args.issue)

        choices = {}
        for pair in args.choose.split(","):
            pair = pair.strip()
            if not pair:
                continue
            if "=" not in pair:
                die(f"--choose expects d1=slug,d2=slug; got {pair!r}")
            key, value = pair.split("=", 1)
            choices[key.strip()] = value.strip()

        unknown = sorted(set(choices) - set(state["decisions"]))
        if unknown:
            die(f"unknown decision id(s): {unknown}; have {sorted(state['decisions'])}")

        # Deliberately NOT "every fanned decision must be answered". In a prefix
        # tree a decision only exists on the paths that reached it: the `redis` leaf
        # in one real ledger never met d2, so demanding a d2 answer would make
        # that whole path unselectable. The only rule that holds for every shape of
        # tree is that the given choices must single out exactly one leaf.
        matches = []
        for node_id in leaf_ids(state):
            node = state["nodes"][node_id]
            made = {c["decision"]: c["option"] for c in node["choices"]}
            if all(made.get(d) == o for d, o in choices.items()):
                matches.append(node_id)

        if len(matches) != 1:
            print(
                f"fanout: --choose resolved to {len(matches)} leaves, not 1",
                file=sys.stderr,
            )
            for node_id in sorted(matches):
                print(f"  {node_id}\t{choices_expr(state['nodes'][node_id])}", file=sys.stderr)
            if not matches:
                print(
                    "fanout: no leaf made exactly those choices - a path that never "
                    "reached a decision cannot be selected by answering it. Run "
                    "`fanout.py leaves` for the valid paths.",
                    file=sys.stderr,
                )
            else:
                print(
                    "fanout: add another decision to narrow it to one leaf",
                    file=sys.stderr,
                )
            return 4

        survivor_id = matches[0]
        survivor = state["nodes"][survivor_id]
        survivor_path = node_abs_path(root, survivor)

        cwd = Path.cwd().resolve()
        doomed = [
            node
            for nid, node in state["nodes"].items()
            if node["worktree"] is not None and nid != survivor_id
        ]
        for node in doomed:
            path = node_abs_path(root, node)
            if cwd == path or path in cwd.parents:
                die(
                    f"cwd is inside {node['worktree']}, which collapse would remove; "
                    f"cd to {root} first"
                )

        # Prune BEFORE deleting, not after. A worktree whose directory was
        # removed by hand is still registered, and git refuses to delete a branch
        # it believes is checked out somewhere - so the branch delete failed, and
        # with check=False that failure was swallowed while `removed` still
        # claimed it. Pruning first clears the stale registration.
        git("worktree", "prune", cwd=root)

        removed, kept_dirty, failed = [], [], []
        for node in doomed:
            path = node_abs_path(root, node)
            if path.exists():
                dirty = git("status", "--porcelain", cwd=path, check=False)
                if dirty and not args.force:
                    kept_dirty.append(node["worktree"])
                    continue
                git("worktree", "remove", "--force", str(path), cwd=root)
            proc = subprocess.run(
                ["git", "branch", "-D", node["branch"]],
                cwd=str(root), capture_output=True, text=True,
            )
            # Never report a deletion that did not happen: the whole point of
            # this command is that the author can trust what is left behind.
            if proc.returncode == 0:
                removed.append(node["branch"])
            else:
                failed.append((node["branch"], proc.stderr.strip().splitlines()[-1:]))

        git("worktree", "prune", cwd=root)

        state["collapsed"] = {
            "choose": choices,
            "survivor": survivor_id,
            "branch": survivor["branch"],
            "removed": removed,
            "kept_dirty": kept_dirty,
            "failed": [branch for branch, _err in failed],
        }
        save(root, args.issue, state)

        print(f"survivor: {survivor['branch']}")
        print(f"  path: {survivor['worktree'] or '.'}")
        print(f"  choices: {choices_expr(survivor)}")
        print(f"removed {len(removed)} branch(es)")
        if kept_dirty:
            print(
                "fanout: NOT fully collapsed. Kept (uncommitted changes, re-run "
                "with --force to drop): " + ", ".join(kept_dirty),
                file=sys.stderr,
            )
        for branch, err in failed:
            print(
                f"fanout: could NOT delete branch {branch}: "
                f"{err[0] if err else 'unknown error'}",
                file=sys.stderr,
            )
        print(f"next: rebase {survivor['branch']} onto current main, then continue execute-issue")
        # NOT exit 4, which means "the choice did not name exactly one leaf".
        # Here the choice was unambiguous and the survivor is correct; what
        # failed is the cleanup. Reusing 4 would make one code mean two
        # conditions, which is the ambiguous-signal defect this repo already
        # paid for once: a caller could not tell which to conclude.
        if kept_dirty or failed:
            return 6
        return 0


def cmd_abandon(args):
    root = repo_root()
    with state_lock(root, args.issue):
        state = load(root, args.issue)
        cwd = Path.cwd().resolve()
        for node in state["nodes"].values():
            if node["worktree"] is None:
                continue
            path = node_abs_path(root, node)
            if cwd == path or path in cwd.parents:
                die(f"cwd is inside {node['worktree']}; cd to {root} first")
            if path.exists():
                dirty = git("status", "--porcelain", cwd=path, check=False)
                if dirty and not args.force:
                    die(f"{node['worktree']} has uncommitted changes; re-run with --force")
                git("worktree", "remove", "--force", str(path), cwd=root)
            git("branch", "-D", node["branch"], cwd=root, check=False)
        git("worktree", "prune", cwd=root)

        directory = state_dir(root, args.issue)
        for child in sorted(directory.glob("*")):
            if child.is_file():
                child.unlink()
        directory.rmdir()

        # `fork` turns on extensions.worktreeConfig so the leaf marker is
        # readable. That is a persistent change to the developer's repo config
        # made as a side effect of running a skill, so undo it once the last tree
        # is gone - and only then, because a surviving tree still needs its
        # markers readable.
        remaining = sorted((root / STATE_DIR / "fanout").glob("*/tree.json"))
        if not remaining:
            git("config", "--unset", "extensions.worktreeConfig", cwd=root, check=False)
            print("that was the last tree; extensions.worktreeConfig unset")

        print(f"abandoned {args.issue}")
        return 0


def registered_fan_worktree(cwd):
    """The issue whose tree records this worktree, from tree.json rather than config.

    Returns the issue slug, or None. Deliberately independent of repo config and
    of the current path: it keys on the linked worktree's git-dir name, which git
    assigns when the worktree is created and keeps across `git worktree move`.
    """
    git_dir = Path(git("rev-parse", "--absolute-git-dir", cwd=cwd, check=False) or ".")
    if git_dir.parent.name != "worktrees":
        return None
    name = git_dir.name
    try:
        root = repo_root(cwd)
    except SystemExit:
        return None
    for state_file in sorted((root / STATE_DIR / "fanout").glob("*/tree.json")):
        try:
            state = json.loads(state_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for node in state.get("nodes", {}).values():
            recorded = node.get("worktree")
            if recorded and Path(recorded).name == name:
                return state.get("issue") or state_file.parent.name
    return None


def cmd_check_scope(args):
    """Pre-commit gate: no commit on a fan/* branch may cross the must-stop line.

    This is the enforcement that does not depend on anybody remembering a rule.
    A skill doc or a CLAUDE.md paragraph is a prompt: usually followed, never
    guaranteed, and impossible to audit after the fact. This runs on every
    commit, reads the boundary from cadence.toml, and cannot be reasoned with.

    A no-op outside a fan/* branch, so it is safe to run always.
    """
    cwd = Path.cwd()
    branch = git("rev-parse", "--abbrev-ref", "HEAD", cwd=cwd, check=False)
    # The branch name alone is not enough to know you are in a fanned option.
    # `git checkout --detach` inside a leaf makes --abbrev-ref print "HEAD", and
    # the gate used to exit 0 on that - so detaching was a one-command bypass of
    # the whole must-stop boundary. The worktree's LOCATION cannot be detached
    # from, so check that too.
    toplevel = git("rev-parse", "--show-toplevel", cwd=cwd, check=False)
    in_fan_worktree = "/.cadence/worktrees/" in (toplevel.replace("\\", "/") + "/")
    # The authoritative marker, because it is the only one that survives both
    # `git checkout --detach` (which erases the branch name) and
    # `git worktree move` (which erases the path). Those two together were a
    # complete bypass; the branch and path checks stay as fallbacks for a tree
    # created before the marker existed.
    marked = git("config", "--worktree", "--get", MARKER_KEY, cwd=cwd, check=False)
    # Config is mutable, so the marker alone is not enough either: unsetting it
    # (or turning extensions.worktreeConfig off) after a move and a detach put the
    # leaf back out of scope. This last check derives scope from the tool's own
    # state instead of from anything a caller can edit in the repo — a linked
    # worktree's git dir is <common>/worktrees/<name>, and <name> stays the
    # original leaf directory name across a move, so it can be matched against
    # the worktrees recorded in tree.json.
    registered = registered_fan_worktree(cwd)
    if not (marked or registered or branch.startswith("fan/") or in_fan_worktree):
        return 0
    if branch.startswith("fan/"):
        where = branch
    elif registered and not marked:
        where = f"a fanned worktree for {registered} (marker removed) at {toplevel}"
    elif marked:
        where = f"a fanned worktree for {marked} (detached or moved) at {toplevel}"
    else:
        where = f"detached HEAD in {toplevel}"

    # `--no-renames` is load-bearing, not a style choice. With rename detection
    # on, `git diff --cached --name-only` reports only the DESTINATION of a
    # rename, so `git mv api/event-schema.yaml api/moved.yaml` shows
    # one unprotected path and sails through — while being the most destructive
    # way to touch a contract. Disabling detection reports the delete and the add
    # separately, so the protected source path is visible.
    staged = [
        line for line in
        git("diff", "--cached", "--name-only", "--no-renames", cwd=cwd, check=False).splitlines()
        if line.strip()
    ]
    hits = must_stop_hits(staged)
    if not hits:
        return 0

    print(
        f"fanout: refusing this commit on `{where}`: a fanned option must not "
        f"cross the must-stop boundary.",
        file=sys.stderr,
    )
    for path, reason in hits:
        print(f"  {path}  -  {reason}", file=sys.stderr)
    print(
        "\nA decision reaching these paths is a question for the author, not a "
        "fan-out: N variants of a contract or schema change multiply reviewers "
        "rather than options. Abandon the tree (`fanout.py abandon`) and ask via "
        f"{ASK_TOOL}. The boundary is [[must_stop]] in cadence.toml - one "
        "definition, so there is one thing to change.",
        file=sys.stderr,
    )
    return 5


def tree_size_kb(root, issue):
    """Disk used by a tree's worktrees. `du` in one subprocess, not os.walk."""
    path = root / STATE_DIR / "worktrees" / issue_slug(issue)
    if not path.exists():
        return None
    out = subprocess.run(
        ["du", "-sk", str(path)], capture_output=True, text=True, check=False
    )
    if out.returncode != 0:
        return None
    try:
        return int(out.stdout.split()[0])
    except (ValueError, IndexError):
        return None


def cmd_status_all(root):
    """Every tree on disk, for a session that does not know what to look for.

    The gap this closes: every other command takes an issue id, and the
    worktrees are gitignored so `git status` is clean while hundreds of MB sit
    there. A run that dies between `fork` and `collapse` leaves a tree nothing
    points at — invisible unless you already knew to ask about that ticket.
    """
    directory = root / STATE_DIR / "fanout"
    trees = sorted(directory.glob("*/tree.json")) if directory.exists() else []
    if not trees:
        print("no fan-out trees on disk")
        return 0

    print(f"{len(trees)} tree(s) under {rel(root, directory)}:")
    total = 0
    for state_file in trees:
        try:
            state = json.loads(state_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"  {state_file.parent.name}\tUNREADABLE\t{exc}")
            continue
        issue = state.get("issue", state_file.parent.name)
        leaves = leaf_ids(state)
        if state.get("collapsed"):
            status = "collapsed"
        elif any(state["nodes"][n]["result"] is None for n in leaves):
            status = "building"
        else:
            status = "awaiting-decision"
        size = tree_size_kb(root, issue)
        total += size or 0
        stamp = time.strftime("%Y-%m-%d %H:%M", time.localtime(state_file.stat().st_mtime))
        size_text = f"{size / 1024:.0f}MB" if size else "-"
        noun = "leaf" if len(leaves) == 1 else "leaves"
        print(f"  {issue}\t{status}\t{len(leaves)} {noun}\t{size_text}\tlast touched {stamp}")

    if total:
        print(f"total on disk: {total / 1024:.0f}MB")
    print("`status <issue>` for one tree; `abandon <issue>` to remove one.")
    return 0


def cmd_status(args):
    """The resume contract: what state is this tree in, and what happens next.

    A fresh session (or a human back from a night's sleep) has no memory of the
    run that built the tree. Everything needed to pick it up has to be
    derivable from state, not from the transcript that is gone.
    """
    root = repo_root()
    if not args.issue:
        return cmd_status_all(root)
    state = load(root, args.issue)
    leaves = sorted(leaf_ids(state))
    collapsed = state.get("collapsed")
    unresolved = [n for n in leaves if state["nodes"][n]["result"] is None]
    unranked = [d for d in sorted(state["decisions"])
                if not state["decisions"][d].get("recommend")]

    print(f"issue: {state['issue']}")
    print(f"base: {state['base_sha'][:12]} on {state['base_branch']}")

    if collapsed:
        print("state: collapsed")
        print(f"survivor: {collapsed['branch']}")
        print(f"chosen: {','.join(f'{k}={v}' for k, v in sorted(collapsed['choose'].items()))}")
        print(f"removed: {len(collapsed['removed'])} branch(es)")
        leftovers = list(collapsed.get("kept_dirty") or []) + list(collapsed.get("failed") or [])
        if leftovers:
            # `collapsed` used to imply "nothing else is left", which is a lie
            # whenever a doomed worktree was dirty or a branch delete failed.
            print(f"NOT fully collapsed - still present: {', '.join(leftovers)}")
            print("      re-run collapse with --force, or clean these up by hand.")
        print("next: rebase the survivor onto current main, then continue")
        print("      execute-issue from step 6 (pre-commit + tests, then code-review).")
        return 0

    print(f"state: {'building' if unresolved else 'awaiting-decision'}")
    print(f"decisions fanned: {len(state['decisions'])}  leaves: {len(leaves)}")
    print(f"max parallel leaf subagents: {caps_of(state)['max_parallel']}")
    if state["records"]:
        print(f"decided without fanning: {len(state['records'])}")
    if state["refusals"]:
        print(f"refused fan-outs (asked instead): {len(state['refusals'])}")
    if unresolved:
        print(f"leaves with no result yet: {', '.join(unresolved)}")
        print("next: finish the evidence gate in each leaf, then `ledger`.")
        return 0
    if unranked:
        print(f"decisions with no recommendation: {', '.join(unranked)}")
        print("next: record a recommendation for each, then `ledger`.")
        return 0

    print("next: the author picks a path. One of:")
    for node_id in leaves:
        node = state["nodes"][node_id]
        choose = ",".join(f"{c['decision']}={c['option']}" for c in node["choices"])
        print(f"  python3 {FANOUT_TOOL} collapse {state['issue']} --choose {choose}")
    return 0


def cmd_notify(args):
    """Post a Slack-shaped digest of the ledger, and print it locally too.

    Slack is a convenience here and deliberately not the delivery guarantee.
    C-12: a post can succeed into a channel nobody watches, and nothing in
    the exit code can tell you that. So this always prints the digest to stdout
    (the session that ran it is the channel that definitely has a reader), and a
    Slack failure is reported without failing the command.
    """
    root = repo_root()
    state = load(root, args.issue)
    digest = render_digest(state, root)
    if len(digest) > DIGEST_LIMIT:
        # Degrade deliberately, and keep the two things that matter: which option
        # is recommended, and the command to take it. The full detail is in the
        # ledger, whose path the digest carries. `limit` makes this a bound rather
        # than a reduction: dropping the per-option detail shrinks the digest but
        # every field left is still unbounded prose.
        digest = render_digest(state, root, compact=True, limit=DIGEST_LIMIT)
    print(digest)

    if args.print_only:
        return 0

    script = root / ASK_TOOL
    if not script.exists():
        print(f"fanout: {ASK_TOOL} not found; digest printed above only", file=sys.stderr)
        return 0
    try:
        proc = subprocess.run(  # noqa: S603
            ["python3", str(script), "notify", digest, "--context", f"{state['issue']} fanout"],
            capture_output=True,
            text=True,
            # The docstring and the workflow doc both promise this does not
            # block. Without a timeout a hung Slack call stalls the last step of
            # an unattended run forever, which is the promise inverted.
            timeout=60,
        )
    except subprocess.TimeoutExpired:
        print(
            "fanout: ask-tool notify timed out after 60s. The digest above is still "
            "the record; put it in front of the author another way.",
            file=sys.stderr,
        )
        return 0
    except OSError as exc:
        # The launch itself can fail without the child ever running: no python3
        # on PATH, or an argument list over ARG_MAX (E2BIG). Both must degrade
        # like a nonzero exit, because `notify` promises a Slack problem never
        # fails the command.
        print(
            f"fanout: could not launch ask-tool notify ({exc.__class__.__name__}: "
            f"{exc}). The digest above is still the record; put it in front of "
            f"the author another way.",
            file=sys.stderr,
        )
        return 0
    if proc.returncode != 0:
        print(
            f"fanout: ask-tool notify failed ({proc.returncode}): "
            f"{proc.stderr.strip() or proc.stdout.strip()}. The digest above is "
            f"still the record; put it in front of the author another way.",
            file=sys.stderr,
        )
        return 0
    print("\nfanout: posted to Slack. A successful post is not a delivered one "
          "(C-12) - say it in the session too.", file=sys.stderr)
    return 0


def render_digest(state, root, compact=False, limit=None):
    """Shape A over Slack: mrkdwn, no tables, and NUMBERED options.

    Slack does not render markdown tables, and `human-brief` asks for numbered
    options over Slack so a reply can be one token. The content is the same
    brief either way - only the rendering changes.
    """
    issue = state["issue"]
    leaves = sorted(leaf_ids(state))
    out = [f"*{issue}* - {len(state['decisions'])} decision(s) need an answer."]

    for decision_id in sorted(state["decisions"]):
        decision = state["decisions"][decision_id]
        out.append("")
        out.append(f"*{decision_id.upper()} - {decision['question']}*")
        out.append(f"_Why you: {decision.get('why_you') or 'not recorded'}_")
        for index, option in enumerate(decision["options"], start=1):
            cells = option_cells(state, option)
            out.append(f"  *{index}. {option['slug']}* - {option['what']}")
            if compact:
                continue
            out.append(f"      you would notice: {cells['notice']}")
            out.append(f"      cost & risk: {cells['cost']}")
            out.append(f"      reversible: {cells['reversible']}")
        recommend = decision.get("recommend")
        if recommend:
            out.append(f"  RECOMMEND `{recommend['slug']}` - {recommend['reason']}")
            out.append(f"  WRONG IF: {recommend.get('wrong_if') or 'not recorded'}")
            out.append(f"  IF SILENT: {recommend.get('if_silent') or 'not recorded'}")
        else:
            out.append("  RECOMMEND: none recorded")

    if compact:
        out.append("")
        out.append("_Shortened for Slack; the full brief is in the ledger._")

    # Split here so the bound below can trim the discussion while keeping the
    # part that is actionable. Compact mode drops the per-option detail but every
    # remaining field — the question, why-you, the recommendation, WRONG IF, IF
    # SILENT — is still unbounded prose, so compacting reduces the size without
    # bounding it.
    head = list(out)
    out = []
    out.append("")
    out.append("Reply with the option numbers, or run one of these yourself:")
    out.append("```")
    for node_id in leaves:
        node = state["nodes"][node_id]
        choose = ",".join(f"{c['decision']}={c['option']}" for c in node["choices"])
        out.append(f"python3 {FANOUT_TOOL} collapse {issue} --choose {choose}")
    out.append("```")
    out.append(f"Full ledger: {rel(root, state_dir(root, issue) / LEDGER_NAME)}")
    tail = "\n".join(out)
    body = "\n".join(head)
    if limit is None:
        return f"{body}\n{tail}"
    return clamp_digest(body, tail, limit)


def clamp_digest(body, tail, limit):
    """Trim the discussion to fit, never the commands or the ledger pointer.

    The tail is what the author acts on, so it is preserved whole even if that
    means the digest carries almost none of the reasoning: the ledger has all of
    it, and the message says where. Trimming from the end instead would leave a
    digest that reads fine and cannot be acted on.
    """
    marker = "\n_[trimmed for chat: read the ledger for the full brief]_"
    room = limit - len(tail) - len(marker) - 1
    if len(body) <= room:
        return f"{body}\n{tail}"
    if room <= 0:
        # Pathological: the commands alone exceed the limit. Send them anyway —
        # a digest without them is useless, and Slack will handle the length.
        return tail
    kept = body[:room]
    cut = kept.rfind("\n")
    if cut > 0:
        kept = kept[:cut]
    return f"{kept}{marker}\n{tail}"


# --------------------------------------------------------------------------
# ledger rendering
# --------------------------------------------------------------------------


def cell(text):
    """Make prose safe inside a markdown table cell."""
    return (text or "").replace("|", "\\|").replace("\n", " ").strip() or "-"


def fmt_stat(stat):
    if not stat or not stat["files"]:
        return "no change"
    return f"+{stat['added']}/-{stat['removed']} in {stat['files']} file(s)"


def fmt_files(names, limit=6):
    if not names:
        return "-"
    shown = ", ".join(f"`{n}`" for n in names[:limit])
    if len(names) > limit:
        shown += f" (+{len(names) - limit} more)"
    return shown


def option_cells(state, option):
    """The Shape A row for one option.

    The hard case is an option that forked again underneath. Its leaves each
    answer a LATER question, so summing their `notice` and `cost` produces a cell
    describing the wrong decision — "retries every 5 seconds; retries spread out"
    read as the consequence of choosing an in-memory counter, which is nonsense.
    So a forked option is described by what IT changed, and the cell says plainly
    that the rest depends on the next question.
    """
    node = state["nodes"][option["node"]]
    leaves = sorted(descendant_leaves(state, option["node"]))

    # The simple case: this option is a leaf, so its result describes it exactly.
    if leaves == [option["node"]]:
        result = node["result"]
        if not result:
            return {"notice": "not built yet", "cost": "not measured", "reversible": "unknown"}
        costs = [f"{(result.get('contribution') or {}).get('added', 0)} lines added"]
        if result.get("dependencies"):
            costs.append(f"needs {', '.join(result['dependencies'])}")
        if result.get("risk"):
            costs.append(result["risk"])
        if result["tests"] == "fail":
            costs.append("tests do not pass")
        return {
            "notice": result.get("notice") or "nothing a user would see",
            "cost": "; ".join(costs),
            "reversible": result.get("reversible", "unknown"),
        }

    # The forked case. Describe this option's own change, and defer the rest.
    child_decision = next(
        (d for d in sorted(state["decisions"])
         if state["decisions"][d]["node"] == option["node"]),
        None,
    )
    contribution = node.get("contribution") or {}
    costs = [f"{contribution.get('added', 0)} lines added"]
    deps = dependency_changes(contribution.get("names") or [])
    if deps:
        costs.append(f"needs {', '.join(deps)}")
    if child_decision:
        costs.append(f"then {child_decision.upper()} still has to be answered")

    results = [state["nodes"][n]["result"] for n in leaves]
    present = [r for r in results if r]
    reversible = {r.get("reversible", "unknown") for r in present} or {"unknown"}
    return {
        "notice": (
            f"depends on {child_decision.upper()}" if child_decision
            else "depends on the next decision"
        ),
        "cost": "; ".join(costs),
        "reversible": reversible.pop() if len(reversible) == 1 else "depends on the next decision",
    }


def render_ledger(state):
    issue = state["issue"]
    caps = state["caps"]
    leaves = sorted(leaf_ids(state))
    lines = []

    lines.append(f"# Fan-out ledger: {issue}")
    lines.append("")
    lines.append(
        f"{len(state['decisions'])} decision(s) need an answer. "
        f"{len(state['records'])} were decided without asking. "
        f"{len(leaves)} version(s) of the change were built and are waiting."
    )
    lines.append("")
    lines.append(
        "Nothing has been pushed and nothing has a pull request. Read the "
        "decisions, then run one command from *Choose a path*."
    )
    lines.append("")

    if not state["decisions"]:
        lines.append("No decision was fanned out.")
        lines.append("")

    # One Shape A brief per decision (`human-brief`,
    # reference/human-brief.md). The table cells stay plain
    # English and every file:line, branch name and node id lives in the evidence
    # line underneath, because a cell full of jargon is what makes a ledger
    # readable by an agent and not by the person deciding.
    for decision_id in sorted(state["decisions"]):
        decision = state["decisions"][decision_id]
        lines.append(f"## {decision_id.upper()}")
        lines.append("")
        lines.append(f"**DECISION:** {decision['question']}")
        lines.append("")
        lines.append(f"**WHY YOU:** {decision.get('why_you') or 'not recorded'}")
        lines.append("")
        lines.append(
            "| Option | In plain English | What you would notice | Cost & risk | Reversible? |"
        )
        lines.append("|---|---|---|---|---|")
        for option in decision["options"]:
            cells = option_cells(state, option)
            lines.append(
                f"| `{option['slug']}` | {cell(option['what'])} | {cell(cells['notice'])} | "
                f"{cell(cells['cost'])} | {cells['reversible']} |"
            )
        lines.append("")
        recommend = decision.get("recommend")
        if recommend:
            lines.append(f"**RECOMMEND:** `{recommend['slug']}` - {recommend['reason']}")
            lines.append("")
            lines.append(f"**WRONG IF:** {recommend.get('wrong_if') or 'not recorded'}")
            lines.append("")
            lines.append(f"**IF SILENT:** {recommend.get('if_silent') or 'not recorded'}")
        else:
            lines.append(
                "**RECOMMEND:** none recorded. The options are unranked, which "
                "means this decision was handed back rather than argued."
            )
        lines.append("")
        evidence = [f"came up at `{decision['source']}`"]
        for option in decision["options"]:
            carriers = ", ".join(f"`{n}`" for n in sorted(descendant_leaves(state, option["node"])))
            evidence.append(f"`{option['slug']}` is built in {carriers}")
        lines.append(f"*Evidence: {'; '.join(evidence)}.*")
        lines.append("")
        for option in decision["options"]:
            lines.append(f"*Why you would pick `{option['slug']}`: {option['why']}*")
            lines.append("")
        if decision["dropped"]:
            lines.append("*Considered and dropped before building:*")
            lines.append("")
            for drop in decision["dropped"]:
                lines.append(f"- `{drop['slug']}` - {drop['reason']}")
            lines.append("")

    lines.append("## Choose a path")
    lines.append("")
    lines.append("Run exactly one of these, from the repository root:")
    lines.append("")
    lines.append("```bash")
    for node_id in leaves:
        node = state["nodes"][node_id]
        choose = ",".join(f"{c['decision']}={c['option']}" for c in node["choices"])
        # Per leaf rather than one `d1=<slug>,d2=<slug>` template: a leaf that
        # never reached a decision has no answer to give for it, so the generic
        # form would print a command that matches nothing.
        lines.append(
            f"python3 {FANOUT_TOOL} collapse {issue} --choose {choose}   # {node_id}"
        )
    lines.append("```")
    lines.append("")
    lines.append(
        "That keeps the one version you picked, deletes the others, and prints "
        "what happens next. If the answer is none of them, run `abandon` instead."
    )
    lines.append("")

    if state["records"]:
        lines.append("## Decided without asking you")
        lines.append("")
        lines.append("| Question | Answer | Cost to reverse |")
        lines.append("|---|---|---|")
        for record in state["records"]:
            lines.append(
                f"| {cell(record['question'])} | {cell(record['answer'])} | "
                f"{cell(record['reversal'])} |"
            )
        lines.append("")

    if state["refusals"]:
        lines.append("## Refused to fan out (asked instead)")
        lines.append("")
        for refusal in state["refusals"]:
            options = ", ".join(f"`{s}`" for s in refusal["options"]) or "-"
            lines.append(
                f"- **{refusal['question']}** - {refusal['reason']}. "
                f"Not built: {options}. Came up at `{refusal['source']}`."
            )
        lines.append("")

    # Everything below is the audit trail. Deciding should not require it, which
    # is why it sits under the commands rather than above them.
    lines.append("---")
    lines.append("")
    lines.append("## Detail (not needed to decide)")
    lines.append("")
    lines.append(
        f"Base `{state['base_sha'][:12]}` on `{state['base_branch']}`; "
        f"{len(leaves)}/{caps['max_leaves']} leaves, "
        f"up to {caps_of(state)['max_parallel']} built in parallel."
    )
    lines.append("")
    for node_id in leaves:
        node = state["nodes"][node_id]
        result = node["result"]
        lines.append(f"### `{node_id}` - {choices_expr(node)}")
        lines.append("")
        lines.append(f"Branch `{node['branch']}` at `{node['worktree'] or '.'}`")
        lines.append("")
        if result is None:
            lines.append(
                "**No result recorded.** The evidence gate never ran here, so this "
                "path is unranked: treat it as unbuilt rather than as neutral."
            )
            lines.append("")
            continue
        tests = result["tests"]
        label = "**FAIL**" if tests == "fail" else f"**{tests}**"
        lines.append(f"- tests: {label} - {result.get('evidence') or 'no evidence recorded'}")
        if result.get("failure"):
            lines.append(f"  - failure: `{result['failure']}`")
        lines.append(
            f"- contributes: {fmt_stat(result.get('contribution'))} "
            f"(this option alone) · total vs base: {fmt_stat(result.get('total'))}"
        )
        deps = result.get("dependencies") or []
        lines.append(
            f"- new/changed dependency manifests: "
            f"{', '.join('`' + d + '`' for d in deps) if deps else 'none'}"
        )
        lines.append(f"- what it lost: {result['lost']}")
        lines.append(
            f"- cost to switch off this option later: "
            f"{result.get('switch_cost') or 'not recorded'} "
            f"({result.get('reversible', 'unknown')})"
        )
        if result.get("risk"):
            lines.append(f"- risk: {result['risk']}")
        for question in result.get("open_questions") or []:
            lines.append(f"- open question: {question}")
        if result.get("note"):
            lines.append(f"- note: {result['note']}")
        contribution = result.get("contribution") or {}
        lines.append(f"- files: {fmt_files(contribution.get('names') or [])}")
        lines.append("")

    failing = [
        n for n in leaves if (state["nodes"][n]["result"] or {}).get("tests") == "fail"
    ]
    if failing:
        lines.append(
            "A leaf whose tests will not go green is an answer, not a gap: "
            f"{', '.join('`' + n + '`' for n in failing)} is evidence against that "
            "option, and its failure line above says why."
        )
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def rel(root, path):
    try:
        return str(Path(path).resolve().relative_to(root))
    except ValueError:
        return str(path)


# --------------------------------------------------------------------------
# argument parsing
# --------------------------------------------------------------------------


def build_parser():
    parser = argparse.ArgumentParser(
        prog="fanout.py",
        description="Decision fan-out tree for autonomous execution.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("init", help="pin the base commit and create the root node")
    p.add_argument("issue")
    p.add_argument("--base", help="base commit (default: HEAD)")
    p.add_argument("--max-leaves", type=int, default=DEFAULT_MAX_LEAVES)
    p.add_argument("--max-depth", type=int, default=DEFAULT_MAX_DEPTH)
    p.add_argument("--max-options", type=int, default=DEFAULT_MAX_OPTIONS)
    p.add_argument(
        "--max-parallel",
        type=int,
        default=DEFAULT_MAX_PARALLEL,
        help="leaf subagents building at once. 2-3 locally (Docker is the limit); "
             "up to the leaf count in a cloud run, which trades spend for wall clock",
    )
    p.add_argument("--force", action="store_true", help="overwrite an existing tree")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("fork", help="branch one worktree per surviving option")
    p.add_argument("issue")
    p.add_argument("--decision", required=True, help="the question being deferred")
    p.add_argument(
        "--why-you",
        required=True,
        help="one sentence: why the agent cannot settle this. Shape A's WHY YOU",
    )
    p.add_argument("--source", required=True, help="file:line that forced it")
    p.add_argument(
        "--option",
        action="append",
        required=True,
        metavar="SLUG:WHAT:WHY",
        help="repeatable; WHY is mandatory so dominated options get dropped, not built",
    )
    p.add_argument(
        "--drop",
        action="append",
        metavar="SLUG:REASON",
        help="repeatable; an option ruled out before forking",
    )
    p.add_argument("--parent", help="node to fork from (default: the node owning cwd)")
    p.add_argument(
        "--touches",
        action="append",
        metavar="PATH",
        help="repeatable; paths the options will change. Checked against the "
             "must-stop boundary before anything is created",
    )
    p.set_defaults(func=cmd_fork)

    p = sub.add_parser("record", help="log a decision that does NOT get a branch")
    p.add_argument("issue")
    p.add_argument("--kind", required=True, choices=RECORD_KINDS)
    p.add_argument("--question", required=True)
    p.add_argument("--answer", required=True)
    p.add_argument("--reversal", help="cost to undo later (required for two-way)")
    p.add_argument("--source")
    p.add_argument("--node")
    p.set_defaults(func=cmd_record)

    p = sub.add_parser("result", help="attach the evidence gate outcome to a leaf")
    p.add_argument("issue")
    p.add_argument("--tests", required=True, choices=TESTS_CHOICES)
    p.add_argument(
        "--evidence",
        required=True,
        help="the command run and what it reported, e.g. "
             "'pytest -q: 412 passed'. Not 'tests pass'",
    )
    p.add_argument("--failure", help="the assertion or error text; required when tests fail")
    p.add_argument(
        "--notice",
        required=True,
        help="what a user or operator would NOTICE if this option ships. Plain "
             "English, no file names, no type names - Shape A's consequence test",
    )
    p.add_argument(
        "--reversible",
        required=True,
        choices=("yes", "one-way"),
        help="can this be undone later without a migration or a rewrite?",
    )
    p.add_argument("--lost", required=True, help="what choosing this option forecloses")
    p.add_argument(
        "--switch-cost",
        required=True,
        help="what it would cost to move off this option later. The author is "
             "picking a door; they need to know how hard it shuts",
    )
    p.add_argument("--risk", help="what could still go wrong with this option")
    p.add_argument(
        "--open-question",
        action="append",
        help="repeatable; something this leaf could not settle",
    )
    p.add_argument("--note")
    p.add_argument("--node")
    p.set_defaults(func=cmd_result)

    p = sub.add_parser("recommend", help="name the option you would ship")
    p.add_argument("issue")
    p.add_argument("--decision", required=True)
    p.add_argument("--option", required=True)
    p.add_argument("--reason", required=True, help="one sentence for the recommendation")
    p.add_argument(
        "--wrong-if",
        required=True,
        help="the ONE fact that would flip this recommendation. Shape A's WRONG IF; "
             "a recommendation without a falsifier gets rubber-stamped",
    )
    p.add_argument(
        "--if-silent",
        required=True,
        help="what happens if the author never answers. Shape A's IF SILENT",
    )
    p.set_defaults(func=cmd_recommend)

    p = sub.add_parser("leaves", help="list leaves and their decision paths")
    p.add_argument("issue")
    p.set_defaults(func=cmd_leaves)

    p = sub.add_parser("ledger", help="render LEDGER.md from tree state")
    p.add_argument("issue")
    p.set_defaults(func=cmd_ledger)

    p = sub.add_parser("collapse", help="keep the chosen leaf, delete the rest")
    p.add_argument("issue")
    p.add_argument("--choose", required=True, metavar="d1=slug,d2=slug")
    p.add_argument("--force", action="store_true", help="drop worktrees with uncommitted work")
    p.set_defaults(func=cmd_collapse)

    p = sub.add_parser(
        "check-scope",
        help="pre-commit gate: refuse a fan/* commit that crosses the must-stop boundary",
    )
    p.set_defaults(func=cmd_check_scope)

    p = sub.add_parser(
        "status",
        help="state of one tree, or every tree on disk when no issue is given",
    )
    p.add_argument("issue", nargs="?")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("notify", help="post a Slack digest of the ledger (and print it)")
    p.add_argument("issue")
    p.add_argument("--print-only", action="store_true", help="render locally, do not post")
    p.set_defaults(func=cmd_notify)

    p = sub.add_parser("abandon", help="remove every worktree, branch, and the state dir")
    p.add_argument("issue")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_abandon)

    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
