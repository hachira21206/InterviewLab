import re
from typing import Optional
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, ConfigDict, field_validator
from .cv_document import CVStatus

def normalize_jd(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    # Remove control characters except standard whitespace (\n, \t)
    value = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', value)
    # Normalize CRLF/CR to LF
    value = value.replace('\r\n', '\n').replace('\r', '\n')
    # Collapse multiple tabs/spaces but keep newlines
    value = re.sub(r'[ \t]+', ' ', value)
    value = value.strip()
    if not value:
        return None
    if len(value) < 50:
        raise ValueError("Job Description phải chứa ít nhất 50 ký tự hợp lệ.")
    if len(value) > 20000:
        raise ValueError("Job Description không được vượt quá 20000 ký tự.")
    return value

class JobApplicationCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    
    cv_document_id: UUID
    target_role: str
    job_description: Optional[str] = None
    
    @field_validator('target_role')
    @classmethod
    def validate_target_role(cls, v: str) -> str:
        if v != "Backend Developer Intern":
            raise ValueError("Hiện tại chỉ hỗ trợ vị trí 'Backend Developer Intern'.")
        return v
        
    @field_validator('job_description', mode='before')
    @classmethod
    def validate_jd(cls, v: Optional[str]) -> Optional[str]:
        return normalize_jd(v)

class JobApplicationPatch(BaseModel):
    model_config = ConfigDict(extra='forbid')
    
    job_description: Optional[str] = None
    
    @field_validator('job_description', mode='before')
    @classmethod
    def validate_jd(cls, v: Optional[str]) -> Optional[str]:
        return normalize_jd(v)

class CVInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    original_filename: str
    status: CVStatus

class JobApplicationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    cv_document_id: UUID
    target_role: str
    job_description: Optional[str]
    interview_language: str
    created_at: datetime
    updated_at: datetime
    cv_document: Optional[CVInfo] = None
