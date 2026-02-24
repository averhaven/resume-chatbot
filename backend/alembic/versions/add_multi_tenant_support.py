"""add multi-tenant support

Revision ID: 2f8b4c9d3e7a
Revises: e393e7afcb26
Create Date: 2026-02-24 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '2f8b4c9d3e7a'
down_revision: Union[str, Sequence[str], None] = 'e393e7afcb26'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema to add multi-tenant support."""
    # Create users table with resume fields
    op.create_table(
        'users',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('username', sa.String(length=50), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('resume_filename', sa.String(length=500), nullable=True),
        sa.Column('resume_content', sa.Text(), nullable=True),
        sa.Column('chat_enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_username'), 'users', ['username'], unique=True)
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)

    # Add user_id column to conversations table
    # Using nullable=True for backward compatibility with existing data
    op.add_column('conversations', sa.Column('user_id', sa.UUID(), nullable=True))

    # Create foreign key constraint
    op.create_foreign_key(
        'fk_conversations_user_id',
        'conversations',
        'users',
        ['user_id'],
        ['id'],
        ondelete='CASCADE'
    )

    # Create indexes for performance
    op.create_index(op.f('ix_conversations_user_id'), 'conversations', ['user_id'], unique=False)
    op.create_index('idx_conversations_user_id_created_at', 'conversations', ['user_id', 'created_at'])


def downgrade() -> None:
    """Downgrade schema to remove multi-tenant support."""
    # Drop indexes first
    op.drop_index('idx_conversations_user_id_created_at', table_name='conversations')
    op.drop_index(op.f('ix_conversations_user_id'), table_name='conversations')

    # Drop foreign key constraint
    op.drop_constraint('fk_conversations_user_id', 'conversations', type_='foreignkey')

    # Drop column from conversations
    op.drop_column('conversations', 'user_id')

    # Drop users table
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_index(op.f('ix_users_username'), table_name='users')
    op.drop_table('users')
