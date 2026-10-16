import logging
from uuid import UUID
from typing import Optional
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.job_application import JobApplication
from app.models.cv_document import CVStatus
from app.repositories.job_application import JobApplicationRepository
from app.repositories.cv_document import CVDocumentRepository
from app.schemas.job_application import JobApplicationCreate, JobApplicationPatch
from app.services.storage import StorageService

logger = logging.getLogger(__name__)

class JobApplicationService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = JobApplicationRepository(session)
        self.cv_repo = CVDocumentRepository(session)

    async def create_application(self, data: JobApplicationCreate) -> JobApplication:
        # Check CV existence
        cv = await self.cv_repo.get_by_id(data.cv_document_id)
        if not cv:
            raise HTTPException(status_code=404, detail="CV không tồn tại.")
            
        if cv.status != CVStatus.extracted:
            raise HTTPException(
                status_code=409, 
                detail="CV chưa được trích xuất hoàn tất. Không thể tạo hồ sơ ứng tuyển."
            )
            
        job_app = JobApplication(
            cv_document_id=data.cv_document_id,
            target_role=data.target_role,
            job_description=data.job_description,
            interview_language="vi"
        )
        
        try:
            created = await self.repo.create(job_app)
            await self.session.commit()
            await self.session.refresh(created)
            created.cv_document = cv
            return created
        except Exception:
            await self.session.rollback()
            logger.exception("Lỗi hệ thống khi lưu hồ sơ ứng tuyển")
            raise HTTPException(status_code=500, detail="Lỗi hệ thống khi tạo hồ sơ ứng tuyển.")

    async def get_application(self, id: UUID) -> JobApplication:
        job_app = await self.repo.get(id)
        if not job_app:
            raise HTTPException(status_code=404, detail="Hồ sơ ứng tuyển không tồn tại.")
        return job_app

    async def list_applications(self, limit: int = 20) -> list[JobApplication]:
        return await self.repo.list_recent(limit=limit)

    async def update_application(self, id: UUID, data: JobApplicationPatch) -> JobApplication:
        job_app = await self.repo.get(id)
        if not job_app:
            raise HTTPException(status_code=404, detail="Hồ sơ ứng tuyển không tồn tại.")
            
        # exclude_unset=True makes sure we only update what was actually sent
        update_data = data.model_dump(exclude_unset=True)
        if "job_description" in update_data:
            job_app.job_description = update_data["job_description"]
            
        try:
            await self.session.flush()
            await self.session.commit()
            await self.session.refresh(job_app)
            return job_app
        except Exception:
            await self.session.rollback()
            logger.exception("Lỗi hệ thống khi cập nhật hồ sơ ứng tuyển")
            raise HTTPException(status_code=500, detail="Lỗi hệ thống khi cập nhật hồ sơ ứng tuyển.")

    async def delete_application(self, id: UUID) -> None:
        """Delete one application and its dependent data without deleting a shared CV.

        A CV file is quarantined before the database commit and restored if the
        transaction fails. This keeps database/storage state recoverable.
        """
        job_app = await self.repo.get(id)
        if not job_app:
            raise HTTPException(status_code=404, detail="Hồ sơ ứng tuyển không tồn tại.")

        cv = job_app.cv_document
        cv_id = cv.id
        cv_storage_key = cv.storage_key
        quarantined_file = None
        storage = StorageService()
        try:
            await self.session.delete(job_app)
            await self.session.flush()

            # CVs can technically be shared by several applications. Preserve
            # it until this was the final reference.
            if await self.repo.count_by_cv_document_id(cv_id) == 0:
                quarantined_file = await storage.quarantine_file_by_key(cv_storage_key)
                await self.session.delete(cv)
                await self.session.flush()

            await self.session.commit()
        except HTTPException:
            await self.session.rollback()
            raise
        except Exception:
            await self.session.rollback()
            if quarantined_file is not None:
                try:
                    await storage.restore_quarantined_file(quarantined_file, cv_storage_key)
                except Exception:
                    logger.exception("Không thể phục hồi file CV sau khi hủy thao tác xóa")
            logger.exception("Lỗi hệ thống khi xóa hồ sơ ứng tuyển")
            raise HTTPException(status_code=500, detail="Không thể xóa hồ sơ ứng tuyển. Vui lòng thử lại.")

        if quarantined_file is not None:
            try:
                await storage.delete_quarantined_file(quarantined_file)
            except Exception:
                # The database removal is already committed. Keep the error
                # server-side for cleanup tooling; never expose storage paths.
                logger.exception("Không thể hoàn tất dọn dẹp file CV đã xóa")
