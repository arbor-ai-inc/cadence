# Provider notes: CodeRabbit

Applies when `[review].provider = "coderabbit"`. The neutral rules are in
[`../code-review-and-quality.md`](../code-review-and-quality.md) § *Working With
Automated Reviewers* and are not repeated here; this is only what is specific to
this reviewer.

Every command below was measured against real pull requests. Where a number
appears, it was counted.

## Command map

`git-pr-workflow.md` and `code-review-and-quality.md` name these by role, because
the reasoning around them is not specific to this reviewer. Here is what each one
actually is.

| Role in the neutral docs | CodeRabbit command or setting |
|---|---|
| the **full re-review** command | `@coderabbitai full review` — as a **top-level PR comment** |
| the **incremental** review command | `@coderabbitai review` — a no-op past an auto-pause, and it still spends an attempt |
| the **approve** command | `@coderabbitai approve` — top-level only; refused as a review-thread reply |
| the **resolve** command | `@coderabbitai resolve` — top-level only; records answers, schedules nothing |
| the reviewer's **config** | `.coderabbit.yaml` |
| the **blocking-review** setting | `request_changes_workflow: true` |
| the **auto-pause** setting | `auto_pause_after_reviewed_commits` |
| a **path-filter exclusion** | `reviews.path_filters` |
| a **title-keyword exclusion** | `ignore_title_keywords` |
| the reviewer's login | `coderabbitai[bot]` in REST, **`coderabbitai` in GraphQL** |

**Ask for `resolve`, not `approve`.** Resolving records that every finding has an
answer, which is a true statement you can defend. Approving asks the reviewer to
bless a diff whose findings you partly declined — a green check you did not earn,
and the human reviewer is the real gate either way. The reviewer's own approval is
weak evidence regardless: one measured `APPROVED` review carried, in the same
comment, *"This does not approve the PR."*

**A round that ends at `resolve` ends with nothing scheduled.** `resolve` records
answers and closes threads; it does not ask for a look, and neither does a reply
or a push once the auto-pause has fired. The working shape is: **a per-thread
reply carrying that finding's reasoning, then one top-level resolve with the
dispositions summarised, then a separate full re-review.**

**Keep title-keyword exclusions free of domain vocabulary.** One keyword —
`draft` — was also a legitimate status value in the product, so a PR whose title
ended `… → draft` was skipped outright, and the check row rendered that as
**passing**. Grep a candidate against status values, type names and column names
before adding it.

CodeRabbit is configured as a blocking review (`.coderabbit.yaml`). It has found real
defects that several human-style review rounds missed — a hung fetch that left a promise
unsettled, a prototype-pollution hazard, a test that could not fail — and it has also
been confidently wrong.

- **Take the concern, not necessarily the patch.** Verify every finding against the code
  before applying it. One review asked to narrow a "nothing renders yet" statement in a
  way that would have made it *false*; the real defect was a different line implying a
  component was live. Accepting a wrong edit to close a comment makes the tree worse.
- **Verify a CI claim before acting on it.** A reviewer asserted two lint findings "will
  fail the hygiene job" when the repo selects neither rule. Check with
  `pre-commit run <hook> --files …`. Accepting such a claim quietly becomes an argument
  for widening the lint config later.
- **State the disagreement in the reply.** When declining a patch, say which decision it
  would reverse and why the concern is still addressed — a reviewer that runs its own
  verification will often confirm and withdraw the finding.
