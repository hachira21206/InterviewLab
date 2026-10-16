"""Add interview evaluations tables

Revision ID: f5a8b79e1234
Revises: de10a47503ba
Create Date: 2026-10-10 09:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'f5a8b79e1234'
down_revision: Union[str, Sequence[str], None] = 'de10a47503ba'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create interview_evaluations table
    op.create_table(
        'interview_evaluations',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('interview_session_id', sa.UUID(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('provider', sa.String(length=50), nullable=False),
        sa.Column('model', sa.String(length=100), nullable=False),
        sa.Column('prompt_version', sa.String(length=50), nullable=False),
        sa.Column('schema_version', sa.String(length=50), nullable=False),
        sa.Column('total_score', sa.Float(), nullable=True),
        sa.Column('average_score', sa.Float(), nullable=True),
        sa.Column('answered_count', sa.Integer(), nullable=True),
        sa.Column('skipped_count', sa.Integer(), nullable=True),
        sa.Column('category_scores', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('overall_summary', sa.Text(), nullable=True),
        sa.Column('key_strengths', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('knowledge_gaps', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('priority_improvements', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('recommended_study_topics', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('short_term_study_plan', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('next_interview_advice', sa.Text(), nullable=True),
        sa.Column('readiness_level', sa.String(length=50), nullable=True),
        sa.Column('error_code', sa.String(length=50), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('evaluated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['interview_session_id'], ['interview_sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('interview_session_id'),
        sa.CheckConstraint(
            "status IN ('pending', 'evaluating', 'evaluated', 'evaluation_failed')",
            name='check_interview_evaluation_status'
        ),
        sa.CheckConstraint(
            "total_score IS NULL OR (total_score >= 0 AND total_score <= 100)",
            name='check_evaluation_total_score_range'
        ),
        sa.CheckConstraint(
            "average_score IS NULL OR (average_score >= 0 AND average_score <= 10)",
            name='check_evaluation_avg_score_range'
        ),
        sa.CheckConstraint(
            "answered_count IS NULL OR (answered_count >= 0 AND answered_count <= 10)",
            name='check_evaluation_answered_count'
        ),
        sa.CheckConstraint(
            "skipped_count IS NULL OR (skipped_count >= 0 AND skipped_count <= 10)",
            name='check_evaluation_skipped_count'
        ),
        sa.CheckConstraint(
            "(answered_count IS NULL AND skipped_count IS NULL) OR (answered_count + skipped_count = 10)",
            name='check_evaluation_counts_sum'
        ),
        sa.CheckConstraint(
            "readiness_level IS NULL OR readiness_level IN ('needs_foundation', 'developing', 'intern_ready', 'strong_intern_candidate')",
            name='check_evaluation_readiness_level'
        )
    )
    op.create_index(op.f('ix_interview_evaluations_id'), 'interview_evaluations', ['id'], unique=False)

    # 2. Create interview_response_evaluations table
    op.create_table(
        'interview_response_evaluations',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('interview_evaluation_id', sa.UUID(), nullable=False),
        sa.Column('interview_response_id', sa.UUID(), nullable=False),
        sa.Column('technical_accuracy', sa.Float(), nullable=False),
        sa.Column('completeness', sa.Float(), nullable=False),
        sa.Column('reasoning_clarity', sa.Float(), nullable=False),
        sa.Column('relevance', sa.Float(), nullable=False),
        sa.Column('practical_example', sa.Float(), nullable=False),
        sa.Column('total_score', sa.Float(), nullable=False),
        sa.Column('feedback', sa.Text(), nullable=False),
        sa.Column('strengths', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('missing_points', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('suggested_answer', sa.Text(), nullable=False),
        sa.Column('study_topics', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('confidence', sa.String(length=20), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['interview_evaluation_id'], ['interview_evaluations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['interview_response_id'], ['interview_responses.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('interview_response_id'),
        sa.CheckConstraint('technical_accuracy >= 0 AND technical_accuracy <= 4', name='check_resp_eval_tech_acc'),
        sa.CheckConstraint('completeness >= 0 AND completeness <= 2', name='check_resp_eval_complete'),
        sa.CheckConstraint('reasoning_clarity >= 0 AND reasoning_clarity <= 2', name='check_resp_eval_reason'),
        sa.CheckConstraint('relevance >= 0 AND relevance <= 1', name='check_resp_eval_relevance'),
        sa.CheckConstraint('practical_example >= 0 AND practical_example <= 1', name='check_resp_eval_example'),
        sa.CheckConstraint('total_score >= 0 AND total_score <= 10', name='check_resp_eval_total_score_range'),
        sa.CheckConstraint(
            'abs(total_score - (technical_accuracy + completeness + reasoning_clarity + relevance + practical_example)) < 0.01',
            name='check_resp_eval_total_score_sum'
        ),
        sa.CheckConstraint("confidence IN ('low', 'medium', 'high')", name='check_resp_eval_confidence')
    )
    op.create_index(op.f('ix_interview_response_evaluations_id'), 'interview_response_evaluations', ['id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_interview_response_evaluations_id'), table_name='interview_response_evaluations')
    op.drop_table('interview_response_evaluations')

    op.drop_index(op.f('ix_interview_evaluations_id'), table_name='interview_evaluations')
    op.drop_table('interview_evaluations')
