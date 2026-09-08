# Tools & Services

<!--
  A stub. Cadence ships no inventory of its own, because a vendor list is the
  most project-specific document there is and the least useful to inherit.

  It is here because several cadence workflows ask "which tool owns this?" and
  answer better with a written inventory than with a guess:

    - `[review].provider`, `[tracker].provider` and `[ask].provider` in
      cadence.toml each name a service. This is where you record what that
      service costs, who administers it, and what happens if it goes away.
    - `code-review-standards` asks who the required reviewers are.
    - An agent proposing a NEW external dependency should be able to check
      whether you already pay for something that does the job. That is the
      single most common form of accidental duplication.

  Fill in the rows you have and delete the rest. Every sample row below is
  commented out, so an unfilled file renders as empty rather than as a claim
  about tools you do not use.

  ## One caution before you commit it

  Cost and owner columns make this document sensitive in a way its filename does
  not suggest. A per-seat price list plus named owners is competitive and
  personal information, and it is the kind of thing that gets copied into a
  public repo by accident — which is exactly why cadence ships this file empty
  and its own release gate refuses any file containing one.

  If your repository is public, or may become public, keep the inventory
  elsewhere and leave this file as a pointer to it. If it is private, consider
  recording a ROLE rather than a person's name in the Owner column: roles
  survive people leaving, and a role is not personal data.
-->

## Identity & collaboration

<!--
| Tool | Purpose | Plan | Cost | Owner |
|---|---|---|---|---|
| <name> | SSO, email, calendar | <plan> | <cost> | <role> |
| <name> | Shared secrets, credential management | <plan> | <cost> | <role> |
-->

## Code & development

<!--
| Tool | Purpose | Plan | Cost | Owner |
|---|---|---|---|---|
| <name> | Source control, CI | <plan> | <cost> | <role> |
| <name> | Dev environments | <plan> | <cost> | <role> |
-->

## Project management & docs

<!--
  If you set [tracker].provider in cadence.toml, the tracker belongs here.

| Tool | Purpose | Plan | Cost | Owner |
|---|---|---|---|---|
| <name> | Issues, planning — `[tracker].provider` | <plan> | <cost> | <role> |
| <name> | Non-code docs | <plan> | <cost> | <role> |
-->

## Observability & quality

<!--
| Tool | Purpose | Plan | Cost | Owner |
|---|---|---|---|---|
| <name> | Error tracking | <plan> | <cost> | <role> |
| <name> | Logs, metrics, traces | <plan> | <cost> | <role> |
| <name> | Product analytics | <plan> | <cost> | <role> |
-->

## Code review & security

<!--
  If you set [review].provider in cadence.toml, the reviewer belongs here.

| Tool | Purpose | Plan | Cost | Owner |
|---|---|---|---|---|
| <name> | Automated PR review — `[review].provider` | <plan> | <cost> | <role> |
| <name> | Dependency and secret scanning | <plan> | <cost> | <role> |
-->

## Infrastructure

<!--
| Tool | Purpose | Plan | Cost | Owner |
|---|---|---|---|---|
| <name> | Compute, storage, managed databases | <plan> | <cost> | <role> |
| <name> | DNS, CDN | <plan> | <cost> | <role> |
-->

## Notes

<!--
  Worth recording, and easy to forget:

  - **Which of these an agent may spend money on.** Almost certainly none. If a
    workflow could provision a paid resource, that path belongs in
    `[[must_stop]]` in cadence.toml, not in a sentence here.
  - **What is a current pick versus a settled choice.** A tool marked as
    provisional will otherwise harden into a dependency by accident.
  - **What replaces each one if it goes away**, for anything on a critical path.
-->
