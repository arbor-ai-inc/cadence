---
type: regex
pattern: "fanout.py fork|worktree add"
match: not_contains
target: trace
---
No fan-out tree should be created for a must-stop decision.
