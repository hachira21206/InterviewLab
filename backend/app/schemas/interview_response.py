import uuid
import re
from typing import Optional, List, Any
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict, model_validator
from app.models.interview_session import SessionStatus
from app.models.interview_question import QuestionCategory, QuestionDifficulty

class ResponseSubmitRequest(BaseModel):
    answer_text: Optional[str] = Field(None, max_length=10000)
    is_skipped: bool

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="before")
    @classmethod
    def validate_and_normalize(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        
        if "is_skipped" not in data:
            raise ValueError("Thiếu trường is_skipped.")
        
        is_skipped = data.get("is_skipped")
        if not isinstance(is_skipped, bool):
            raise ValueError("is_skipped phải là giá trị boolean (true/false).")
            
        answer_text = data.get("answer_text")

        if is_skipped is True:
            if answer_text is not None:
                raise ValueError("Khi bỏ qua câu hỏi (is_skipped=True), answer_text phải là null.")
            return {"answer_text": None, "is_skipped": True}
        else:
            if answer_text is None:
                raise ValueError("Khi trả lời câu hỏi (is_skipped=False), answer_text không được để trống.")
            if not isinstance(answer_text, str):
                raise ValueError("answer_text phải là chuỗi ký tự.")
            
            # Normalize CRLF -> LF
            normalized = answer_text.replace("\r\n", "\n").replace("\r", "\n")
            # Remove dangerous control chars (keep \n and \t)
            normalized = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', normalized)
            # Trim leading/trailing whitespace
            normalized = normalized.strip()

            if len(normalized) == 0:
                raise ValueError("Câu trả lời không được chỉ chứa khoảng trắng.")
            if len(normalized) > 10000:
                raise ValueError("Câu trả lời không được vượt quá 10.000 ký tự.")
            return {"answer_text": normalized, "is_skipped": False}


class InterviewQuestionSummary(BaseModel):
    id: uuid.UUID
    order_index: int
    question_text: str
    category: QuestionCategory
    difficulty: QuestionDifficulty

    model_config = ConfigDict(extra="forbid", from_attributes=True)


class InterviewResponseDetail(BaseModel):
    id: uuid.UUID
    interview_question_id: uuid.UUID
    order_index: int
    question_text: str
    category: QuestionCategory
    difficulty: QuestionDifficulty
    answer_text: Optional[str] = None
    is_skipped: bool
    answered_at: Optional[datetime] = None

    model_config = ConfigDict(extra="forbid", from_attributes=True)


class InterviewProgressResponse(BaseModel):
    session_id: uuid.UUID
    status: SessionStatus
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    total_questions: int = 10
    completed_count: int
    progress_percent: float
    current_question: Optional[InterviewQuestionSummary] = None
    responses: List[InterviewResponseDetail] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class QuestionHintResponse(BaseModel):
    question_id: uuid.UUID
    order_index: int
    category: QuestionCategory
    difficulty: QuestionDifficulty
    interview_goal: str
    key_concepts: List[str] = Field(default_factory=list)
    answer_structure_tips: List[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")

