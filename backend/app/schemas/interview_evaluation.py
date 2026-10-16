import uuid
from typing import Optional, List, Dict
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict, model_validator
from app.models.interview_evaluation import EvaluationStatus, ReadinessLevel, EvaluationConfidence
from app.models.interview_question import QuestionCategory, QuestionDifficulty


from app.core.rounding import round_score, round_delta, round_sum_scores


class CreateEvaluationRequest(BaseModel):
    consent_to_external_ai: bool

    model_config = ConfigDict(extra="forbid")


from typing_extensions import Annotated
from pydantic import StringConstraints

ShortItemString = Annotated[str, StringConstraints(min_length=1, max_length=300)]
TopicString = Annotated[str, StringConstraints(min_length=1, max_length=100)]


class QuestionEvaluationAI(BaseModel):
    question_order: int = Field(..., ge=1, le=10)
    technical_accuracy: float = Field(..., ge=0.0, le=4.0)
    completeness: float = Field(..., ge=0.0, le=2.0)
    reasoning_clarity: float = Field(..., ge=0.0, le=2.0)
    relevance: float = Field(..., ge=0.0, le=1.0)
    practical_example: float = Field(..., ge=0.0, le=1.0)
    total_score: float = Field(..., ge=0.0, le=10.0)
    feedback: str = Field(..., min_length=10, max_length=2000)
    strengths: List[ShortItemString] = Field(default_factory=list, max_length=8)
    missing_points: List[ShortItemString] = Field(default_factory=list, max_length=8)
    suggested_answer: str = Field(..., min_length=10, max_length=2000)
    study_topics: List[TopicString] = Field(default_factory=list, max_length=8)
    confidence: EvaluationConfidence

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_total_score(self) -> "QuestionEvaluationAI":
        tech = round_score(self.technical_accuracy)
        comp = round_score(self.completeness)
        reas = round_score(self.reasoning_clarity)
        rel = round_score(self.relevance)
        prac = round_score(self.practical_example)
        computed = round_sum_scores([tech, comp, reas, rel, prac])
        tot = round_score(self.total_score)
        if abs(round_delta(tot, computed)) >= 0.01:
            raise ValueError(
                f"total_score ({self.total_score}) không bằng tổng 5 thành phần ({computed})."
            )
        self.technical_accuracy = tech
        self.completeness = comp
        self.reasoning_clarity = reas
        self.relevance = rel
        self.practical_example = prac
        self.total_score = computed
        return self


class InterviewEvaluationAISet(BaseModel):
    evaluations: List[QuestionEvaluationAI] = Field(..., min_length=1, max_length=10)
    overall_summary: str = Field(..., min_length=10, max_length=3000)
    key_strengths: List[ShortItemString] = Field(default_factory=list, max_length=8)
    knowledge_gaps: List[ShortItemString] = Field(default_factory=list, max_length=8)
    priority_improvements: List[ShortItemString] = Field(default_factory=list, max_length=8)
    recommended_study_topics: List[TopicString] = Field(default_factory=list, max_length=8)
    short_term_study_plan: List[ShortItemString] = Field(default_factory=list, max_length=8)
    next_interview_advice: str = Field(..., min_length=10, max_length=2000)

    model_config = ConfigDict(extra="forbid")


class ResponseEvaluationDetail(BaseModel):
    interview_response_id: uuid.UUID
    question_order: int
    question_text: str
    category: QuestionCategory
    difficulty: QuestionDifficulty
    is_skipped: bool
    technical_accuracy: float
    completeness: float
    reasoning_clarity: float
    relevance: float
    practical_example: float
    total_score: float
    feedback: str
    strengths: List[str]
    missing_points: List[str]
    suggested_answer: str
    study_topics: List[str]
    confidence: EvaluationConfidence

    model_config = ConfigDict(extra="forbid", from_attributes=True)


class InterviewEvaluationResponse(BaseModel):
    id: uuid.UUID
    interview_session_id: uuid.UUID
    status: EvaluationStatus
    provider: str
    model: str
    prompt_version: str
    schema_version: str
    total_score: Optional[float] = None
    average_score: Optional[float] = None
    answered_count: Optional[int] = None
    skipped_count: Optional[int] = None
    category_scores: Optional[Dict[str, float]] = None
    overall_summary: Optional[str] = None
    key_strengths: Optional[List[str]] = None
    knowledge_gaps: Optional[List[str]] = None
    priority_improvements: Optional[List[str]] = None
    recommended_study_topics: Optional[List[str]] = None
    short_term_study_plan: Optional[List[str]] = None
    next_interview_advice: Optional[str] = None
    readiness_level: Optional[ReadinessLevel] = None
    responses: List[ResponseEvaluationDetail] = Field(default_factory=list)
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    evaluated_at: Optional[datetime] = None

    model_config = ConfigDict(extra="forbid", from_attributes=True)
