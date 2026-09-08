# Setup

Numbered, in order, for a repo of any age. Each step says whether it is
**required**, what it unlocks, and **what skipping it costs** — because several
things here degrade quietly rather than failing, and a degraded workflow that
reports success is worse than one that refuses.

## What you actually have to do

| Step | Required? | Time | If you skip it |
|---|---|---|---|
| 1. Install | **yes** | 1 min | nothing works |
| 2. `/cadence:init` | **yes** | 1 min | no config; every workflow guesses |
| 3. Lint and test commands | **yes** | 2 min | workflows cannot verify their own work |
| 4. Retro ledger | for retro | 1 min | `/cadence:retro-synthesis` has nowhere to read |
| 5. Must-stop boundary + hook | **before any autonomous run** | 15 min | an agent decides things it should have asked about |
| 6. A reviewer | strongly recommended | 2 min | review falls back to the same model that wrote the code |
| 7. Issue tracker | optional | 2 min | you paste the issue body instead |
| 8. Chat transport | only for unattended runs | 10 min | a blocked run waits out its timeout with nobody watching |
| 9. Principles rubric | **for the spec pipeline only** | 1–2 hrs | Gate 2 grades against generalities, which manufactures the appearance of review |
| 10. Architecture / background docs | optional | varies | review checks correctness but not boundaries, and says so |

**You can stop after step 4** and have something worth using. Steps 5–8 are for
autonomy. Step 9 is only if you want the spec pipeline, and it is the one step
that is genuinely hours rather than minutes.

---

## 1. Install the plugin — required

In an interactive `claude` terminal:

```
/plugin marketplace add arbor-ai-inc/cadence
/plugin install cadence@cadence
/reload-plugins
```

Check it took:

```
/plugin list
```

**Updating later is three commands, not one.** The first only refreshes a local
clone; the second is what actually changes your install:

```
/plugin marketplace update cadence
/plugin update cadence@cadence
/reload-plugins
```

A stale clone and a stale install look identical from the `/` menu, so if a
skill you expect is missing, check the version rather than the menu.

## 2. Scaffold the config — required

From your repo:

```
/cadence:init
```

That writes:

| File | What it is |
|---|---|
| `cadence.toml` | your config — the only file cadence reads |
| `.cadence/cadence` | a shim so you can run cadence's tools from a plain shell |
| `docs/retros/` | the retro ledger (step 4) |

**It never overwrites.** An existing file is reported and left alone, so it is
safe to re-run on a repo that already has a `cadence.toml`.

Add `--hook` for step 5, `--all` for the optional templates.

Everything after this is editing `cadence.toml`. Check what it reads at any
time with `./.cadence/cadence config`.

## 3. Lint and test commands — required

```toml
[commands]
lint = "pre-commit run --all-files"
test = "pytest"
```

**Put the whole command in.** Venv activation, env vars, workspace filters — all
of it. Cadence runs the string verbatim. Workflows say *"run the lint command"*
and never hardcode one, which is what makes them portable.

Use the same commands your CI uses. If they differ, a workflow can go green
locally and red in CI, and it has no way to know.

**Why required:** every workflow that changes code verifies it before handing
back. Without these it cannot, and it will tell you so rather than pretend —
but you have lost the check.

## 4. The retro ledger — required for the retro loop

`/cadence:init` already made it:

```
docs/retros/
  TRAPS.md               cumulative occurrence counts
  _fragment_template.md  the shape a capture writes
  pending/               one fragment per ticket, awaiting a batch
  archive/               fragments a batch consumed
```

From now on, **every pull request leaves one fragment** naming what it taught.
An observation and what it cost. No rule, no imperative.

At 15 fragments, run `/cadence:retro-synthesis`.

**Write no rules before then**, however general a lesson feels. That judgement is
exactly what the count table exists to overrule — writing rules one ticket at a
time was measured over twelve consecutive retros and failed three ways at once.
See [`examples/case-studies.md`](../examples/case-studies.md).

**Why this is step 4 and not step 9:** it is the cheapest thing here and the
only one that compounds. Two minutes of setup, one fragment per PR.

## 5. The must-stop boundary — required before any autonomous run

This is the one step where skipping it is actively unsafe, so it is worth the
fifteen minutes.

`[[must_stop]]` lists the surfaces where an agent must **stop and ask** — never
decide, never fan out:

```toml
[[must_stop]]
path = "db/migrations/"
reason = "applied forward against real data; reverting the commit does not undo it"

[[must_stop]]
path = "src/billing/"
reason = "moves money; a wrong amount is refunded, not redeployed"

[[must_stop]]
path = "api/openapi.yaml"
reason = "a published contract; a breaking edit breaks callers this repo cannot see"
```

**Cadence ships none, because only you know yours.** An empty boundary means an
autonomous run will never stop for a human.

Rules:

- `path` ending in `/` covers that directory and everything under it. Without a
  trailing slash it is an exact file, so `models.py` does not also match
  `models.py.bak`.
- `reason` is required. It is what the agent shows you when it stops, and an
  unexplained boundary gets argued with.
- **Own only what carries real risk.** A boundary that lists everything stops
  for everything, and then gets bypassed. Good candidates: migrations, published
  contracts, auth, money, ranking, audit trails, anything shipped to third
  parties. Bad candidates: UI components, utilities, tests.

Check an entry works:

```bash
./.cadence/cadence must-stop db/migrations/007.sql   # exit 5 — inside
./.cadence/cadence must-stop src/ui/Button.tsx       # exit 0 — clear
```

### 5b. Wire the hook — this is the part that enforces it

