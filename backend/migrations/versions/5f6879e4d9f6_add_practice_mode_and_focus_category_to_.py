"""add_practice_mode_and_focus_category_to_interview_sessions

Revision ID: 5f6879e4d9f6
Revises: feae8be1dc16
Create Date: 2026-10-19 08:16:41.418867

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5f6879e4d9f6'
down_revision: Union[str, Sequence[str], None] = 'feae8be1dc16'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. Add practice_mode column with default full_mock
    op.add_column('interview_sessions', sa.Column('practice_mode', sa.String(length=50), nullable=True))
    op.execute("UPDATE interview_sessions SET practice_mode = 'full_mock' WHERE practice_mode IS NULL")
    op.alter_column('interview_sessions', 'practice_mode', nullable=False, server_default='full_mock')

    # 2. Add focus_category column
    op.add_column('interview_sessions', sa.Column('focus_category', sa.String(length=50), nullable=True))

    # 3. Add check constraints
    op.create_check_constraint(
        'check_interview_session_practice_mode',
        'interview_sessions',
        "practice_mode IN ('full_mock', 'focus_category', 'weakness_recovery')"
    )
    op.create_check_constraint(
        'check_interview_session_focus_category',
        'interview_sessions',
        "(practice_mode = 'full_mock' AND focus_category IS NULL) OR "
        "(practice_mode IN ('focus_category', 'weakness_recovery') AND "
        "focus_category IN ('backend_fundamentals', 'cv_project_experience', 'database', 'api_web_design', 'debugging_problem_solving', 'behavioral_teamwork'))"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('check_interview_session_focus_category', 'interview_sessions', type_='check')
    op.drop_constraint('check_interview_session_practice_mode', 'interview_sessions', type_='check')
    op.drop_column('interview_sessions', 'focus_category')
    op.drop_column('interview_sessions', 'practice_mode')
