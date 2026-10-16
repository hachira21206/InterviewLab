"""Add extraction fields to CVDocument

Revision ID: 64fb29db9514
Revises: bc3a583cb1b0
Create Date: 2026-10-08 23:52:07.158374

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '64fb29db9514'
down_revision: Union[str, Sequence[str], None] = 'bc3a583cb1b0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("ALTER TYPE cvstatus RENAME TO cvstatus_old")
    op.execute("CREATE TYPE cvstatus AS ENUM('uploaded', 'extracting', 'extracted', 'extraction_failed')")
    op.execute("ALTER TABLE cv_documents ALTER COLUMN status TYPE cvstatus USING status::text::cvstatus")
    op.execute("DROP TYPE cvstatus_old")

    op.add_column('cv_documents', sa.Column('extracted_text', sa.Text(), nullable=True))
    op.add_column('cv_documents', sa.Column('extraction_error', sa.Text(), nullable=True))
    op.add_column('cv_documents', sa.Column('extracted_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('cv_documents', 'extracted_at')
    op.drop_column('cv_documents', 'extraction_error')
    op.drop_column('cv_documents', 'extracted_text')

    op.execute("UPDATE cv_documents SET status = 'uploaded' WHERE status::text IN ('extracting', 'extracted', 'extraction_failed')")
    op.execute("ALTER TYPE cvstatus RENAME TO cvstatus_new")
    op.execute("CREATE TYPE cvstatus AS ENUM('uploaded')")
    op.execute("ALTER TABLE cv_documents ALTER COLUMN status TYPE cvstatus USING status::text::cvstatus")
    op.execute("DROP TYPE cvstatus_new")
