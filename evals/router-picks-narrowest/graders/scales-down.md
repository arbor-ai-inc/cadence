---
type: llm
criteria: >
  Did the response say that this needs little or no workflow ceremony — a
  narrow fix, not the spec pipeline and not test-driven-development? A correct
  answer names at most the git flow for getting it committed, and explicitly
  declines to escalate. An INCORRECT answer routes a typo through
  spec-driven-development, the spec pipeline, or a full review loop.
focus: Whether the workflow scaled down rather than up.
---
Every one of these workflows can fail by being too heavy. The routing doc says
to use the narrowest one and skip the ceremony; an agent that always escalates
makes the whole set unusable.
