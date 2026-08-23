# Triage Labels

Canonical role → label string (defaults, no overrides):

| Role | Label |
|------|-------|
| Needs triage | `needs-triage` |
| Needs more info | `needs-info` |
| Ready for an agent to implement | `ready-for-agent` |
| Ready for a human | `ready-for-human` |
| Will not fix | `wontfix` |

## Severity prefixes (repo-local extension)

- `severity-critical` — 军事审计红线 / 可直接沦陷
- `severity-high` — 数据丢失 / 功能完全失效
- `severity-medium` — 防御纵深缺口
- `severity-low` — 卫生与一致性

Apply exactly one triage label + at most one severity label per ticket.
