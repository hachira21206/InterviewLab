from pydantic import BaseModel, Field, ConfigDict, StringConstraints, model_validator, computed_field
from typing import List, Optional
from datetime import datetime
from app.models.interview_session import SessionStatus, PracticeMode
from app.models.interview_question import QuestionCategory, QuestionDifficulty, QuestionSource
import uuid
from typing_extensions import Annotated

KeyPointString = Annotated[str, StringConstraints(min_length=1, max_length=300)]

PRACTICE_MODE_LABELS = {
    PracticeMode.full_mock: "Phỏng vấn tổng hợp",
    PracticeMode.focus_category: "Luyện theo chuyên đề",
    PracticeMode.weakness_recovery: "Luyện bù điểm yếu",
}

CATEGORY_LABELS = {
    QuestionCategory.backend_fundamentals: "Kiến thức cốt lõi Backend",
    QuestionCategory.cv_project_experience: "Kinh nghiệm dự án & CV",
    QuestionCategory.database: "Cơ sở dữ liệu & SQL",
    QuestionCategory.api_web_design: "Thiết kế API & Web Architecture",
    QuestionCategory.debugging_problem_solving: "Debug & Xử lý sự cố",
    QuestionCategory.behavioral_teamwork: "Kỹ năng mềm & Làm việc nhóm",
}

SHORT_CATEGORY_LABELS = {
    QuestionCategory.backend_fundamentals: "Nền tảng Backend",
    QuestionCategory.cv_project_experience: "Dự án trong CV",
    QuestionCategory.database: "Database",
    QuestionCategory.api_web_design: "API & Web Design",
    QuestionCategory.debugging_problem_solving: "Debugging",
    QuestionCategory.behavioral_teamwork: "Behavioral",
}

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
    practice_mode: PracticeMode = PracticeMode.full_mock
    focus_category: Optional[QuestionCategory] = None
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

    @computed_field
    @property
    def practice_mode_label(self) -> str:
        return PRACTICE_MODE_LABELS.get(self.practice_mode, self.practice_mode.value)

    @computed_field
    @property
    def focus_category_label(self) -> Optional[str]:
        if self.focus_category:
            return CATEGORY_LABELS.get(self.focus_category, self.focus_category.value)
        return None

    @computed_field
    @property
    def mode_display_title(self) -> str:
        short_cat = SHORT_CATEGORY_LABELS.get(self.focus_category, self.focus_category.value) if self.focus_category else ""
        if self.practice_mode == PracticeMode.full_mock:
            return f"Lần {self.attempt_number} · Phỏng vấn tổng hợp"
        elif self.practice_mode == PracticeMode.focus_category:
            return f"Lần {self.attempt_number} · Luyện {short_cat}"
        elif self.practice_mode == PracticeMode.weakness_recovery:
            return f"Lần {self.attempt_number} · Bù điểm yếu: {short_cat}"
        return f"Lần {self.attempt_number}"


from app.models.interview_evaluation import ReadinessLevel


class CreateSessionRequest(BaseModel):
    consent_to_external_ai: bool
    practice_mode: PracticeMode = PracticeMode.full_mock
    focus_category: Optional[QuestionCategory] = None

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_practice_mode_and_category(self):
        if self.practice_mode == PracticeMode.full_mock:
            if self.focus_category is not None:
                raise ValueError("Chế độ phỏng vấn tổng hợp (full_mock) không được chỉ định focus_category.")
        elif self.practice_mode == PracticeMode.focus_category:
            if self.focus_category is None:
                raise ValueError("Vui lòng chọn một chuyên đề hợp lệ cho chế độ luyện theo chuyên đề.")
        elif self.practice_mode == PracticeMode.weakness_recovery:
            if self.focus_category is not None:
                raise ValueError("Chế độ luyện bù điểm yếu (weakness_recovery) do hệ thống tự xác định, không truyền focus_category.")
        return self


class WeaknessRecommendationResponse(BaseModel):
    available: bool
    category: Optional[QuestionCategory] = None
    category_label: Optional[str] = None
    average_score: Optional[float] = None
    evaluated_sessions_count: int = Field(..., ge=0)
    message: str

    model_config = ConfigDict(extra="forbid")


class InterviewHistoryItem(BaseModel):
    id: uuid.UUID
    job_application_id: uuid.UUID
    attempt_number: int = Field(..., ge=1)
    practice_mode: PracticeMode = PracticeMode.full_mock
    focus_category: Optional[QuestionCategory] = None
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

    @computed_field
    @property
    def practice_mode_label(self) -> str:
        return PRACTICE_MODE_LABELS.get(self.practice_mode, self.practice_mode.value)

    @computed_field
    @property
    def focus_category_label(self) -> Optional[str]:
        if self.focus_category:
            return CATEGORY_LABELS.get(self.focus_category, self.focus_category.value)
        return None

    @computed_field
    @property
    def mode_display_title(self) -> str:
        short_cat = SHORT_CATEGORY_LABELS.get(self.focus_category, self.focus_category.value) if self.focus_category else ""
        if self.practice_mode == PracticeMode.full_mock:
            return f"Lần {self.attempt_number} · Phỏng vấn tổng hợp"
        elif self.practice_mode == PracticeMode.focus_category:
            return f"Lần {self.attempt_number} · Luyện {short_cat}"
        elif self.practice_mode == PracticeMode.weakness_recovery:
            return f"Lần {self.attempt_number} · Bù điểm yếu: {short_cat}"
        return f"Lần {self.attempt_number}"


class InterviewHistoryListResponse(BaseModel):
    items: List[InterviewHistoryItem]
    total: int = Field(..., ge=0)
    limit: int = Field(..., ge=1, le=50)
    offset: int = Field(..., ge=0)

    model_config = ConfigDict(extra="forbid")
