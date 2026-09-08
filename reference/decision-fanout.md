# Decision Fan-out

## Overview

When an autonomous run reaches a decision it cannot make alone, it has two bad
options today: guess, or block on a human who is probably asleep. This workflow
adds a third. The agent builds **every defensible option in its own git
worktree**, records the decision, and keeps going. In the morning the author
reads one ledger, picks one answer per decision, and runs one command that keeps
the matching branch and deletes the rest.

The trade is deliberate: tokens are cheap and human calendar time is not. A
night spent blocked on one question costs more than eight branches nobody keeps.

Three things make this work rather than produce a pile of half-built branches:

- **A four-way classification**, so only decisions that deserve a branch get
  one. Most do not.
- **A prefix tree, not a Cartesian product.** Each fork branches from its
  parent's current HEAD, so shared work is built once.
- **The ledger is the deliverable.** Worktrees are the mechanism. Waking up to
  eight diffs is more human work, not less. Each decision in it is a
  [`human-brief`](./human-brief.md) **Shape A decision brief**, which owns that
  format; `WRONG IF` is the line that does the work here, because a
  recommendation with no stated falsifier is the one that gets rubber-stamped.

The under-appreciated payoff is empirical: a leaf whose tests will not go green
is an answer. Fan-out does not only defer decisions, it kills options overnight,
and some decisions are already resolved by the time the author looks.

`tools/fanout.py` owns all tree state. Call it; never hand-manage
worktrees, branch names, or the ledger. `collapse` can only be exact if one
writer produced the tree.

## When To Use

- During [`execute-issue`](./execute-issue.md) implementation, when a decision
  with more than one defensible answer blocks progress.
- When the author is unavailable and the alternative is a run that stalls until
  its `ask.py ask` timeout expires.

Do **not** use it for:

- **Spec text.** Variants of `design.md` are harder to compare than diffs and do
  not collapse empirically overnight. Gate decisions stay with
  [`spec-pipeline`](./spec-pipeline.md).
- **Anything in the `must-stop` class below.** Eight variants of a schema change
  are strictly worse than one blocking question.
- **A decision you can just make.** See the classification first: most
  decisions are reversible and want a log line, not a branch.

## Classify Before You Fork

This is **two questions in a fixed order**, not one judgement across four
options. Answer the gate first and only reach the second question if the gate
passes. The order is the point: the two costs are not symmetric, and reversibility
is the easier question to answer, so a single combined judgement reliably answers
it and skips the other.

### Step 1 — the gate: does this touch a protected surface?

If yes, it is **`must-stop`**: stop and ask. Do not fan out, and do not go on to
Step 2. Reversibility is irrelevant here — a one-line column-type change is
trivially reversible in the editor and is still a migration.

**The authoritative answer is `[[must_stop]]` in `cadence.toml`**, and
`python3 tools/cadence_config.py must-stop <path>...` gives it — exit 5 means
inside the boundary. Ask that before reasoning about it.

The paths cannot cover everything, so a decision is also `must-stop` when it
involves any of:

- a new, moved, or retired endpoint across one of your architecture's declared
  boundaries: a route, RPC, topic, or a table another component reads
- a schema or migration change, or a change to **which** component writes a table
- behaviour or latency on a serving, request or payment critical path
- money, ranking, or auditability logic
- anything under a published contract other teams build against
- an architectural decision that should have gone through the design gate and did not
- anything that can only be evaluated by running a dev server, which a leaf must
  not do

**An empty `[[must_stop]]` does not make these disappear.** It makes the prose
list the only gate, which is a prompt rather than an enforcement — so a project
with an empty boundary should expect fan-out to reach places it should not, and
should fill the config in rather than trusting this list.

**The decision will almost never name the surface — it names a mechanism.** This
is the failure mode the eval measured, so translate before answering:

