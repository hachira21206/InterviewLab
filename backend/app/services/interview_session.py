import uuid
import logging
import re
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from app.models.job_application import JobApplication
from app.models.application_analysis import ApplicationAnalysis, AnalysisStatus
from app.models.interview_session import InterviewSession, SessionStatus
from app.models.interview_question import InterviewQuestion, QuestionCategory, QuestionDifficulty
from app.services.analysis_provider import get_analysis_provider, AnalysisInput
from app.prompts.interview_questions import INTERVIEW_SYSTEM_PROMPT, build_interview_user_prompt, INTERVIEW_PROMPT_VERSION, INTERVIEW_SCHEMA_VERSION
from app.schemas.interview_questions import InterviewQuestionSet
from app.schemas.application_analysis import CandidateAnalysis
from app.core.config import settings
from app.core.exceptions import ProviderConfigurationError
from collections import Counter
from pydantic import ValidationError

logger = logging.getLogger(__name__)


class InterviewSessionService:
    @classmethod
    async def create_or_retry_session(cls, db: AsyncSession, application_id: uuid.UUID, consent: bool) -> InterviewSession:
        return await cls._create_or_retry_attempt_internal(db, application_id, consent, is_new_attempt_endpoint=False)

    @classmethod
    async def create_attempt(cls, db: AsyncSession, application_id: uuid.UUID, consent: bool) -> InterviewSession:
        return await cls._create_or_retry_attempt_internal(db, application_id, consent, is_new_attempt_endpoint=True)

    @classmethod
    async def _create_or_retry_attempt_internal(
        cls,
        db: AsyncSession,
        application_id: uuid.UUID,
        consent: bool,
        is_new_attempt_endpoint: bool
    ) -> InterviewSession:
        if not consent:
            raise HTTPException(status_code=422, detail="Vui lòng xác nhận sự đồng ý.")
            
        # Short transaction with FOR UPDATE lock on JobApplication to serialize concurrent requests
        app_record = (await db.execute(
            select(JobApplication).where(JobApplication.id == application_id).with_for_update()
        )).scalars().first()
        if not app_record:
            raise HTTPException(status_code=404, detail="Không tìm thấy hồ sơ ứng tuyển.")
            
        analysis = (await db.execute(
            select(ApplicationAnalysis).where(ApplicationAnalysis.job_application_id == application_id)
        )).scalars().first()
        if not analysis or analysis.status != AnalysisStatus.completed:
            raise HTTPException(status_code=409, detail="CV chưa được phân tích thành công.")
            
        try:
            analysis_data = CandidateAnalysis(**analysis.analysis_data)
        except ValidationError:
            raise HTTPException(status_code=409, detail="Dữ liệu phân tích ứng viên không hợp lệ.")
            
        jd_text = app_record.job_description or ""
        
        user_prompt = build_interview_user_prompt(
            target_role=app_record.target_role,
            cv_summary=analysis_data.summary_vi,
            technical_skills=[s.model_dump(mode='json') for s in analysis_data.technical_skills],
            projects=[p.model_dump(mode='json') for p in analysis_data.projects],
            jd=jd_text
        )
        total_input_chars = len(INTERVIEW_SYSTEM_PROMPT) + len(user_prompt)
        max_chars = getattr(settings, 'AI_MAX_INTERVIEW_INPUT_CHARS', 20000)
        if total_input_chars > max_chars:
            raise HTTPException(status_code=409, detail=f"Tổng dung lượng đầu vào quá lớn. Tối đa {max_chars} ký tự.")

        # Check existing active sessions
        active_session = (await db.execute(
            select(InterviewSession)
            .options(selectinload(InterviewSession.questions))
            .where(
                InterviewSession.job_application_id == application_id,
                InterviewSession.status.in_([
                    SessionStatus.generating,
                    SessionStatus.generation_failed,
                    SessionStatus.ready,
                    SessionStatus.in_progress
                ])
            )
            .order_by(InterviewSession.attempt_number.desc())
        )).scalars().first()
        
        if active_session:
            if active_session.status == SessionStatus.ready:
                if not is_new_attempt_endpoint and len(active_session.questions) == 10:
                    await db.refresh(active_session, ['questions'])
                    return active_session
                raise HTTPException(status_code=409, detail="Đang có phiên phỏng vấn chưa hoàn thành.")
                    
            if active_session.status in (SessionStatus.generating, SessionStatus.in_progress):
                raise HTTPException(status_code=409, detail="Đang có phiên phỏng vấn chưa hoàn thành.")
                
            if active_session.status == SessionStatus.generation_failed:
                if is_new_attempt_endpoint:
                    raise HTTPException(status_code=409, detail="Đang có phiên phỏng vấn chưa hoàn thành.")

                # Retry on the same attempt: obtain provider before altering state
                try:
                    provider = get_analysis_provider()
                except ProviderConfigurationError as e:
                    raise HTTPException(status_code=503, detail=str(e))

                active_session.status = SessionStatus.generating
                active_session.error_code = None
                active_session.error_message = None
                await db.commit()
                session_to_process = active_session
        else:
            # No active session: obtain provider before creating row
            try:
                provider = get_analysis_provider()
            except ProviderConfigurationError as e:
                raise HTTPException(status_code=503, detail=str(e))

            # Determine next attempt_number
            latest_session = (await db.execute(
                select(InterviewSession)
                .where(InterviewSession.job_application_id == application_id)
                .order_by(InterviewSession.attempt_number.desc())
            )).scalars().first()

            next_attempt = (latest_session.attempt_number + 1) if latest_session else 1

            session_to_process = InterviewSession(
                job_application_id=application_id,
                attempt_number=next_attempt,
                status=SessionStatus.generating,
                provider=settings.AI_PROVIDER,
                model=settings.get_active_model(),
                prompt_version=INTERVIEW_PROMPT_VERSION,
                schema_version=INTERVIEW_SCHEMA_VERSION
            )
            db.add(session_to_process)
            try:
                await db.commit()
            except IntegrityError:
                await db.rollback()
                raise HTTPException(status_code=409, detail="Đang có phiên phỏng vấn chưa hoàn thành.")
        
        # Row lock is released after commit! Provider call is performed outside DB transactions.
        session_id = session_to_process.id
        
        input_data = AnalysisInput(INTERVIEW_SYSTEM_PROMPT, user_prompt, InterviewQuestionSet.model_json_schema())
        
        try:
            result = await provider.generate_interview_questions(input_data)
        except Exception:
            logger.exception("Unexpected error calling provider")
            result = None
            
        try:
            if not result or result.error_code:
                raise ValueError(result.error_code if result else "INTERNAL_ANALYSIS_ERROR", result.error_message if result else "Lỗi hệ thống bất ngờ.")
                
            if not result.data:
                raise ValueError("INVALID_PROVIDER_RESPONSE", "Phản hồi rỗng từ AI.")
                
            questions = result.data.questions
            if not questions or len(questions) != 10:
                raise ValueError("INVALID_PROVIDER_RESPONSE", "Không đủ số lượng câu hỏi.")

            categories = Counter([q.category.value for q in questions])
            difficulties = Counter([q.difficulty.value for q in questions])
            
            if (categories.get("backend_fundamentals", 0) != 2 or
                categories.get("cv_project_experience", 0) != 2 or
                categories.get("database", 0) != 2 or
                categories.get("api_web_design", 0) != 2 or
                categories.get("debugging_problem_solving", 0) != 1 or
                categories.get("behavioral_teamwork", 0) != 1):
                raise ValueError("INVALID_PROVIDER_RESPONSE", "Sai phân bổ category.")
                
            if (difficulties.get("easy", 0) != 4 or
                difficulties.get("medium", 0) != 4 or
                difficulties.get("hard", 0) != 2):
                raise ValueError("INVALID_PROVIDER_RESPONSE", "Sai phân bổ difficulty.")
                
            def normalize_text(text: str) -> str:
                t = text.casefold().strip()
                t = re.sub(r'[\?\.\!\,:;\"\']', '', t)
                t = re.sub(r'\s+', ' ', t)
                return t
                
            unique_texts = set(normalize_text(q.question_text) for q in questions)
            if len(unique_texts) < 10:
                raise ValueError("INVALID_PROVIDER_RESPONSE", "Có câu hỏi trùng lặp.")
                
            for q in questions:
                if q.source.value != "general_backend" and not q.source_evidence:
                    raise ValueError("INVALID_PROVIDER_RESPONSE", "Thiếu evidence cho source.")
                    
            db_questions = []
            for i, q in enumerate(questions, start=1):
                db_questions.append(InterviewQuestion(
                    interview_session_id=session_id,
                    order_index=i,
                    question_text=q.question_text,
                    category=q.category.value,
                    difficulty=q.difficulty.value,
                    purpose=q.purpose,
                    expected_key_points=q.expected_key_points,
                    source=q.source.value,
                    source_evidence=q.source_evidence
                ))
            
            # Final Transaction
            await db.execute(delete(InterviewQuestion).where(InterviewQuestion.interview_session_id == session_id))
            db.add_all(db_questions)
            
            from sqlalchemy import func
            stmt = (
                update(InterviewSession)
                .where(InterviewSession.id == session_id)
                .values(
                    status=SessionStatus.ready,
                    provider=settings.AI_PROVIDER,
                    model=settings.get_active_model(),
                    generated_at=func.now(),
                    error_code=None,
                    error_message=None
                )
            )
            await db.execute(stmt)
            await db.commit()
            
        except ValueError as ve:
            await db.rollback()
            code, msg = ve.args[0], ve.args[1]
            logger.warning("Validation failed for interview questions: code=%s, msg=%s", code, msg)
            try:
                stmt = (
                    update(InterviewSession)
                    .where(InterviewSession.id == session_id)
                    .values(
                        status=SessionStatus.generation_failed,
                        error_code=code,
                        error_message=msg
                    )
                )
                await db.execute(stmt)
                await db.commit()
            except Exception:
                await db.rollback()
                logger.exception("Failed to recover interview session state (ValueError)")
                raise HTTPException(status_code=500, detail="Lỗi máy chủ nội bộ.")
        except Exception:
            await db.rollback()
            logger.exception("Unexpected error saving interview questions")
            try:
                stmt = (
                    update(InterviewSession)
                    .where(InterviewSession.id == session_id)
                    .values(
                        status=SessionStatus.generation_failed,
                        error_code="INTERNAL_ANALYSIS_ERROR",
                        error_message="Lỗi hệ thống trong quá trình lưu câu hỏi."
                    )
                )
                await db.execute(stmt)
                await db.commit()
            except Exception:
                await db.rollback()
                logger.exception("Failed to recover interview session state (Exception)")
                raise HTTPException(status_code=500, detail="Lỗi máy chủ nội bộ.")
            
        sess2 = (await db.execute(select(InterviewSession).options(selectinload(InterviewSession.questions)).where(InterviewSession.id == session_id))).scalars().first()
        await db.refresh(sess2, ['questions'])
        if sess2.status == SessionStatus.ready:
            if len(sess2.questions) != 10:
                raise HTTPException(status_code=500, detail="Bộ câu hỏi phỏng vấn không hợp lệ (không đủ 10 câu).")
        return sess2

    @staticmethod
    async def get_current_session(db: AsyncSession, application_id: uuid.UUID) -> InterviewSession:
        # 1. Prioritize active attempt
        active_session = (await db.execute(
            select(InterviewSession)
            .options(selectinload(InterviewSession.questions))
            .where(
                InterviewSession.job_application_id == application_id,
                InterviewSession.status.in_([
                    SessionStatus.generating,
                    SessionStatus.generation_failed,
                    SessionStatus.ready,
                    SessionStatus.in_progress
                ])
            )
            .order_by(InterviewSession.attempt_number.desc())
        )).scalars().first()
        if active_session:
            await db.refresh(active_session, ['questions'])
            return active_session

        # 2. Otherwise return the latest completed attempt
        latest_session = (await db.execute(
            select(InterviewSession)
            .options(selectinload(InterviewSession.questions))
            .where(InterviewSession.job_application_id == application_id)
            .order_by(InterviewSession.attempt_number.desc())
        )).scalars().first()
        if not latest_session:
            raise HTTPException(status_code=404, detail="Không tìm thấy phiên phỏng vấn.")
        await db.refresh(latest_session, ['questions'])
        return latest_session

    @staticmethod
    async def get_session_by_id(
        db: AsyncSession, application_id: uuid.UUID, session_id: uuid.UUID
    ) -> InterviewSession:
        session = (await db.execute(
            select(InterviewSession)
            .options(selectinload(InterviewSession.questions))
            .where(InterviewSession.id == session_id)
        )).scalars().first()
        if not session or session.job_application_id != application_id:
            raise HTTPException(status_code=404, detail="Không tìm thấy phiên phỏng vấn thuộc hồ sơ này.")
        await db.refresh(session, ['questions'])
        return session

    @staticmethod
    async def get_history(
        db: AsyncSession, application_id: uuid.UUID, limit: int = 20, offset: int = 0
    ):
        from app.schemas.interview_questions import InterviewHistoryItem, InterviewHistoryListResponse
        from sqlalchemy import func

        app_exists = (await db.execute(
            select(JobApplication.id).where(JobApplication.id == application_id)
        )).scalar_one_or_none()
        if not app_exists:
            raise HTTPException(status_code=404, detail="Không tìm thấy hồ sơ ứng tuyển.")

        total = (await db.execute(
            select(func.count(InterviewSession.id)).where(InterviewSession.job_application_id == application_id)
        )).scalar() or 0

        stmt = (
            select(InterviewSession)
            .options(
                selectinload(InterviewSession.questions),
                selectinload(InterviewSession.responses),
                selectinload(InterviewSession.evaluation)
            )
            .where(InterviewSession.job_application_id == application_id)
            .order_by(InterviewSession.attempt_number.desc())
            .offset(offset)
            .limit(limit)
        )
        sessions = (await db.execute(stmt)).scalars().all()

        items = []
        for s in sessions:
            answered_count = sum(1 for r in s.responses if not r.is_skipped and r.answer_text)
            skipped_count = sum(1 for r in s.responses if r.is_skipped)
            total_score = float(s.evaluation.total_score) if (s.evaluation and s.evaluation.total_score is not None) else None
            average_score = float(s.evaluation.average_score) if (s.evaluation and s.evaluation.average_score is not None) else None
            readiness_level = s.evaluation.readiness_level if s.evaluation else None
            evaluated_at = s.evaluation.evaluated_at if s.evaluation else None

            items.append(InterviewHistoryItem(
                id=s.id,
                job_application_id=s.job_application_id,
                attempt_number=s.attempt_number,
                status=s.status,
                question_count=len(s.questions),
                answered_count=answered_count,
                skipped_count=skipped_count,
                total_score=total_score,
                average_score=average_score,
                readiness_level=readiness_level,
                created_at=s.created_at,
                started_at=s.started_at,
                completed_at=s.completed_at,
                evaluated_at=evaluated_at
            ))

        return InterviewHistoryListResponse(
            items=items,
            total=total,
            limit=limit,
            offset=offset
        )

    @classmethod
    async def start_session(cls, db: AsyncSession, session_id: uuid.UUID):
        from app.schemas.interview_response import InterviewProgressResponse
        session = (await db.execute(select(InterviewSession).where(InterviewSession.id == session_id))).scalars().first()
        if not session:
            raise HTTPException(status_code=404, detail="Không tìm thấy phiên phỏng vấn.")

        if session.status == SessionStatus.in_progress:
            return await cls.get_progress(db, session_id)

        if session.status == SessionStatus.completed:
            return await cls.get_progress(db, session_id)

        if session.status in (SessionStatus.generating, SessionStatus.generation_failed):
            raise HTTPException(status_code=409, detail=f"Phiên phỏng vấn chưa sẵn sàng (trạng thái: {session.status}).")

        if session.status == SessionStatus.ready:
            questions = (await db.execute(
                select(InterviewQuestion)
                .where(InterviewQuestion.interview_session_id == session_id)
                .order_by(InterviewQuestion.order_index)
            )).scalars().all()

            if len(questions) != 10:
                raise HTTPException(status_code=409, detail="Phiên phỏng vấn không có đủ 10 câu hỏi.")

            order_indices = [q.order_index for q in questions]
            if order_indices != list(range(1, 11)):
                raise HTTPException(status_code=409, detail="Thứ tự các câu hỏi không hợp lệ.")

            from sqlalchemy import func
            stmt = (
                update(InterviewSession)
                .where(InterviewSession.id == session_id, InterviewSession.status == SessionStatus.ready)
                .values(status=SessionStatus.in_progress, started_at=func.now())
                .returning(InterviewSession)
            )
            updated = (await db.execute(stmt)).scalars().first()
            if not updated:
                await db.rollback()
                curr = (await db.execute(select(InterviewSession).where(InterviewSession.id == session_id))).scalars().first()
                if curr and curr.status in (SessionStatus.in_progress, SessionStatus.completed):
                    return await cls.get_progress(db, session_id)
                raise HTTPException(status_code=409, detail="Không thể bắt đầu phiên phỏng vấn.")

            await db.commit()
            return await cls.get_progress(db, session_id)

        raise HTTPException(status_code=409, detail=f"Trạng thái không hợp lệ: {session.status}")

    @classmethod
    async def get_progress(cls, db: AsyncSession, session_id: uuid.UUID):
        from app.schemas.interview_response import (
            InterviewProgressResponse,
            InterviewQuestionSummary,
            InterviewResponseDetail,
        )
        from app.models.interview_response import InterviewResponse

        session = (await db.execute(select(InterviewSession).where(InterviewSession.id == session_id))).scalars().first()
        if not session:
            raise HTTPException(status_code=404, detail="Không tìm thấy phiên phỏng vấn.")

        questions = (await db.execute(
            select(InterviewQuestion)
            .where(InterviewQuestion.interview_session_id == session_id)
            .order_by(InterviewQuestion.order_index)
        )).scalars().all()

        responses = (await db.execute(
            select(InterviewResponse)
            .where(InterviewResponse.interview_session_id == session_id)
        )).scalars().all()

        resp_map = {r.interview_question_id: r for r in responses}
        completed_count = len(responses)
        progress_percent = round((completed_count / 10.0) * 100.0, 1) if completed_count > 0 else 0.0

        current_question = None
        if session.status in (SessionStatus.ready, SessionStatus.in_progress):
            for q in questions:
                if q.id not in resp_map:
                    current_question = InterviewQuestionSummary(
                        id=q.id,
                        order_index=q.order_index,
                        question_text=q.question_text,
                        category=q.category,
                        difficulty=q.difficulty
                    )
                    break

        responses_detail = []
        for q in questions:
            if q.id in resp_map:
                r = resp_map[q.id]
                responses_detail.append(InterviewResponseDetail(
                    id=r.id,
                    interview_question_id=q.id,
                    order_index=q.order_index,
                    question_text=q.question_text,
                    category=q.category,
                    difficulty=q.difficulty,
                    answer_text=r.answer_text,
                    is_skipped=r.is_skipped,
                    answered_at=r.answered_at
                ))

        return InterviewProgressResponse(
            session_id=session.id,
            status=session.status,
            started_at=session.started_at,
            completed_at=session.completed_at,
            total_questions=10,
            completed_count=completed_count,
            progress_percent=progress_percent,
            current_question=current_question,
            responses=responses_detail
        )

    @classmethod
    async def submit_question_response(
        cls,
        db: AsyncSession,
        session_id: uuid.UUID,
        question_id: uuid.UUID,
        request_data
    ):
        from app.models.interview_response import InterviewResponse
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        from sqlalchemy import func

        session = (await db.execute(select(InterviewSession).where(InterviewSession.id == session_id))).scalars().first()
        if not session:
            raise HTTPException(status_code=404, detail="Không tìm thấy phiên phỏng vấn.")

        if session.status == SessionStatus.completed:
            raise HTTPException(status_code=409, detail="Buổi phỏng vấn đã hoàn thành, không thể sửa câu trả lời.")

        if session.status != SessionStatus.in_progress:
            raise HTTPException(status_code=409, detail="Phiên phỏng vấn chưa ở trạng thái đang diễn ra (in_progress).")

        question = (await db.execute(select(InterviewQuestion).where(InterviewQuestion.id == question_id))).scalars().first()
        if not question or question.interview_session_id != session_id:
            raise HTTPException(status_code=404, detail="Không tìm thấy câu hỏi thuộc phiên phỏng vấn này.")

        questions = (await db.execute(
            select(InterviewQuestion)
            .where(InterviewQuestion.interview_session_id == session_id)
            .order_by(InterviewQuestion.order_index)
        )).scalars().all()

        if len(questions) != 10:
            raise HTTPException(status_code=409, detail="Phiên phỏng vấn không hợp lệ.")

        existing_responses = (await db.execute(
            select(InterviewResponse)
            .where(InterviewResponse.interview_session_id == session_id)
        )).scalars().all()
        resp_by_q_id = {r.interview_question_id: r for r in existing_responses}

        next_unanswered_q = None
        for q in questions:
            if q.id not in resp_by_q_id:
                next_unanswered_q = q
                break

        target_question_id = question.id

        if target_question_id in resp_by_q_id:
            existing = resp_by_q_id[target_question_id]
            existing.answer_text = request_data.answer_text
            existing.is_skipped = request_data.is_skipped
            existing.answered_at = func.now()
            existing.updated_at = func.now()
        else:
            if next_unanswered_q is None or question.order_index != next_unanswered_q.order_index:
                raise HTTPException(status_code=400, detail="Vui lòng trả lời câu hỏi theo đúng thứ tự tuần tự.")

            new_resp = InterviewResponse(
                id=uuid.uuid4(),
                interview_session_id=session_id,
                interview_question_id=target_question_id,
                answer_text=request_data.answer_text,
                is_skipped=request_data.is_skipped,
                answered_at=func.now(),
            )
            db.add(new_resp)

        try:
            await db.flush()
        except IntegrityError:
            await db.rollback()
            db.expire_all()

            fresh_session = (await db.execute(
                select(InterviewSession).where(InterviewSession.id == session_id)
            )).scalars().first()
            if not fresh_session:
                raise HTTPException(status_code=404, detail="Không tìm thấy phiên phỏng vấn.")

            if fresh_session.status == SessionStatus.completed:
                raise HTTPException(status_code=409, detail="Buổi phỏng vấn đã hoàn thành, không thể sửa câu trả lời.")

            if fresh_session.status != SessionStatus.in_progress:
                raise HTTPException(status_code=409, detail=f"Phiên phỏng vấn không ở trạng thái in_progress (trạng thái: {fresh_session.status}).")

            fresh_question = (await db.execute(
                select(InterviewQuestion).where(InterviewQuestion.id == target_question_id)
            )).scalars().first()
            if not fresh_question or fresh_question.interview_session_id != session_id:
                raise HTTPException(status_code=404, detail="Không tìm thấy câu hỏi thuộc phiên phỏng vấn này.")

            existing = (await db.execute(
                select(InterviewResponse)
                .where(
                    InterviewResponse.interview_session_id == session_id,
                    InterviewResponse.interview_question_id == target_question_id
                )
            )).scalars().first()
            if not existing:
                raise HTTPException(status_code=409, detail="Xung đột dữ liệu khi ghi câu trả lời.")

            total_resp = (await db.execute(
                select(func.count(InterviewResponse.id))
                .where(InterviewResponse.interview_session_id == session_id)
            )).scalar()

            if total_resp >= 10:
                raise HTTPException(status_code=409, detail="Buổi phỏng vấn đã hoàn thành, không thể sửa câu trả lời.")

            existing.answer_text = request_data.answer_text
            existing.is_skipped = request_data.is_skipped
            existing.answered_at = func.now()
            existing.updated_at = func.now()
            await db.flush()

        resp_count = (await db.execute(
            select(func.count(InterviewResponse.id))
            .where(InterviewResponse.interview_session_id == session_id)
        )).scalar()

        if resp_count == 10:
            await db.execute(
                update(InterviewSession)
                .where(InterviewSession.id == session_id, InterviewSession.status == SessionStatus.in_progress)
                .values(status=SessionStatus.completed, completed_at=func.now())
            )

        try:
            await db.commit()
            db.expire_all()
        except Exception:
            await db.rollback()
            logger.exception("Failed to commit interview response")
            raise HTTPException(status_code=500, detail="Lỗi máy chủ nội bộ.")

        return await cls.get_progress(db, session_id)

    @classmethod
    async def get_question_hint(
        cls,
        db: AsyncSession,
        session_id: uuid.UUID,
        question_id: uuid.UUID,
    ):
        from app.schemas.interview_response import QuestionHintResponse

        session = (
            await db.execute(
                select(InterviewSession).where(InterviewSession.id == session_id)
            )
        ).scalars().first()
        if not session:
            raise HTTPException(
                status_code=404, detail="Không tìm thấy phiên phỏng vấn."
            )

        question = (
            await db.execute(
                select(InterviewQuestion).where(InterviewQuestion.id == question_id)
            )
        ).scalars().first()
        if not question or question.interview_session_id != session_id:
            raise HTTPException(
                status_code=404,
                detail="Không tìm thấy câu hỏi thuộc phiên phỏng vấn này.",
            )

        category_tips = {
            "backend_fundamentals": [
                "Mở đầu bằng định nghĩa cốt lõi, ngắn gọn và chính xác về khái niệm được hỏi.",
                "Giải thích cơ chế hoạt động bên dưới (luồng xử lý, vòng đời hoặc nguyên lý kỹ thuật).",
                "Nêu 1 ví dụ thực tế hoặc so sánh ưu/nhược điểm (trade-offs) khi áp dụng.",
            ],
            "cv_project_experience": [
                "Giới thiệu ngắn gọn bối cảnh dự án và vai trò cụ thể của bạn.",
                "Tập trung làm rõ quyết định kỹ thuật (tại sao chọn công nghệ/kiến trúc đó).",
                "Nêu kết quả đạt được hoặc bài học rút ra sau khi triển khai.",
            ],
            "database": [
                "Xác định rõ bài toán dữ liệu (truy vấn, toàn vẹn dữ liệu, indexing hay transaction).",
                "Giải thích cách hệ quản trị CSDL thực thi (ví dụ: B-Tree Index, ACID, Isolation Level).",
                "Đưa ra ví dụ câu lệnh SQL hoặc tình huống tối ưu hiệu năng cụ thể.",
            ],
            "api_web_design": [
                "Làm rõ chuẩn thiết kế API (RESTful conventions, HTTP method, status code, payload).",
                "Đề cập đến tính bảo mật, xác thực (Auth), phân trang hoặc xử lý lỗi (Error Handling).",
                "Liên hệ với trải nghiệm thực tế khi tích hợp giữa Frontend và Backend.",
            ],
            "debugging_problem_solving": [
                "Trình bày quy trình khoanh vùng lỗi có hệ thống (tái hiện lỗi -> đọc log -> kiểm tra giả thuyết).",
                "Nêu công cụ hoặc kỹ thuật hỗ trợ kiểm tra (logging, profiler, unit test, query plan).",
                "Đề xuất giải pháp khắc phục triệt để và cách phòng ngừa lỗi tái diễn.",
            ],
            "behavioral_teamwork": [
                "Áp dụng mô hình STAR: Tình huống (Situation) -> Nhiệm vụ (Task) -> Hành động (Action) -> Kết quả (Result).",
                "Nhấn mạnh cách giao tiếp, phối hợp nhóm và tinh thần chủ động học hỏi của vị trí Intern.",
                "Kết thúc bằng bài học thực tế giúp bạn cải thiện quy trình làm việc.",
            ],
        }

        cat_key = (
            question.category.value
            if hasattr(question.category, "value")
            else str(question.category)
        )
        tips = category_tips.get(
            cat_key,
            [
                "Trình bày câu trả lời theo bố cục: Khái niệm chính -> Giải thích chi tiết -> Ví dụ thực tế.",
                "Sử dụng thuật ngữ kỹ thuật chính xác và đi thẳng vào trọng tâm câu hỏi.",
            ],
        )

        return QuestionHintResponse(
            question_id=question.id,
            order_index=question.order_index,
            category=question.category,
            difficulty=question.difficulty,
            interview_goal=question.purpose or "Đánh giá tư duy kỹ thuật và mức độ hiểu bản chất vấn đề.",
            key_concepts=list(question.expected_key_points or []),
            answer_structure_tips=tips,
        )


