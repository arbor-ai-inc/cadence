# handoff

Write or resume a **handoff**: the file that lets a later session pick up a
multi-session track without re-deriving it.

## Overview

Left alone, a handoff turns into a ledger. New "start here" sections stack on top of
old ones, durable facts sit beside one-off state, and the hard-won rules are never read
again, because the file lives in a gitignored folder nobody else opens. So a handoff
holds four kinds of memory, each with its own section, lifetime and cap, and the kinds
that outlive the track move into the repository instead of piling up in the file.

| Memory | What it is | Section | Lifetime | When it outgrows the track |
|---|---|---|---|---|
| **Working** | Goal, where things stand, the next action, what is in flight | `## Resume here` | Rewritten every write | Never promoted; it goes stale |
| **Episodic** | What happened: tried, shipped, decided and why | `## Log` | Appended, then folded | Never as a whole: commits, PRs and the tracker hold the detail |
| **Semantic** | Durable facts: verified state, settled and rejected decisions | `## Facts` | Kept while true, each with source and date | The repo doc that owns the area |
| **Procedural** | How to act: rules, traps, things not to do | `## Rules` | Kept while they apply | A retro fragment, or the doc that owns the behaviour |

Working and episodic memory are what a handoff is for. Facts and rules stay only while
they are specific to the track; **learn from** moves the rest into the repo by PR.

`python3 ${CLAUDE_PLUGIN_ROOT}/tools/handoff.py` does the mechanical steps (Python 3.11+,
standard library, no network, runs only `git`). Its settings are the `[handoff]` table
of `cadence.toml`. Without it, do the same steps by hand (§ *Without the tool*); the
procedure doesn't change.

## When To Use

| Say | Mode |
|---|---|
| `save <slug> handoff` | **write**: creates the file if missing, else updates it |
| `update <slug> handoff` | **write**, but refuses if no handoff matches and lists those that exist |
| `pick up from <slug> handoff` | **resume** |
| `learn from <slug> handoff` | **harvest**: move what it learned into the repo, then prune |
| `prune <slug> handoff` | **prune** |
| `close <slug> handoff` | **close** |
| `list handoffs` | **list**: `handoff.py list` |

Also run a **write** unprompted when a long session on an unfinished track is about to
end or compact. A project can have [`execute-issue`](./execute-issue.md) resume an
issue's handoff at the start of a run, and save one when it stops unfinished, through
that workflow's overlay.

Not for:

- Work that finishes in one session. The PR body and a retro fragment cover it.
- Facts or rules everyone needs today. Put those in their real home directly.
- Anything meant for another person. Use [`human-brief`](./human-brief.md).

## Workflow

### The file

- **Location:** `<dir>/HANDOFF-<slug>.md` in the **main** worktree, `<dir>` defaulting
  to `.local/`. `handoff.py` always reads and writes there, from whichever worktree it
  runs, so a handoff saved in one worktree is found from every other. The header's
  `Checkout:` names the worktree the work happens in. One exception: from a linked
  worktree of a checkout whose git directory lives elsewhere, it stops and says to run
  from the main worktree.
- **Never tracked:** `handoff.py new` refuses a path git would track. Add `<dir>/` to
  `.gitignore` first. `<dir>` may also sit outside the repository; it is then checked
  against whichever repository holds it, if any.
- **One copy:** another clone reads the file by path; it never copies it. A copy
  written back resurrects what the original deleted.
- **Slug:** the name the team already uses: an issue id plus topic
  (`PROJ-12-widget-cache`), `epic-…`, `spec-…` or `theme-…`. No dates.
- **Resolving:** `handoff.py resolve <query>` takes the full slug, an issue id or a
  unique fragment. Exit 0 is one match, 3 ambiguous (ask which), 4 none (only **save**
  may create). An issue id matches only that issue: `PROJ-1` never finds `PROJ-12-…`.
- **Backup:** one `<file>.prev` (`handoff.py backup <slug>`), rotated before each write.
- **Caps** (non-blank lines, configurable): `## Resume here` 40, the file 300, the
  archive 300, a log entry 5.

