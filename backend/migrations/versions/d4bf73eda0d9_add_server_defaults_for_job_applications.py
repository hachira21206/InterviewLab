"""Add server defaults for job_applications

Revision ID: d4bf73eda0d9
Revises: c83848b7410e
Create Date: 2026-10-09 09:59:49.219186

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4bf73eda0d9'
down_revision: Union[str, Sequence[str], None] = 'c83848b7410e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column('job_applications', 'interview_language', server_default='vi')
    op.alter_column('job_applications', 'created_at', server_default=sa.text('now()'))
    op.alter_column('job_applications', 'updated_at', server_default=sa.text('now()'))


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column('job_applications', 'interview_language', server_default=None)
    op.alter_column('job_applications', 'created_at', server_default=None)
    op.alter_column('job_applications', 'updated_at', server_default=None)
