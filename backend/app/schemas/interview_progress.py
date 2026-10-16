import uuid
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.models.interview_evaluation import ReadinessLevel
from app.models.interview_question import QuestionCategory


class ComparisonStatus(str, Enum):
    no_data = "no_data"
    insufficient_data = "insufficient_data"
    improved = "improved"
    declined = "declined"
    unchanged = "unchanged"


class ReadinessDirection(str, Enum):
    improved = "improved"
    declined = "declined"
    unchanged = "unchanged"


class InterviewProgressTrendItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: uuid.UUID
    attempt_number: int = Field(ge=1)
    total_score: float = Field(ge=0.0, le=100.0)
    average_score: float = Field(ge=0.0, le=10.0)
    answered_count: int = Field(ge=0, le=10)
    skipped_count: int = Field(ge=0, le=10)
    readiness_level: ReadinessLevel
    category_scores: Dict[str, float]
    completed_at: Optional[datetime] = None
    evaluated_at: Optional[datetime] = None


class InterviewProgressLatestItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: uuid.UUID
    attempt_number: int = Field(ge=1)
    total_score: float = Field(ge=0.0, le=100.0)
    average_score: float = Field(ge=0.0, le=10.0)
    readiness_level: ReadinessLevel


class InterviewProgressDelta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_score_delta: float
    average_score_delta: float
    answered_count_delta: int
    skipped_count_delta: int
    readiness_changed: bool
    readiness_direction: ReadinessDirection


class InterviewProgressComparison(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: ComparisonStatus
    latest_vs_previous: Optional[InterviewProgressDelta] = None
    latest_vs_first: Optional[InterviewProgressDelta] = None


class CategoryProgressItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: str
    first_score: float = Field(ge=0.0, le=10.0)
    previous_score: Optional[float] = Field(default=None, ge=0.0, le=10.0)
    latest_score: float = Field(ge=0.0, le=10.0)
    latest_vs_previous_delta: Optional[float] = None
    latest_vs_first_delta: Optional[float] = None
    attempts_with_data: int = Field(ge=1)


class InterviewProgressReportResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_application_id: uuid.UUID
    total_attempts: int = Field(ge=0)
    completed_attempts: int = Field(ge=0)
    evaluated_attempts: int = Field(ge=0)
    trend: List[InterviewProgressTrendItem]
    latest: Optional[InterviewProgressLatestItem] = None
    comparison: InterviewProgressComparison
    category_progress: List[CategoryProgressItem]
