"""Add check constraints and JSONB

Revision ID: 02dba523c750
Revises: 0d8dd00d54a0
Create Date: 2026-10-09 16:29:07.355592

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '02dba523c750'
down_revision: Union[str, Sequence[str], None] = '0d8dd00d54a0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column('interview_questions', 'expected_key_points',
               existing_type=postgresql.JSON(astext_type=sa.Text()),
               type_=postgresql.JSONB(astext_type=sa.Text()),
               existing_nullable=False,
               postgresql_using='expected_key_points::jsonb')
               
    op.create_check_constraint('check_order_index', 'interview_questions', 'order_index >= 1 AND order_index <= 10')
    op.create_check_constraint('check_question_category', 'interview_questions', "category IN ('backend_fundamentals', 'cv_project_experience', 'database', 'api_web_design', 'debugging_problem_solving', 'behavioral_teamwork')")
    op.create_check_constraint('check_question_difficulty', 'interview_questions', "difficulty IN ('easy', 'medium', 'hard')")
    op.create_check_constraint('check_question_source', 'interview_questions', "source IN ('cv', 'job_description', 'candidate_analysis', 'general_backend')")
    op.create_check_constraint('check_session_status', 'interview_sessions', "status IN ('generating', 'ready', 'generation_failed')")


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('check_session_status', 'interview_sessions', type_='check')
    op.drop_constraint('check_question_source', 'interview_questions', type_='check')
    op.drop_constraint('check_question_difficulty', 'interview_questions', type_='check')
    op.drop_constraint('check_question_category', 'interview_questions', type_='check')
    op.drop_constraint('check_order_index', 'interview_questions', type_='check')
    
    op.alter_column('interview_questions', 'expected_key_points',
               existing_type=postgresql.JSONB(astext_type=sa.Text()),
               type_=postgresql.JSON(astext_type=sa.Text()),
               existing_nullable=False,
               postgresql_using='expected_key_points::json')
