import logging
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import UploadFile, HTTPException

from app.schemas.cv_document import CVDocumentCreate, CVDocumentResponse
from app.repositories.cv_document import CVDocumentRepository
from app.services.storage import StorageService
from app.services.validation import FileValidator, FileValidationError
from app.models.cv_document import CVStatus
import uuid

logger = logging.getLogger(__name__)

class CVDocumentService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = CVDocumentRepository(db)
        self.storage = StorageService()

    async def get_document(self, doc_id: uuid.UUID) -> CVDocumentResponse:
        doc = await self.repo.get_by_id(doc_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        return CVDocumentResponse.model_validate(doc)

    async def update_extracted_text(self, doc_id: uuid.UUID, extracted_text: str) -> CVDocumentResponse:
        doc = await self.repo.get_by_id(doc_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Không tìm thấy tài liệu CV.")
        if doc.status != CVStatus.extracted:
            raise HTTPException(
                status_code=409,
                detail="Chỉ có thể chỉnh sửa nội dung sau khi CV đã được trích xuất.",
            )
        doc.extracted_text = extracted_text
        try:
            await self.db.commit()
            await self.db.refresh(doc)
        except Exception:
            await self.db.rollback()
            logger.exception("Failed to update extracted_text")
            raise HTTPException(status_code=500, detail="Lỗi hệ thống khi lưu nội dung CV.")
        return CVDocumentResponse.model_validate(doc)

    async def extract_document(self, doc_id: uuid.UUID) -> CVDocumentResponse:
        from sqlalchemy import update
        from app.models.cv_document import CVDocument
        
        doc = await self.repo.get_by_id(doc_id)
        if not doc:
            raise HTTPException(status_code=404, detail="CV Document not found")
        
        if doc.status == CVStatus.extracted:
            # Idempotent: return current state without re-extracting
            return CVDocumentResponse.model_validate(doc)
            
        if doc.status == CVStatus.extracting:
            raise HTTPException(status_code=409, detail="Document is currently being extracted")
            
        # Update to extracting atomically
        result = await self.db.execute(
            update(CVDocument)
            .where(CVDocument.id == doc_id, CVDocument.status.in_([CVStatus.uploaded, CVStatus.extraction_failed]))
            .values(status=CVStatus.extracting)
        )
        
        if result.rowcount == 0:
            # Another transaction might have changed it
            await self.db.refresh(doc)
            if doc.status == CVStatus.extracting:
                raise HTTPException(status_code=409, detail="Document is currently being extracted")
            elif doc.status == CVStatus.extracted:
                return CVDocumentResponse.model_validate(doc)
            else:
                raise HTTPException(status_code=400, detail="Cannot extract document in its current state")
                
        try:
            await self.db.commit()
            await self.db.refresh(doc)
        except Exception as e:
            await self.db.rollback()
            logger.exception("Failed to commit extracting status")
            raise HTTPException(status_code=500, detail="Lỗi lưu trạng thái CSDL.")
        
        from app.services.extractor import CVTextExtractor, ExtractionError
        from datetime import datetime, timezone
        
        try:
            file_path = self.storage.get_file_path_by_key(doc.storage_key)
            text = await CVTextExtractor.extract_text(file_path, doc.media_type)
            
            doc.status = CVStatus.extracted
            doc.extracted_text = text
            doc.extraction_error = None
            doc.extracted_at = datetime.now(timezone.utc)
            
        except (ValueError, FileNotFoundError) as e:
            doc.status = CVStatus.extraction_failed
            doc.extracted_text = None
            doc.extraction_error = "Lỗi hệ thống lưu trữ."
        except ExtractionError as e:
            doc.status = CVStatus.extraction_failed
            doc.extracted_text = None
            doc.extraction_error = str(e)
        except Exception as e:
            doc.status = CVStatus.extraction_failed
            doc.extracted_text = None
            doc.extraction_error = "Lỗi trích xuất không xác định."
            
        # Final commit
        try:
            await self.db.commit()
            await self.db.refresh(doc)
        except Exception as db_e:
            await self.db.rollback()
            logger.exception("Final extraction commit failed, attempting recovery")
            
            # Recovery
            doc.status = CVStatus.extraction_failed
            doc.extracted_text = None
            doc.extraction_error = "Lỗi lưu kết quả, vui lòng thử lại."
            try:
                self.db.add(doc)
                await self.db.commit()
                await self.db.refresh(doc)
            except Exception as recovery_e:
                logger.exception("Recovery commit also failed")
                await self.db.rollback()
                raise HTTPException(status_code=500, detail="Lỗi hệ thống nghiêm trọng khi lưu trạng thái.")
                
            raise HTTPException(status_code=500, detail="Lỗi lưu kết quả trích xuất vào CSDL.")
            
        return CVDocumentResponse.model_validate(doc)

    async def upload_document(self, file: UploadFile) -> CVDocumentResponse:
        if not file.filename:
            raise HTTPException(status_code=400, detail="No filename provided")

        # 1. Validate extension and length
        try:
            ext = FileValidator.validate_filename(file.filename)
        except FileValidationError as e:
            raise HTTPException(status_code=400, detail=str(e))
            
        # Validate MIME mismatch
        try:
            FileValidator.validate_mime_type(ext, file.content_type)
        except FileValidationError as e:
            raise HTTPException(status_code=415, detail=str(e))

        temp_path = None
        storage_key = None
        try:
            # 2. Stream to temp file and calculate size/hash
            temp_path, sha256_hash, size_bytes = await self.storage.save_temp_file(file)

            if size_bytes == 0:
                raise HTTPException(status_code=400, detail="File is empty")

            # 3. Validate content magic bytes / zip structure
            try:
                media_type = FileValidator.validate_file_content(temp_path, ext)
            except FileValidationError as e:
                raise HTTPException(status_code=415, detail=str(e))

            # 4. Finalize storage file
            storage_key = await self.storage.finalize_file(temp_path, ext)
            temp_path = None # Moved successfully

            # 5. Create database record
            cv_in = CVDocumentCreate(
                original_filename=file.filename,
                storage_key=storage_key,
                media_type=media_type,
                size_bytes=size_bytes,
                sha256=sha256_hash,
                status=CVStatus.uploaded
            )
            
            doc = await self.repo.create(cv_in)
            
            # Construct response BEFORE commit so no serialization/refresh errors happen post-commit
            response = CVDocumentResponse.model_validate(doc)
            
            # 6. Commit transaction safely
            try:
                await self.db.commit()
            except Exception as e:
                await self.db.rollback()
                await self.storage.delete_file_by_key(storage_key)
                storage_key = None # Prevent double-deletion in outer except
                logger.error(f"DB Commit failed, file rolled back: {e}")
                raise HTTPException(status_code=500, detail="Database error during upload")

            return response

        except HTTPException:
            # Re-raise HTTP exceptions immediately
            if temp_path:
                await self.storage.delete_temp_file(temp_path)
            if storage_key:
                # If we get HTTP exception after finalize but before commit finishes successfully
                await self.storage.delete_file_by_key(storage_key)
            raise

        except ValueError as e:
            # Thrown by save_temp_file for size limit
            if temp_path:
                await self.storage.delete_temp_file(temp_path)
            raise HTTPException(status_code=413, detail=str(e))

        except Exception as e:
            logger.error(f"Error uploading document: {e}")
            await self.db.rollback()
            if temp_path:
                await self.storage.delete_temp_file(temp_path)
            if storage_key:
                await self.storage.delete_file_by_key(storage_key)
            raise HTTPException(status_code=500, detail="Internal server error")
