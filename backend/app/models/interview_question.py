from enum import Enum
from sqlalchemy import Column, String, Text, Integer, ForeignKey, DateTime, func, UniqueConstraint, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import relationship
import uuid
from app.db.session import Base

class QuestionCategory(str, Enum):
    backend_fundamentals = "backend_fundamentals"
    cv_project_experience = "cv_project_experience"
    database = "database"
    api_web_design = "api_web_design"
    debugging_problem_solving = "debugging_problem_solving"
    behavioral_teamwork = "behavioral_teamwork"

class QuestionDifficulty(str, Enum):
    easy = "easy"
    medium = "medium"
    hard = "hard"

class QuestionSource(str, Enum):
    cv = "cv"
    job_description = "job_description"
    candidate_analysis = "candidate_analysis"
    general_backend = "general_backend"

class InterviewQuestion(Base):
    __tablename__ = "interview_questions"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    interview_session_id = Column(PG_UUID(as_uuid=True), ForeignKey("interview_sessions.id", ondelete="CASCADE"), nullable=False)
    order_index = Column(Integer, nullable=False)
    question_text = Column(Text, nullable=False)
    category = Column(String(50), nullable=False)
    difficulty = Column(String(50), nullable=False)
    purpose = Column(Text, nullable=False)
    expected_key_points = Column(JSONB, nullable=False)
    source = Column(String(50), nullable=False)
    source_evidence = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    session = relationship("InterviewSession", back_populates="questions")
    response = relationship("InterviewResponse", back_populates="question", cascade="all, delete-orphan", uselist=False)

    __table_args__ = (
        UniqueConstraint("interview_session_id", "order_index", name="uq_interview_session_order"),
        CheckConstraint(
            "order_index >= 1 AND order_index <= 10",
            name="check_order_index"
        ),
        CheckConstraint(
            "category IN ('backend_fundamentals', 'cv_project_experience', 'database', 'api_web_design', 'debugging_problem_solving', 'behavioral_teamwork')",
            name="check_question_category"
        ),
        CheckConstraint(
            "difficulty IN ('easy', 'medium', 'hard')",
            name="check_question_difficulty"
        ),
        CheckConstraint(
            "source IN ('cv', 'job_description', 'candidate_analysis', 'general_backend')",
            name="check_question_source"
        )
    )