- **Reply where the bot is listening, or the disagreement is not stated at all.** A
  standalone top-level comment is not a reply. On T-17 (#618) four declines posted that
  way sat unprocessed while the review stayed `CHANGES_REQUESTED` — and were reported to
  the author as "answered", which was wrong. Reply **inside the review thread** and
  `@`-mention the bot. Thread replies cannot clear the review, though: CodeRabbit answered
  all four with the same line — *"Post `@coderabbitai resolve` or `@coderabbitai approve`
  as a new top-level PR comment. Approve commands are disabled for review-thread replies."*
  So the working shape is **per-thread reply carrying that finding's reasoning, then one
  top-level `@coderabbitai resolve`** with the dispositions summarised — **and then a
  separate `@coderabbitai full review`** (the plain `review` is a no-op once the bot has
  paused itself, and still spends an attempt). `resolve` records answers and closes threads; it
  does not ask for a look, and neither does a reply or a push once
  `auto_pause_after_reviewed_commits` has fired. A round that ends at `resolve` ends with
  nothing scheduled (`git-pr-workflow` § *Requesting the re-review*).
- **Ask for `resolve`, not `approve`.** Resolving records that every finding has an
  answer, which is a true statement you can defend. Approving asks the bot to bless a diff
  whose findings you partly declined — a green check you did not earn, and the human
  reviewer is the real gate either way. Note the bot's own approval is weak evidence: on
  #618 it filed an `APPROVED` review in the same comment that said *"This does not approve
  the PR."*
- **A passing status does not mean it said nothing.** Read the inline comments even on an
  approving review.
- **A passing status can also mean it never looked.** `.coderabbit.yaml` carries
  `ignore_title_keywords`, and on T-23 one of them — `draft` — was also a
  `format_templates.status` value, so a PR titled `… deprecated → draft` was skipped
  outright. `gh pr checks` rendered that as a **passing** `CodeRabbit` row,
  indistinguishable from a clean review; only the row's description said *"Review
  skipped: ignored keyword in the PR title"*. Retitling and commenting
  `@coderabbitai review` recovered it, and the review then returned four findings, two
  of them real.

  **That keyword is gone** — `drafts: false` already skips real draft PRs by their
  GitHub state — but both halves of the lesson outlive it. **Read the description, not
  the bucket**: that row is synthesized from review state and reports skipped,
  rate-limited, paused and happy identically, and a stale `CHANGES_REQUESTED` on an
  older commit reads as `pass` too.

  **Do not hand-roll the verdict query.** It was wrong three times before it was right,
  and reading it wrong is `automation-silently-paused`, n=9 in one batch. It is now:

  ```bash
  python3 .github/scripts/pr_review_state.py --pr "${PR:?}"
  ```

  Every detail that made the old pipeline load-bearing — selecting on `state` rather
  than recency so a reply-borne `COMMENTED` cannot displace the verdict, filtering to
  the bot so a human approval at head does not read as "head was reviewed", treating
  `no verdict yet` as a real state rather than `null null`, paginating, and aggregating
  pages *before* selecting because `gh --jq` evaluates per page — is implemented and
  self-tested there, with the PR each was measured on. Read the script, not a second
  copy of its reasoning.

  Add `ignore_title_keywords` care to that: keep it free of domain vocabulary — grep a
  candidate against status values, format names, event types and column names before
  adding it.

  **`auto_pause_after_reviewed_commits` is the cause to expect on a branch under active
  development.** After several commits CodeRabbit pauses itself and says so only in a
  comment; the row still reads `pass · "Review completed"`. It fired three times on
  #604, once leaving the *forward-merge commit* — the largest change on the branch —
  unreviewed while the dashboard was fully green. **`@coderabbitai full review` resumes it** —
  the plain `review` is a no-op past the pause and still spends an attempt; see
  [`../code-review.md`](../code-review.md#automated-ai-review-coderabbit).

- **Unresolved-thread count is not finding count.** A finding whose line falls outside
  the diff cannot be posted inline, so it arrives in the **review body** instead. #604's
  merge commit reported `unresolved threads: 0` with a Major finding open — a real defect
  in the test harness, described in prose nothing counted. Read the review body even when
  the thread count is zero.

- **Findings live on three surfaces, and the review state shows none of them.** The
  verdict command above returns `state` and `commit_id`; neither says what was found. To
  clear the terminal condition you have to enumerate all three, because no one of them
  counts the others.

  **Review bodies — every bot review at head with a body, not just the newest:**

  ```bash
  head=$(gh pr view "${PR:?}" --json headRefOid --jq .headRefOid)
  gh api --paginate --slurp "repos/:owner/:repo/pulls/${PR:?}/reviews" \
    | jq -r --arg head "$head" \
        'add | map(select(.user.login=="coderabbitai[bot]"
                   and .commit_id==$head and (.body|length)>0))
         | .[] | "--- \(.state) \(.submitted_at)\n\(.body)"'
  ```

  On #618 that returns the `CHANGES_REQUESTED` body the newest-review check misses
  entirely. Filtering to the newest review here is the same mistake in a second place.

  **`(.body|length)>0` belongs here and nowhere near a stop condition.** Enumerating
  findings is exactly what it is for. But an `APPROVED` review has no body — 11 of 11
  approvals across eight PRs in this repo measured zero-length, against 2,000–7,000
  characters for every `CHANGES_REQUESTED` — so a loop that waits for "the newest review
  with a body at head" is waiting for something a clean PR never produces. #633 approved
  at head and was asked six more times on that predicate. Terminal conditions select on
  `state`.

  **Inline findings — thread openers only:**

  ```bash
  gh api --paginate --slurp "repos/:owner/:repo/pulls/${PR:?}/comments" \
    | jq -r 'add | map(select(.user.login=="coderabbitai[bot]" and .in_reply_to_id==null))
             | .[] | "\(.path):\(.line // .original_line)\n\(.body)"'
  ```

  **`in_reply_to_id==null` is what makes this a finding count.** The bot replies to its
  own threads, and those replies are inline comments too: #618 has 8 bot comments and 4
  findings, the other 4 being *"Post `@coderabbitai resolve` …"*. Note this is a
  different endpoint from `/reviews` — a review body and an inline comment never appear
  in each other's response.

  **Resolution state — GraphQL only:**

  ```bash
  gh api graphql -F owner="${OWNER:?}" -F name="${REPO:?}" -F n="${PR:?}" -f query='
    query($owner:String!,$name:String!,$n:Int!){repository(owner:$owner,name:$name){
      pullRequest(number:$n){reviewThreads(first:100){totalCount nodes{
        isResolved isOutdated path comments(first:1){nodes{author{login}}}}}}}}' \
    --jq '.data.repository.pullRequest.reviewThreads
          | "fetched \(.nodes|length) of \(.totalCount) threads",
            (.nodes | map(select(.comments.nodes[0].author.login=="coderabbitai"))
             | "bot threads: \(length)  unresolved: \(map(select(.isResolved|not))|length)")'
  ```

  **`totalCount` is there so the cap fails loudly.** `first:100` is not pagination —
  GraphQL paging needs `pageInfo`/`endCursor`, which `gh --paginate` cannot drive from a
  bare query — so a PR with more than 100 threads silently reports the unresolved count
  of the first page. That reads as a cleared gate while later threads still block merge.
  If the two numbers differ, page it or narrow the query; do not use the count.

  REST exposes no resolution state at all, and `required_review_thread_resolution` means
  an unresolved thread blocks merge — so this is the only way to see the gate you are
  trying to clear.

  **The login is spelled differently in the two APIs**, and getting it wrong fails
  silently. GraphQL reports `coderabbitai`; REST reports `coderabbitai[bot]`. Filtering
  the GraphQL query on the REST spelling returns **0 threads** on a PR that has 4 — an
  empty result that reads as "no findings" rather than as a bad filter. Verified on #618
  both ways.

