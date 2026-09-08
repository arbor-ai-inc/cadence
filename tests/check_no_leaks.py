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

Usage:
    check_no_leaks.py               # scan the whole repo; what CI and pre-commit run
    check_no_leaks.py --list        # print every rule and where it is exempt
    check_no_leaks.py path ...      # scan only these paths (pre-commit passes files)

Exit codes:
    0  clean
    1  a leak, or a usage error
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# Attribution is deliberate and narrow: cadence is published BY the company, so
# its name belongs in the licence, the plugin author block and the README, and
# nowhere else. See the plan's "Settled" section. Any other pattern below gets
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

    def compiled(self) -> re.Pattern:
        return re.compile(self.pattern, self.flags)


RULES: tuple[Rule, ...] = (
    # --- company identity: 82 hits at fork time, attributed exception only ---
    Rule(
        "company-name",
        r"arbor",
        "the originating company name; allowed only in LICENSE, README and the plugin author block",
        exempt=ATTRIBUTION_OK,
    ),
    Rule(
        "company-email-domain",
        r"[\w.+-]*@?arborai\.(?:xyz|ai|com)",
        "an internal email domain",
    ),
    Rule(
        "company-github-org",
        r"@arbor-ai-inc|@murty-arbor|arbor-ai-inc/(?!cadence)",
        "a private GitHub org, team handle or CODEOWNERS entry",
        exempt=ATTRIBUTION_OK,
    ),
    # --- issue tracker: 124 ALT- + 30 ENG- hits across 49 + 6 distinct issues ---
    # These are the evidence anchors. reference/ must cite the case map
    # (C-01..C-NN in examples/case-studies.md) instead. No exemptions: a public
    # reader cannot open any of these, and they name internal work.
    Rule(
        "private-issue-id",
        r"\b(?:ALT|ENG)-\d+\b",
        "a private issue id; cite the case map (C-NN) from examples/case-studies.md instead",
        flags=0,
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
        r"\b(?:services|platform)/(?:bidder|recirculation|crawler|catalog|openrtb"
        r"|auctioncore|fallback_composer|api|formats|ui|offline)\b",
        "an internal service path",
    ),
    Rule(
        "private-docs-path",
        r"\bdocs/(?:contracts|architecture|context)/",
        "an internal docs tree that does not exist for adopters",
    ),
    Rule(
        "private-state-doc",
        r"PROJECT_STATE|PRODUCT_CAPABILITY_STATUS|GATED_CONTRACTS",
        "an internal state or contract artifact",
        flags=0,
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
        r"arborai-(?:dev|staging|prod|ml-dev|ml-prod|shared|tf-state[\w-]*|jwt[\w-]*)",
        "a real GCP project, bucket or secret name",
    ),
    Rule(
        "secret-naming-convention",
        r"JWT_SECRET\s*=|arborai-<env>",
        "the private repo's secret-naming convention",
    ),
    Rule(
        "private-slack-channel",
        r"#(?:eng-standup|alerts|deploys|eng-[\w-]+)\b",
        "a private Slack channel name",
    ),
    # --- model aliases: `model: fable` in 6 files, an internal alias that will
    # not resolve for an external user, and easy to miss because it is
    # frontmatter rather than prose.
    Rule(
        "private-model-alias",
        r"^\s*model:\s*fable|\bfable\[1m\]|\bopus\[1m\]",
        "a non-public model alias; use the [models] config instead",
        flags=re.IGNORECASE | re.MULTILINE,
    ),
    # --- ad-tech product vocabulary that should have left with author-format ---
    Rule(
        "product-vocabulary",
        r"\barbor\.\w+@\d|--arbor-|arbor-tokens:|runtime-registry\.json",
        "ad-format product vocabulary from the excluded author-format workflow",
    ),
)

