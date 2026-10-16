from typing import Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.models.job_application import JobApplication

class JobApplicationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, job_app: JobApplication) -> JobApplication:
        self.session.add(job_app)
        await self.session.flush()
        return job_app
        
    async def get(self, id: UUID) -> Optional[JobApplication]:
        stmt = select(JobApplication).options(selectinload(JobApplication.cv_document)).where(JobApplication.id == id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_recent(self, limit: int = 20) -> list[JobApplication]:
        stmt = (
            select(JobApplication)
            .options(selectinload(JobApplication.cv_document))
            .order_by(JobApplication.created_at.desc(), JobApplication.id.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_by_cv_document_id(self, cv_document_id: UUID) -> int:
        result = await self.session.execute(
            select(func.count()).select_from(JobApplication).where(JobApplication.cv_document_id == cv_document_id)
        )
        return int(result.scalar_one())

