# human-brief

The layer a human reads at a stop point. Every other artifact cadence produces
at a stop point — round files, reviewer findings, verdict first lines — is written
for an agent. This one is written for the person who has to decide.

## Overview

Two shapes. **Shape A** when the agent stops for a choice; **Shape B** when it
hands back work it has already done. Both are bounded, both are tabular, and both
carry, per row, the one thing a human could look at to check the claim.

The brief never replaces the detailed artifact. Round files, `LGTM`/`FINDINGS`
output, and `PRODUCT_READY` verdicts are machine-parsed contracts and stay exactly
as they are. The brief sits on top of them and may only compress what they already
support.

## When To Use

Emit a brief at every point where the workflow stops and waits for a human:

| Stop point | Shape |
|---|---|
| `code-review` reaching LGTM, findings handed back, or the 3-round circuit breaker firing | B |
| `code-review` finding that needs a product decision | A |
| `spec-pipeline` `decision: author` batch | A |
| `spec-pipeline` DESIGN_READY changelog + decomposition | B |
| `execute-issue` ambiguity question (Slack, or the in-session fallback) | A |
| `retro` PR body — each proposed lesson | B |
| Any PR body written under `git-pr-workflow` | B |

Do not emit one for progress narration, for a step that did what was asked with
no choices along the way, or for a question with a single defensible answer —
that last one is `decision: mechanical`, and the fix is to resolve it, not to ask.

## Shape A — the decision brief

```text
DECISION: <one sentence — what is being chosen>
WHY YOU:  <one sentence — why the agent cannot settle it>

| Option | In plain English | What users/operators notice | Cost & risk | Reversible? |
|---|---|---|---|---|
| A | … | … | … | yes / one-way |
| B | … | … | … | … |

RECOMMEND: <option> — <one sentence>.
WRONG IF:  <the specific fact that would flip this>.
IF SILENT: <what happens with no answer>.
```

At most 4 options, at most ~20 words per cell, the whole brief on one screen.

**`WRONG IF` is the load-bearing line.** A recommendation with no stated falsifier
is the thing that gets rubber-stamped; a recommendation that names the fact which
would flip it can be checked in seconds. A brief without one is incomplete.

**Transport — the table is the contract; the picker is an optimization.** Where the
harness offers a structured picker, use it: in Claude Code that is `AskUserQuestion`,
one option per row, `label` the option, recommended first. It mechanically forces
options to be short and mutually exclusive where prose does not.

**Print the table, then offer the picker.** Do not try to fit the brief inside the
widget: four options at four columns each is far more text than an option
`description` renders legibly, and a picker that has to be squinted at is a worse
brief than the plain table. So emit the full Shape A brief — table, `RECOMMEND`,
`WRONG IF`, `IF SILENT` — as text first, and then raise the picker over it with a
short `description` per option: the plain-English reading plus the single fact that
most distinguishes it, around fifteen words.

That keeps both properties. Nothing is dropped, because the full table is on screen
directly above; and the picker stays a one-keystroke answer rather than a second wall
of text. **The picker is how the answer is given, not where the reasoning lives.** If
you ever find yourself trimming a column to make the widget fit, you have inverted
this rule.

Where no picker exists — Codex, headless and cron runs, and any chat-only path — print
or send the identical table as text. **This is a fallback, not a downgrade**, and no stop
point may block on a picker being available: the required content is the same either way,
and only the rendering changes. Which transport carries the question is
`[ask].provider` in `cadence.toml`, never a choice made here; `tools/ask.py` is
the one caller. When the transport is a chat channel rather than a session,
number the options so a one-token reply is unambiguous. The channel stays
transport, not record: the answer is still recorded where the calling workflow
says it is recorded.

**A posted question is not a delivered one, and the difference is invisible from
here.** `tools/ask.py` exits 0 on a reply and 2 on timeout; both are honest, and
neither can tell you the channel is empty and nobody is reading. So treat exit 2
as *unanswered* rather than as an answer, never self-answer either way, and do
every part of the task that does not depend on the answer while the ask is out.
A question that expired unrecorded is indistinguishable from one never asked.

## Shape B — the change brief

1. **In one paragraph** — what changed and why, readable by someone who has not
   seen the diff.
2. **Architecture delta** — `| Component | Before | After | Who notices |`. Only
   rows that actually changed.
3. **Use-case impact** — `| Scenario | Before | After |`. When nothing user-facing
   moved, say *"no user-visible change"* in the table. Dropping the section reads
   as coverage.