# CodeRabbit is a supported review provider, not a leak -- but it should appear
# only where it is named as one implementation among several, never as the
# assumed reviewer in a workflow doc.
CODERABBIT = Rule(
    "review-provider-assumed",
    r"coderabbit",
    "CodeRabbit named outside the provider layer; workflow docs must go through [review]",
)
CODERABBIT_OK_PREFIXES = ("providers/", "reference/", "docs/", "templates/", "tests/")

# Matched as whole path COMPONENTS, never as string prefixes. Prefix-matching
# ".git" also skips ".gitignore", ".gitattributes" and everything under
# ".github/" -- and a deploy workflow is precisely where an infra project name
# leaks. The same off-by-a-separator bug is on record in the source repo's own
# adapter checker, so it is not hypothetical.
SKIP_DIRS = frozenset({".git", ".venv", "node_modules", "__pycache__"})
# Multi-component prefixes, matched on the full relative path with a separator.
SKIP_PREFIXES = ("evals/results/",)
SKIP_SUFFIXES = frozenset({".pyc", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf", ".zip", ".ico"})
# The case map is the private C-NN -> ALT-NN mapping. It must never be tracked;
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
    if not rel.startswith(CODERABBIT_OK_PREFIXES):
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
        for m in rule.compiled().finditer(text):
            # Report the line, not the offset: a reviewer needs to open it.
            lineno = text.count("\n", 0, m.start()) + 1
            hits.append((lineno, rule.name, m.group(0).strip(), rule.why))
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


# One string per rule that MUST match it. A rule whose probe stops matching has
# been broken by an edit; a rule with no probe is unproven and fails the suite.
# This is the mutation test for the gate itself: `guard-cannot-fire` is the
# second-most-frequent trap in the ledger this project ships, at n=14.
PROBES: dict[str, str] = {
    "company-name": "the Arbor AI workflow",
    "company-email-domain": "you@arborai.xyz",
    "company-github-org": "@arbor-ai-inc/infra",
    "private-issue-id": "carried forward from ENG-147, and ALT-302",
    "private-tracker-url": "https://linear.app/arbor-ai/issue/ALT-162",
    "private-decision-id": "recorded in DECISIONS.md (D087)",
    "private-service-path": "guard services/bidder/internal/serving/ and platform/api",
    "private-docs-path": "see docs/contracts/README.md",
    "private-state-doc": "canonical current-state is PROJECT_STATE.md",
    "private-venv-incantation": 'run PATH="$(pwd)/platform/api/venv/bin:$PATH" pre-commit',
    "gcp-project-slug": "gcloud config set project arborai-dev",
    "secret-naming-convention": "JWT_SECRET=arborai-jwt-secret:latest",
    "private-slack-channel": "post to #eng-standup",
    "private-model-alias": "model: fable\n",
    "product-vocabulary": "the arbor.button@2 component and --arbor-color tokens",
    "review-provider-assumed": "run @coderabbitai full review",
}


def selftest() -> int:
    """Prove every rule fires, and that the attribution exemption exempts."""
    failures = []
    all_rules = (*RULES, CODERABBIT)

    missing = {r.name for r in all_rules} - set(PROBES)
    for name in sorted(missing):
        failures.append(f"rule {name!r} has no probe, so nothing proves it can fire")

    for rule in all_rules:
        probe = PROBES.get(rule.name)
        if probe is None:
            continue
        if not rule.compiled().search(probe):
            failures.append(f"rule {rule.name!r} did not match its own probe {probe!r}")

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
    args = ap.parse_args()

    if args.selftest:
        return selftest()

    if args.list:
        print(f"{len(RULES) + 1} leak rules:\n")
        for r in (*RULES, CODERABBIT):
            print(f"  {r.name}")
            print(f"      why:     {r.why}")
            print(f"      pattern: {r.pattern}")
            if r.exempt:
                print(f"      exempt:  {', '.join(sorted(r.exempt))}")
            if r is CODERABBIT:
                print(f"      exempt:  everything under {', '.join(CODERABBIT_OK_PREFIXES)}")
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
