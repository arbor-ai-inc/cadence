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
python3 tools/cadence_config.py
python3 tools/cadence_config.py --json
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
python3 tools/cadence_config.py must-stop db/migrations/007.sql   # exit 5
python3 tools/cadence_config.py must-stop src/ui/button.tsx       # exit 0
```

Enforce it on every commit by installing this as a pre-commit hook:

```bash
python3 tools/fanout.py check-scope
```

That hook is the enforcement that matters — it is derived from git rather than
from a model's reading of a rule, and no reasoning inside a fan-out leaf gets
past it. **Absent enforcement and working enforcement look identical from inside
a run**, which is why `fanout.py init` warns when the hook is missing.

## Providers

| Section | Options | Default | Needs credentials? |
|---|---|---|---|
| `[tracker]` | `linear`, `github`, `none` | `none` | `linear` needs a Linear MCP server; `github` uses your `gh` auth |
| `[ask]` | `harness`, `slack`, `stdout` | `harness` | only `slack` |
| `[review]` | `coderabbit`, `codex`, `subagent`, `none` | `none` | no |

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

With `provider = "none"` the whole post-PR watch loop is skipped, and workflows
say so explicitly rather than reporting an unrun review as settled.

Read review state with the reader, never the check row:

```bash
python3 tools/review_state.py --pr 123
python3 tools/review_state.py --pr 123 --json
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

Cadence pins no model anywhere, and `tests/check_agent_skills.py` fails on a pin.
A shipped pin silently overrides the model you chose for a role you are paying
for. `[models]` exists for your own layer to read; nothing in the plugin
enforces it.

If you do pin, know the asymmetry: **a subagent pin holds for that subagent's
whole run; a skill or command pin binds only the invoking turn.** The pipeline
stops for author decisions, and each answer starts a turn that has fallen back to
the session model — so treat an explicit re-pin as owed after every pause.
