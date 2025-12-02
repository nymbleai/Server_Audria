"""Add billing tables

Revision ID: a1b2c3d4e5f6
Revises: 81a53520953b
Create Date: 2025-10-16 12:00:00.000000

"""
from typing import Sequence, Union
import uuid
from datetime import datetime

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '81a53520953b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create token_pricing table
    op.create_table('token_pricing',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('usd_per_1k_tokens', sa.Float(), nullable=False),
        sa.Column('effective_date', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_token_pricing_id'), 'token_pricing', ['id'], unique=False)
    
    # Create subscription_tiers table
    op.create_table('subscription_tiers',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('plan_name', sa.String(length=100), nullable=False),
        sa.Column('token_limit', sa.Integer(), nullable=False),
        sa.Column('billing_cycle', sa.String(length=50), nullable=False),
        sa.Column('stripe_price_id', sa.String(length=255), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('plan_name')
    )
    op.create_index(op.f('ix_subscription_tiers_id'), 'subscription_tiers', ['id'], unique=False)
    op.create_index(op.f('ix_subscription_tiers_plan_name'), 'subscription_tiers', ['plan_name'], unique=False)
    
    # Create user_subscriptions table
    op.create_table('user_subscriptions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('supabase_user_id', sa.String(), nullable=False),
        sa.Column('subscription_plan', sa.String(length=100), nullable=False),
        sa.Column('tokens_consumed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('dollar_spent', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('status', sa.Enum('ACTIVE', 'INACTIVE', 'EXPIRED', 'CANCELED', 'LIMIT_REACHED', name='subscriptionstatus'), nullable=False),
        sa.Column('billing_period', sa.String(length=20), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('stripe_customer_id', sa.String(length=255), nullable=True),
        sa.Column('stripe_subscription_id', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_user_subscriptions_id'), 'user_subscriptions', ['id'], unique=False)
    op.create_index(op.f('ix_user_subscriptions_supabase_user_id'), 'user_subscriptions', ['supabase_user_id'], unique=False)
    
    # Create usage_log table
    op.create_table('usage_log',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('supabase_user_id', sa.String(), nullable=False),
        sa.Column('feature_used', sa.Enum('INGESTION', 'REVISION', 'ORCHESTRATOR', 'CHAT', 'PRECEDENT_SEARCH', 'PRECEDENT_EMBED', name='featuretype'), nullable=False),
        sa.Column('tokens_used', sa.Integer(), nullable=False),
        sa.Column('dollar_cost', sa.Float(), nullable=False),
        sa.Column('prompt_tokens', sa.Integer(), nullable=True),
        sa.Column('completion_tokens', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('latency_ms', sa.Integer(), nullable=True),
        sa.Column('model_used', sa.String(length=255), nullable=True),
        sa.Column('project_id', sa.String(length=64), nullable=True),
        sa.Column('file_id', sa.String(length=64), nullable=True),
        sa.Column('request_id', sa.String(length=255), nullable=True),
        sa.Column('meta_data', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_usage_log_id'), 'usage_log', ['id'], unique=False)
    op.create_index(op.f('ix_usage_log_supabase_user_id'), 'usage_log', ['supabase_user_id'], unique=False)
    
    # Create stripe_webhooks table (idempotency and auditing of webhook events)
    op.create_table('stripe_webhooks',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('event_id', sa.String(length=255), nullable=False),
        sa.Column('stripe_customer_id', sa.String(length=255), nullable=False),
        sa.Column('stripe_subscription_id', sa.String(length=255), nullable=True),
        sa.Column('subscription_plan', sa.String(length=255), nullable=True),
        sa.Column('subscription_status', sa.String(length=50), nullable=True),
        sa.Column('last_webhook_update', sa.String(length=100), nullable=True),
        sa.Column('webhook_timestamp', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('event_id'),
    )
    op.create_index(op.f('ix_stripe_webhooks_id'), 'stripe_webhooks', ['id'], unique=False)
    op.create_index(op.f('ix_stripe_webhooks_event_id'), 'stripe_webhooks', ['event_id'], unique=False)
    op.create_index(op.f('ix_stripe_webhooks_stripe_customer_id'), 'stripe_webhooks', ['stripe_customer_id'], unique=False)

    # Insert default token pricing
    current_time = datetime.utcnow().isoformat()
    default_pricing_id = str(uuid.uuid4())
    op.execute(
        f"""
        INSERT INTO token_pricing (id, usd_per_1k_tokens, effective_date, created_at, updated_at, is_deleted)
        VALUES ('{default_pricing_id}', 0.02, '{current_time}', '{current_time}', '{current_time}', false)
        """
    )
    
    # Insert default subscription tiers
    free_tier_id = str(uuid.uuid4())
    pro_tier_id = str(uuid.uuid4())
    enterprise_tier_id = str(uuid.uuid4())
    
    op.execute(
        f"""
        INSERT INTO subscription_tiers (id, plan_name, token_limit, billing_cycle, stripe_price_id, description, created_at, updated_at, is_deleted)
        VALUES 
        ('{free_tier_id}', 'Free', 1000, 'Monthly', NULL, 'Free tier with 1K tokens per month', '{current_time}', '{current_time}', false),
        ('{pro_tier_id}', 'Pro', 1000000, 'Monthly', NULL, 'Pro tier with 1M tokens per month', '{current_time}', '{current_time}', false),
        ('{enterprise_tier_id}', 'Enterprise', 10000000, 'Monthly', NULL, 'Enterprise tier with 10M tokens per month', '{current_time}', '{current_time}', false)
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Drop stripe_webhooks
    op.drop_index(op.f('ix_stripe_webhooks_stripe_customer_id'), table_name='stripe_webhooks')
    op.drop_index(op.f('ix_stripe_webhooks_event_id'), table_name='stripe_webhooks')
    op.drop_index(op.f('ix_stripe_webhooks_id'), table_name='stripe_webhooks')
    op.drop_table('stripe_webhooks')
    # Drop tables in reverse order
    op.drop_index(op.f('ix_usage_log_supabase_user_id'), table_name='usage_log')
    op.drop_index(op.f('ix_usage_log_id'), table_name='usage_log')
    op.drop_table('usage_log')
    
    op.drop_index(op.f('ix_user_subscriptions_supabase_user_id'), table_name='user_subscriptions')
    op.drop_index(op.f('ix_user_subscriptions_id'), table_name='user_subscriptions')
    op.drop_table('user_subscriptions')
    
    op.drop_index(op.f('ix_subscription_tiers_plan_name'), table_name='subscription_tiers')
    op.drop_index(op.f('ix_subscription_tiers_id'), table_name='subscription_tiers')
    op.drop_table('subscription_tiers')
    
    op.drop_index(op.f('ix_token_pricing_id'), table_name='token_pricing')
    op.drop_table('token_pricing')
    
    # Drop enums
    op.execute('DROP TYPE IF EXISTS subscriptionstatus')
    op.execute('DROP TYPE IF EXISTS featuretype')

