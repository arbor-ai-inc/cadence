---
name: review-spec
description: >
  Runs one spec-pipeline review round — Gate 1 (product) or Gate 2 (eng design)
  — by invoking the matching reviewer subagent. Use when asked to review a spec,
  or to re-run a single gate on an edited artifact. For the full loop to READY,
  use /cadence:spec-pipeline instead.
argument-hint: <specs>/<slug>/{product|design}.md
allowed-tools: Read, Grep, Glob, Write, Bash, Task
---

**Before anything else, check the model.** Run `python3 ${CLAUDE_PLUGIN_ROOT}/tools/cadence_config.py --json` and read `models_recommended`. If it is set and you are not running on it, **say so and stop** — name the model you are on, the one recommended, and how to switch (`/model <name>`, or `"model"` in `.claude/settings.json` to make it stick). Continue only if the author says to.

This is a real gate, not a formality. Cadence cannot switch models: a skill's `model:` pin covers only the turn that invoked it, and this workflow spans many turns because it stops to ask you things. So without this check the pipeline silently runs the first round on one model and everything after on another, and nothing reports it.

Follow the canonical procedure in `${CLAUDE_PLUGIN_ROOT}/reference/review-spec.md` exactly.

Read `[paths].specs` and `[paths].principles` from the user's config: `python3 ${CLAUDE_PLUGIN_ROOT}/tools/cadence_config.py --json`.

**Decide the scope before invoking anyone.** Apply the ordered state table in `reference/spec-pipeline.md` § *The rule* to the latest round **for the gate under review** — round numbers are global across gates, so the highest-numbered round in the directory may belong to the other gate. A gate with zero blockers and a hash matching the artifact is closed: say so and stop, without invoking a reviewer.

Compute hashes with `python3 ${CLAUDE_PLUGIN_ROOT}/tools/spec_hash.py` and pass them in. Never compute a hash by hand and never write a placeholder — that is the failure this tool exists to prevent.

Gate 1 → the `product-spec-reviewer` subagent. Gate 2 → `eng-design-reviewer`. The reviewer writes the round file; it never edits the spec.

Report the verdict as the literal first line — `PRODUCT_READY`, `DESIGN_READY` or `NOT_READY`, since callers branch on it — then a Shape B brief, not the reviewer's raw findings.
