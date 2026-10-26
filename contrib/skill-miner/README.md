# skill-miner

Find reusable-skill candidates in the session logs your coding agents already keep on
your machine. Local-only, deterministic, standard-library Python.

It reads your [Claude Code](https://docs.claude.com/en/docs/claude-code) and
[Codex](https://github.com/openai/codex) history for one git repository and looks for:

| Kind | What it means | Suggested as |
|---|---|---|
| `request` | You asked for roughly the same thing in several sessions | a skill |
| `correction` | You corrected the agent the same way several times | a rule |
| `workflow` | You keep invoking a slash command / skill the repo has no skill for | a skill |
| `handoff-rule` | A similar rule or trap is written down in two or more handoffs | a rule |
| `handoff-decision` | A similar decision or rejection recurs across handoffs | a decision-log entry |
| `pending-promotion` | A handoff's `→ to promote:` line has sat there too long | as written |

Each finding becomes an **inactive** Markdown file for you to review. Nothing is
installed, activated, uploaded or shared. Whether a candidate becomes a real skill is
your decision, made in your normal review process.

## Quick start

```bash
# from anywhere inside the repository you want to mine
echo ".skill-candidates/" >> .gitignore        # first: candidates quote your own prompts
python3 /path/to/skill_miner.py --dry-run      # summary only, writes nothing
python3 /path/to/skill_miner.py                # writes candidates to .skill-candidates/
```

Try it on invented data first, without touching your real sessions:

```bash
python3 contrib/skill-miner/examples/demo.py
```

Requirements: Python 3.11+ and `git`. No packages to install.

## How much history there is to mine

The tool can only mine logs that are still on disk, and patterns only show up once
there are enough sessions.

- **Claude Code deletes local session logs after 30 days by default.** Its
  `cleanupPeriodDays` setting controls this. To keep more, raise it in
  `~/.claude/settings.json`, for example `"cleanupPeriodDays": 90`. Logs that are
  already deleted can't be recovered this way, and a longer window means full
  transcripts, including tool output, stay on disk longer. Pick a value you're
  comfortable with.
- **Codex** kept its session logs under `~/.codex/sessions` with no automatic expiry
  when this was written. Check your version's documentation.
- **Run it on a schedule you'll remember**, such as monthly, and at least once per
  retention window. Otherwise sessions expire before they are mined. Use `--since` to
  match the window, for example `--since 90d`.

## Privacy and security guarantees

- **No network.** The tool makes no network calls. The only subprocess it starts is
  `git` (`rev-parse`, `worktree list`, `check-ignore`, `config --get remote.origin.url`).
- **No model.** Detection is plain text matching and set similarity. No LLM is
  called, so no transcript leaves your machine.
- **Human prompts only.** It extracts only what you typed. It skips assistant text,
  tool calls, tool output, thinking, subagent turns, system-injected messages and
  pasted blocks.
- **Scoped reads.** It reads only session files whose recorded working directory is
  inside the repository or one of its git worktrees, plus, with `--same-remote`, other
  checkouts of the same repository. It also reads the repository's skill directories,
  for dedupe. To decide whether another Claude Code project folder belongs to the same
  repository, `--same-remote` reads only that folder's recorded working directory,
  never its prompts.
- **Inactive output.** Candidates are written only under `--out`, as `<kind>-<name>.md`,
  never as `SKILL.md`. The tool refuses an output directory inside any skill
  directory. Files are mode `0600` and directories `0700`. It warns if the output
  directory is inside the repository but not gitignored.
- **Redacted evidence.** Quotes are truncated to 160 characters, and common secret
  shapes are masked: API keys, tokens, JWTs, private keys, emails, URL query strings,
  long hex/base64 strings, and home-directory usernames. You can add your own
  patterns.

Each guarantee is exercised by `tests/test_skill_miner.py`. Redaction is best-effort
pattern matching, so read the evidence before you paste a candidate anywhere.

**What it cannot protect against:** the candidate files contain short excerpts of your
own prompts. Anyone who can read your home directory can read them, just as they can
read the agents' own logs.

## Usage

```
python3 skill_miner.py [--repo PATH] [--config FILE] [--out DIR] [--since 30d]
                       [--min-count 3] [--min-sessions 2] [--similarity 0.5]
                       [--skills-dir DIR]... [--same-remote] [--claude-home DIR] [--codex-home DIR]
                       [--dry-run] [--json]
```

| Option | Default | Meaning |
|---|---|---|
| `--repo` | cwd | Any path inside the repository to scope to |
| `--config` | none | TOML file, see [`examples/skill-miner.example.toml`](examples/skill-miner.example.toml) |
| `--out` | `<repo>/.skill-candidates` | Where candidates are written |
| `--since` | `30d` | Only sessions newer than `Nd` / `Nh` / `Nw`, or `all` |
| `--min-count` | `3` | Minimum occurrences for a candidate |
| `--min-sessions` | `2` | Minimum distinct sessions for a candidate |
| `--similarity` | `0.5` | Jaccard threshold for grouping prompts and handoff items; lower finds more, with more noise |
| `--handoffs` / `--no-handoffs` | on | Also mine handoff files (see below) |
| `--min-handoffs` | `2` | Minimum distinct handoff tracks for a handoff pattern |
| `--skills-dir` | see below | Extra skill directory to dedupe against (repeatable) |
| `--same-remote` / `--no-same-remote` | off | Also mine other checkouts whose `origin` has the same owner/name, such as a second clone. See below |
| `--claude-home` / `--codex-home` | `~/.claude` / `~/.codex` | Agent data directories |
| `--dry-run` | off | Print the summary and write nothing |
| `--json` | off | Machine-readable summary on stdout |

Command-line flags override the config file. List-valued config keys add to the
built-in defaults: `skills_dirs`, `correction_markers`, `ignore_commands`,
`extra_redact_patterns` and the three `handoff_*_headings`. They don't replace them.
`handoff_globs` replaces its default.

Exit status: `0` on success, including when nothing is found, and `2` on a usage or
config error.

### Other checkouts of the same repository

Session logs are keyed by directory, so a second or third clone of the same repository
(`~/src/widget`, `~/src/widget2`) is a different project to the agents. Worktrees are
always included. Separate clones are included only with `--same-remote`, or
`same_remote = true` in the config.

A checkout matches when its `origin` remote has the same owner/name as this
repository's. Scheme, user and host are ignored, so an SSH host alias such as
`git@github.com-work:acme/widget.git` matches `https://github.com/acme/widget`. The
cost is that two different hosts serving the same owner/name count as one repository.

For Codex, the remote recorded in the session is also accepted, so a deleted clone's
sessions still count. The checkouts that were included are listed in `--json` output
under `checkouts`.

### Handoffs

It also reads **handoff files**: the notes an agent leaves so a later session can pick
up a track, in the format of cadence's [`handoff`](../../reference/handoff.md) workflow. By
default these are `.local/HANDOFF-*.md`, set with `handoff_globs`, in every checkout in
scope.

- **What is read:** bullets under rule-like headings ("Rules", "Gotchas", "Do not",
  "How to work") and decision-like ones ("Decided", "Rejected", "Don't re-open"), plus
  any `→ to promote:` line.
  - Legacy handoffs that predate the format still work, because the heading keywords
    decide what's read. You can extend the lists with the `handoff_*_headings` keys.
- **What is skipped:** plain facts, including sections like "Facts" and "Do not
  re-derive". A recurring fact belongs in the doc that owns it, not in a skill or a
  rule.
- **Tracks, not files:** a pattern needs at least `min_handoffs` (default 2) different
  tracks. A handoff and its archive (`.archive.md`, or a legacy `-ARCHIVE.md`) count as
  one track.
- **Session matches rank first:** a handoff rule that matches a correction you keep
  giving in sessions is marked `also:` and listed first, since the two sources agree.
- **Scope:**
  - `--since` doesn't apply to handoffs, because a rule written a month ago is still a
    rule.
  - Under `--same-remote`, other clones are found through their session logs. A clone
    you have never run an agent in is not seen.
- **Read-only:** the tool never edits a handoff. Turning a candidate into a real rule
  or doc is the job of the handoff skill's `learn from` step, with your confirmation.
- **Turning it off:** `--no-handoffs`.

### Dedupe against existing skills

A pattern your repository already has a skill for is counted but not written. By
default the tool looks in `.claude/skills`, `.codex/skills` and `.agents/skills`. Add
your own directories of workflow docs with `--skills-dir` or `skills_dirs`. Each entry
may be a `<name>/SKILL.md` folder or a flat `*.md` file. `name:` and `description:`
frontmatter is used when present.

### Output

```
.skill-candidates/
  2026-01-31/
    request-regenerate-changelog-merged.md
    correction-run-formatter-committing.md
    workflow-release-notes.md
```

Re-running on the same day replaces the files the tool generated in that day's folder.
Your own files there are left alone. See [`examples/sample-candidate.md`](examples/sample-candidate.md)
for the format.

## How detection works

1. **Scope.** The tool resolves the git top level of `--repo`, plus every
   `git worktree list` entry. With `--same-remote`, it also adds any checkout whose
   `origin` matches.
2. **Collect.**
   - Claude Code: `<claude_home>/projects/<encoded path>/*.jsonl`, keeping records
     whose `cwd` is in scope.
   - Codex: `<codex_home>/sessions/**/*.jsonl`, keeping rollouts whose `session_meta` /
     `turn_context` `cwd` is in scope.
   - It keeps typed user turns and slash-command or `$skill` invocations. It drops
     everything else.
3. **Classify.** A user turn that follows an assistant turn and opens with a correction
   marker counts as a correction. Examples are "no", "don't", "instead" and "I said".
   Every other turn is a request.
4. **Cluster.**
   - Turns are grouped by token-set Jaccard similarity (stopwords, URLs, paths, code
     fences and numbers are removed first).
   - Invocations are grouped by name. Built-in agent commands such as `/clear` and
     `/model` are ignored.
5. **Filter.** Clusters below `min_count` / `min_sessions`, or matching an existing
   skill, are dropped.
6. **Write.** One redacted candidate per cluster.

The same input always produces the same output.

## Limits

- The formats of both agents' session logs are undocumented and may change. The
  parsers skip records they don't recognise rather than fail, so a format change shows
  up as fewer prompts, not an error. Check `prompts` in the summary.
- Similarity is lexical. Two requests that mean the same thing in different words
  won't cluster.
- It only sees sessions still on disk; see
  [How much history there is to mine](#how-much-history-there-is-to-mine).
- One person's history is a small sample. Candidates get more reliable the more
  sessions there are to mine.

## Tests

```bash
python3 -m unittest discover -s contrib/skill-miner/tests -v
```