`/cadence:init --hook` writes `.cadence/check-scope`. **It does nothing until
something calls it.** Point your hook runner at it:

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: cadence-check-scope
        name: cadence must-stop boundary
        entry: ./.cadence/check-scope
        language: system
        pass_filenames: false
        always_run: true
```

No pre-commit? Any runner works — husky, lefthook, a plain
`.git/hooks/pre-commit` — the shim is an ordinary executable.

**Be precise about what this buys you.** It refuses a commit **only on a `fan/*`
branch or inside a fan-out worktree**. On main or an ordinary feature branch it
is a no-op. So it bounds decision fan-out; it does **not** guard those paths on
every commit. Reading five `[[must_stop]]` entries it is easy to assume
otherwise.

Everywhere else, the boundary is read by the agent and obeyed because it chose
to. That is guidance, not a gate — which is exactly why the config exists, so at
least the agent is reading a list you wrote rather than guessing.

**Absent enforcement and working enforcement look identical from inside a run.**
That is why `fanout.py init` warns when the hook is missing, and why this is a
step rather than a footnote.

## 6. A reviewer — strongly recommended

```toml
[review]
provider = "codex"
```

**The one rule: the reviewer must not be the agent that wrote the code.**

| Value | What runs | Available when driving with |
|---|---|---|
| `codex` | `codex exec` on the diff | anything with the Codex CLI |
| `claude` | `claude -p` on the diff | anything with the Claude CLI |
| `subagent` | a bundled reviewer, fresh context | **Claude Code only** (needs Task) |
| `coderabbit` | a PR-time bot | anything |
| `none` | nothing | — |

Driving with Claude Code, use `codex`. Driving with Codex, use `claude`.

`subagent` is the fallback when only one agent is available: still fresh
context, but the same model — so it is the weakest of the three at finding what
that model missed the first time. That is the cost of skipping this step: you
get the weakest option by default.

With `none`, workflows skip the review loop and **say so**, rather than
reporting an unrun review as settled.

## 7. Issue tracker — optional

```toml
[tracker]
provider = "github"          # linear | github | none
issue_key = "^([A-Z]{2,5}-[0-9]+)$"
```

`none` works fine: you paste the issue body and lose only the automatic
state transitions. `/cadence:execute-issue` still runs.

## 8. Chat transport — only for unattended runs

```toml
[ask]
provider = "slack"
```

Default is `harness`, which asks in your current session and needs no
credentials. Switch to `slack` only if you want runs that continue while you
are away.

**Know the failure mode before relying on it.** No transport can tell a quiet
channel from a slow one. A question can post cleanly, nobody sees it, and the
run waits out its timeout — that is a real measured incident
([`C-12`](../examples/case-studies.md#c-12--the-question-nobody-saw)). Cadence
treats a timeout as *unanswered*, never as an answer, and never self-answers.

## 9. The principles rubric — required for the spec pipeline, and only for it

**Skip this entirely unless you want `/cadence:spec`.** Nothing else reads it.

Gate 2 grades an engineering design against `[paths].principles` **and nothing
else**. So:

```bash
./.cadence/cadence init --all      # writes docs/architectural-principles.md
```

Then do the work, which is the actual cost of this step:

1. **Delete every principle you would not enforce.** Ten you mean beat
   twenty-six you inherited. A principle nobody would enforce is one a design
   can violate with a shrug, and that teaches an agent the whole file is
   advisory.
2. **Fill in the `In your codebase` line for each survivor** — one concrete
   pattern or decision in your system that the principle already governs, that a
   reviewer can point at. If you cannot name one, that is evidence for step 1.
3. **Renumber, and expect it to break references.** Prose cites these by number
   and nothing validates it.

**Why an unfilled rubric is worse than none:** Gate 2 will run, produce
verdicts, and grade against generalities. You get the appearance of
architectural review with none of the substance — and unlike a missing gate,
nothing tells you.

Budget an hour or two. It is the only step here that is not minutes.

## 10. Architecture and background docs — optional, and honest about it

Cadence does not require these and does not create them. What they change:

| Workflow | Reads | Without it |
|---|---|---|
| `code-review` | the architecture doc for the boundary the diff touches | a **correctness** review, not an architecture review — and the findings say so rather than implying boundaries were checked |
| `spec-driven-development` | your current-state doc | assumptions about what is built go unchecked |
| `eng-design-reviewer` | the rubric, plus architecture | Gate 2 sees the design and not the system it lands in |

There is no config key for these. Workflows load context **by kind** — "the
architecture doc for this boundary", "the current-state doc" — and find whatever
you have. So the useful move is not creating files to satisfy cadence; it is
having them where a reader would look.

Two warnings the workflows carry, worth knowing whatever you write:

- **A roadmap entry is not a built feature.** Treating one as current is a
  recurring trap.
- **A current-state doc can be stale**, and stale reads exactly like accurate.
  Check the code.

---

## Verify the whole thing

```bash
./.cadence/cadence config        # everything cadence reads
./.cadence/cadence root          # which installed version you are on
```

Then the cheapest real test — pick a small change, and:

```
/cadence:code-review
```

If it names the reviewer it used, runs your lint and test commands, and hands
back findings in plain English with something checkable per row, setup is done.

## When something is wrong

| Symptom | Cause |
|---|---|
| a skill is missing from `/` | stale install — run all three update commands, then `/reload-plugins` |
| `./.cadence/cadence: No such file` | run `/cadence:init` |
| "could not find the installed plugin" | marketplace added but plugin not installed — `/plugin install cadence@cadence` |
| `must-stop` says `NOT CHECKED` | no `[[must_stop]]` configured; every path passes trivially |
| the hook never fires | it only fires on `fan/*` branches — by design |
| a config change had no effect | `cadence.toml` must be at the **repo root** |
