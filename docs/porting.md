# Porting cadence to your stack

Cadence assumes git and a pull-request model. Everything else is configuration or
a provider. This is what to do when your stack differs.

## What is genuinely assumed

| Assumed | Negotiable? |
|---|---|
| git, with branches and a squash-or-merge PR flow | No. The workflows are built around it. |
| the `gh` CLI for PR operations | Partly — see below |
| Python 3.11+ for the tools | No, but only the tools; the workflows are prose |
| an issue tracker | Yes: `[tracker].provider = "none"` passes the issue body inline |
| a chat transport for blocking questions | Yes: `harness` asks in-session |
| an automated PR reviewer | Yes: `[review].provider = "none"` skips the loop |

## GitHub

`tools/review_state.py` and the PR steps in `git-pr-workflow` speak `gh`. On
GitLab or elsewhere:

- **The reasoning ports; the commands do not.** The four ways a check row lies
  about a review that never ran are not GitHub-specific, but the API calls that
  detect them are.
- Write a sibling reader with the same output contract — the verdict line, and
  `--json` with `review_landed_at_head`. Every workflow reads only those.
- Set `[review].provider = "none"` until you have one, and accept that the
  post-PR watch loop is skipped rather than pretending it ran.

## A different issue tracker

`[tracker].provider` covers Linear and GitHub Issues. For anything else, the
integration surface is small and stated in
[`reference/execute-issue.md`](../reference/execute-issue.md) § *Procedure* steps
1, 2 and 9: fetch an issue, move it to a state, comment on it.

`provider = "none"` works today and loses only the state transitions.

## A different automated reviewer

Add `reference/providers/<name>.md` following
[`coderabbit.md`](../reference/providers/coderabbit.md) as the model: a **command
map** translating the roles the neutral docs use into your reviewer's actual
commands, then whatever API-level detail is needed to read its state honestly.

The neutral docs name commands by role precisely so this is additive. Do not edit
them to name your reviewer.

## Not Python

The tools are Python; the workflows are Markdown. You can adopt every workflow
with none of the tools, and lose:

- `fanout.py` — decision fan-out entirely. There is no prose substitute; the
  exit codes are the protocol.
- `spec_hash.py` — the frozen-artifact gate. Without it, an edit after a gate
  closes goes undetected.
- `review_state.py` — honest review state. Without it you are reading the check
  row, which is the thing the whole section warns about.
- `ask.py` — the ask transport. `[ask].provider = "harness"` needs no tool.

Reimplementing `spec_hash.py` is a morning's work; its normalization rules are
stated in the module docstring and pinned by `--selftest`. Reimplementing
`fanout.py` is not.

## Adopting only part of it

The workflows form three clusters that are cleanly separable:

- **The retro loop** — `retro`, `retro-synthesis`. Zero dependencies on the
  others. Start here.
- **The implementation loop** — `execute-issue` → `decision-fanout` →
  `code-review` → `git-pr-workflow`. Needs `[[must_stop]]` and the scope hook to
  be safe.
- **The spec pipeline** — `spec-pipeline`, `review-spec`, `draft-plan`. Needs a
  rubric at `[paths].principles`.

`human-brief` is cross-cutting: sixteen other docs cite it, and it is the one to
read first regardless of which cluster you adopt.

## Do not edit the vendored reference docs

A local edit to `reference/` is silently reverted by the next plugin update. A
lesson about **your** project belongs in your own repo — see
[`retro-synthesis`](../reference/retro-synthesis.md) § *Workflow* step 6 for the
destination table. A lesson about a cadence workflow is an upstream issue.
