from fastapi import APIRouter, Depends, UploadFile, File, status
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from app.db.session import get_db
from app.schemas.cv_document import CVDocumentResponse, CVDocumentTextUpdateRequest
from app.services.cv_document import CVDocumentService

router = APIRouter()

@router.post("", response_model=CVDocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_cv(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    service = CVDocumentService(db)
    return await service.upload_document(file)

@router.get("/{doc_id}", response_model=CVDocumentResponse)
async def get_cv_metadata(
    doc_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    service = CVDocumentService(db)
    return await service.get_document(doc_id)

@router.post("/{doc_id}/extract", response_model=CVDocumentResponse)
async def extract_cv_text(
    doc_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    service = CVDocumentService(db)
    return await service.extract_document(doc_id)

@router.patch("/{doc_id}/extracted-text", response_model=CVDocumentResponse)
async def update_cv_extracted_text(
    doc_id: uuid.UUID,
    request: CVDocumentTextUpdateRequest,
    db: AsyncSession = Depends(get_db)
):
    service = CVDocumentService(db)
    return await service.update_extracted_text(doc_id, request.extracted_text)

