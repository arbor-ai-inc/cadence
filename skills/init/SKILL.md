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

**Then do the two things the script prints, because the files alone do nothing:**

1. **Set `[commands].lint` and `[commands].test`.** Read them from the project — a Makefile, a CI workflow, a package manifest, a contributing guide — rather than asking. Put the whole command in, including venv activation and env vars. Offer what you found and let the author correct it.

2. **Fill in `[[must_stop]]`.** Look for the surfaces where being wrong is expensive and hard to undo: migrations, published API contracts, auth, billing, anything shipped to third parties. Propose a list from what is actually in the tree, with a reason per entry. **Say plainly that an empty boundary means an autonomous run will never stop for a human** — that is the whole point of the section, and it is the one thing cadence cannot guess.

Confirm it loaded with `python3 ${CLAUDE_PLUGIN_ROOT}/tools/cadence_config.py`, and show the author the effective config.

Do not set up the spec pipeline unless asked. It needs a principles rubric written first, and an empty rubric makes Gate 2 grade against generalities — worse than no gate, because it looks like review.
