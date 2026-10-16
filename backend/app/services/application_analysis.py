import uuid
import logging
from typing import Optional
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from app.models.application_analysis import ApplicationAnalysis, AnalysisStatus
from app.models.job_application import JobApplication
from app.models.cv_document import CVStatus
from app.schemas.application_analysis import AnalysisCreateRequest, CandidateAnalysis
from app.services.analysis_provider import get_analysis_provider, AnalysisInput, AnalysisResult
from app.prompts.candidate_analysis import build_user_prompt, SYSTEM_PROMPT, VERSION
from app.core.config import settings

logger = logging.getLogger(__name__)

class ApplicationAnalysisService:
    @staticmethod
    async def get_by_application_id(session: AsyncSession, application_id: uuid.UUID) -> Optional[ApplicationAnalysis]:
        result = await session.execute(
            select(ApplicationAnalysis).where(ApplicationAnalysis.job_application_id == application_id)
        )
        return result.scalars().first()
        
    @staticmethod
    async def create_or_retry_analysis(session: AsyncSession, application_id: uuid.UUID, req: AnalysisCreateRequest) -> ApplicationAnalysis:
        if not req.consent_to_external_ai:
            raise ValueError("Người dùng chưa đồng ý chia sẻ dữ liệu với AI bên ngoài.")
            
        provider = get_analysis_provider()
            
        from sqlalchemy.orm import joinedload
        result = await session.execute(
            select(JobApplication)
            .options(joinedload(JobApplication.cv_document))
            .where(JobApplication.id == application_id)
        )
        app_record = result.scalars().first()
        
        if not app_record:
            raise KeyError("Không tìm thấy hồ sơ ứng tuyển.")
            
        cv_doc = app_record.cv_document
        if not cv_doc or cv_doc.status != CVStatus.extracted:
            raise ValueError("CV chưa được trích xuất thành công.")
            
        cv_text = cv_doc.extracted_text or ""
        jd_text = app_record.job_description or ""
        
        if len(cv_text) > settings.AI_MAX_CV_CHARS:
            raise ValueError(f"Nội dung CV quá dài ({len(cv_text)} ký tự). Vui lòng dùng CV ngắn hơn.")
        if len(jd_text) > settings.AI_MAX_JD_CHARS:
            raise ValueError(f"Nội dung JD quá dài ({len(jd_text)} ký tự). Vui lòng dùng JD ngắn hơn.")
        if len(cv_text) + len(jd_text) > settings.AI_MAX_TOTAL_CHARS:
            raise ValueError("Tổng nội dung CV và JD quá dài. Vui lòng rút gọn.")
            
        analysis = await ApplicationAnalysisService.get_by_application_id(session, application_id)
        
        if analysis:
            if analysis.status == AnalysisStatus.completed:
                return analysis
            if analysis.status == AnalysisStatus.analyzing:
                raise ValueError("Hồ sơ đang được phân tích.")
            
            stmt = (
                update(ApplicationAnalysis)
                .where(
                    ApplicationAnalysis.job_application_id == application_id,
                    ApplicationAnalysis.status.in_([AnalysisStatus.pending, AnalysisStatus.failed])
                )
                .values(
                    status=AnalysisStatus.analyzing,
                    provider=settings.AI_PROVIDER,
                    model=settings.get_active_model(),
                    schema_version="v1",
                    prompt_version=VERSION,
                    error_code=None,
                    error_message=None,
                    requested_at=datetime.now(timezone.utc)
                )
                .returning(ApplicationAnalysis)
            )
            try:
                upd_result = await session.execute(stmt)
                updated_analysis = upd_result.scalars().first()
                if not updated_analysis:
                    await session.rollback()
                    check = await ApplicationAnalysisService.get_by_application_id(session, application_id)
                    if check and check.status == AnalysisStatus.completed:
                        return check
                    raise ValueError("Hồ sơ đang được phân tích.")
                analysis = updated_analysis
                await session.commit()
                await session.refresh(analysis)
            except Exception:
                await session.rollback()
                raise
        else:
            analysis = ApplicationAnalysis(
                job_application_id=application_id,
                status=AnalysisStatus.analyzing,
                provider=settings.AI_PROVIDER,
                model=settings.get_active_model(),
                schema_version="v1",
                prompt_version=VERSION,
                requested_at=datetime.now(timezone.utc)
            )
            session.add(analysis)
            try:
                await session.commit()
                await session.refresh(analysis)
            except IntegrityError:
                await session.rollback()
                check = await ApplicationAnalysisService.get_by_application_id(session, application_id)
                if check and check.status == AnalysisStatus.completed:
                    return check
                raise ValueError("Hồ sơ đang được phân tích.")
            except Exception:
                await session.rollback()
                raise
        
        user_prompt = build_user_prompt(cv_text, jd_text)
        schema_dict = CandidateAnalysis.model_json_schema()
        
        analysis_input = AnalysisInput(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
            schema=schema_dict
        )
        
        try:
            res = await provider.analyze_application(analysis_input)
        except Exception:
            logger.error("Unexpected error calling provider", exc_info=True)
            res = AnalysisResult(None, "INTERNAL_ANALYSIS_ERROR", "Lỗi không xác định khi gọi AI.")
        
        analysis_id = analysis.id
        analysis_to_update = await session.get(ApplicationAnalysis, analysis_id)
        if not analysis_to_update:
            raise RuntimeError("Hồ sơ phân tích không còn tồn tại trên hệ thống.")
            
        if res.error_code:
            analysis_to_update.status = AnalysisStatus.failed
            analysis_to_update.error_code = res.error_code
            analysis_to_update.error_message = res.error_message
        else:
            analysis_to_update.status = AnalysisStatus.completed
            analysis_to_update.analysis_data = res.data.model_dump()
            analysis_to_update.completed_at = datetime.now(timezone.utc)
            
        analysis_to_update.input_chars = len(user_prompt)
        analysis_to_update.input_tokens = res.input_tokens
        analysis_to_update.output_tokens = res.output_tokens
        
        try:
            await session.commit()
            await session.refresh(analysis_to_update)
            return analysis_to_update
        except Exception:
            await session.rollback()
            try:
                rec_analysis = await session.get(ApplicationAnalysis, analysis_id)
                if rec_analysis:
                    rec_analysis.status = AnalysisStatus.failed
                    rec_analysis.error_code = "INTERNAL_ANALYSIS_ERROR"
                    rec_analysis.error_message = "Lỗi khi lưu kết quả phân tích."
                    await session.commit()
            except Exception:
                await session.rollback()
                logger.error("Recovery transaction failed", exc_info=True)
                raise
            raise RuntimeError("Lỗi khi lưu kết quả phân tích.")
