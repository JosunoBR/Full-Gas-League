"""add_audit_log

Revision ID: c3a9f1b2de34
Revises: bca631398eca
Create Date: 2026-03-02 22:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c3a9f1b2de34'
down_revision = 'bca631398eca'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'audit_log',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('user.id')),
        sa.Column('action', sa.String(length=50)),
        sa.Column('model', sa.String(length=50)),
        sa.Column('model_id', sa.Integer()),
        sa.Column('details', sa.Text()),
    )


def downgrade():
    op.drop_table('audit_log')
