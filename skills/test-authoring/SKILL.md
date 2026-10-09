---
name: test-authoring
description: >
  Use when planning the tests for a spec, when adding or changing an integration,
  component behavioral, smoke or E2E test or shared fixture, or when a change
  touches a cross-component contract edge or adds a deployed surface. Not for unit
  tests inside a feature PR.
allowed-tools: Read, Grep, Glob, Write, Edit, Bash
---

Follow the canonical procedure in `${CLAUDE_PLUGIN_ROOT}/reference/test-authoring.md` exactly.

Reuse the project's harness and fixtures; extend the shared factory, never add a private seed.

Answer the E2E/smoke step in the PR, every time, even when the answer is "not applicable". In plan mode, which has no PR, answer it in `testing-plan.md` § *Cross-cutting*.

Never wire an expensive suite into a blocking CI job without the user's yes.