| What the decision says | What it actually is |
|---|---|
| "should this column be TEXT or UUID" | a **migration** |
| "add a field to the payload we publish" | a **published contract**, and a boundary edge |
| "cache the fee calculation in process" | **money logic** — the mechanism is a cache, the subject is fees |
| "should the generated bundle read the registry" | the **artifact shipped to third parties** |
| "an attribute on the embed script" | shipped to **third parties** |
| "validate synchronously or in a worker" | a **critical path**, if it is on a request |
| "which table should own this counter" | a **schema** decision, and possibly money-bearing tables |

Ask what the decision is *about*, not what it is *made of*. If the answer names
a surface on the list, the gate has fired however small the mechanism looks.

Default to `must-stop` for anything brushing that list, and to fan-out
otherwise. That inversion is the whole speed gain: the old default was to ask.

### Step 2 — only now, how costly is it to reverse?

Reached only by decisions that cleared the gate. Everything here is already known
not to touch a protected surface, so the only remaining question is reversal cost:

| Class | Test | Action |
|---|---|---|
| `mechanical` | one defensible answer | decide, `record --kind mechanical`, continue |
| `two-way-door` | wrong is cheap to undo later | decide, `record --kind two-way` with the reversal cost, continue. **No branch** |
| `one-way-door, contained` | costly to undo, effects stay inside this diff | **fan out** |

**The `two-way-door` row is what keeps a ticket from producing eight worktrees.**
Ask the reversal question literally: if this is wrong, what does undoing it cost?

"Costly" needs a threshold or it collapses into opinion, so use this one: a
decision is a **one-way door** when undoing it later means changing code that
calls it, migrating data already written, or removing an operational or packaging
dependency. If undoing it is confined to the file that made the choice, it is a
**two-way door** — pick, write down the reversal cost, and move on.

By that test, swapping a constant for a function is two-way even though it changes
behaviour; adding a dependency is one-way even though it is one line.

**Do not reach for `two-way-door` because a change is small.** A new dependency
and a concurrency structure are both easy to *write* and expensive to *remove* —
they are one-way doors, and calling them two-way means deciding an irreversible
thing silently, with no ledger and no human. The test is the cost of undoing it
later, not the size of the diff today.

**The categories above are prose because they need judgment. The paths are
enforced in code because they do not.** `[[must_stop]]` in `cadence.toml` is the
single machine-readable definition — one loader parses it and one matcher
applies it — and it bites twice:

- `fork` refuses (exit 3) if the work leading to the decision already touches a
  must-stop path, or if `--touches` declares one. The tree is illegitimate
  before it exists.
- The `fanout-scope` commit hook refuses **any** commit on a `fan/*` branch
  touching one (exit 5). This is the enforcement that matters: it is derived
  from git rather than from a model's reading of a rule, it runs on every
  commit, and no amount of reasoning inside a leaf gets past it. Install it as a
  pre-commit hook running `python3 tools/fanout.py check-scope`.

Do not restate those paths anywhere else. A rule written in two places is a rule
that will disagree with itself; change the config. Note the hook only fires
where it has actually been installed, which is why `init` warns when it is
missing — **absent enforcement and working enforcement look identical from
inside a run.**

**Prune dominated options before forking.** Every option must carry a reason a
competent engineer would choose *it*. If you cannot write that sentence, the
option is dominated: pass it as `--drop slug:why` so the ledger records that it
was considered and rejected. This routinely takes a 3x4x2 tree down to 2x2x2.
`fork` refuses an option string without a reason, which is the point.

## Workflow

1. Pin the base once, on the issue branch, before any decision:

   ```bash
   python3 tools/agent-spec/fanout.py init XX-341
   ```

   Every leaf descends from this commit, so overnight drift on `main` costs one
   rebase of one survivor rather than one per leaf.

   `--max-parallel N` (default 3) sets how many leaf subagents build at once, and
   it is recorded in state so a resumed session honours the same number. It is
   the only dial here that trades money for calendar time: see step 6.

2. Implement until a decision blocks you. Classify it with the table above.

3. `mechanical` or `two-way-door`: record it and keep going. This is the common
   case.

   ```bash
   python3 tools/agent-spec/fanout.py record XX-341 --kind two-way \
     --question "One file or a retry/ package?" --answer "one file for now" \
     --reversal "a rename plus one import line"
   ```

