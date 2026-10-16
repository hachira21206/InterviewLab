"""Change evaluation scores from float to numeric

Revision ID: a1b2c3d4e5f6
Revises: f5a8b79e1234
Create Date: 2026-10-10 10:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'f5a8b79e1234'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Alter interview_evaluations score columns to NUMERIC
    op.alter_column(
        'interview_evaluations',
        'total_score',
        existing_type=sa.Float(),
        type_=sa.Numeric(precision=5, scale=2),
        existing_nullable=True
    )
    op.alter_column(
        'interview_evaluations',
        'average_score',
        existing_type=sa.Float(),
        type_=sa.Numeric(precision=4, scale=2),
        existing_nullable=True
    )

    # 2. Alter interview_response_evaluations score columns to NUMERIC
    op.alter_column(
        'interview_response_evaluations',
        'technical_accuracy',
        existing_type=sa.Float(),
        type_=sa.Numeric(precision=3, scale=2),
        existing_nullable=False
    )
    op.alter_column(
        'interview_response_evaluations',
        'completeness',
        existing_type=sa.Float(),
        type_=sa.Numeric(precision=3, scale=2),
        existing_nullable=False
    )
    op.alter_column(
        'interview_response_evaluations',
        'reasoning_clarity',
        existing_type=sa.Float(),
        type_=sa.Numeric(precision=3, scale=2),
        existing_nullable=False
    )
    op.alter_column(
        'interview_response_evaluations',
        'relevance',
        existing_type=sa.Float(),
        type_=sa.Numeric(precision=3, scale=2),
        existing_nullable=False
    )
    op.alter_column(
        'interview_response_evaluations',
        'practical_example',
        existing_type=sa.Float(),
        type_=sa.Numeric(precision=3, scale=2),
        existing_nullable=False
    )
    op.alter_column(
        'interview_response_evaluations',
        'total_score',
        existing_type=sa.Float(),
        type_=sa.Numeric(precision=4, scale=2),
        existing_nullable=False
    )


def downgrade() -> None:
    # 1. Revert interview_response_evaluations score columns to Float
    op.alter_column(
        'interview_response_evaluations',
        'total_score',
        existing_type=sa.Numeric(precision=4, scale=2),
        type_=sa.Float(),
        existing_nullable=False
    )
    op.alter_column(
        'interview_response_evaluations',
        'practical_example',
        existing_type=sa.Numeric(precision=3, scale=2),
        type_=sa.Float(),
        existing_nullable=False
    )
    op.alter_column(
        'interview_response_evaluations',
        'relevance',
        existing_type=sa.Numeric(precision=3, scale=2),
        type_=sa.Float(),
        existing_nullable=False
    )
    op.alter_column(
        'interview_response_evaluations',
        'reasoning_clarity',
        existing_type=sa.Numeric(precision=3, scale=2),
        type_=sa.Float(),
        existing_nullable=False
    )
    op.alter_column(
        'interview_response_evaluations',
        'completeness',
        existing_type=sa.Numeric(precision=3, scale=2),
        type_=sa.Float(),
        existing_nullable=False
    )
    op.alter_column(
        'interview_response_evaluations',
        'technical_accuracy',
        existing_type=sa.Numeric(precision=3, scale=2),
        type_=sa.Float(),
        existing_nullable=False
    )

    # 2. Revert interview_evaluations score columns to Float
    op.alter_column(
        'interview_evaluations',
        'average_score',
        existing_type=sa.Numeric(precision=4, scale=2),
        type_=sa.Float(),
        existing_nullable=True
    )
    op.alter_column(
        'interview_evaluations',
        'total_score',
        existing_type=sa.Numeric(precision=5, scale=2),
        type_=sa.Float(),
        existing_nullable=True
    )
