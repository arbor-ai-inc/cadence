# Changelog

What changed for adopters, newest first. Every version that reaches `main` is
tagged `v<version>`.

## 0.11.0

Review and explanation lessons from the source project, rewritten in the short style.

- **explain-plain has a tutor mode.** When the reader asks to be walked through or
  taught, the skill teaches 2-4 ideas, one per turn, pausing with a check question,
  hinting rather than correcting. Written mode is still the default; the takeaway
  rule, Red Flags and Verification now say which mode they cover. A new row in the
  numbers table gives the tutor limits' basis. Regenerate your wrappers to pick up
  the new description.
- **code-review-and-quality:**
  - New § *Before You Close A Question*: searches that cannot match wrapped prose,
    descriptions taken for enforcement, deferrals to tickets that don't cover them,
    bare numbers changed without `git log -S`, dependency claims checked at the wrong
    version, and re-reviews that only re-read your own findings.
  - New § *Posting A Review*, after *Finding Format*: pin to the head (moved here
    from *Habits*), take `file:line` from the head, anchor only inside diff hunks
    (one comment outside fails the whole review with 422), `side: LEFT` for deleted
    lines, and check where each comment landed.
  - *Read across the open queue* now names three more places a change meets work
    outside its diff, how the composition check hides its own failure, and
    `gh pr list`'s 30-item default.
- **git-pr-workflow:** archive a stale PR by closing it; its ref survives.
- **Budgets raised:** `code-review-and-quality.md` 14000 → 17000 and
  `explain-plain.md` 7000 → 9500 bytes. Each addition is a rule or step the source
  project hit at least once, with at most a one-sentence example.

## 0.10.1

Fixes for projects that vendor cadence.

- **Overlays reach every workflow you follow.** A wrapper used to send the agent to
  its own overlay only, so a workflow that execute-issue merely links to (say,
  git-pr-workflow) ran without its project rules. Now, following any
  `.cadence/reference/<name>.md`, or a persona under `reference/personas/`, means
  reading `<overlays>/<name>.md` too. Regenerate your wrappers.
- **`wrappers.py --check` works in a linked git worktree.** It checks that
  worktree's own wrappers, `.cadence/` and `cadence.toml`. It used to refuse, so an
  always-on pre-commit hook was red in every worktree. The worktree needs
  `git submodule update --init` like any checkout.
- **`[[must_stop]]` keeps a leading dot.** `.github/` was stored as `github/`: it
  still caught `.github/...` paths, but also caught a `github/` directory and printed
  the wrong path.
- Text: the security-auditor persona's garbled "customer, customer or tenant data",
  and broken backticks around `[paths].principles` in the spec-pipeline skill and
  the eng-design-reviewer agent.

## 0.10.0

For projects that vendor cadence and have their own conventions. Every new setting,
unset, keeps today's behavior; the behavior changes are marked.

- **`[models.pins]`:** per-skill or per-agent models, written by `tools/wrappers.py`
  into the generated Claude wrappers. An agent's pin holds for its whole run; a skill's
  covers its first turn, so a pinned workflow in Claude Code checks the model on start
  and on every resume and stops if it differs. Cadence's published files still pin
  nothing. **Behavior change:** the spec workflows' `[models].recommended` check now
  runs in Claude Code only.
- **`[git]`:** `branch`, `commit_style` (`issue-prefix`, `conventional` or
  `imperative`) and `pr_title`, with placeholders checked at load. Unset, execute-issue
  and git-pr-workflow keep their own defaults.
- **`[paths].templates`:** use your own spec templates.
- **Circuit breakers in config:** `[review].circuit_breaker` (pre-PR code-review
  rounds) and `[review].spec_circuit_breaker` (spec rounds without fewer blockers),
  both default 3, alongside the existing post-PR `[review].max_rounds`.
- **Wait for CI:** a PR is done when every required check has run and passed on the
  head commit, whatever the reviewer. **Behavior change** for `[review].provider =
  "none"`, which used to end at a locally green PR.
- **Messages go to the issue and the ask transport, not Slack by name:** the
  circuit-breaker findings, "PR ready", and an unanswered spec question.
- **code-review:** no Codex-first default; the configured reviewer runs, at high
  effort, with an optional second opinion. **Behavior change:** the skill no longer
  falls back to `codex exec` or the subagent on its own; with `[review].provider =
  "none"` no reviewer runs, as the reference doc already said. The cross-boundary BLOCKER names the
  artifacts your rubric lists, not a fixed set.
- **Facts from the source project removed:** its ruleset settings, merge-strategy
  claims, a CI job, a lint config, a principle count and ad-domain vocabulary are now
  checks or generic wording. Garbled genericization text fixed.
- New rules: choose a spec's slug once; a reviewer's reading set bounds what it can
  find; post-merge proof is the step after the merge; issue comments follow
  explain-plain; model escalation rules; a project lesson about a cadence workflow can
  go in an overlay.
