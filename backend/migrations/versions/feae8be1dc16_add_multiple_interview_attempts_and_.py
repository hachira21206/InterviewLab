"""add_multiple_interview_attempts_and_history

Revision ID: feae8be1dc16
Revises: a1b2c3d4e5f6
Create Date: 2026-10-10 14:59:21.827277

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'feae8be1dc16'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. Drop existing unique constraint on job_application_id
    op.drop_constraint('interview_sessions_job_application_id_key', 'interview_sessions', type_='unique')

    # 2. Add attempt_number column (nullable first, populate existing rows with 1, then set not null)
    op.add_column('interview_sessions', sa.Column('attempt_number', sa.Integer(), nullable=True))
    op.execute("UPDATE interview_sessions SET attempt_number = 1 WHERE attempt_number IS NULL")
    op.alter_column('interview_sessions', 'attempt_number', nullable=False)

    # 3. Add check constraint attempt_number >= 1
    op.create_check_constraint(
        'check_interview_session_attempt_number',
        'interview_sessions',
        'attempt_number >= 1'
    )

    # 4. Add unique constraint UNIQUE(job_application_id, attempt_number)
    op.create_unique_constraint(
        'uq_interview_sessions_app_attempt',
        'interview_sessions',
        ['job_application_id', 'attempt_number']
    )

    # 5. Add query indexes
    op.create_index(
        'ix_interview_sessions_job_application_id',
        'interview_sessions',
        ['job_application_id'],
        unique=False
    )
    op.create_index(
        'ix_interview_sessions_app_created_at',
        'interview_sessions',
        ['job_application_id', 'created_at'],
        unique=False
    )

    # 6. Add partial unique index ensuring at most one active attempt at any time
    op.create_index(
        'uq_interview_sessions_active_attempt',
        'interview_sessions',
        ['job_application_id'],
        unique=True,
        postgresql_where=sa.text("status IN ('generating', 'generation_failed', 'ready', 'in_progress')")
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Safe downgrade guard: fail clearly if multiple attempts exist
    conn = op.get_bind()
    res = conn.execute(sa.text("""
        SELECT job_application_id, count(*)
        FROM interview_sessions
        GROUP BY job_application_id
        HAVING count(*) > 1
    """)).fetchall()
    if res:
        raise RuntimeError(
            f"Cannot downgrade: multiple interview sessions exist for {len(res)} job applications"
        )

    # 1. Drop partial unique index
    op.drop_index('uq_interview_sessions_active_attempt', table_name='interview_sessions')

    # 2. Drop query indexes
    op.drop_index('ix_interview_sessions_app_created_at', table_name='interview_sessions')
    op.drop_index('ix_interview_sessions_job_application_id', table_name='interview_sessions')

    # 3. Drop unique constraint on (job_application_id, attempt_number)
    op.drop_constraint('uq_interview_sessions_app_attempt', 'interview_sessions', type_='unique')

    # 4. Drop check constraint on attempt_number
    op.drop_constraint('check_interview_session_attempt_number', 'interview_sessions', type_='check')

    # 5. Drop attempt_number column
    op.drop_column('interview_sessions', 'attempt_number')

    # 6. Recreate unique constraint on job_application_id
    op.create_unique_constraint(
        'interview_sessions_job_application_id_key',
        'interview_sessions',
        ['job_application_id']
    )
