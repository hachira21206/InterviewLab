import uuid
from enum import Enum
from sqlalchemy import (
    Column,
    String,
    Text,
    Float,
    Numeric,
    Integer,
    ForeignKey,
    DateTime,
    func,
    CheckConstraint,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import relationship, backref
from app.db.session import Base


class EvaluationStatus(str, Enum):
    pending = "pending"
    evaluating = "evaluating"
    evaluated = "evaluated"
    evaluation_failed = "evaluation_failed"


class ReadinessLevel(str, Enum):
    needs_foundation = "needs_foundation"
    developing = "developing"
    intern_ready = "intern_ready"
    strong_intern_candidate = "strong_intern_candidate"


class EvaluationConfidence(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class InterviewEvaluation(Base):
    __tablename__ = "interview_evaluations"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    interview_session_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("interview_sessions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    status = Column(String(50), nullable=False, default=EvaluationStatus.pending)
    provider = Column(String(50), nullable=False)
    model = Column(String(100), nullable=False)
    prompt_version = Column(String(50), nullable=False)
    schema_version = Column(String(50), nullable=False)

    # Overall report fields
    total_score = Column(Numeric(5, 2), nullable=True)
    average_score = Column(Numeric(4, 2), nullable=True)
    answered_count = Column(Integer, nullable=True)
    skipped_count = Column(Integer, nullable=True)
    category_scores = Column(JSONB, nullable=True)
    overall_summary = Column(Text, nullable=True)
    key_strengths = Column(JSONB, nullable=True)
    knowledge_gaps = Column(JSONB, nullable=True)
    priority_improvements = Column(JSONB, nullable=True)
    recommended_study_topics = Column(JSONB, nullable=True)
    short_term_study_plan = Column(JSONB, nullable=True)
    next_interview_advice = Column(Text, nullable=True)
    readiness_level = Column(String(50), nullable=True)

    # Status tracking & metadata
    error_code = Column(String(50), nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    evaluated_at = Column(DateTime(timezone=True), nullable=True)

    session = relationship("InterviewSession", back_populates="evaluation")
    response_evaluations = relationship(
        "InterviewResponseEvaluation",
        back_populates="evaluation",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'evaluating', 'evaluated', 'evaluation_failed')",
            name="check_interview_evaluation_status",
        ),
        CheckConstraint(
            "total_score IS NULL OR (total_score >= 0 AND total_score <= 100)",
            name="check_evaluation_total_score_range",
        ),
        CheckConstraint(
            "average_score IS NULL OR (average_score >= 0 AND average_score <= 10)",
            name="check_evaluation_avg_score_range",
        ),
        CheckConstraint(
            "answered_count IS NULL OR (answered_count >= 0 AND answered_count <= 10)",
            name="check_evaluation_answered_count",
        ),
        CheckConstraint(
            "skipped_count IS NULL OR (skipped_count >= 0 AND skipped_count <= 10)",
            name="check_evaluation_skipped_count",
        ),
        CheckConstraint(
            "(answered_count IS NULL AND skipped_count IS NULL) OR (answered_count + skipped_count = 10)",
            name="check_evaluation_counts_sum",
        ),
        CheckConstraint(
            "readiness_level IS NULL OR readiness_level IN ('needs_foundation', 'developing', 'intern_ready', 'strong_intern_candidate')",
            name="check_evaluation_readiness_level",
        ),
    )


class InterviewResponseEvaluation(Base):
    __tablename__ = "interview_response_evaluations"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    interview_evaluation_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("interview_evaluations.id", ondelete="CASCADE"),
        nullable=False,
    )
    interview_response_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("interview_responses.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    # Five component scores
    technical_accuracy = Column(Numeric(3, 2), nullable=False)
    completeness = Column(Numeric(3, 2), nullable=False)
    reasoning_clarity = Column(Numeric(3, 2), nullable=False)
    relevance = Column(Numeric(3, 2), nullable=False)
    practical_example = Column(Numeric(3, 2), nullable=False)
    total_score = Column(Numeric(4, 2), nullable=False)

    # Detailed feedback
    feedback = Column(Text, nullable=False)
    strengths = Column(JSONB, nullable=False)
    missing_points = Column(JSONB, nullable=False)
    suggested_answer = Column(Text, nullable=False)
    study_topics = Column(JSONB, nullable=False)
    confidence = Column(String(20), nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    evaluation = relationship("InterviewEvaluation", back_populates="response_evaluations")
    response = relationship(
        "InterviewResponse",
        backref=backref("evaluation", uselist=False, cascade="all, delete-orphan"),
    )

    __table_args__ = (
        CheckConstraint(
            "technical_accuracy >= 0 AND technical_accuracy <= 4",
            name="check_resp_eval_tech_acc",
        ),
        CheckConstraint(
            "completeness >= 0 AND completeness <= 2",
            name="check_resp_eval_complete",
        ),
        CheckConstraint(
            "reasoning_clarity >= 0 AND reasoning_clarity <= 2",
            name="check_resp_eval_reason",
        ),
        CheckConstraint(
            "relevance >= 0 AND relevance <= 1",
            name="check_resp_eval_relevance",
        ),
        CheckConstraint(
            "practical_example >= 0 AND practical_example <= 1",
            name="check_resp_eval_example",
        ),
        CheckConstraint(
            "total_score >= 0 AND total_score <= 10",
            name="check_resp_eval_total_score_range",
        ),
        CheckConstraint(
            "abs(total_score - (technical_accuracy + completeness + reasoning_clarity + relevance + practical_example)) < 0.01",
            name="check_resp_eval_total_score_sum",
        ),
        CheckConstraint(
            "confidence IN ('low', 'medium', 'high')",
            name="check_resp_eval_confidence",
        ),
    )