4. **Findings and fixes** — `| # | Sev | Problem in plain English | What changed | Evidence |`.
5. **Not fixed, and why** — deferred findings, declined NITs, follow-ups filed.
6. **Where the reviewer and I disagreed** — what was contested and how it settled.
   Required whenever a review ran, and *"every finding was accepted as written"* is a
   complete, honest answer: a review can be fully adversarial and produce no
   disagreement at all, because the findings were simply right. What this section
   exists to prevent is **silent** acceptance, not agreement. Never manufacture a
   dispute to fill it — that would violate the no-new-claims rule two lines below.
7. **What to check yourself** — one to three concrete things: a command, a file, a
   screen.

Two screens, maximum.

**Scale the brief to the change.** The seven sections are the shape of a brief for a
change that has architecture and user-facing surface, not a floor every change must
clear. Omit any section the change *cannot* have — a typo fix has no architecture
delta and no findings table, and inventing empty ones to satisfy the shape is the
wall-of-text failure this doc exists to prevent, re-created by its own template. A
change with no architectural surface and no user-visible effect gets one paragraph,
*what to check yourself*, and whatever the workflow independently requires — nothing
more.

**Proportionality never overrides another rule.** It drops sections the change cannot
have; it does not drop sections something else requires. Concretely: a one-line fix
that still went through review carries *where the reviewer and I disagreed*, because
that section is keyed to whether a review ran, not to how large the change was. A
trivial change can be reviewed, and if it was, the acceptance still has to be visible.

The distinction that matters: **omit a section that cannot apply; state a section that
applies and is empty.** A refactor that genuinely touches user-facing behaviour and
changes none of it must say "no user-visible change", because there silence is
ambiguous. A typo fix need not, because there is nothing for the reader to wonder
about.

## Plain-English rules

- **Consequence test.** A line that names a symbol, a file, or a severity tag and
  no consequence is not a finding — restate it with who is affected and how. "Nil
  `Metrics` in the handler" fails; "the counter reads zero in dev, so the dashboard
  will look healthy while nothing is being recorded" passes.
- **Jargon budget.** `file:line`, type names, principle numbers, and ticket ids
  live in the evidence column. They never appear in the plain-English column.
- **Every row is falsifiable.** Each carries the one thing a human could look at to
  check it. A row with nothing to point at is labelled `UNVERIFIED`, the same
  convention the reviewer already uses.
- **Translate, do not invent.** Cadence runs two severity vocabularies that do
  not reconcile — BLOCKER/SHOULD/NIT in code review, BLOCKER/MAJOR/MINOR in the
  spec pipeline. Render both as consequences. Do not introduce a third.
- **No new claims.** If the brief needs something the detail layer does not
  support, the detail layer is what is wrong. Fix that instead of asserting it here.
- **Phone test.** A brief should be readable on a phone in under two minutes. If it
  is not, it is not a brief. (The same standard is applied to retro PRs, though this
  rule stands on its own and does not depend on that one.)

## Common Rationalizations

| Rationalization | Reality |
|---|---|
| "The findings list is already structured, so it is already readable." | Structure for a parser is not structure for a person. `BLOCKER … file.go:214` says something is wrong, not what it costs or who feels it. |
| "The human can read the round file if they want the detail." | A 270-line round file at ~17 lines per finding is what the brief exists to make decidable. Pointing at it is not answering. |
| "Recommending an option is leading the witness." | Withholding a recommendation does not prevent rubber-stamping; it just removes the reasoning that could be challenged. `WRONG IF` is the safeguard. |
| "There was no real disagreement this round." | Then write that. An empty section stated is evidence; an absent section is indistinguishable from one that was skipped. |
| "This change has no user impact, so the impact table is noise." | "No user-visible change" is a claim a human can challenge. Silence is not. |

## Red Flags

- A brief longer than the artifact it summarizes.
- A plain-English column containing a file path, a type name, or a severity tag.
- A recommendation with no `WRONG IF`.
- Options that are not mutually exclusive, or that restate each other with
  different emphasis.
- A change brief with no "what to check yourself" — the human has been told, not
  equipped.
- A decision sent as printed prose when the harness had a picker available.
- A stop point that stalls or degrades its content because no picker was available.
- A section that *applies* dropped because it was empty — as opposed to one correctly
  omitted because the change cannot have it.
- A one-line change wearing all seven sections.

## Verification

Before handing a brief to a human, confirm:

- [ ] Every row's plain-English cell names a consequence, not just a symbol.
- [ ] Every row carries something checkable, or is marked `UNVERIFIED`.
- [ ] Shape A has a `WRONG IF` and an `IF SILENT`.
- [ ] Shape B states use-case impact explicitly, including "no user-visible change".
- [ ] Shape B has the disagreement section whenever a review ran at all — including a
      single round, where "every finding was accepted as written" is the expected answer.
- [ ] Decision brief fits one screen; change brief fits two.
- [ ] Nothing in the brief is unsupported by the detail artifact behind it.
