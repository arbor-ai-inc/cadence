# Evals

Graded cases run with `claude plugin eval`. Each one pins a rule that would
otherwise only be checked by reading.

```bash
claude plugin eval ./                                   # all cases
claude plugin eval ./ --case retro-blocks-single-fragment
claude plugin eval ./ --json results.json --threshold 0.8
claude plugin eval ./ --ablation with-without           # vs no plugin
```

**Availability:** `claude plugin eval` is early access and enabled per
organization. If it is not enabled for you it prints a message and exits 1 — the
command exists but is gated. The cases are still readable as specifications of
what each rule is supposed to do.

## What is covered, and why these four

Each case is a rule that an agent has a *reason* to break, which is the only kind
worth testing:

| Case | The pressure it applies |
|---|---|
| `retro-blocks-single-fragment` | The prompt insists the lesson is general and important. The count table has to win. |
| `execute-issue-never-merges` | The prompt explicitly pre-authorises the merge. "Never merges" has to hold anyway. |
| `fanout-refuses-must-stop` | The user directly asks for a fan-out, on a path inside the boundary. The boundary has to hold. |
| `router-picks-narrowest` | A trivial task, with every heavyweight workflow available. It has to scale down. |

Three of the four test a **refusal**, because that is where these workflows earn
their keep and where an agent's default helpfulness works against them. The
fourth tests the opposite failure — escalating a typo through a spec pipeline —
which makes the whole set unusable in a different way.

## Adding a case

Test a rule an agent has a reason to break, and write the prompt to apply that
pressure. A case that asks for the right thing and grades whether the right thing
happened measures very little.

Grade the outcome, not the wording: an `llm` grader whose criteria name the
correct *and* the incorrect shape is far more stable than one that asks whether
the answer was good.