- `fanout.py` no longer tells you to ask when only one option survives — unless it
  touches the must-stop boundary, which is now checked for a single option too.

## 0.9.0

- **Design-only specs.** A change nothing a customer could see, be billed for, or
  complain about may skip `product.md`; the design carries the Rn and why, and Gate 2
  grades that claim (a user-visible goal is a BLOCKER). `draft-plan` refuses one that
  is user-visible.
- **Split designs.** A large design is an HLD plus `design/` sub-designs; `spec_hash.py
  design` hashes them together.
- `check_vocab.py` also scans files not yet added, and its own docstring no longer
  names the source project's files.
- **Testing plans and `test-authoring`.** New workflow and `_testing_plan_template.md`
  for tests above unit level. `testing-plan.md` sits outside the design hash; rows are
  never deleted after the gate.
- **Cross-artifact pass.** Before the design PR, each artifact pair is checked and the
  result committed in `review/cross-check.md`.
## 0.8.1

- **Scrubbed the source project's names** from the docs, case studies and tests: spec
  names, PR numbers, branch names, file and table names. Wording changed; no rule did.
- **`tests/check_vocab.py`:** fails if a name from a private repo appears in cadence.
  The list is derived at run time from the repos you point it at and never stored.
- **`check_no_leaks.py`** stores private names as digests (`--hash NAME` adds one), and
  matches issue ids in any case.
- `code-review` and `spec-pipeline` name cadence's `tools/ask.py`, not a source-project
  script.

## 0.8.0

- **Fan-out is now opt-in: `[fanout].enabled`, default `false`.** With it off, a
  one-way decision inside the diff is asked with a decision brief, and `fanout.py`
  refuses `init` and `fork` (exit 3, naming the switch). **Behavior change:** a project
  that relied on fan-out sets `enabled = true` under `[fanout]` to keep it.
  `check-scope` is unaffected.

## 0.7.0

New rules from the source project's recent retros, in the short style, within budget.

- **code-review:** a docs-only diff is all claims; a quoted spec sentence is a premise;
  sweep the dimension, not only the phrase; stop means stop after round 3, and a commit
  after the last review is named in the PR.
- **automated-review:** check all three parts of the terminal condition every round;
  one push per fix round, never during a running review; refills are per developer.
- **git-pr-workflow:** re-run the suites with `main` merged in before merging.
- **code-review-and-quality:** read across the open queue (merged-tree test for
  migrations, `__init__` and registries); quiet test doubles; remerge-diff.
- **test-driven-development:** anti-vacuity stated over the property; benchmarks need a
  correctness assertion; cached runs; tests that read docs; a local suite runner.
- **using-agent-skills:** route the model by phase; delegated skill runs pass the model.
- **retro-synthesis:** check the ledger against raw fragment text.
- **execute-issue:** quoted premises; "what calls this" is a reachability question.
- **New skill: `explain-plain`.**

## 0.6.0

Leaner docs: an issue run now loads roughly half what it did. No rule was removed.

- **Review-bot material moved to `reference/automated-review.md`**, loaded only when
  `[review].provider` is a PR bot. **Stacked, parallel and out-of-date branches moved to
  `reference/branch-updates.md`**, loaded only in those situations. `git-pr-workflow`
  drops from 54 KB to 18 KB.
- **Case write-ups moved to `examples/case-studies.md`** from `code-review`,
  `code-review-and-quality`, `test-driven-development` and `execute-issue`. Each rule
  keeps one sentence of why and its case id. Those four docs are 35% smaller.
- **Every reference doc has a byte budget** (`tests/doc_budget.json`, checked by
  `tests/check_doc_budget.py` in CI and pre-commit). A new rule makes room or raises the
  budget visibly.
- `code-review` Loop step 1 no longer carries a command from the source project.

## 0.5.0

Additive. Nothing changes for an existing plugin install.

- **Vendor cadence as a git submodule at `.cadence/`, with no plugin.** The
  dispatcher now ships at the repo root as `cadence`, so `./.cadence/cadence`
  resolves the copy it sits in. See `docs/setup.md`.
- **`tools/wrappers.py`** generates unprefixed wrappers from the vendored copy:
  `.claude/skills/`, `.codex/skills/` and `.claude/agents/`. `--check` fails on a
  stale, orphaned or hand-edited wrapper. It never overwrites a file it did not
  generate.
- **`[paths].overlays`**: per-workflow project addenda that generated wrappers
  tell the agent to read after the canonical doc. Unset by default.
- **Fan-out leaves get the vendored copy.** When a project vendors cadence at
  `.cadence/`, `fanout.py fork` populates it in each new leaf from the local
  checkout, offline, or warns if it cannot. No other submodule is touched.
- **Release tags.** A workflow tags each new version `v<version>` on `main`.
