# Configuration

Two surfaces, split by who owns the value.

**`cadence.toml`** at your repository root describes the *project*. Commit it.
Start from [`templates/cadence.toml`](../templates/cadence.toml), which documents
every key inline.

**`userConfig`**, prompted when you install the plugin, holds *per-user secrets*
— a chat bot token, a tracker API token. Never committed, and cadence never
writes them anywhere.

Check what is in effect at any time:

```bash
./.cadence/cadence config
./.cadence/cadence config --json
```

**A missing `cadence.toml` is fine and supported.** The defaults assume GitHub,
no issue tracker, and asking questions in-session, which needs no credentials. A
*malformed* one is not fine: the loader raises rather than falling back, because
silently running on defaults when you wrote a config is how a must-stop boundary
stops being enforced.

## The one section with no useful default

```toml
[[must_stop]]
path = "db/migrations/"
reason = "a schema migration"
```

`[[must_stop]]` is the list of surfaces where an agent must **stop and ask** —
never decide, never fan out. Only you know where those are, so cadence ships
none, and **an empty boundary means an autonomous run will never stop for a
human.** That is almost never what you want.

`path` ending in `/` means that directory and everything under it. Without a
trailing slash it is an exact file, so `models.py` does not also match
`models.py.bak`.

`reason` is required. It is what an agent shows a human when it stops, and an
unexplained boundary gets argued with.

Good candidates: schema and migrations, published API contracts, anything on a
serving or payment critical path, money and ranking logic, audit trails, and
anything shipped to third parties.

Check a path against it:

```bash
./.cadence/cadence must-stop db/migrations/007.sql   # exit 5
./.cadence/cadence must-stop src/ui/button.tsx       # exit 0
```

Enforce it on every commit. Run `/cadence:init --hook` to write
`.cadence/check-scope` into your repo, then point a pre-commit hook at that
path. The shim is there because a hook runs in a plain shell with no
`${CLAUDE_PLUGIN_ROOT}` and the plugin path is version-pinned; it resolves the
plugin at run time and exits non-zero if it cannot, rather than passing.

That hook is the enforcement that matters — it is derived from git rather than
from a model's reading of a rule, and no reasoning inside a fan-out leaf gets
past it. **Absent enforcement and working enforcement look identical from inside
a run**, which is why `fanout.py init` warns when the hook is missing.

## Providers

| Section | Options | Default | Needs credentials? |
|---|---|---|---|
| `[tracker]` | `linear`, `github`, `none` | `none` | `linear` needs a Linear MCP server; `github` uses your `gh` auth |
| `[ask]` | `harness`, `slack`, `stdout` | `harness` | only `slack` |
| `[review]` | `coderabbit`, `codex`, `claude`, `subagent`, `none` | `none` | no |

### `[ask]` — how a workflow asks a human

`tools/ask.py` is the single entry point, and **its exit codes are the contract**
every workflow branches on:

| Exit | Meaning |
|---|---|
| `0` | answered; the reply is on stdout and nothing else is |
| `2` | **unanswered** — timed out, or the transport accepted the post and nobody replied |
| `3` | usage or configuration error |
| `4` | this provider cannot ask on its own; the caller must ask in-session |

`2` and `4` are deliberately distinct. Collapsing them would let a caller read
"ask in session" as "nobody answered", which is how a run ends up self-answering.

**A posted question is not a delivered one**, and no transport can tell a quiet
channel from a slow one — see
[`C-12`](../examples/case-studies.md#c-12--the-question-nobody-saw). Treat `2` as
unanswered, never as an answer.

`harness` is the default because it needs nothing: it prints the brief and exits
`4`, and the skill asks in the session that invoked it. Use `slack` for
unattended runs.

### `[review]` — the automated reviewer

**The one rule: the reviewer must not be the agent that wrote the code.** All
five options exist to satisfy that.

| Value | What runs | Available when driving with |
|---|---|---|
| `codex` | `codex exec` on the branch diff | anything with the Codex CLI |
| `claude` | `claude -p` on the branch diff | anything with the Claude CLI |
| `subagent` | a bundled reviewer subagent, fresh context | **Claude Code only** (needs Task) |
| `coderabbit` | a PR-time bot | anything |
| `none` | nothing | — |

Driving with Claude Code, prefer `codex`. **Driving with Codex, use `claude`** —
Codex has no Task tool so it cannot invoke a Claude subagent, but it can shell
out to the Claude CLI. `subagent` is the fallback when only one agent is
available: still fresh context, but the same model, so it is the weakest at
finding what that model missed the first time.

`bot_login` is only read by `coderabbit`, and it is threaded through every
function that reads it — so setting it genuinely changes which account's reviews
count, rather than being overridden by a default deeper in the call stack.

With `provider = "none"` the whole post-PR watch loop is skipped, and workflows
say so explicitly rather than reporting an unrun review as settled.

Read review state with the reader, never the check row:

```bash
./.cadence/cadence review-state --pr 123
./.cadence/cadence review-state --pr 123 --json
```

**A check row renders `pass` for a skipped, rate-limited, paused and stale
review alike.** That is nine measured occurrences
([`C-09`](../examples/case-studies.md#c-09--a-reviewer-that-reports-success-without-running))
and it is why this reader exists.

Provider specifics — exact commands, API quirks — are in
[`reference/providers/`](../reference/providers/).

### `[paths].principles` — the Gate 2 rubric

Gate 2 grades an engineering design against this file and nothing else, so
**a project that has not written one is running Gate 2 against generalities.**

Start from
[`templates/architectural-principles.starter.md`](../templates/architectural-principles.starter.md),
then do the part that makes it real: delete every principle you would not
actually enforce, and fill in the `In your codebase` line for each survivor. Ten
principles you mean beat twenty-six you inherited.

## Models

**Cadence pins no model and cannot set one.** This is a harness limitation, and
worth understanding because the failure it produces is silent.

Three facts:

1. A skill's `model:` pin **applies only to the turn that invoked the skill.**
   Your session model resumes on your next prompt.
2. A **subagent's** pin holds for that subagent's whole run.
3. Nothing else persists. No hook can change a model, and `modelOverrides` maps
   provider model IDs rather than assigning models to roles.

The spec pipeline stops to ask you questions, so it spans many turns. A pin on
it would cover the first round and nothing after — reading as though it applied
throughout. That is why cadence ships none, and why
`tests/check_agent_skills.py` fails on one.

### What `[models].recommended` does

```toml
[models]
recommended = "opus"
```

A workflow reads it, compares it to the model it is actually running on, and
**stops if they differ** — naming both, and how to switch. It enforces nothing
about which model runs. What it enforces is that you **find out**.

The defect this fixes is not "the wrong model ran". It is "the wrong model ran
and nothing said so".

Leave it unset if you do not care which model runs a workflow.

### Setting a model for real

Two ways, both the harness's own and both durable:

- **`/model <name>`** before starting. Lasts the session.
- **`"model"` in `.claude/settings.json`** — durable, and shared with the team if
  committed. Use `.claude/settings.local.json` for yourself only.

If a model choice appears to be ignored, check for an `availableModels`
allowlist. A value it excludes **is not used and the session keeps its current
model**, silently — which looks exactly like a pin that did not hold.
