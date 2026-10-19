"""merge all migration heads

Revision ID: merge_20260530
Revises: 8f7ef51ff62e, fk_cascade_001, region_code_001, token_version_001
Create Date: 2026-05-30

This merge ties together the main migration chain (001 → ... → 8f7ef51ff62e)
with three orphaned branches:
- fk_cascade_001 (foreign key cascade fixes)
- region_code_001 (region code model additions)
- token_version_001 (token versioning)

All branches are empty merges — no new DDL operations.
This ensures `alembic upgrade head` applies all migrations.
"""

from collections.abc import Sequence



# revision identifiers, used by Alembic.
revision: str = "merge_20260530"
down_revision: tuple[str, ...] | None = (
    "8f7ef51ff62e",  # main chain head
    "fk_cascade_001",  # FK cascade fixes
    "region_code_001",  # region code additions
    "token_version_001",  # token versioning
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Empty merge migration — all schema changes are in the parent revisions."""
    pass


def downgrade() -> None:
    """No-op downgrade."""
    pass
