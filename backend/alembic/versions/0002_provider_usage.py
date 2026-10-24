"""Persist provider budget reservations independently of process lifetime."""
from alembic import op
import sqlalchemy as sa
revision='0002_provider_usage'
down_revision='0001_viva'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('viva_provider_usage',
        sa.Column('id',sa.String(),primary_key=True),
        sa.Column('session_id',sa.String(),sa.ForeignKey('viva_sessions.id',ondelete='CASCADE'),nullable=False),
        sa.Column('request_kind',sa.String(),nullable=False),
        sa.Column('price_version',sa.String(),nullable=False),
        sa.Column('reserved_microdollars',sa.Integer(),nullable=False),
        sa.Column('actual_microdollars',sa.Integer(),nullable=True),
        sa.Column('status',sa.String(),nullable=False),
        sa.Column('usage',sa.JSON(),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('settled_at',sa.DateTime(timezone=True),nullable=True))
    op.create_index('ix_viva_provider_usage_session_id','viva_provider_usage',['session_id'])

def downgrade():
    op.drop_index('ix_viva_provider_usage_session_id',table_name='viva_provider_usage')
    op.drop_table('viva_provider_usage')
