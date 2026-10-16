"""Add interview responses and session status

Revision ID: de10a47503ba
Revises: 02dba523c750
Create Date: 2026-10-09 21:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'de10a47503ba'
down_revision: Union[str, Sequence[str], None] = '02dba523c750'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add started_at and completed_at to interview_sessions
    op.add_column('interview_sessions', sa.Column('started_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('interview_sessions', sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True))

    # 2. Update check constraint on interview_sessions status
    op.drop_constraint('check_session_status', 'interview_sessions', type_='check')
    op.create_check_constraint(
        'check_session_status',
        'interview_sessions',
        "status IN ('generating', 'ready', 'generation_failed', 'in_progress', 'completed')"
    )

    # 3. Create interview_responses table
    op.create_table(
        'interview_responses',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('interview_session_id', sa.UUID(), nullable=False),
        sa.Column('interview_question_id', sa.UUID(), nullable=False),
        sa.Column('answer_text', sa.Text(), nullable=True),
        sa.Column('is_skipped', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('answered_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['interview_session_id'], ['interview_sessions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['interview_question_id'], ['interview_questions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('interview_session_id', 'interview_question_id', name='uq_session_question_response'),
        sa.CheckConstraint(
            "((is_skipped = true AND answer_text IS NULL) OR (is_skipped = false AND answer_text IS NOT NULL))",
            name='check_response_skip_consistency'
        ),
        sa.CheckConstraint(
            "(answer_text IS NULL OR length(trim(answer_text)) > 0)",
            name='check_response_answer_not_whitespace'
        )
    )
    op.create_index(op.f('ix_interview_responses_id'), 'interview_responses', ['id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_interview_responses_id'), table_name='interview_responses')
    op.drop_table('interview_responses')

    op.drop_constraint('check_session_status', 'interview_sessions', type_='check')
    op.create_check_constraint(
        'check_session_status',
        'interview_sessions',
        "status IN ('generating', 'ready', 'generation_failed')"
    )

    op.drop_column('interview_sessions', 'completed_at')
    op.drop_column('interview_sessions', 'started_at')
