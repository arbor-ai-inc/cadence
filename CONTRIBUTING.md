# Contributing

Pull requests are welcome from anyone. You need no access to the repository.

1. **Fork and branch.** Nobody pushes to `main` directly, maintainers included:
   every change lands through a reviewed pull request.
2. **Make the change.** Read README § *Contributing* first. It lists the three
   rules that catch most first attempts. For a new or changed workflow, also read
   [`reference/skill-anatomy.md`](reference/skill-anatomy.md).
3. **Run the gates.** Run every command in README § *Verifying it* except
   `check_vocab.py`, which needs repositories you do not have; a maintainer runs it.
4. **Open the pull request.** Say what changes for someone who already uses cadence.
   CI must pass. Your first CI run waits until a maintainer starts it.
5. **Review.** A maintainer ([`.github/CODEOWNERS`](.github/CODEOWNERS)) reviews it
   and merges it. When it merges, the release workflow tags
   `v<version>`.

Contributions are licensed under Apache 2.0 (section 5 of [`LICENSE`](LICENSE)).
There is no CLA.

**A rule that is wrong only for your project** belongs in your project, not here. See
README § *Contributing*.
