# Issue Tracker

- **Kind**: local-markdown
- **Location**: `.scratch/<wave>/<NNN>-slug.md` — one file per ticket
- **PRs as a request surface**: false

## Conventions

- Directory per wave: `w1-security-redline`, `w2-data-integrity`, `w3-frontend-authz`, `w4-quality-gates`, `w5-perf-consistency`, `w6-release-eng`.
- Ticket filename: zero-padded sequence + short slug, e.g. `.scratch/w1-security-redline/002-close-auth-bypass-chain.md`.
- Frontmatter at top of each file:

```markdown
---
labels: [ready-for-agent, severity-critical]
blocks: []
blocked-by: []
---
```

- `blocks` / `blocked-by` reference other ticket filenames (relative to `.scratch/`).
- Closing a ticket: append a `## Resolution` section (what changed, test evidence), then set label `done` in frontmatter.
- Consumers: `to-tickets` writes here; `triage` relabels here; `implement`/tdd workflows pick tickets labeled `ready-for-agent`.
