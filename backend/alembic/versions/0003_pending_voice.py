"""Track one accepted voice utterance and its bounded drain deadline."""
from alembic import op
import sqlalchemy as sa
revision='0003_pending_voice'
down_revision='0002_provider_usage'
branch_labels=None
depends_on=None

def upgrade():
    op.add_column('viva_connections',sa.Column('pending_utterance_id',sa.String(),nullable=True))
    op.add_column('viva_connections',sa.Column('pending_since',sa.DateTime(timezone=True),nullable=True))
    op.add_column('viva_connections',sa.Column('drain_started_at',sa.DateTime(timezone=True),nullable=True))

def downgrade():
    with op.batch_alter_table('viva_connections') as batch:
        batch.drop_column('drain_started_at')
        batch.drop_column('pending_since')
        batch.drop_column('pending_utterance_id')
