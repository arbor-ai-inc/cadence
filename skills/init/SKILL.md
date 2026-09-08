---
name: init
description: >
  Use when setting up cadence in a project for the first time, or when asked
  where cadence's config and templates are. Creates cadence.toml and, on
  request, the retro ledger. Never overwrites an existing file.
allowed-tools: Read, Bash, Edit
---

Run the scaffolder. It sits beside the templates and finds them relative to itself, so nothing here needs to know where the plugin is installed:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/tools/init_project.py --retros
```

Add `--hook` to also write `.cadence/check-scope`, the shim a commit hook calls — needed before any autonomous run, because it is what actually enforces `[[must_stop]]`. Add `--all` for the optional templates (principles rubric, review standards, spec templates, tools inventory). Add `--dry-run` to show what would happen first. It never overwrites — an existing file is reported as kept.

**Never edit the project's hook config yourself without asking.** The script writes `.cadence/check-scope`; wiring it into `.pre-commit-config.yaml` (or whatever runs their hooks) is a change to their build. **Propose the exact block and let the author apply it**, or ask first. Two runs of this skill that make different decisions there is not a reproducible setup.

When you propose it, say precisely what it gates: it refuses a commit **only on a `fan/*` branch or inside a fan-out worktree**. On main or an ordinary feature branch it is a no-op. So it bounds fan-out; it does **not** protect those paths on every commit, and an author reading eight `[[must_stop]]` entries may reasonably assume otherwise.

**Check `.gitignore` covers `.cadence/fanout/` and `.cadence/worktrees/`.** Leaf worktrees inside the repo will otherwise show up as untracked files. `.cadence/cadence` and `.cadence/check-scope` stay tracked on purpose.

**Then do the two things the script prints, because the files alone do nothing:**

1. **Set `[commands].lint` and `[commands].test`.** Read them from the project — a Makefile, a CI workflow, a package manifest, a contributing guide — rather than asking. Put the whole command in, including venv activation and env vars. Offer what you found and let the author correct it.

2. **Fill in `[[must_stop]]`.** Look for the surfaces where being wrong is expensive and hard to undo: migrations, published API contracts, auth, billing, anything shipped to third parties. Propose a list from what is actually in the tree, with a reason per entry. **Say plainly that an empty boundary means an autonomous run will never stop for a human** — that is the whole point of the section, and it is the one thing cadence cannot guess.

Confirm it loaded with `python3 ${CLAUDE_PLUGIN_ROOT}/tools/cadence_config.py`, and show the author the effective config.

Do not set up the spec pipeline unless asked. It needs a principles rubric written first, and an empty rubric makes Gate 2 grade against generalities — worse than no gate, because it looks like review.
