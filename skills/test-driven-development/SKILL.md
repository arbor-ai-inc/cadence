---
name: test-driven-development
description: >
  Use when code behaviour is changing and tests should prove the change or guard
  the regression — a bug fix, a new rule, a refactor with observable effects.
  Covers test quality, not just test presence.
allowed-tools: Read, Grep, Glob, Write, Edit, Bash
---

Follow the canonical procedure in `${CLAUDE_PLUGIN_ROOT}/reference/test-driven-development.md` exactly.

Start from the nearest existing tests — they carry the framework, the fixtures and the invocation. Prefer local conventions over introducing a second framework.

**Mutation-test any change that adds a rule.** Break the thing deliberately, watch the test fail, restore it. A guard nobody has seen fail is not known to work, and a passing suite proves nothing about a check the harness never reaches.

State the rule over the **property**, not over the syntactic form you happened to delete — an absence audit written to one spelling passes on every other spelling, which is a silent false negative.

A comment asserting an invariant is a test you have not written yet. Either write it, or downgrade the prose to intent.

**Coverage that does not exist reports the same green as coverage that passes.** A suite no job runs, and a migration nothing executes, both look covered. Verify what actually runs.

Run the project's `[commands].test` before claiming green, and quote what it printed — never "tests pass".
