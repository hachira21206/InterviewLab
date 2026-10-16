import uuid
import enum
from sqlalchemy import Column, String, Integer, DateTime, Enum, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.db.session import Base

class CVStatus(str, enum.Enum):
    uploaded = "uploaded"
    extracting = "extracting"
    extracted = "extracted"
    extraction_failed = "extraction_failed"

class CVDocument(Base):
    __tablename__ = "cv_documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    original_filename = Column(String(255), nullable=False)
    storage_key = Column(String(255), nullable=False, unique=True)
    media_type = Column(String(100), nullable=False)
    size_bytes = Column(Integer, nullable=False)
    sha256 = Column(String(64), nullable=False)
    status = Column(Enum(CVStatus), nullable=False, default=CVStatus.uploaded)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    extracted_text = Column(Text, nullable=True)
    extraction_error = Column(Text, nullable=True)
    extracted_at = Column(DateTime(timezone=True), nullable=True)
