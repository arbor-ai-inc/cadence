#!/usr/bin/env python3
"""check_no_leaks.py - fail if anything from the originating private repo survives.

Cadence was extracted from a private production codebase. Publishing it by
reading and editing is how a company name survives into a public repo, so this
check exists instead: the gate is a script that fails, not a reviewer who
skims. That is the same argument cadence itself makes about guidance
(reference/retro-synthesis.md step 5), applied to its own release.

Every pattern below was measured against the source tree before extraction.
The counts in the comments are what was there at fork time, so a regression is
recognisable rather than merely nonzero.

The private names are not written out in this file. A rule is a generic shape
(any `XX-123` id, any `#channel`, any email domain) plus the digests of the
private values that shape must not carry. Plain patterns name nothing private:
generic shapes, the company name, which the licence already attributes, and
public model names.
That obscures the names; it does not keep them secret. Most are short common
words, so anyone who guesses one can confirm it against its digest.

Usage:
    check_no_leaks.py               # scan the whole repo; what CI and pre-commit run
    check_no_leaks.py --list        # print every rule and where it is exempt
    check_no_leaks.py path ...      # scan only these paths (pre-commit passes files)
    check_no_leaks.py --hash NAME   # the digest to list a new private name under

Exit codes:
    0  clean
    1  a leak, or a usage error
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# Attribution is deliberate and narrow: cadence is published BY the company, so
# its name belongs in the licence, the plugin author block and the README, and
# nowhere else. Any other pattern below gets
# no exemption at all -- issue ids, internal paths, infra slugs and private
# model aliases are leaks wherever they appear.
ATTRIBUTION_OK = frozenset({
    "LICENSE",
    "NOTICE",
    "README.md",
    ".claude-plugin/plugin.json",
    ".claude-plugin/marketplace.json",
})


@dataclass(frozen=True)
class Rule:
    """One leak class. `exempt` is a set of repo-relative POSIX paths."""

    name: str
    pattern: str
    why: str
    exempt: frozenset = field(default_factory=frozenset)
    flags: int = re.IGNORECASE
    # When set, `pattern` only finds candidates, and a candidate is a leak only
    # if the digest of its key is listed. A hashed pattern is one lookahead,
    # `(?=(HIT))`, so it is tried at every position and one candidate can never
    # swallow the next. Group 1 is what gets reported; the key is the first
    # later group that matched, or group 1 when there is none.
    hashed: frozenset = field(default_factory=frozenset)
    # Also test every prefix of the key, for a value the private pattern did
    # not end at a boundary: `@org-team` still carries `@org`.
    prefixes: bool = False

    def compiled(self) -> re.Pattern:
        return re.compile(self.pattern, self.flags)


def digest(text: str) -> str:
    """What a hashed rule stores: `check_no_leaks.py --hash <name>` prints it.

    It keeps a name from being read off this file, not from being guessed: anyone
    can hash a candidate and compare.
    """
    return hashlib.sha256(text.lower().encode()).hexdigest()[:16]


def key_group(m: re.Match) -> int:
    """The group a hashed rule judges: the first after group 1 that matched."""
    return next((i for i in range(2, len(m.groups()) + 1) if m.group(i) is not None), 1)


def matches(rule: Rule, text: str, listed: frozenset | None = None):
    """Yield the (start, end) span of every leak of `rule` in `text`.

    A plain rule leaks on every match. A hashed rule leaks only where a key's
    digest is in `listed` (default: the rule's own list); ignored for a plain rule.
    """
    if not rule.hashed:  # `listed` applies to hashed rules only
        for m in rule.compiled().finditer(text):
            yield m.span()
        return
    listed = rule.hashed if listed is None else listed
    seen = set()
    for m in rule.compiled().finditer(text):
        g = key_group(m)
        k, at = m.group(g), m.start(g)
        for n in (range(1, len(k) + 1) if rule.prefixes else (len(k),)):
            if digest(k[:n]) in listed:
                span = (m.start(1), at + n) if rule.prefixes else m.span(1)
                if span not in seen:
                    seen.add(span)
                    yield span
                break


def redact(rule: Rule, text: str, repl: str, listed: frozenset | None = None) -> str:
    """`text` with every leak of `rule` replaced; scripts/drift_report.py uses it."""
    out, end = [], 0
    for start, stop in sorted(matches(rule, text, listed)):
        if start < end:  # overlaps the previous leak, already replaced
            end = max(end, stop)
            continue
        out.append(text[end:start] + repl)
        end = stop
    return "".join(out) + text[end:]


RULES: tuple[Rule, ...] = (
    # --- company identity: 82 hits at fork time, attributed exception only ---
    # The company name is public (LICENSE, NOTICE), so it is the one plain name.
    Rule(
        "company-name",
        r"arbor",
        "the originating company name; allowed only in LICENSE, README and the plugin author block",
        exempt=ATTRIBUTION_OK,
    ),
    Rule(
        "company-email-domain",
        r"(?=([a-z0-9-]{1,63}\.(?:xyz|ai|com)))",
        "an internal email domain",
        hashed=frozenset({
            "274f80d2514bf361",
            "3fb5436d65ee61e1",
            "9a0283fb8a8a03d7",
        }),
    ),
    Rule(
        "company-github-org",
        r"arbor-ai-inc/(?!cadence\b)",
        "a private repository in the company's GitHub org",
        exempt=ATTRIBUTION_OK,
    ),
    Rule(
        "private-github-handle",
        r"(?=(@([\w-]+)))",
        "a private GitHub org, team handle or CODEOWNERS entry",
        exempt=ATTRIBUTION_OK,
        prefixes=True,
        hashed=frozenset({
            "24667b206f539469",
            "e15b14c0892bce04",
        }),
    ),
    # --- issue tracker: 154 hits across 55 distinct issues, two prefixes ---
    # These are the evidence anchors. reference/ must cite the case map
    # (C-01..C-NN in examples/case-studies.md) instead. No exemptions: a public
    # reader cannot open any of these, and they name internal work.
    Rule(
        "private-issue-id",
        r"(?=(\b([a-z]{2,5})-\d+\b))",
        "a private issue id; cite the case map (C-NN) from examples/case-studies.md instead",
        # Case-insensitive: a branch name carries the id in lower case.
        hashed=frozenset({
            "4d48fba6cf5f7d6a",
            "82fe032bd9337b5d",
        }),
    ),
    Rule(
        "private-tracker-url",
        r"linear\.app/[\w-]+",
        "a private Linear workspace URL",
    ),
    Rule(
        "private-decision-id",
        r"\bD0\d\d\b",
        "a private DECISIONS.md id",
        flags=0,
    ),
    # --- codebase structure: the service and doc tree of the private repo ---
    Rule(
        "private-service-path",
        r"(?=(\b(?:services|platform)/\w+))",
        "an internal service path",
        hashed=frozenset({
            "0381c4f6d798e329",
            "0970f2351296b7e6",
            "0ef04126762cff1b",
            "2c3fb52b571e9bc8",
            "2dd0d2ff34c21708",
            "303628c2970ff38a",
            "3ed9913ca8c9a1c9",
            "4972abacac21e5f6",
            "4f6870b0db07e254",
            "521d60840480a264",
            "53a53be63bfdc26e",
            "5bbbcbd15bcf6d0e",
            "5ea103bd8adc451d",
            "758223de23b596e4",
            "75830963dcd85726",
            "778b5581a3dbf974",
            "80dc29d905bfcf27",
            "a13ac184d370487e",
            "ac7b9a375e2637f5",
            "af4c2ce27a4f7027",
            "f01d4a6c3c110add",
            "fe3b7a5f1359cc0a",
        }),
    ),
    Rule(
        "private-docs-path",
        r"(?=(\bdocs/([\w-]+)/))",
        "an internal docs tree that does not exist for adopters",
        hashed=frozenset({
            "4ca303a3bf7ddf7b",
            "b094db7ce2f99cbc",
            "ea7792a26f405e2a",
        }),
    ),
    Rule(
        "private-state-doc",
        r"(?=(\b[A-Z]+(?:_[A-Z]+)+\b))",
        "an internal state or contract artifact",
        flags=0,
        hashed=frozenset({
            "1a0c1090b6d92417",
            "23b87e90dd3a3dc9",
            "a96212c7c46cb6ca",
        }),
    ),
    Rule(
        "private-venv-incantation",
        r'PATH="\$\(pwd\)/[\w/]+/venv/bin:\$PATH"',
        "the private repo's pre-commit incantation; use the [commands] config instead",
        flags=0,
    ),
    # --- infrastructure ---
    Rule(
        "gcp-project-slug",
        r"(?=(([a-z0-9]{1,40})-[\w<][\w<>-]{0,40}))",
        "a real GCP project, bucket or secret name, or the prefix they share",
        hashed=frozenset({"64bb058d4a89947a"}),
    ),
    Rule(
        "secret-naming-convention",
        # The last two words before `=`, so a prefixed variable still matches.
        r"(?=(([a-z][a-z0-9]{0,39}_[a-z0-9]{1,40})\s*=))",
        "the private repo's secret-naming convention",
        hashed=frozenset({"e88040e7d0052eeb"}),
    ),
    Rule(
        "private-slack-channel",
        r"(?=(#([a-z]+)(?:-[\w-]*\w)?))",
        "a private Slack channel name",
        hashed=frozenset({
            "82fe032bd9337b5d",
            "deb3e366c077c228",
            "efb5202cc8685e24",
        }),
    ),
    # --- model aliases: `model: fable` in 6 files at fork time. The model names
    # are public; the leak is a workflow pinned to one alias, which may not
    # resolve for an adopter and is easy to miss in frontmatter.
    Rule(
        "pinned-model-alias",
        r"^\s*model:\s*fable|\bfable\[1m\]|\bopus\[1m\]",
        "a workflow pinned to one model alias; use the [models] config instead",
        flags=re.IGNORECASE | re.MULTILINE,
    ),
    # --- product vocabulary from a workflow that was left out of cadence ---
    Rule(
        "product-vocabulary",
        r"(?=(--([a-z]{1,40})-|\b([a-z]{1,40})\.\w{1,40}@\d|([a-z]{1,40})-tokens:))",
        "product vocabulary from a workflow that was not extracted",
        hashed=frozenset({"b86c24fb6243540a"}),
    ),
    Rule(
        "private-file-name",
        r"(?=(\b[\w-]+\.json\b))",
        "a generated file from the private tree",
        hashed=frozenset({"93ff5f8c8aef9b94"}),
    ),
)

# CodeRabbit is a public product, so naming it discloses nothing about the
# private source tree -- it is not a leak, and the first draft of this rule was
# wrong to treat it as one. What it IS is a workflow-layer coupling risk: a
# reference doc that says "run @coderabbitai full review" has hardcoded one
# reviewer where the [review] provider should decide.
#
# So it is scoped to the workflow layer and exempt everywhere else. The first
# draft had this exactly inverted -- exempting reference/ (where the risk
# lives) and firing on tools/ and README.md (where naming the provider is
# correct) -- which is why it failed on its own repository before porting a
# single workflow doc.
CODERABBIT = Rule(
    "review-provider-hardcoded",
    r"coderabbit",
    "a workflow file names one reviewer directly; go through the [review] provider instead",
)
CODERABBIT_SCOPE = ("reference/", "skills/", "agents/", "adapters/")
# ...except a provider-notes directory, whose entire purpose is to name one
# provider and document its specifics. The neutral workflow doc says "the
# configured reviewer"; reference/providers/<name>.md says exactly which
# command that provider needs and why. Suppressing the specifics would have
# thrown away the most useful part of the corpus.
CODERABBIT_SCOPE_EXEMPT = ("reference/providers/",)
# A neutral doc is SUPPOSED to link to the provider notes; that link contains
# the provider's name and is not a hardcoding. Only this exact form is allowed,
# so a bare command or a prose mention still fires.
CODERABBIT_LINK_OK = "providers/coderabbit.md"
# A neutral doc must be able to name the ENUM VALUE, or it cannot document what
# `[review].provider` accepts. The backticked form is that value; a bare
# `@coderabbitai` command or a prose "CodeRabbit" still fires.
CODERABBIT_VALUE_OK = "`coderabbit`"

# The marketplace coordinate is how anyone installs this, so it has to appear in
# the install instructions. It is the one place the org name is a URL rather than
# an attribution, and it is exempted the same narrow way as the provider link:
# only when every occurrence on the line is part of the coordinate, so a prose
# mention beside it still fires.
INSTALL_COORDINATE = "arbor-ai-inc/cadence"

SKIP_DIRS = frozenset({".git", ".venv", "node_modules", "__pycache__"})
# Multi-component prefixes, matched on the full relative path with a separator.
SKIP_PREFIXES = ("evals/results/",)
SKIP_SUFFIXES = frozenset({".pyc", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf", ".zip", ".ico"})
# The case map is the private C-NN -> issue id mapping. It must never be tracked;
# a separate check below fails if it is, which is stronger than exempting it.
NEVER_TRACKED = ("casemap.json",)


def relpath(path: Path) -> str:
    """Repo-relative where possible, absolute otherwise.

    A path outside the repo is not an error: auditing the source tree before
    extraction is a real use, and `relative_to` raises rather than coping.
    Exemptions are keyed on repo-relative paths, so an outside path simply
    matches none of them -- which is the strict reading, and the safe one.
    """
    try:
        return path.resolve().relative_to(REPO).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def scannable(path: Path) -> bool:
    rel = relpath(path)
    if any(part in SKIP_DIRS for part in path.parts):
        return False
    if any(rel.startswith(d) for d in SKIP_PREFIXES):
        return False
    if path.suffix.lower() in SKIP_SUFFIXES:
        return False
    # This file states every forbidden pattern, so it cannot scan itself.
    return rel != "tests/check_no_leaks.py"


def targets(argv_paths: list[str]) -> list[Path]:
    if argv_paths:
        out = []
        for raw in argv_paths:
            p = Path(raw).resolve()
            if p.is_file() and scannable(p):
                out.append(p)
        return out
    return sorted(p for p in REPO.rglob("*") if p.is_file() and scannable(p))


def rules_for(rel: str) -> list[Rule]:
    active = [r for r in RULES if rel not in r.exempt]
    if rel.startswith(CODERABBIT_SCOPE) and not rel.startswith(CODERABBIT_SCOPE_EXEMPT):
        active.append(CODERABBIT)
    return active


def scan(path: Path) -> list[tuple[int, str, str, str]]:
    """Return (lineno, rule name, matched text, why) for every hit in `path`."""
    rel = relpath(path)
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []

    hits = []
    for rule in rules_for(rel):
        for start, stop in matches(rule, text):
            # Report the line, not the offset: a reviewer needs to open it.
            lineno = text.count("\n", 0, start) + 1
            if rule.name == "company-name":
                line = text.splitlines()[lineno - 1]
                if line.count(INSTALL_COORDINATE) >= line.lower().count("arbor"):
                    continue
            if rule is CODERABBIT:
                line = text.splitlines()[lineno - 1]
                # A pointer to the provider notes is the intended pattern. Only
                # exempt the line when every occurrence on it is part of that
                # path, so a link sitting beside a bare command still fires.
                allowed = line.count(CODERABBIT_LINK_OK) + line.count(CODERABBIT_VALUE_OK)
                if allowed >= line.lower().count("coderabbit"):
                    continue
            hits.append((lineno, rule.name, text[start:stop].strip(), rule.why))
    return sorted(hits)


def check_never_tracked() -> list[str]:
    """The case map must not be committed, which beats exempting it from scans."""
    problems = []
    for name in NEVER_TRACKED:
        for found in REPO.rglob(name):
            if ".git" in found.parts:
                continue
            problems.append(relpath(found))
    return problems


# Every rule, and every alternative inside it, has a probe that MUST fire. A rule
# whose probe stops matching has been broken by an edit; a rule with no probe is
# unproven and fails the suite. This is the mutation test for the gate itself:
# `guard-cannot-fire` is the second-most-frequent trap in the ledger this
# project ships, at n=14.
PROBES: dict[str, tuple[str, ...]] = {
    "company-name": ("the Arbor AI workflow",),
    "company-github-org": ("see arbor-ai-inc/probe-repo",),
    "private-tracker-url": ("https://linear.app/probe-ws/issue/PRB-162",),
    "private-decision-id": ("recorded in DECISIONS.md (D087)",),
    "private-venv-incantation": ('run PATH="$(pwd)/src/app/venv/bin:$PATH" pre-commit',),
    "pinned-model-alias": ("model: fable\n", "use fable[1m] here", "or opus[1m]"),
    "review-provider-hardcoded": ("run @coderabbitai full review",),
}

# A hashed rule's probe is (text, stand-in). The stand-in is never a real name:
# selftest proves the text does not fire as written, then lists the stand-in's
# digest and proves it does.
HASHED_PROBES: dict[str, tuple[tuple[str, str], ...]] = {
    "company-email-domain": (
        ("you@probe-corp.xyz", "probe-corp.xyz"),
        ("you_probe-corp.xyz", "probe-corp.xyz"),
        ("see x-probe-corp.com", "probe-corp.com"),
        ("at probe-corp.company", "probe-corp.com"),
        ("you@probe-corp.ai", "probe-corp.ai"),
    ),
    "private-github-handle": (
        ("@probe-org/infra", "probe-org"),
        ("@probe-org-team", "probe-org"),
        ("@probe-org_bot", "probe-org"),
    ),
    "private-issue-id": (
        ("carried forward from PRB-147", "prb"),
        ("branch jdoe/prb-302-x", "prb"),
    ),
    "private-service-path": (("guard services/probe-svc/internal/", "services/probe"),),
    "private-docs-path": (
        ("see docs/probe-tree/README.md", "probe-tree"),
        ("see docs/docs/probe-tree/x", "probe-tree"),
    ),
    "private-state-doc": (("canonical current-state is PROBE_STATE.md", "PROBE_STATE"),),
    "gcp-project-slug": (
        ("gcloud config set project probecorp-dev", "probecorp"),
        ("bucket my_probecorp-tf-state", "probecorp"),
        ("secrets live in probecorp-<env>", "probecorp"),
        ("bucket terraform-probecorp-tf-state", "probecorp"),
    ),
    "secret-naming-convention": (
        ("PROBE_SECRET=probecorp-jwt-secret:latest", "probe_secret"),
        ("probe_secret = os.environ[...]", "probe_secret"),
        ("LEGACY_PROBE_SECRET=false", "probe_secret"),
        ("XPROBE_SECRET=1", "probe_secret"),
    ),
    "private-slack-channel": (
        ("post to #probe-standup", "probe"),
        ("page #probe", "probe"),
    ),
    "product-vocabulary": (
        ("the probe.button@2 component", "probe"),
        ("--probe-color tokens", "probe"),
        ("load myprobe-tokens: from the theme", "probe"),
    ),
    "private-file-name": (("regenerate probe-registry.json", "probe-registry.json"),),
}

# Near misses that must NOT fire with the stand-in listed: a shape that grew too
# loose would flood every adopter's repo with false leaks.
HASHED_NEAR_MISSES: dict[str, tuple[tuple[str, str], ...]] = {
    "private-issue-id": (("PRBX-147", "prb"), ("XPRB-147", "prb")),
    "private-slack-channel": (("#probestandup", "probe"),),
    "private-docs-path": (("docs/probe-tree.md", "probe-tree"),),
    "private-github-handle": (("@xprobe-org", "probe-org"),),
}


def selftest() -> int:
    """Prove every rule fires, and that the attribution exemption exempts."""
    failures = []
    all_rules = (*RULES, CODERABBIT)

    for rule in all_rules:
        probes = HASHED_PROBES.get(rule.name) if rule.hashed else PROBES.get(rule.name)
        if not probes:
            failures.append(f"rule {rule.name!r} has no probe, so nothing proves it can fire")
            continue
        if not rule.hashed:
            for probe in probes:
                if not any(matches(rule, probe)):
                    failures.append(f"rule {rule.name!r} did not match its probe {probe!r}")
            continue
        # Fires on a listed digest, and only on a listed one.
        for probe, standin in probes:
            listed = rule.hashed | {digest(standin)}
            if digest(standin) in rule.hashed:
                failures.append(f"rule {rule.name!r}: stand-in {standin!r} must not be a real entry")
            elif any(matches(rule, probe)):
                failures.append(f"rule {rule.name!r} fired on {probe!r}, a name it does not list")
            elif not any(matches(rule, probe, listed)):
                failures.append(f"rule {rule.name!r} did not fire on {probe!r} with {standin!r} listed")
        for probe, standin in HASHED_NEAR_MISSES.get(rule.name, ()):
            if any(matches(rule, probe, rule.hashed | {digest(standin)})):
                failures.append(f"rule {rule.name!r} fired on near miss {probe!r}")

    stray = (set(PROBES) | set(HASHED_PROBES)) - {r.name for r in all_rules}
    for name in sorted(stray):
        failures.append(f"probe {name!r} names no rule")

    # redact() replaces exactly the leaks, so drift_report compares like with like.
    slack = next(r for r in RULES if r.name == "private-slack-channel")
    got = redact(slack, "post to #probe-standup and #other", "<x>", slack.hashed | {digest("probe")})
    if got != "post to <x> and #other":
        failures.append(f"redact() on a hashed rule gave {got!r}")
    # Overlapping leaks collapse into one replacement that covers both.
    email = next(r for r in RULES if r.name == "company-email-domain")
    both = email.hashed | {digest("probe.com"), digest("com.xyz")}
    got = redact(email, "see probe.com.xyz end", "<x>", both)
    if got != "see <x> end":
        failures.append(f"redact() on overlapping leaks gave {got!r}")
    decision = next(r for r in RULES if r.name == "private-decision-id")
    got = redact(decision, "see D087 and D012", "<x>")
    if got != "see <x> and <x>":
        failures.append(f"redact() on a plain rule gave {got!r}")

    # The company name must be caught in a workflow doc and allowed in README.
    company = next(r for r in RULES if r.name == "company-name")
    if "README.md" not in company.exempt:
        failures.append("attribution exemption missing: README.md must be allowed to name the company")
    if "reference/git-pr-workflow.md" in company.exempt:
        failures.append("attribution exemption too broad: reference/ must never be exempt")
    if not rules_for("README.md") == [r for r in RULES if r.name != "company-name"]:
        pass  # rules_for also appends CODERABBIT for README; asserted below instead.
    if any(r.name == "company-name" for r in rules_for("README.md")):
        failures.append("rules_for('README.md') still applies company-name")
    if not any(r.name == "company-name" for r in rules_for("reference/retro.md")):
        failures.append("rules_for('reference/retro.md') does not apply company-name")
    # The install coordinate is exempt; a prose mention beside it is not.
    coord_only = "/plugin marketplace add arbor-ai-inc/cadence"
    if not (coord_only.count(INSTALL_COORDINATE) >= coord_only.lower().count("arbor")):
        failures.append("the bare install coordinate should be exempt")
    coord_plus = "install arbor-ai-inc/cadence, built by Arbor"
    if coord_plus.count(INSTALL_COORDINATE) >= coord_plus.lower().count("arbor"):
        failures.append("a prose company mention beside the coordinate must NOT be exempted")

    # The provider-notes link is exempt; a bare command on the same line is not.
    link_only = "see [`providers/coderabbit.md`](./providers/coderabbit.md) for the command"
    if CODERABBIT.compiled().search(link_only) and not (
        link_only.count(CODERABBIT_LINK_OK) >= link_only.lower().count("coderabbit")
    ):
        failures.append("a bare link to the provider notes should be exempt")
    both = "run `@coderabbitai full review`, see [x](./providers/coderabbit.md)"
    if both.count(CODERABBIT_LINK_OK) + both.count(CODERABBIT_VALUE_OK) >= both.lower().count("coderabbit"):
        failures.append("a line carrying a bare command must NOT be exempted by a link beside it")

    # The enum value is exempt; a prose mention or a command beside it is not.
    value_only = "| `coderabbit` | a PR-time bot | anything |"
    if not (value_only.count(CODERABBIT_VALUE_OK) >= value_only.lower().count("coderabbit")):
        failures.append("the backticked enum value should be exempt")
    value_plus = "set `coderabbit`, then post @coderabbitai review"
    if value_plus.count(CODERABBIT_VALUE_OK) + value_plus.count(CODERABBIT_LINK_OK) >= value_plus.lower().count("coderabbit"):
        failures.append("a command beside the enum value must NOT be exempted")

    # An issue id gets no exemption anywhere, including the attributed files.
    if not any(r.name == "private-issue-id" for r in rules_for("README.md")):
        failures.append("private-issue-id must not be exempt in README.md")

    # Dotfiles and CI config must be scanned. Prefix-matching SKIP_DIRS silently
    # excluded every one of these, which is a false negative rather than a crash
    # -- so it is asserted, not left to be noticed.
    for must_scan in (".gitignore", ".gitattributes", ".github/workflows/ci.yml"):
        if not scannable(REPO / must_scan):
            failures.append(f"{must_scan} is not scanned; SKIP_DIRS is matching a prefix again")
    for must_skip in (".git/config", "__pycache__/x.pyc", "evals/results/run/aggregate-result.json"):
        if scannable(REPO / must_skip):
            failures.append(f"{must_skip} should be skipped but is not")

    # The reviewer-coupling rule must cover the workflow layer and nothing else.
    for workflow in ("reference/git-pr-workflow.md", "skills/code-review/SKILL.md", "agents/code-reviewer.md"):
        if not any(r.name == "review-provider-hardcoded" for r in rules_for(workflow)):
            failures.append(f"{workflow} must be checked for a hardcoded reviewer")
    for not_workflow in ("README.md", "tools/cadence_config.py", "docs/configuration.md",
                         "reference/providers/coderabbit.md"):
        if any(r.name == "review-provider-hardcoded" for r in rules_for(not_workflow)):
            failures.append(f"{not_workflow} names providers legitimately and must not be checked")

    for line in failures:
        print(f"selftest: {line}", file=sys.stderr)
    if failures:
        print(f"\ncheck_no_leaks selftest: {len(failures)} failure(s).", file=sys.stderr)
        return 1
    print(f"check_no_leaks selftest: {len(all_rules)} rules, all provably firing")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="*", help="files to scan; default is the whole repo")
    ap.add_argument("--list", action="store_true", help="print the rules and exit")
    ap.add_argument("--selftest", action="store_true", help="prove every rule fires, then exit")
    ap.add_argument("--hash", metavar="NAME", help="print the digest a hashed rule stores for NAME")
    args = ap.parse_args()

    if args.hash:
        print(digest(args.hash))
        return 0

    if args.selftest:
        return selftest()

    if args.list:
        print(f"{len(RULES) + 1} leak rules:\n")
        for r in (*RULES, CODERABBIT):
            print(f"  {r.name}")
            print(f"      why:     {r.why}")
            print(f"      pattern: {r.pattern}")
            if r.hashed:
                print(f"      hashed:  {len(r.hashed)} private names, stored as digests")
            if r.exempt:
                print(f"      exempt:  {', '.join(sorted(r.exempt))}")
            if r is CODERABBIT:
                print(f"      scope:   only {', '.join(CODERABBIT_SCOPE)}")
                print(f"      except:  {', '.join(CODERABBIT_SCOPE_EXEMPT)}")
            print()
        return 0

    if not args.paths and selftest() != 0:
        return 1

    files = targets(args.paths)
    total = 0
    for path in files:
        hits = scan(path)
        if not hits:
            continue
        rel = relpath(path)
        for lineno, name, matched, why in hits:
            print(f"{rel}:{lineno}: [{name}] {matched!r} — {why}")
            total += 1

    for leaked in check_never_tracked():
        print(f"{leaked}: [never-tracked] this file maps public case ids to private issue ids")
        total += 1

    if total:
        print(f"\ncheck_no_leaks: {total} leak(s) across {len(files)} scanned file(s). Not publishable.", file=sys.stderr)
        return 1

    print(f"check_no_leaks: clean ({len(files)} files, {len(RULES) + 1} rules)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
