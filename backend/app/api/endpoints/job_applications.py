from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.schemas.job_application import JobApplicationCreate, JobApplicationPatch, JobApplicationResponse
from app.services.job_application import JobApplicationService

router = APIRouter()

@router.get("", response_model=List[JobApplicationResponse])
async def list_job_applications(
    limit: int = Query(default=20, ge=1, le=50),
    db: AsyncSession = Depends(get_db)
):
    service = JobApplicationService(db)
    return await service.list_applications(limit=limit)

@router.post("", response_model=JobApplicationResponse, status_code=status.HTTP_201_CREATED)
async def create_job_application(
    data: JobApplicationCreate,
    db: AsyncSession = Depends(get_db)
):
    service = JobApplicationService(db)
    return await service.create_application(data)

@router.get("/{id}", response_model=JobApplicationResponse)
async def get_job_application(
    id: UUID,
    db: AsyncSession = Depends(get_db)
):
    service = JobApplicationService(db)
    return await service.get_application(id)

@router.patch("/{id}", response_model=JobApplicationResponse)
async def update_job_application(
    id: UUID,
    data: JobApplicationPatch,
    db: AsyncSession = Depends(get_db)
):
    service = JobApplicationService(db)
    return await service.update_application(id, data)

@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job_application(
    id: UUID,
    db: AsyncSession = Depends(get_db)
):
    service = JobApplicationService(db)
    await service.delete_application(id)
