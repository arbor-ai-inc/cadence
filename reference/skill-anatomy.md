# Skill Anatomy

How to author a cadence workflow — whether you are contributing one upstream or
adding your own alongside it. The goal is a workflow usable by more than one
coding agent without the content existing twice.

## Canonical Location

**One canonical statement per workflow, and every agent-facing file routes to
it.** That split is the whole design, and it is load-bearing rather than
tidiness: a 900-line workflow doc cannot sit in every session's context, and a
rule that exists in two places has already started to drift.

Durable workflow content lives under `reference/`:

```text
reference/
  using-agent-skills.md
  spec-driven-development.md
  test-driven-development.md
  code-review-and-quality.md
  personas/
```

Everything else is an adapter, and points at the canonical doc rather than
restating the process:

```text
skills/<skill-name>/SKILL.md        Claude Code — discovered by the plugin
adapters/codex/<skill-name>/SKILL.md  Codex — generated, see scripts/gen_adapters.py
CLAUDE.md / AGENTS.md               the user's own entry points
```

Inside a plugin, an adapter refers to its canonical doc through
`${CLAUDE_PLUGIN_ROOT}`, never a repo-relative path — the plugin is installed
outside the user's tree, so a relative path resolves to nothing.

## Codex Skill Adapter Format

Every Codex skill lives in its own directory under `adapters/codex/`:

```text
adapters/codex/
  skill-name/
    SKILL.md
```

**These are generated, not hand-written** — `scripts/gen_adapters.py` derives
them from the Claude adapters so the two cannot drift. Edit the Claude adapter
and regenerate.

`SKILL.md` is the only required file. Add scripts or supporting files only when
the adapter actually needs them. Most should not.

### Frontmatter

```yaml
---
name: skill-name-with-hyphens
description: Guides agents through [task/workflow]. Use when [specific trigger conditions].
---
```

Rules:

- `name`: Lowercase, hyphen-separated. Must match the directory name.
- `description`: Start with what the skill does, then include clear "Use when"
  trigger conditions. Include both what and when.
- Keep descriptions concise. Do not summarize the whole workflow in the
  description.

### Adapter Body

Adapter bodies should usually be thin:

```markdown
# Spec-Driven Development

Follow the canonical procedure in
`${CLAUDE_PLUGIN_ROOT}/reference/spec-driven-development.md` exactly.
```

A little more than a bare pointer is fine and often right: the two or three
rules an agent must not get wrong even before it loads the doc. What is not
fine is a second copy of the procedure.

## Claude Subagent Format

Some workflows require Claude Code subagents — isolated agents with defined
tool access that the skill adapter invokes by registered name. Subagents are
appropriate when a workflow step needs strict tool constraints or role
isolation (e.g., a reviewer that must never write to the spec file).

Subagents live under `agents/`:

```text
agents/
  skill-name-role.md
```

**Do not pin `model:` in a shipped subagent.** It silently overrides the model
the user chose for a role they are paying for, and a plugin agent's model is
not conveniently overridable. Omitting it inherits the session model.

### Frontmatter

```yaml
---
name: skill-name-role
description: One sentence describing the role. Invoke for .
tools: Read, Grep, Glob, Write
---
```

Rules:

- `name`: Lowercase, hyphen-separated. The invoking skill references this name.
- `tools`: List only what the role needs. Omit `Bash` and `Edit` unless
  required — prefer passing computed values in from the adapter instead.
- Keep tool access as narrow as possible.
- **A subagent prompt carries role mechanics, not workflow substance.** Its job
  is who the agent is, what it may touch, what it reads, and the exact output
  and verdict format. The *rules it grades by* belong in the canonical doc, and
  the prompt points at them.

#### Why this rule is stricter than it looks

Subagent files are the easiest place in the repo to create agent drift, and the
presubmit **cannot** catch it:

- The thinness and duplication checks in `tests/check_agent_skills.py` run over
  the adapters. `agents/*` is **not** checked for thinness, and a line cap would
  be the wrong instrument anyway — these files are legitimately long.
- The duplication check only catches lines copied **verbatim**. A rule
  *paraphrased* out of a canonical doc into a subagent prompt passes every hook.

So the failure mode is silent and one-directional: a check added only to a
subagent prompt is a check the other agent never runs, and the two reviewers
quietly stop grading the same way. Reviewers enforce this by reading, not by CI.
If a subagent needs behaviour the canonical doc lacks, add it to the canonical
doc and reference it — the point of `reference/` is that every agent inherits
from one source.

### Intentional Duplication

Claude Code subagents must carry enough local instruction to act safely when
invoked with limited context. Role-specific safety constraints (prime
directives, write restrictions, output schemas) may therefore be repeated from
the canonical workflow doc. Make this explicit near the top of the subagent
file:

```markdown
<!-- Canonical workflow: ${CLAUDE_PLUGIN_ROOT}/reference/<workflow>.md.
This subagent intentionally repeats role-specific safety constraints
because subagents must carry enough local instruction to act safely when
invoked with limited context. Keep durable workflow changes in the
canonical doc; mirror only role-specific guardrails here. -->
```

Acknowledge the duplication in the adapter body with:

```markdown
<!-- agent-skill-duplication: acknowledged reason="Subagent carries role-specific safety constraints per skill-anatomy § Intentional Duplication." -->
```

### Adapter-Computed Values

When a subagent needs a computed value (e.g., a file hash), compute it in
the skill adapter — not inside the subagent. Pass the value in as part of
the invocation. This keeps the subagent's tool list narrow and makes the
computation testable independently of the subagent.

