from pydantic import BaseModel, ConfigDict, field_validator
from typing import Optional, Any
import uuid
import re
from datetime import datetime
from app.models.cv_document import CVStatus

class CVDocumentBase(BaseModel):
    original_filename: str
    media_type: str
    size_bytes: int
    sha256: str
    status: CVStatus

class CVDocumentCreate(CVDocumentBase):
    storage_key: str

class CVDocumentTextUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    extracted_text: str

    @field_validator("extracted_text", mode="before")
    @classmethod
    def validate_extracted_text(cls, v: Any) -> str:
        if not isinstance(v, str):
            raise ValueError("Nội dung CV phải là chuỗi ký tự.")
        v = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", v)
        v = v.replace("\r\n", "\n").replace("\r", "\n").strip()
        if len(v) < 50:
            raise ValueError("Nội dung CV sau chỉnh sửa phải có ít nhất 50 ký tự.")
        if len(v) > 30000:
            raise ValueError("Nội dung CV không được vượt quá 30.000 ký tự.")
        return v

class CVDocumentResponse(CVDocumentBase):
    id: uuid.UUID
    created_at: datetime
    extracted_at: Optional[datetime] = None
    extracted_text: Optional[str] = None
    extraction_error: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

