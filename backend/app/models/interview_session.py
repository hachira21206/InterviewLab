from enum import Enum
from sqlalchemy import (
    Column,
    String,
    Text,
    Integer,
    ForeignKey,
    DateTime,
    func,
    JSON,
    UniqueConstraint,
    CheckConstraint,
    Index,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship, backref
import uuid
from app.db.session import Base

class SessionStatus(str, Enum):
    generating = "generating"
    ready = "ready"
    generation_failed = "generation_failed"
    in_progress = "in_progress"
    completed = "completed"

class InterviewSession(Base):
    __tablename__ = "interview_sessions"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    job_application_id = Column(PG_UUID(as_uuid=True), ForeignKey("job_applications.id", ondelete="CASCADE"), nullable=False)
    attempt_number = Column(Integer, nullable=False, default=1)
    status = Column(String(50), nullable=False)
    provider = Column(String(50), nullable=False)
    model = Column(String(100), nullable=False)
    prompt_version = Column(String(50), nullable=False)
    schema_version = Column(String(50), nullable=False)
    error_code = Column(String(50), nullable=True)
    error_message = Column(Text, nullable=True)
    
    requested_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    generated_at = Column(DateTime(timezone=True), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    application = relationship("JobApplication", backref=backref("interview_sessions", cascade="all, delete-orphan", order_by="InterviewSession.attempt_number"))
    questions = relationship("InterviewQuestion", back_populates="session", cascade="all, delete-orphan", order_by="InterviewQuestion.order_index")
    responses = relationship("InterviewResponse", back_populates="session", cascade="all, delete-orphan")
    evaluation = relationship("InterviewEvaluation", back_populates="session", uselist=False, cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint(
            "status IN ('generating', 'ready', 'generation_failed', 'in_progress', 'completed')",
            name="check_session_status"
        ),
        CheckConstraint(
            "attempt_number >= 1",
            name="check_interview_session_attempt_number"
        ),
        UniqueConstraint(
            "job_application_id", "attempt_number",
            name="uq_interview_sessions_app_attempt"
        ),
        Index(
            "ix_interview_sessions_job_application_id",
            "job_application_id"
        ),
        Index(
            "ix_interview_sessions_app_created_at",
            "job_application_id", "created_at"
        ),
        Index(
            "uq_interview_sessions_active_attempt",
            "job_application_id",
            unique=True,
            postgresql_where=text("status IN ('generating', 'generation_failed', 'ready', 'in_progress')")
        ),
    )
