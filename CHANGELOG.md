# Changelog

What changed for adopters, newest first. Every version that reaches `main` is
tagged `v<version>`.

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