4. `must-stop`: fall back to the existing escalation in
   [`execute-issue`](./execute-issue.md) step 5, unchanged. Do every part of
   the task that does not depend on the answer while the ask is out. Create no
   worktrees.

5. `one-way-door`: fork. Run this from the worktree the decision arose in, and
   the parent resolves from the working directory.

   ```bash
   python3 tools/agent-spec/fanout.py fork XX-341 \
     --decision "Where does the retry counter live?" \
     --why-you "both work; the operational cost is the author's to carry" \
     --source "src/publish.go:212" \
     --option "inprocess:counter in the publisher struct:no new dependency" \
     --option "redis:shared counter in Redis:survives a restart, aggregates across pods" \
     --drop "postgres:a write per publish attempt on the money path costs latency the project already refused"
   ```

   Exit 3 means the fan-out was **refused** because a cap would break: 8 leaves,
   depth 3, or 3 options. The refusal is recorded and rendered in the ledger.
   Treat it as a `must-stop` and ask instead. Never work around a cap by
   splitting one decision into two forks.

6. Continue each option in its own worktree. **One session builds all of them.**
   You launched `/execute` in one terminal, and that stays true: the session
   that forked spawns one subagent per leaf, each with its working directory
   pinned to that leaf's worktree, and collects their results. It does not open
   new terminals, and you do not attach to anything.

   Honour `max_parallel` from the tree (`status` prints it; default 3). Locally
   the constraint is not the model, it is Docker: the Python suites each start
   Postgres through `testcontainers`, and an unbounded fan-out exhausts it. In a
   cloud run each leaf gets its own container, so `max_parallel` can go as high
   as the leaf count — the same wall clock as building one leaf, at N times the
   spend. That is the whole trade, and it is the only place in this workflow
   where calendar time is bought with money rather than tokens. Sequential is
   still right when the suites are slow or flaky.

   Each subagent gets: the issue, the option it is building and why, its
   worktree path, and the instruction to close with the evidence gate in step 7.
   It does not get authority to fork again on its own — a decision discovered
   inside a leaf comes back to the parent session, which classifies it and
   decides whether the tree can afford another level.

   Bootstrap and hygiene per leaf:

   - Symlink `node_modules` and any `venv` from the primary checkout; a leaf that
     edits `requirements.txt` or `package.json` builds its own.
   - Run at most two or three leaf test suites at once. The Python suites start
     Postgres via `testcontainers`, and an unbounded fan-out exhausts Docker.
   - Never start a dev server in a leaf. The ports collide across worktrees.
   - Never push a leaf and never open a PR from one.

7. Close each leaf with the evidence gate, then record what it cost:

   ```bash
   python3 tools/agent-spec/fanout.py result XX-341 --tests pass \
     --evidence "go test ./internal/... : ok, 214 tests" \
     --lost "no cross-pod view: a two-pod deploy undercounts by design" \
     --notice "the retry count resets when a pod restarts" \
     --reversible yes \
     --switch-cost "swap one module; no stored data to migrate" \
     --risk "a restart loses the counter mid-window" \
     --open-question "does anything read the aggregate today?"
   ```

   **The tool measures; you judge.** Diff size, files touched, and dependency
   manifests are read from git, not typed — a hand-written line count is exactly
   the number that drifts from the code it describes, and the author is reading
   the ledger *because* they have not read the diff. What only you can supply:

   - `--evidence` is the command and what it reported, not the word "pass".
     "pytest -q: 412 passed" can be checked; "tests pass" cannot.
   - `--lost` is mandatory because an option that states only its upside is how a
     ledger flatters a path.
   - `--switch-cost` is mandatory because the author is choosing a door and needs
     to know how hard it shuts. An option that is cheap to leave is a different
     kind of choice from one that is not.
   - `--notice` is what a person would *see* if this shipped, in plain English
     with no file or type names. Shape A's consequence test: an option described
     only as a code change is not decidable by whoever has to live with it.
   - `--reversible yes|one-way` fills the column the author scans first.
   - `--failure` is required when tests fail, and it is the assertion text. A
     leaf that will not go green keeps its worktree: that is evidence, not a gap,
     and the assertion is what makes it evidence rather than a rumour.

