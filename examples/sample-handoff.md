# Handoff — PROJ-12-widget-cache

Issue: PROJ-12  ·  Epic/project: widgets  ·  Spec: none
Repo: acme/widget  ·  Checkout: /home/sam/src/widget  ·  Branch(es): proj-12-cache
Owner: sam  ·  Started: 2099-01-01  ·  Last written: 2099-01-09  ·  Status: active

## Resume here — 2099-01-09
Goal: cache widget lookups
State:
- PR #4 open, CI green
Next: address the review comment on #4

## Rules
- run the cache tests with the fake clock — why: real clock flakes (2099-01-05)

## Facts
- cache TTL is 60s — source: config/cache.toml · verified 2099-01-09
### Decided — don't re-open
- LRU over LFU — why: simpler, measured equal · 2099-01-03 · log: 2099-01-03
### Rejected — don't re-propose
- Redis — why not: one more service to run · 2099-01-03

## Log
### 2099-01-09 — review round
- Did: pushed fix · Decided: keep TTL · Promoted: nothing
