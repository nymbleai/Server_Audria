"""Add scheduled_calls table

Revision ID: f7g8h9i0j1k2
Revises: e4f5g6h7i8j9
Create Date: 2025-01-XX 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'f7g8h9i0j1k2'
down_revision: Union[str, Sequence[str], None] = 'e4f5g6h7i8j9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create scheduled_calls table
    op.create_table('scheduled_calls',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('person_id', sa.UUID(), nullable=True),
        sa.Column('agent_name', sa.String(length=100), nullable=False),
        sa.Column('call_type', sa.String(length=20), nullable=False),
        sa.Column('scheduled_datetime', postgresql.TIMESTAMPTZ(), nullable=True),
        sa.Column('scheduled_time', sa.Time(), nullable=True),
        sa.Column('recurrence_pattern', postgresql.JSONB(), nullable=True),
        sa.Column('leading_reminders', sa.Text(), nullable=True),
        sa.Column('leading_topics', sa.Text(), nullable=True),
        sa.Column('memories', postgresql.JSONB(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='scheduled'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('initiated_at', postgresql.TIMESTAMPTZ(), nullable=True),
        sa.Column('created_at', postgresql.TIMESTAMPTZ(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', postgresql.TIMESTAMPTZ(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false'),
        sa.ForeignKeyConstraint(['person_id'], ['persons.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes
    op.create_index(op.f('ix_scheduled_calls_id'), 'scheduled_calls', ['id'], unique=False)
    op.create_index(op.f('ix_scheduled_calls_user_id'), 'scheduled_calls', ['user_id'], unique=False)
    op.create_index(op.f('ix_scheduled_calls_person_id'), 'scheduled_calls', ['person_id'], unique=False)
    op.create_index(op.f('ix_scheduled_calls_scheduled_datetime'), 'scheduled_calls', ['scheduled_datetime'], unique=False)
    op.create_index(op.f('ix_scheduled_calls_is_active'), 'scheduled_calls', ['is_active'], unique=False)
    op.create_index(op.f('ix_scheduled_calls_is_deleted'), 'scheduled_calls', ['is_deleted'], unique=False)
    
    # GIN index for JSONB columns
    op.execute('CREATE INDEX IF NOT EXISTS idx_scheduled_calls_recurrence_pattern ON scheduled_calls USING GIN(recurrence_pattern)')
    op.execute('CREATE INDEX IF NOT EXISTS idx_scheduled_calls_memories ON scheduled_calls USING GIN(memories)')
    
    # Composite index for common queries
    op.create_index('ix_scheduled_calls_user_active', 'scheduled_calls', ['user_id', 'is_active', 'is_deleted'], unique=False)
    op.create_index('ix_scheduled_calls_user_datetime', 'scheduled_calls', ['user_id', 'scheduled_datetime'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    # Drop indexes
    op.drop_index('ix_scheduled_calls_user_datetime', table_name='scheduled_calls')
    op.drop_index('ix_scheduled_calls_user_active', table_name='scheduled_calls')
    op.execute('DROP INDEX IF EXISTS idx_scheduled_calls_memories')
    op.execute('DROP INDEX IF EXISTS idx_scheduled_calls_recurrence_pattern')
    op.drop_index(op.f('ix_scheduled_calls_is_deleted'), table_name='scheduled_calls')
    op.drop_index(op.f('ix_scheduled_calls_is_active'), table_name='scheduled_calls')
    op.drop_index(op.f('ix_scheduled_calls_scheduled_datetime'), table_name='scheduled_calls')
    op.drop_index(op.f('ix_scheduled_calls_person_id'), table_name='scheduled_calls')
    op.drop_index(op.f('ix_scheduled_calls_user_id'), table_name='scheduled_calls')
    op.drop_index(op.f('ix_scheduled_calls_id'), table_name='scheduled_calls')
    
    # Drop table
    op.drop_table('scheduled_calls')

