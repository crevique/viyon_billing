"""Add Phase 5.2 staff management columns to users table (username, phone, last_login_at).

Revision ID: e51f28b79a04
Revises: d38f1902a7b1
Create Date: 2026-11-11 23:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e51f28b79a04'
down_revision: Union[str, None] = 'd38f1902a7b1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add username, phone, and last_login_at columns
    op.add_column('users', sa.Column('username', sa.String(length=100), nullable=True))
    op.add_column('users', sa.Column('phone', sa.String(length=50), nullable=True))
    op.add_column('users', sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True))

    # 2. Backfill existing users with a collision-free default username derived from email
    op.execute(
        """
        WITH numbered AS (
            SELECT id, email,
                   LOWER(SPLIT_PART(email, '@', 1)) AS base_name,
                   ROW_NUMBER() OVER (
                       PARTITION BY LOWER(SPLIT_PART(email, '@', 1))
                       ORDER BY created_at ASC, id ASC
                   ) AS rn
            FROM users
            WHERE username IS NULL
        )
        UPDATE users u
        SET username = CASE
            WHEN n.rn = 1 THEN n.base_name
            ELSE n.base_name || '_' || n.rn
        END
        FROM numbered n
        WHERE u.id = n.id;
        """
    )

    # 3. Create unique index on username
    op.create_index(op.f('ix_users_username'), 'users', ['username'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_users_username'), table_name='users')
    op.drop_column('users', 'last_login_at')
    op.drop_column('users', 'phone')
    op.drop_column('users', 'username')
