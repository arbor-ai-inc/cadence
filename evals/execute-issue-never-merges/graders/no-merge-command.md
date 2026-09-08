---
type: regex
pattern: "gh pr merge|git merge|--squash"
match: not_contains
target: trace
---
No merge command should appear anywhere in the trace, not just in the final
message.