Example: the `spec-pipeline` workflow computes `spec_hash` and `product_hash`
in the `skills/review-spec/SKILL.md` adapter by running
`python3 ${CLAUDE_PLUGIN_ROOT}/tools/spec_hash.py`, then passes both values to
the reviewer subagent. The subagent uses `Read`, `Grep`, `Glob`, `Write` only —
no `Bash`.

## Multi-Step Workflows and Sub-Step Adapters

Some workflows decompose into individually invocable steps. Each step gets
its own canonical doc, Codex adapter, and Claude skill adapter, but the
parent workflow doc is the authoritative entry point.

```text
reference/
  parent-workflow.md        ← authoritative; describes the full loop
  step-one.md               ← canonical doc for the step
  step-two.md               ← canonical doc for the step

skills/
  parent-workflow/SKILL.md
  step-one/SKILL.md         ← thin adapter; points to step-one.md
  step-two/SKILL.md
```

Sub-step canonical docs should be thin: a brief overview, when to use the
step standalone vs as part of the parent workflow, and a pointer to the
parent for the full procedure.

Add sub-steps to `reference/README.md` as discoverable entries under their
parent, not as peer workflows. See `spec-pipeline`, `review-spec`, and
`draft-plan` as the reference implementation of this pattern.

## Canonical Workflow Format

Canonical workflow docs should use this shape unless a different structure is
clearer:

```markdown
# Skill Title

## Overview
One or two sentences explaining what this workflow does and why it matters.

## When To Use
- Triggering conditions.
- Explicit exclusions.

## Workflow
The main process, broken into concrete steps or phases.

## Common Rationalizations
| Rationalization | Reality |
|---|---|
| Excuse agents use to skip steps | Why the excuse is wrong |

## Red Flags
- Observable signs that the workflow is being violated.

## Verification
After completing the workflow, confirm:
- [ ] Evidence-backed exit criteria.
```

## Section Purposes

### Overview

The elevator pitch for the workflow. It should answer what the skill does and
why an agent should follow it.

### When To Use

Helps agents and humans decide if the workflow applies. Include positive
triggers and exclusions.

### Workflow

The heart of the skill. Steps should be specific and actionable.

Good:

```text
Run the project's `[commands].test` and fix failures before proceeding.
```

Bad:

```text
Make sure the tests work.
```

**Name the command, or name where the command is configured — never neither.**
A workflow that hardcodes one project's test invocation is unusable elsewhere;
one that says "run the tests" is unusable anywhere.

### Common Rationalizations

Capture excuses agents use to skip important steps and pair them with factual
counterpoints. Keep it short, and keep each row anchored to something that
actually happened — a rationalization row invented at the desk is a guess about
how an agent will misbehave, and they are cheap to write and easy to get
wrong.

### Red Flags

List observable signs that the workflow is being violated. These should help
during review and self-checks.

### Verification

Exit criteria must require evidence: test output, build output, screenshots,
manual reproduction notes, or a clear explanation of what could not be run.

## Supporting Files

Create supporting files only when:

- Reference material exceeds about 100 lines.
- Code tools or scripts are needed.
- Checklists are long enough to justify separate files.

Keep patterns and principles inline when they are short. Do not create empty
directories for symmetry.

## Writing Principles

1. Process over knowledge. Skills are workflows, not architecture dumps.
2. Specific over general. Commands and evidence beat vague guidance.
3. Evidence over assumption. Verification must prove the work.
4. Anti-rationalization. Name the tempting shortcut and why it fails.
5. Progressive disclosure. Load details only when needed.
6. Token-conscious. If removing a section would not change agent behavior,
   remove it.

## Naming Conventions

- Canonical workflow files: `lowercase-hyphen-separated.md`.
- Skill directories: `lowercase-hyphen-separated`, matching the workflow name.
- Skill files: `SKILL.md`.
- Supporting files: `lowercase-hyphen-separated.md`.

## Cross-Skill References

Reference other workflows by name and path:

```markdown
Follow `test-driven-development`
(`${CLAUDE_PLUGIN_ROOT}/reference/test-driven-development.md`) for test work.
```

Inside `reference/` itself, use a plain relative link
(`[test-driven-development](./test-driven-development.md)`) so the docs stay
navigable when read on their own.

Do not duplicate content between skills. Reference and link instead.

## Presubmit Guardrails

`tests/check_agent_skills.py` checks that shared workflow content stays
canonical:

- Every adapter must have valid frontmatter, include "Use when" trigger text,
  and reference its matching canonical doc.
- Adapters stay thin. They route to canonical docs instead of copying sections.
- Markdown links inside `reference/` must resolve.

**A check that has never been seen to fail is not known to work.** When you add
one, break the thing it guards, watch it fail, and restore it.

If duplicated workflow content is intentionally needed, acknowledge it in the
adapter with a reason:

```markdown
<!-- agent-skill-duplication: acknowledged reason="Claude needs this exact short excerpt before loading repo docs." -->
```

Use this sparingly. The reviewer should confirm that duplication is deliberate
and worth the maintenance cost.

## Required vs Recommended

Required for canonical workflow docs:

- Clear workflow title.
- Clear trigger conditions.
- Concrete process steps.
- Evidence-backed verification.

Required for adapters:

- `skills/<skill-name>/SKILL.md`.
- Valid YAML frontmatter with `name` and `description`.
- A body that points to the canonical workflow doc via `${CLAUDE_PLUGIN_ROOT}`.

Recommended:

- The standard canonical section flow above.
- Common rationalizations and red flags when they prevent real failure modes.
- Supporting files only when they keep the main workflow focused.