```markdown
# Handoff — <slug>

Issue: <id(s) or "none — theme">  ·  Epic/project: <name or none>  ·  Spec: <path or none>
Repo: <owner/name>  ·  Checkout: <absolute path>  ·  Branch(es): <names or none>
Owner: <person>  ·  Started: <date>  ·  Last written: <date>  ·  Status: active | parked (<why>) | closing

## Resume here — <date>
Goal: <one line: what done looks like>
State: <3–8 bullets: what is true now, with PR / branch / issue ids>
Next: <the single next action, startable without asking>
Waiting on: <who, what, since when>  (omit if nothing)
In flight: <anything that breaks if forgotten>

## Rules
- <track-specific rule or trap> — why: <one line> (<date>)

## Facts
- <fact> — source: <command, PR, doc> · verified <date>
### Decided — don't re-open
- <decision> — why: <one line> · <date>
### Rejected — don't re-propose
- <option> — why not: <one line> · <date>

## Log
### <date> — <one-line summary>
- Did: … · Decided: … (why) · Rejected: … · Promoted: <item> → <home>
```

[`examples/sample-handoff.md`](../examples/sample-handoff.md) is a complete one; it lints with no errors.

### Resume

1. **Resolve the slug.** Continue in whichever worktree holds the branch now; the
   header's `Checkout:` may be stale.
2. **Read `## Resume here` and `## Rules` in full.** Read `## Facts` only for what the
   next action touches, and `## Log` only when you need the reason for something.
3. **Check every state line you'll rely on** against the real system before acting:
   git, the forge (PRs, CI), the tracker. Working memory is a snapshot.
4. **Say back in 3–5 lines:** the goal, the state, the next action, and anything the
   handoff got wrong. Then continue.

### Write (save / update)

1. **Rotate the backup** (`handoff.py backup <slug>`), or create the file
   (`handoff.py new <slug> [--issue ID]`).
2. **Refresh the header:** `Last written`, `Status`, `Branch(es)`, any new issue.
3. **Rewrite `## Resume here` from scratch.** Verify each state line now; don't copy
   the old one. `Next` must be one action someone can start without asking.
4. **Append one log entry** of five lines or fewer: what happened (with ids), what was
   decided and why, what was rejected, what was promoted.
5. **Classify each new durable item** as a fact or a rule. Track-only: keep it, with
   its source or reason and a date. Broader: tell the user where you'd promote it
   (§ *Harvest*), and promote only on their yes. If not now, record
   `- → to promote: <item> → <home> — source: … · verified <date>` for the next harvest.
6. **Prune** what is no longer true, then **`handoff.py lint <slug>`**: no errors. Over a
   cap, compress (§ *Prune*); never append to make room.
7. **Report in 2–4 lines:** the path, the next action, every promotion made or proposed.

### Harvest (`learn from`)

1. **Inventory** `## Facts` and `## Rules`, plus any "gotchas" or "how to work here"
   sections. Tag each item **track-only** or **broader**.
2. **Re-check each broader fact** against its source today. A stale fact is deleted,
   not promoted.
