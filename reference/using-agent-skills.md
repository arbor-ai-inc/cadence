# Using Agent Skills

## Overview

Use this meta-skill to choose the right agent aid before starting work. It
distinguishes skills, personas, agents, adapters, and project context so
different agents and human developers share one workflow language.

The output should be a short routing decision: what to use, why, and what
source-of-truth docs to load.

## When To Use

- Starting work and unsure which agent workflow applies.
- Onboarding a developer to Codex, Claude, or shared agent conventions.
- Deciding whether a task needs a skill, persona, delegated agent, or repo doc.
- Combining multiple aids, such as a workflow skill plus a specialist persona.
- Adding or updating agent-facing guidance and needing the correct layer.

Do not use this meta-skill as a substitute for the selected workflow. Once the
route is clear, switch to the specific skill, persona, or repo doc.

## Core Concepts

| Layer | Purpose | Examples |
|---|---|---|
| Skills | Reusable workflows for how to do work | `spec-driven-development`, `test-driven-development`, `code-review-and-quality`, `git-pr-workflow` |
| Personas | Specialist lenses for how to think about or review work | `security-auditor`, `test-engineer`, `web-performance-auditor`, `code-reviewer` |
| Agents or subagents | Delegated workers for bounded tasks | security review pass, test coverage scan, focused implementation spike |
| Project context | Source-of-truth facts about your product and system | architecture, decisions, roadmap, runbooks, current-state docs |
| Adapters | Agent-native entry points that point back to canonical docs | `skills/*/SKILL.md`, `adapters/codex/*/SKILL.md`, `CLAUDE.md`, `AGENTS.md` |

Cadence keeps its canonical guidance in `reference/` and `reference/personas/`,
and its adapters thin. Follow the same split for anything you add: one
canonical statement, thin routes to it.

## Workflow

1. Classify the task by outcome before choosing a tool.
2. Pick the narrowest skill that covers the workflow.
3. Add a persona only when a specialist review lens changes the expected
   output.
4. Use agents or subagents only for bounded work that can be independently
   verified.
5. Load project context when the task depends on product, architecture,
   operations, security, or roadmap facts.
6. State the routing decision briefly, then follow the selected workflow.

## Routing Guide

| Situation | Use |
|---|---|
| Need to define what to build | [`spec-driven-development`](./spec-driven-development.md) |
| Need to prove behavior works | [`test-driven-development`](./test-driven-development.md) |
| Need merge readiness or quality review | [`code-review-and-quality`](./code-review-and-quality.md) |
| Need branch, commit, PR, merge, or cleanup flow | [`git-pr-workflow`](./git-pr-workflow.md) |
| Need to pick up a tracked issue and implement it | [`execute-issue`](./execute-issue.md) |
| A ticket taught something worth keeping | [`retro`](./retro.md) — capture is a step in git-pr-workflow, not a separate PR |
| The retros `pending/` directory has reached `[retro].synthesis_threshold` | [`retro-synthesis`](./retro-synthesis.md) |
| Blocked mid-implementation on the author's decision | [`decision-fanout`](./decision-fanout.md) |
| Need a specialist review perspective | [`personas/`](./personas/) plus the relevant workflow skill |
| Need project facts | your own architecture, current-state and runbook docs, plus nearby code and tests |
| Need to author or update a skill | [`skill-anatomy`](./skill-anatomy.md) |

## Output Shape

For routing-only requests, produce:

- Recommended skill, persona, agent, or repo doc.
- Reason for the choice.
- Any repo context to inspect first.
- The next prompt or action.

For implementation requests, keep the routing note to one or two sentences and
continue with the selected workflow.

## Common Rationalizations

| Rationalization | Reality |
|---|---|
| "Everything should be a skill." | Skills are for repeatable workflows. Use personas for review lenses and repo docs for facts. |
| "A persona can replace the workflow." | A persona changes perspective; it does not replace verification gates. |
| "The adapter should explain the whole process." | Adapters help a tool discover the canonical docs. Duplicating content creates drift. |
| "A subagent means less need to verify." | Delegation increases the need for clear scope and independent verification. |

## Red Flags

- Duplicating workflow content in `CLAUDE.md`, `AGENTS.md`, or an adapter.
- Invoking several skills when one narrow workflow would do.
- Using a persona for implementation instead of review perspective.
- Delegating broad or ambiguous work to an agent without acceptance criteria.
- Reading roadmap or status docs as current facts without checking code and
  dates. A roadmap entry is an intention; a current-state doc can be stale.

## Verification

Before proceeding, confirm:

- [ ] The selected aid matches the task outcome.
- [ ] Canonical docs, not adapters, contain the durable guidance.
- [ ] Any specialist persona has a clear review lens and output expectation.
- [ ] Any delegated agent task is bounded and independently verifiable.
- [ ] Needed project context is named before implementation or review starts.
