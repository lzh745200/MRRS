# Domain Docs

- **Layout**: single-context
- **Root context**: `CONTEXT.md`
- **ADRs**: `docs/adr/NNNN-title.md`

## Consumer rules

1. Before doing non-trivial work in this repo, read `CONTEXT.md` top-to-bottom once.
2. When the task touches a concept listed there, trust that file's terminology; do not invent synonyms.
3. If you discover a durable domain fact that contradicts `CONTEXT.md`, update it in the same change set.
4. Any decision that changes an invariant, a data-isolation rule, an auth boundary, packaging strategy, or a schema-management convention must be recorded as an ADR in `docs/adr/` and referenced from the ticket's Resolution section.
5. ADR numbering: zero-padded four digits, next available number wins; ADRs are immutable once accepted — supersede instead of editing.
