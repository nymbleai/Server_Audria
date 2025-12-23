"""Add persons and person_details tables

Revision ID: e4f5g6h7i8j9
Revises: a1b2c3d4e5f6
Create Date: 2025-01-XX 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'e4f5g6h7i8j9'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create persons table
    op.create_table('persons',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('generation', sa.Text(), nullable=True),
        sa.Column('created_at', postgresql.TIMESTAMPTZ(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', postgresql.TIMESTAMPTZ(), nullable=False, server_default=sa.text('NOW()')),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Note: Foreign key to auth.users is handled in Supabase SQL migration
    # as Alembic doesn't have direct access to Supabase auth schema
    # The SQL migration file includes: REFERENCES auth.users(id) ON DELETE CASCADE
    
    op.create_index(op.f('ix_persons_id'), 'persons', ['id'], unique=False)
    op.create_index(op.f('ix_persons_user_id'), 'persons', ['user_id'], unique=False)
    op.create_index(op.f('ix_persons_created_at'), 'persons', ['created_at'], unique=False)
    
    # Create person_details table
    op.create_table('person_details',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('person_id', sa.UUID(), nullable=False),
        sa.Column('data', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('created_at', postgresql.TIMESTAMPTZ(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', postgresql.TIMESTAMPTZ(), nullable=False, server_default=sa.text('NOW()')),
        sa.ForeignKeyConstraint(['person_id'], ['persons.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('person_id')
    )
    
    op.create_index(op.f('ix_person_details_id'), 'person_details', ['id'], unique=False)
    op.create_index(op.f('ix_person_details_person_id'), 'person_details', ['person_id'], unique=False)
    # GIN index for JSONB data (created via raw SQL as Alembic doesn't support GIN indexes directly)
    op.execute('CREATE INDEX IF NOT EXISTS idx_person_details_data ON person_details USING GIN(data)')
    
    # Note: RLS policies and triggers are handled in the Supabase SQL migration file
    # (supabase_migration_persons.sql) as they require Supabase-specific functions


def downgrade() -> None:
    """Downgrade schema."""
    # Drop indexes
    op.execute('DROP INDEX IF EXISTS idx_person_details_data')
    op.drop_index(op.f('ix_person_details_person_id'), table_name='person_details')
    op.drop_index(op.f('ix_person_details_id'), table_name='person_details')
    op.drop_index(op.f('ix_persons_created_at'), table_name='persons')
    op.drop_index(op.f('ix_persons_user_id'), table_name='persons')
    op.drop_index(op.f('ix_persons_id'), table_name='persons')
    
    # Drop tables
    op.drop_table('person_details')
    op.drop_table('persons')

