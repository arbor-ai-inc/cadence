# Agent Personas

Specialist perspectives for AI coding agents. A persona is a review lens,
not a workflow: it changes what gets noticed, never which gates must pass.

Personas answer "who is reviewing or advising?" Skills answer "what workflow
must be followed?" Use personas for focused review passes, audits, and coverage
analysis. Use skills for execution steps and verification gates.

## Available Personas

| Persona | Role | Best For |
|---|---|---|
| [code-reviewer](./code-reviewer.md) | Staff engineer reviewer | General review across correctness, tests, architecture, security, performance, and maintainability. |
| [security-auditor](./security-auditor.md) | Security engineer | Security-focused review of auth, tenancy, data exposure, LLM/tool boundaries, and dependency risk. |
| [test-engineer](./test-engineer.md) | QA engineer | Test strategy, coverage analysis, and regression-test design. |
| [web-performance-auditor](./web-performance-auditor.md) | Web performance engineer | Performance-focused review of web UI, Core Web Vitals risks, rendering, loading, and network behavior. |

## How Personas Relate To Skills

| Layer | Purpose | Examples |
|---|---|---|
| Skill | The required workflow and verification gates | `test-driven-development`, `code-review-and-quality` |
| Persona | The specialist perspective and output format | `security-auditor`, `test-engineer` |
| User prompt or command | The orchestration decision | "Use the security-auditor persona on this diff" |

Personas should not invoke other personas. If another specialist pass is
needed, recommend it in the report and let the user or command harness
orchestrate it.

## Usage Examples

```text
Use the code-reviewer persona and the code-review-and-quality skill to review this PR.
```

```text
Use the test-engineer persona to identify missing regression coverage for this bug.
```

```text
Use the security-auditor persona to review this auth change.
```

## Adding Or Updating Personas

1. Keep each persona to one role and one output format.
2. Link to the relevant workflow skill instead of copying it.
3. Include when to invoke the persona and when not to.
4. Keep findings evidence-based, with file and line references when reviewing
   code.
5. Update this README when adding a persona.
