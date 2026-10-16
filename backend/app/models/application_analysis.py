import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.session import Base
import enum

class AnalysisStatus(str, enum.Enum):
    pending = "pending"
    analyzing = "analyzing"
    completed = "completed"
    failed = "failed"

class ApplicationAnalysis(Base):
    __tablename__ = "application_analyses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    job_application_id = Column(UUID(as_uuid=True), ForeignKey("job_applications.id", ondelete="CASCADE"), nullable=False, unique=True)
    status = Column(String(30), nullable=False)
    provider = Column(String(50), nullable=False)
    model = Column(String(100), nullable=False)
    schema_version = Column(String(50), nullable=False)
    prompt_version = Column(String(50), nullable=False)
    
    analysis_data = Column(JSONB, nullable=True)
    
    error_code = Column(String(100), nullable=True)
    error_message = Column(Text, nullable=True)
    provider_request_id = Column(String(255), nullable=True)
    
    input_chars = Column(Integer, nullable=True)
    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)
    
    requested_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=func.now(), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=func.now(), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    job_application = relationship("JobApplication", back_populates="analysis")