8. Commit to a recommendation per decision. A flat menu pushes the judgment back
   onto the author, which is the cost this workflow exists to remove.

   ```bash
   python3 tools/agent-spec/fanout.py recommend XX-341 --decision d1 \
     --option inprocess --reason "the counter is per-process by definition" \
     --wrong-if "something already reads a cross-pod aggregate of this counter" \
     --if-silent "nothing ships; the tree waits and main drifts under it"
   ```

   `--wrong-if` and `--if-silent` are required, not optional colour. The first
   lets the author check the recommendation instead of trusting it; the second
   tells them what doing nothing costs.

9. Render the ledger, then post the digest. Neither blocks:

   ```bash
   python3 tools/agent-spec/fanout.py ledger XX-341
   python3 tools/agent-spec/fanout.py notify XX-341
   ```

   `notify` renders a chat-shaped digest — no tables, since chat transports do not
   render them — with each decision, its recommendation, per-option test
   outcomes and measured sizes, and the exact `collapse` command per leaf. It
   always prints the digest locally as well, and a transport failure does not fail
   the command.

   **The transport is a convenience here, never the delivery guarantee.** In
   [`C-12`](../examples/case-studies.md#c-12--the-question-nobody-saw) a
   post can succeed into a channel nobody watches, and no exit code can tell you
   that. So say it in the session that invoked the skill too, and mirror each
   fanned decision and its options onto the issue as a comment, the same
   way answered questions are mirrored. The tracker stays the system of record; the
   ledger is a local working artifact.

## What The Author Does

Read the ledger, then run the one command it prints for the chosen path:

```bash
python3 tools/agent-spec/fanout.py collapse XX-341 --choose d1=inprocess,d2=fixed
```

That keeps one worktree and deletes every other branch. Exit 4 means the choices
matched zero or several leaves; the ledger prints one exact command per leaf, so
prefer copying one. A worktree with uncommitted work is kept and reported rather
than dropped, unless `--force`.

The choice set does not have to answer every decision. A path that never reached
a decision has no answer to give for it, which is a property of the tree rather
than a gap in the ledger.

After collapse, rebase the survivor onto current `main` and continue
[`execute-issue`](./execute-issue.md) from its code-review step. The survivor is
an ordinary branch from there on. `abandon` discards a whole tree when the
answer is "none of these".

## The Human-Facing Docs

Two documents in this workflow are written for a person rather than an agent, and
they are what to send to someone who does not work in this repo daily:

- your own operator playbook — the morning
  procedure: read the report, pick a path, carry on. Plain English, terminal only.
- `[[must_stop]]` in `cadence.toml` — what fan-out is
  forbidden to touch, how that is enforced in three layers, what each layer
  misses, and the open questions for review.

Keep them in plain English, and fix them in the same PR as any change that makes
either one wrong. They are the only description of this workflow a reviewer who
is not an agent will read.

## Picking It Back Up

The session that built the tree is gone by morning, so everything needed to
resume is derivable from state rather than from a transcript:

```bash
python3 tools/agent-spec/fanout.py status XX-341
python3 tools/agent-spec/fanout.py status              # every tree on disk
```

Without an issue argument it lists every tree, with state, size and last-touched
time. That is the only way back to a tree whose run died before `collapse`: the
worktrees are gitignored, so `git status` is clean while a few hundred MB sit
there, and every other subcommand needs an issue id you may not know to ask for.
`init` prints the same reminder when other uncollapsed trees exist.

`status` reports one of `building` (leaves still owe results), `awaiting-decision`
(evidence in, recommendations recorded, the author's turn), or `collapsed`, and
in every case prints the next action — including the exact `collapse` commands
while it waits, and the rebase-then-code-review instruction once collapsed.

There are two ways an answer gets back in, and they end in the same state:

- **The author runs `collapse`** in a terminal. No agent involved.
- **The author tells a session** "collapse XX-341 to `d1=inprocess,d2=fixed`
  and carry on", and it runs the same command.

Either way the choice is written into `tree.json` under `collapsed`, so the next
`status` says `collapsed` and names the survivor. Do not invent a third channel:
a decision that lives only in a chat message is a decision the next session
cannot find.

## Common Rationalizations

| Rationalization | Reality |
|---|---|
| "Fan out on everything and let the author sort it out." | Eight diffs to read is more human work than one question to answer. Only one-way doors earn a branch. |
| "This decision is close enough to contained." | If it touches anything on the must-stop list, variants multiply the review surface for a change that needed one considered answer. Check the list rather than a remembered summary of it: it is longer than the three categories people recall. |
| "Three options are all defensible." | Then write the sentence for each. An option whose reason you cannot state is dominated, and building it spends a leaf on a choice nobody would make. |
| "The cap is in the way, so split the decision in two." | Two forks of three options is nine leaves by another name. A cap refusal is a signal to ask, not a routing problem. |
| "Precompute the full grid so every combination exists." | Later decisions often do not arise on every path, and a grid rebuilds the shared trunk once per leaf. |
| "The leaf compiles, so the option works." | Compiling is not evidence. Without the test suite and a stated cost, the ledger cannot rank anything. |
| "The tests fail, so delete that leaf." | A failing leaf is the most useful output here: it kills an option empirically. Report it. |
| "Push the branches so CI can grade them." | CI on eight variants of one change burns runners and fills review with work that will be deleted. |
| "The rule is in CLAUDE.md, so it will be followed." | A doc is a prompt: usually respected, never guaranteed, unauditable afterwards. The must-stop paths are in `cadence.toml` and a commit hook for exactly that reason. |
| "The transport said it posted, so the author knows." | A successful post into an unwatched channel is indistinguishable from a delivered one ([`C-12`](../examples/case-studies.md)). Say it in the session and mirror it onto the issue. |
| "A leaf found another decision, so it should fork." | Only the parent session forks. A leaf that forks itself grows the tree past whatever the caps were protecting. |

## Red Flags

- A fork whose options differ only in naming, file layout, or formatting. That
  is a two-way door wearing a costume.
- A ledger with no `recommend` line: the judgment was handed back to the author.
- An option described only by what it gains, with nothing in `--lost`.
- Worktrees created for a decision that names a route, topic, table, or
  migration.
- More than one fork for what is really one decision.
- A leaf that pushed, opened a PR, or started a server.
- Fan-out used because the author was slow to answer a `must-stop` question.
  Slowness is not reclassification.
- Hand-edited `tree.json` or `LEDGER.md`. `collapse` trusts the tool's writes.
- A tree left uncollapsed after the ticket moved on. `status` with no argument
  finds them; nothing else will, and each one costs a few hundred MB.
- `--evidence "tests pass"`, or a `--switch-cost` that repeats `--lost`. Both mean
  the ledger cannot be used to choose.
- A tree built with no commit hook installed: the must-stop boundary was
  advisory for that whole run.
- A leaf subagent that opened a terminal, forked again, or ran a fourth suite
  concurrently.

## Verification

Before notifying the author, confirm:

- [ ] Every fanned decision is a one-way door whose effects stay inside the diff.
- [ ] No fanned decision appears on the `must-stop` list.
- [ ] Every option carries a reason to choose it; dominated options were dropped
      with `--drop`, not built.
- [ ] Every leaf has a `result` with real `--evidence`, a `--lost` line, and a
      `--switch-cost`; failing leaves carry `--failure`.
- [ ] The `fanout-scope` hook is installed, so it actually gated the leaves.
- [ ] Every decision has a `recommend` line with a `--wrong-if` a reader could
      actually check, and an `--if-silent`.
- [ ] Every plain-English cell is free of file names, type names and ticket ids;
      those live in the evidence line.
- [ ] `fanout.py leaves` shows no leaf reporting `no-result`.
- [ ] Nothing was pushed; no PR exists for any leaf.
- [ ] The ledger renders, and each decision and its options are mirrored to the
      issue.
- [ ] Any cap refusal was escalated as a question, and the ledger names it.
