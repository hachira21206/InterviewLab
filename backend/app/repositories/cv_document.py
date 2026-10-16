from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import uuid
from typing import Optional

from app.models.cv_document import CVDocument
from app.schemas.cv_document import CVDocumentCreate

class CVDocumentRepository:
    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def get_by_id(self, doc_id: uuid.UUID) -> Optional[CVDocument]:
        result = await self.db.execute(select(CVDocument).where(CVDocument.id == doc_id))
        return result.scalars().first()

    async def create(self, cv_in: CVDocumentCreate) -> CVDocument:
        cv_obj = CVDocument(
            original_filename=cv_in.original_filename,
            storage_key=cv_in.storage_key,
            media_type=cv_in.media_type,
            size_bytes=cv_in.size_bytes,
            sha256=cv_in.sha256,
            status=cv_in.status
        )
        self.db.add(cv_obj)
        # Flush to get the ID, commit happens in service layer to ensure consistency
        await self.db.flush()
        return cv_obj
