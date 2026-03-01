"""initial schema - faucet tables

Revision ID: 0001
Revises: 
Create Date: 2026-02-28 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '0001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.create_table(
        'faucet_requests',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('wallet_address', sa.String(length=42), nullable=False),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.String(length=512), nullable=True),
        sa.Column('amount', sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column('tx_hash', sa.String(length=66), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('turnstile_verified', sa.Boolean(), nullable=True, default=False),
        sa.Column('risk_score', sa.Integer(), nullable=True, default=0),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tx_hash'),
    )
    op.create_index(op.f('ix_faucet_requests_id'), 'faucet_requests', ['id'], unique=False)
    op.create_index(op.f('ix_faucet_requests_ip_address'), 'faucet_requests', ['ip_address'], unique=False)
    op.create_index(op.f('ix_faucet_requests_status'), 'faucet_requests', ['status'], unique=False)
    op.create_index(op.f('ix_faucet_requests_tx_hash'), 'faucet_requests', ['tx_hash'], unique=True)
    op.create_index(op.f('ix_faucet_requests_wallet_address'), 'faucet_requests', ['wallet_address'], unique=False)
    op.create_index(op.f('ix_faucet_requests_created_at'), 'faucet_requests', ['created_at'], unique=False)
    op.create_index('idx_wallet_created', 'faucet_requests', ['wallet_address', 'created_at'], unique=False)
    op.create_index('idx_ip_created', 'faucet_requests', ['ip_address', 'created_at'], unique=False)
    op.create_index('idx_status_created', 'faucet_requests', ['status', 'created_at'], unique=False)

    op.create_table(
        'blocked_addresses',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('address_type', sa.String(length=10), nullable=False),
        sa.Column('address_value', sa.String(length=100), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('blocked_by', sa.String(length=42), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, default=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('address_value'),
    )
    op.create_index(op.f('ix_blocked_addresses_id'), 'blocked_addresses', ['id'], unique=False)
    op.create_index(op.f('ix_blocked_addresses_address_value'), 'blocked_addresses', ['address_value'], unique=True)
    op.create_index(op.f('ix_blocked_addresses_is_active'), 'blocked_addresses', ['is_active'], unique=False)

    op.create_table(
        'faucet_stats',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('total_requests', sa.Integer(), nullable=True, default=0),
        sa.Column('successful_requests', sa.Integer(), nullable=True, default=0),
        sa.Column('failed_requests', sa.Integer(), nullable=True, default=0),
        sa.Column('rate_limited_requests', sa.Integer(), nullable=True, default=0),
        sa.Column('total_amount_distributed', sa.Numeric(precision=18, scale=6), nullable=True, default=0),
        sa.Column('unique_wallets', sa.Integer(), nullable=True, default=0),
        sa.Column('unique_ips', sa.Integer(), nullable=True, default=0),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('date'),
    )
    op.create_index(op.f('ix_faucet_stats_id'), 'faucet_stats', ['id'], unique=False)
    op.create_index(op.f('ix_faucet_stats_date'), 'faucet_stats', ['date'], unique=True)


def downgrade() -> None:
    op.drop_table('faucet_stats')
    op.drop_table('blocked_addresses')
    op.drop_index('idx_status_created', table_name='faucet_requests')
    op.drop_index('idx_ip_created', table_name='faucet_requests')
    op.drop_index('idx_wallet_created', table_name='faucet_requests')
    op.drop_table('faucet_requests')