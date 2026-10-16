from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Literal
from uuid import UUID
from datetime import datetime

class TechnicalSkill(BaseModel):
    name: str
    level: Literal["mentioned", "demonstrated", "unclear"]
    evidence: str = Field(..., max_length=300)
    model_config = ConfigDict(extra="forbid")

class ProjectInfo(BaseModel):
    name: str
    description: str
    technologies: List[str]
    evidence: str = Field(..., max_length=300)
    model_config = ConfigDict(extra="forbid")

class EducationInfo(BaseModel):
    institution: str
    major: str
    status: str
    model_config = ConfigDict(extra="forbid")

class SectionEvidence(BaseModel):
    title: str
    evidence: str = Field(..., max_length=300)
    model_config = ConfigDict(extra="forbid")

class GapInfo(BaseModel):
    title: str
    reason: str = Field(..., max_length=300)
    model_config = ConfigDict(extra="forbid")

class RequirementMatch(BaseModel):
    requirement: str
    evidence: str = Field(..., max_length=300)
    model_config = ConfigDict(extra="forbid")

class InterviewTopic(BaseModel):
    topic: str
    reason: str = Field(..., max_length=300)
    priority: Literal["high", "medium", "low"]
    model_config = ConfigDict(extra="forbid")

class CandidateAnalysis(BaseModel):
    summary_vi: str = Field(..., max_length=1500)
    candidate_level: Literal["beginner", "junior_ready", "unclear"]
    technical_skills: List[TechnicalSkill] = Field(..., max_length=20)
    projects: List[ProjectInfo] = Field(..., max_length=10)
    education: List[EducationInfo]
    strengths: List[SectionEvidence] = Field(..., max_length=8)
    gaps: List[GapInfo] = Field(..., max_length=8)
    matched_requirements: List[RequirementMatch] = Field(..., max_length=15)
    missing_requirements: List[str] = Field(..., max_length=15)
    recommended_interview_topics: List[InterviewTopic] = Field(..., max_length=12)
    language_detected: Literal["vi", "en", "mixed", "unknown"]
    warnings: List[str]

    model_config = ConfigDict(extra="forbid")

class AnalysisCreateRequest(BaseModel):
    consent_to_external_ai: bool

    model_config = ConfigDict(extra="forbid")

class ApplicationAnalysisResponse(BaseModel):
    id: UUID
    job_application_id: UUID
    status: str
    provider: str
    model: str
    analysis_data: Optional[CandidateAnalysis]
    error_code: Optional[str]
    error_message: Optional[str]
    requested_at: datetime
    completed_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)
