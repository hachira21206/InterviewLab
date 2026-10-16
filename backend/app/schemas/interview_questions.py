from pydantic import BaseModel, Field, ConfigDict, StringConstraints
from typing import List, Optional
from datetime import datetime
from app.models.interview_session import SessionStatus
from app.models.interview_question import QuestionCategory, QuestionDifficulty, QuestionSource
import uuid
from typing_extensions import Annotated

KeyPointString = Annotated[str, StringConstraints(min_length=1, max_length=300)]

class InterviewQuestionGenerated(BaseModel):
    question_text: str = Field(..., min_length=10, max_length=1000)
    category: QuestionCategory
    difficulty: QuestionDifficulty
    purpose: str = Field(..., min_length=10, max_length=500)
    expected_key_points: List[KeyPointString] = Field(..., min_length=1, max_length=8)
    source: QuestionSource
    source_evidence: Optional[str] = Field(None, max_length=300)

    model_config = ConfigDict(extra="forbid")

class InterviewQuestionSet(BaseModel):
    questions: List[InterviewQuestionGenerated] = Field(..., min_length=10, max_length=10)

    model_config = ConfigDict(extra="forbid")

class InterviewQuestionResponse(BaseModel):
    id: uuid.UUID
    order_index: int
    question_text: str
    category: QuestionCategory
    difficulty: QuestionDifficulty

    model_config = ConfigDict(from_attributes=True, extra="forbid")

class InterviewSessionResponse(BaseModel):
    id: uuid.UUID
    job_application_id: uuid.UUID
    attempt_number: int
    status: SessionStatus
    provider: str
    model: str
    schema_version: str
    prompt_version: str
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    generated_at: Optional[datetime] = None
    questions: List[InterviewQuestionResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True, extra="forbid")


from app.models.interview_evaluation import ReadinessLevel


class CreateSessionRequest(BaseModel):
    consent_to_external_ai: bool

    model_config = ConfigDict(extra="forbid")


class InterviewHistoryItem(BaseModel):
    id: uuid.UUID
    job_application_id: uuid.UUID
    attempt_number: int = Field(..., ge=1)
    status: SessionStatus
    question_count: int = Field(..., ge=0, le=10)
    answered_count: int = Field(..., ge=0, le=10)
    skipped_count: int = Field(..., ge=0, le=10)
    total_score: Optional[float] = Field(None, ge=0.0, le=100.0)
    average_score: Optional[float] = Field(None, ge=0.0, le=10.0)
    readiness_level: Optional[ReadinessLevel] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    evaluated_at: Optional[datetime] = None

    model_config = ConfigDict(extra="forbid")


class InterviewHistoryListResponse(BaseModel):
    items: List[InterviewHistoryItem]
    total: int = Field(..., ge=0)
    limit: int = Field(..., ge=1, le=50)
    offset: int = Field(..., ge=0)

    model_config = ConfigDict(extra="forbid")