3. **Route each item to its home.** If the project says where knowledge lives
   (`AGENTS.md`, `CLAUDE.md`, or this workflow's overlay), use that. Otherwise:

   | Item | Home |
   |---|---|
   | Fact about the system | The doc that owns the area: architecture, component README, runbook, current-state doc |
   | Decision with a reason | The project's decision log |
   | Trap that arose on a ticket | A retro fragment under `[paths].retros` (see [`retro`](./retro.md)) |
   | Standing rule for how to work | The guidance doc or overlay that owns the behaviour |
   | A person's working preference | That agent's own memory, not the repo |
   | A reusable workflow | A new workflow (see [`skill-anatomy`](./skill-anatomy.md)) |

4. **Confirm the list with the user before writing**, including what you'd drop as
   stale. "Learn from" means *move into the repo*, not *read*.
5. **Batch by destination:** one PR per doc area. Rewrite each item for its new home;
   don't paste handoff prose.
6. **Replace each promoted item with a pointer** (`- → promoted to docs/x.md (PR #12)`),
   log it, then prune.

### Prune

1. Delete facts no longer true, rules that no longer apply, and pointers whose PR has
   merged.
2. Collapse superseded items into the latest one.
3. Fold log entries older than the last five sessions into `### Decided` /
   `### Rejected` one-liners. Move the untouched rest to `HANDOFF-<slug>.archive.md`,
   which is capped too. Never trim `## Rules` to make room; promote instead.
4. `handoff.py lint <slug>` reports no errors.

### Close

1. A final harvest: every broader item is promoted or dropped with a reason.
2. Propose a short closing comment for the tracker: the outcome, the PRs, where the
   lessons went. Post it only with the user's approval.
3. Set `Status: closing`, then delete the handoff, its `.prev` and its archive once the
   user confirms.

### Without the tool

If `handoff.py` can't run (no Python 3.11+), do each step by hand from the main
worktree, `$M`. From the main worktree itself (an ordinary clone, a submodule, or a
checkout whose git directory lives elsewhere) that is `git rev-parse --show-toplevel`.
From a linked worktree of an ordinary clone it is the parent of
`git rev-parse --git-common-dir`; of a submodule, the submodule's own checkout.

- **new:** stop if the file exists; `mkdir -p "$M/<dir>"`; stop unless both
  `git -C "$M" check-ignore -q <dir>/HANDOFF-<slug>.md` and the same for
  `<dir>/HANDOFF-<slug>.md.prev` succeed (ignore all of `<dir>/`); fill the template's header from
  `git remote get-url origin`, `git rev-parse --show-toplevel` and
  `git branch --show-current`.
- **resolve / list:** the rules in § *The file*, over `$M/<dir>/HANDOFF-*.md`, leaving
  out `*.archive.md`.
- **lint:** count non-blank lines against the caps; confirm exactly one
  `## Resume here`, with a `Next:`.

Say in the report that the checks were done by hand.

## Common Rationalizations

| Rationalization | Reality |
|---|---|
| "I'll add a new *start here* section at the top." | That is how a handoff reaches a thousand lines with several resume points. `## Resume here` is rewritten, never stacked. |
| "The handoff says the PR is open, so it is." | Working memory is a snapshot. Check before acting. |
| "This rule is useful, I'll keep it in the handoff." | If it's true beyond the track, nobody else will ever read it there. Promote it. |
| "I'll copy the handoff into the other clone." | A copy written back resurrects deleted content. Read it by path. |
| "A timestamped backup on every write is safer." | Nobody reads the pile. One `.prev` covers an undo. |
| "I'll record the full story in the log." | Git, PRs and the tracker hold the detail. The log holds the *what* with ids, plus the *why*. |
| "I'll harvest it all into one big docs PR." | Nobody can review that. Batch by destination. |

## Red Flags

- More than one resume-style section, or a `Next:` that can't be started without asking.
- A fact with no source and date, or a decision with no reason.
- A rule that plainly applies beyond the track, with no `Promoted:` or `→ to promote:` line.
- A `→ to promote:` line that survived a harvest, or is older than `stale_days`.
- Anything promoted, posted or deleted without the user's yes.
- The same handoff in several clones, or timestamped backups piling up.
- Acting on a state line without checking it.

`handoff.py lint` catches the stacked resume sections, a missing `Next:`, unsourced
facts and reasonless decisions, stale `→ to promote:` lines and backups piling up. The
rest need judgment.

## Verification

After a **write**:

- [ ] Exactly one `## Resume here`, dated today; each state line checked this session.
- [ ] One new log entry of five lines or fewer, with `Promoted:` when anything moved.
- [ ] Every new fact has a source and a date; every decision or rejection a reason.
- [ ] `handoff.py lint <slug>` reports no errors (or the by-hand checks were done and
      said so), and `.prev` holds the previous version.

After a **resume**: every state line the next action depends on was checked, any
mismatch was reported, and the say-back came before any action.

After a **harvest / prune**: every broader item is promoted (with its PR or fragment)
or dropped with a reason, promotions are batched by destination, and the file and its
archive are within their caps.
