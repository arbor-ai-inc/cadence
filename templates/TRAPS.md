# Traps — occurrence counts across retro batches

One row per trap slug. Fragments in `pending/` name one or more slugs;
`/cadence:retro-synthesis` updates the counts here.

**What each count earns is defined once, in `reference/retro-synthesis.md`
§ *Workflow* step 4.** It is deliberately not restated here. An earlier draft of
this file carried its own copy of that table and the two had already diverged —
this one had five rows, step 4 had three with the exceptions in prose, and
nothing compared them. Two normative copies of the governing rule is precisely
the drift this whole mechanism exists to catch, so the copy that was easier to
reach lost.

Counts are cumulative across batches, which is the point: a trap seen once in
batch 1 and twice in batch 2 is n=3, and no single batch could have seen that.

## Status values

- `observed` — recorded, no rule written.
- `ruled` — prose guidance exists in the named doc.
- `mechanized` — enforced by a check that fails, not by a doc a reader may skim.

`ruled ×N` means the trap was ruled on N separate occasions, in N separate
places. That is not a tidier way of writing the count — it is the mechanize
signal: one trap answered with seven prose bullets is a rule that never fired.

## Table

<!-- Start here. Delete this comment and the starter rows once you have a batch
     of your own. The four rows below are the traps that recurred most often in
     the codebase cadence came from, seeded at n=0 so they are available as
     slugs without claiming they have happened to you. If one of them never
     recurs here, delete the row: a ledger of other people's traps is not
     evidence about your system. See examples/case-studies.md for what these
     looked like when they were real. -->

| Trap | n | Status | Where ruled / mechanized | Seen in |
|---|---|---|---|---|
| `issue-premise-stale` — an issue or spec body's own counts, file lists, line numbers, names or quoted rules are wrong. Two modes: gone stale since filing, **or never true** — the latter is usually the larger half | 0 | `observed` | — | — |
| `guard-cannot-fire` — a rule, validator or test double is placed where the harness never reaches, or is permissive enough to pass anything | 0 | `observed` | — | — |
| `query-answered-partially` — a search or API call returns a subset, a stale row, or nothing at all, and the answer is read as complete | 0 | `observed` | — | — |
| `automation-silently-paused` — a reviewer or check reports a passing state because it never ran | 0 | `observed` | — | — |

## Standing findings

<!-- One numbered finding per batch that is worth carrying forward: what the
     batch measured, not what it changed. This is where you record that a rule
     was mechanized on recurrence rather than on judgment, or that a candidate
     rule was cut on review — the things a diff cannot show. -->
