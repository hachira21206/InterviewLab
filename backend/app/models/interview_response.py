import uuid
from sqlalchemy import Column, String, Text, Boolean, ForeignKey, DateTime, func, UniqueConstraint, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship
from app.db.session import Base

class InterviewResponse(Base):
    __tablename__ = "interview_responses"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    interview_session_id = Column(PG_UUID(as_uuid=True), ForeignKey("interview_sessions.id", ondelete="CASCADE"), nullable=False)
    interview_question_id = Column(PG_UUID(as_uuid=True), ForeignKey("interview_questions.id", ondelete="CASCADE"), nullable=False)
    answer_text = Column(Text, nullable=True)
    is_skipped = Column(Boolean, nullable=False, default=False, server_default="false")
    answered_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    session = relationship("InterviewSession", back_populates="responses")
    question = relationship("InterviewQuestion", back_populates="response")

    __table_args__ = (
        UniqueConstraint("interview_session_id", "interview_question_id", name="uq_session_question_response"),
        CheckConstraint(
            "((is_skipped = true AND answer_text IS NULL) OR (is_skipped = false AND answer_text IS NOT NULL))",
            name="check_response_skip_consistency"
        ),
        CheckConstraint(
            "(answer_text IS NULL OR length(trim(answer_text)) > 0)",
            name="check_response_answer_not_whitespace"
        ),
    )
