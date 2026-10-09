# Changelog

What changed for adopters, newest first. Every version that reaches `main` is
tagged `v<version>`.

## 0.9.0

- **Design-only specs.** A change nothing a customer could see, be billed for, or
  complain about may skip `product.md`; the design carries the Rn and why, and Gate 2
  grades that claim (a user-visible goal is a BLOCKER). `draft-plan` refuses one that
  is user-visible.
- **Split designs.** A large design is an HLD plus `design/` sub-designs; `spec_hash.py
  design` hashes them together.
- `check_vocab.py` also scans files not yet added, and its own docstring no longer
  names the source project's files.
- **Testing plans and `test-authoring`.** New workflow and `_testing_plan_template.md`
  for tests above unit level. `testing-plan.md` sits outside the design hash; rows are
  never deleted after the gate.
- **Cross-artifact pass.** Before the design PR, each artifact pair is checked and the
  result committed in `review/cross-check.md`.
## 0.8.1

- **Scrubbed the source project's names** from the docs, case studies and tests: spec
  names, PR numbers, branch names, file and table names. Wording changed; no rule did.
- **`tests/check_vocab.py`:** fails if a name from a private repo appears in cadence.
  The list is derived at run time from the repos you point it at and never stored.
- **`check_no_leaks.py`** stores private names as digests (`--hash NAME` adds one), and
  matches issue ids in any case.
- `code-review` and `spec-pipeline` name cadence's `tools/ask.py`, not a source-project
  script.

## 0.8.0

- **Fan-out is now opt-in: `[fanout].enabled`, default `false`.** With it off, a
  one-way decision inside the diff is asked with a decision brief, and `fanout.py`
  refuses `init` and `fork` (exit 3, naming the switch). **Behavior change:** a project
  that relied on fan-out sets `enabled = true` under `[fanout]` to keep it.
  `check-scope` is unaffected.

## 0.7.0

New rules from the source project's recent retros, in the short style, within budget.

- **code-review:** a docs-only diff is all claims; a quoted spec sentence is a premise;
  sweep the dimension, not only the phrase; stop means stop after round 3, and a commit
  after the last review is named in the PR.
- **automated-review:** check all three parts of the terminal condition every round;
  one push per fix round, never during a running review; refills are per developer.
- **git-pr-workflow:** re-run the suites with `main` merged in before merging.
- **code-review-and-quality:** read across the open queue (merged-tree test for
  migrations, `__init__` and registries); quiet test doubles; remerge-diff.
- **test-driven-development:** anti-vacuity stated over the property; benchmarks need a
  correctness assertion; cached runs; tests that read docs; a local suite runner.
- **using-agent-skills:** route the model by phase; delegated skill runs pass the model.
- **retro-synthesis:** check the ledger against raw fragment text.
- **execute-issue:** quoted premises; "what calls this" is a reachability question.
- **New skill: `explain-plain`.**

## 0.6.0

Leaner docs: an issue run now loads roughly half what it did. No rule was removed.

- **Review-bot material moved to `reference/automated-review.md`**, loaded only when
  `[review].provider` is a PR bot. **Stacked, parallel and out-of-date branches moved to
  `reference/branch-updates.md`**, loaded only in those situations. `git-pr-workflow`
  drops from 54 KB to 18 KB.
- **Case write-ups moved to `examples/case-studies.md`** from `code-review`,
  `code-review-and-quality`, `test-driven-development` and `execute-issue`. Each rule
  keeps one sentence of why and its case id. Those four docs are 35% smaller.
- **Every reference doc has a byte budget** (`tests/doc_budget.json`, checked by
  `tests/check_doc_budget.py` in CI and pre-commit). A new rule makes room or raises the
  budget visibly.
- `code-review` Loop step 1 no longer carries a command from the source project.

## 0.5.0

Additive. Nothing changes for an existing plugin install.

- **Vendor cadence as a git submodule at `.cadence/`, with no plugin.** The
  dispatcher now ships at the repo root as `cadence`, so `./.cadence/cadence`
  resolves the copy it sits in. See `docs/setup.md`.
- **`tools/wrappers.py`** generates unprefixed wrappers from the vendored copy:
  `.claude/skills/`, `.codex/skills/` and `.claude/agents/`. `--check` fails on a
  stale, orphaned or hand-edited wrapper. It never overwrites a file it did not
  generate.
- **`[paths].overlays`**: per-workflow project addenda that generated wrappers
  tell the agent to read after the canonical doc. Unset by default.
- **Fan-out leaves get the vendored copy.** When a project vendors cadence at
  `.cadence/`, `fanout.py fork` populates it in each new leaf from the local
  checkout, offline, or warns if it cannot. No other submodule is touched.
- **Release tags.** A workflow tags each new version `v<version>` on `main`.
