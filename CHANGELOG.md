# Changelog

What changed for adopters, newest first. Every version that reaches `main` is
tagged `v<version>`.

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
