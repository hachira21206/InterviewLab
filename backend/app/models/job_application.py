import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.session import Base

class JobApplication(Base):
    __tablename__ = "job_applications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    cv_document_id = Column(UUID(as_uuid=True), ForeignKey("cv_documents.id", ondelete="CASCADE"), nullable=False)
    target_role = Column(String(100), nullable=False)
    job_description = Column(Text, nullable=True)
    interview_language = Column(String(10), nullable=False, default="vi", server_default="vi")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=func.now(), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    cv_document = relationship("CVDocument", backref="job_applications")
    analysis = relationship("ApplicationAnalysis", back_populates="job_application", uselist=False, cascade="all, delete-orphan")
