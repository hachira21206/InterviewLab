import uuid
import logging
from collections import Counter
from typing import Dict, List, Any
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.models.interview_session import InterviewSession, SessionStatus
from app.models.interview_question import InterviewQuestion
from app.models.interview_response import InterviewResponse
from app.models.interview_evaluation import (
    InterviewEvaluation,
    InterviewResponseEvaluation,
    EvaluationStatus,
    ReadinessLevel,
    EvaluationConfidence,
)
from app.services.analysis_provider import get_analysis_provider, AnalysisInput
from app.prompts.interview_evaluation import (
    EVALUATION_SYSTEM_PROMPT,
    build_evaluation_user_prompt,
    EVALUATION_PROMPT_VERSION,
    EVALUATION_SCHEMA_VERSION,
)
from app.schemas.interview_evaluation import (
    InterviewEvaluationAISet,
    QuestionEvaluationAI,
)
from app.core.config import settings
from app.core.exceptions import ProviderConfigurationError
from app.core.rounding import (
    round_score,
    round_average_score,
    round_delta,
    round_sum_scores,
    round_average_values,
)

logger = logging.getLogger(__name__)


def compute_readiness_level(total_score: float) -> ReadinessLevel:
    if total_score < 50.0:
        return ReadinessLevel.needs_foundation
    elif total_score < 70.0:
        return ReadinessLevel.developing
    elif total_score < 85.0:
        return ReadinessLevel.intern_ready
    else:
        return ReadinessLevel.strong_intern_candidate


SAFE_ERROR_MESSAGES = {
    "INVALID_PROVIDER_RESPONSE": "Dữ liệu kết quả đánh giá từ nhà cung cấp AI không đúng cấu trúc yêu cầu.",
    "PROVIDER_UNAVAILABLE": "Dịch vụ AI hiện không khả dụng. Vui lòng thử lại sau.",
    "PROVIDER_TIMEOUT": "Hết thời gian chờ phản hồi từ nhà cung cấp AI.",
    "RATE_LIMITED": "Hệ thống tạm thời đạt giới hạn yêu cầu. Vui lòng thử lại sau.",
    "CONFIGURATION_ERROR": "Cấu hình hệ thống AI chưa chính xác.",
    "ANALYSIS_REFUSED": "Mô hình AI từ chối đánh giá nội dung phỏng vấn.",
    "INTERNAL_ANALYSIS_ERROR": "Lỗi hệ thống trong quá trình đánh giá buổi phỏng vấn.",
}


class InterviewEvaluationService:
    @staticmethod
    async def create_or_retry_evaluation(
        db: AsyncSession, session_id: uuid.UUID, consent: bool
    ) -> InterviewEvaluation:
        if not consent:
            raise HTTPException(
                status_code=422,
                detail="Vui lòng xác nhận sự đồng ý chia sẻ dữ liệu với AI bên ngoài.",
            )

        # Check session existence and status
        session = (
            await db.execute(
                select(InterviewSession).where(InterviewSession.id == session_id)
            )
        ).scalars().first()
        if not session:
            raise HTTPException(
                status_code=404, detail="Không tìm thấy phiên phỏng vấn."
            )

        if session.status != SessionStatus.completed:
            raise HTTPException(
                status_code=409,
                detail="Buổi phỏng vấn chưa hoàn thành, không thể đánh giá.",
            )

        # Retrieve questions and responses
        questions = (
            (
                await db.execute(
                    select(InterviewQuestion)
                    .where(InterviewQuestion.interview_session_id == session_id)
                    .order_by(InterviewQuestion.order_index)
                )
            )
            .scalars()
            .all()
        )

        responses = (
            (
                await db.execute(
                    select(InterviewResponse).where(
                        InterviewResponse.interview_session_id == session_id
                    )
                )
            )
            .scalars()
            .all()
        )

        if len(questions) != 10 or len(responses) != 10:
            raise HTTPException(
                status_code=409,
                detail="Buổi phỏng vấn không có đủ 10 câu hỏi hoặc 10 câu trả lời.",
            )

        order_indices = [q.order_index for q in questions]
        if order_indices != list(range(1, 11)):
            raise HTTPException(
                status_code=409, detail="Thứ tự câu hỏi không hợp lệ (cần đủ 1 đến 10)."
            )

        resp_by_qid = {r.interview_question_id: r for r in responses}
        if any(q.id not in resp_by_qid for q in questions):
            raise HTTPException(
                status_code=409, detail="Thiếu câu trả lời cho một số câu hỏi."
            )

        # Budget verification
        total_q_chars = sum(len(q.question_text) for q in questions)
        total_ans_chars = sum(len(r.answer_text or "") for r in responses)
        total_kp_chars = sum(
            sum(len(kp) for kp in (q.expected_key_points or [])) for q in questions
        )

        if total_q_chars > getattr(settings, "AI_MAX_EVALUATION_QUESTIONS_CHARS", 5000):
            raise HTTPException(
                status_code=409,
                detail="Tổng độ dài câu hỏi vượt quá giới hạn budget cho phép.",
            )
        if total_ans_chars > getattr(settings, "AI_MAX_EVALUATION_ANSWERS_CHARS", 20000):
            raise HTTPException(
                status_code=409,
                detail="Tổng độ dài câu trả lời vượt quá giới hạn budget cho phép.",
            )
        if total_kp_chars > getattr(settings, "AI_MAX_EVALUATION_KEY_POINTS_CHARS", 6000):
            raise HTTPException(
                status_code=409,
                detail="Tổng độ dài expected key points vượt quá giới hạn budget cho phép.",
            )

        # Prepare answered items
        answered_items = []
        for q in questions:
            r = resp_by_qid[q.id]
            if not r.is_skipped:
                answered_items.append(
                    {
                        "question_order": q.order_index,
                        "category": q.category,
                        "difficulty": q.difficulty,
                        "question_text": q.question_text,
                        "expected_key_points": q.expected_key_points or [],
                        "answer_text": r.answer_text or "",
                    }
                )

        # Defer provider check: only require AI provider if there are questions to evaluate!
        provider = None
        if len(answered_items) > 0:
            try:
                provider = get_analysis_provider()
            except ProviderConfigurationError as e:
                raise HTTPException(status_code=503, detail=str(e))

        user_prompt = build_evaluation_user_prompt(
            target_role="Backend Developer Intern",
            questions_and_answers=answered_items,
        )
        total_prompt_chars = len(EVALUATION_SYSTEM_PROMPT) + len(user_prompt)
        if total_prompt_chars > getattr(
            settings, "AI_MAX_EVALUATION_TOTAL_PROMPT_CHARS", 35000
        ):
            raise HTTPException(
                status_code=409,
                detail="Tổng dung lượng prompt đánh giá vượt quá giới hạn budget cho phép.",
            )

        # Check existing evaluation
        existing_eval = (
            await db.execute(
                select(InterviewEvaluation)
                .options(selectinload(InterviewEvaluation.response_evaluations))
                .where(InterviewEvaluation.interview_session_id == session_id)
            )
        ).scalars().first()

        if existing_eval:
            if existing_eval.status == EvaluationStatus.evaluated:
                return existing_eval
            if existing_eval.status == EvaluationStatus.evaluating:
                raise HTTPException(
                    status_code=409,
                    detail="Buổi phỏng vấn đang trong quá trình đánh giá.",
                )

            # Conditional atomic claim for retry
            stmt = (
                update(InterviewEvaluation)
                .where(
                    InterviewEvaluation.interview_session_id == session_id,
                    InterviewEvaluation.status == EvaluationStatus.evaluation_failed,
                )
                .values(
                    status=EvaluationStatus.evaluating,
                    error_code=None,
                    error_message=None,
                    updated_at=func.now(),
                )
                .returning(InterviewEvaluation)
            )
            claimed = (await db.execute(stmt)).scalars().first()
            if not claimed:
                raise HTTPException(
                    status_code=409, detail="Buổi phỏng vấn đang được xử lý."
                )
            await db.commit()
            eval_to_process = claimed
        else:
            # First creation claim
            eval_to_process = InterviewEvaluation(
                interview_session_id=session_id,
                status=EvaluationStatus.evaluating,
                provider=settings.AI_PROVIDER,
                model=settings.get_active_model(),
                prompt_version=EVALUATION_PROMPT_VERSION,
                schema_version=EVALUATION_SCHEMA_VERSION,
            )
            db.add(eval_to_process)
            try:
                await db.commit()
            except IntegrityError:
                await db.rollback()
                # Conflict resolution
                curr = (
                    await db.execute(
                        select(InterviewEvaluation)
                        .options(selectinload(InterviewEvaluation.response_evaluations))
                        .where(InterviewEvaluation.interview_session_id == session_id)
                    )
                ).scalars().first()
                if curr and curr.status == EvaluationStatus.evaluated:
                    return curr
                raise HTTPException(
                    status_code=409, detail="Buổi phỏng vấn đang được xử lý."
                )

        eval_id = eval_to_process.id

        # Call AI Provider for answered questions (No DB transaction held!)
        provider_result = None
        if len(answered_items) > 0 and provider is not None:
            input_data = AnalysisInput(
                system_prompt=EVALUATION_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                schema=InterviewEvaluationAISet.model_json_schema(),
            )
            try:
                provider_result = await provider.evaluate_interview(input_data)
            except Exception:
                logger.exception("Unexpected error calling evaluate_interview")
                provider_result = None

        # Process results & validation
        try:
            if len(answered_items) > 0:
                if not provider_result or provider_result.error_code:
                    err_code = provider_result.error_code if provider_result else "INTERNAL_ANALYSIS_ERROR"
                    err_msg = provider_result.error_message if provider_result else "Lỗi hệ thống bất ngờ."
                    raise ValueError(err_code, err_msg)

                if not provider_result.data:
                    raise ValueError("INVALID_PROVIDER_RESPONSE", "Phản hồi rỗng từ AI.")

                ai_eval_set: InterviewEvaluationAISet = provider_result.data
                ai_evals = ai_eval_set.evaluations

                if len(ai_evals) != len(answered_items):
                    raise ValueError(
                        "INVALID_PROVIDER_RESPONSE",
                        f"Số lượng câu trả lời được đánh giá ({len(ai_evals)}) không khớp với số câu đã trả lời ({len(answered_items)}).",
                    )

                expected_orders = {item["question_order"] for item in answered_items}
                received_orders = {e.question_order for e in ai_evals}
                if received_orders != expected_orders or len(ai_evals) != len(received_orders):
                    raise ValueError(
                        "INVALID_PROVIDER_RESPONSE",
                        "Thứ tự các câu hỏi do AI đánh giá bị trùng lặp hoặc không khớp.",
                    )

                ai_eval_by_order = {e.question_order: e for e in ai_evals}
                overall_summary = ai_eval_set.overall_summary
                key_strengths = ai_eval_set.key_strengths
                knowledge_gaps = ai_eval_set.knowledge_gaps
                priority_improvements = ai_eval_set.priority_improvements
                recommended_study_topics = ai_eval_set.recommended_study_topics
                short_term_study_plan = ai_eval_set.short_term_study_plan
                next_interview_advice = ai_eval_set.next_interview_advice
            else:
                # All 10 questions were skipped
                ai_eval_by_order = {}
                overall_summary = "Ứng viên đã bỏ qua toàn bộ các câu hỏi trong buổi phỏng vấn. Cần củng cố kiến thức nền tảng backend cơ bản trước khi tham gia phỏng vấn."
                key_strengths = []
                knowledge_gaps = ["Kiến thức nền tảng backend", "Cơ sở dữ liệu", "Thiết kế API"]
                priority_improvements = ["Ôn tập kiến thức lý thuyết cơ bản", "Thực hành trả lời các câu hỏi phỏng vấn"]
                recommended_study_topics = ["Backend fundamentals", "Database basics", "REST API concepts"]
                short_term_study_plan = ["Tuần 1: Ôn tập cơ sở dữ liệu và SQL cơ bản", "Tuần 2: Học cấu trúc dữ liệu và giải thuật", "Tuần 3: Tìm hiểu giao thức HTTP và REST API", "Tuần 4: Luyện tập trả lời thử các câu hỏi phỏng vấn"]
                next_interview_advice = "Hãy tự tin trả lời dù chỉ nắm được một phần kiến thức thay vì bỏ qua toàn bộ câu hỏi."

            # Build full 10 evaluations
            db_evals: List[InterviewResponseEvaluation] = []
            category_totals: Dict[str, List[float]] = {}

            for q in questions:
                r = resp_by_qid[q.id]
                cat = q.category
                if cat not in category_totals:
                    category_totals[cat] = []

                if r.is_skipped:
                    category_totals[cat].append(0.0)
                    db_evals.append(
                        InterviewResponseEvaluation(
                            id=uuid.uuid4(),
                            interview_evaluation_id=eval_id,
                            interview_response_id=r.id,
                            technical_accuracy=0.0,
                            completeness=0.0,
                            reasoning_clarity=0.0,
                            relevance=0.0,
                            practical_example=0.0,
                            total_score=0.0,
                            feedback="Câu hỏi này đã bị bỏ qua bởi ứng viên. Cần ôn tập kiến thức liên quan để tự tin trả lời.",
                            strengths=[],
                            missing_points=q.expected_key_points or [],
                            suggested_answer=f"Ý chính cần nắm: {', '.join(q.expected_key_points or [])}.",
                            study_topics=[q.category, f"{q.category} fundamentals"],
                            confidence=EvaluationConfidence.high.value,
                        )
                    )
                else:
                    ai_item = ai_eval_by_order[q.order_index]
                    # Score bounds validation
                    if not (0.0 <= ai_item.technical_accuracy <= 4.0):
                        raise ValueError("INVALID_PROVIDER_RESPONSE", "technical_accuracy ngoài phạm vi [0, 4].")
                    if not (0.0 <= ai_item.completeness <= 2.0):
                        raise ValueError("INVALID_PROVIDER_RESPONSE", "completeness ngoài phạm vi [0, 2].")
                    if not (0.0 <= ai_item.reasoning_clarity <= 2.0):
                        raise ValueError("INVALID_PROVIDER_RESPONSE", "reasoning_clarity ngoài phạm vi [0, 2].")
                    if not (0.0 <= ai_item.relevance <= 1.0):
                        raise ValueError("INVALID_PROVIDER_RESPONSE", "relevance ngoài phạm vi [0, 1].")
                    if not (0.0 <= ai_item.practical_example <= 1.0):
                        raise ValueError("INVALID_PROVIDER_RESPONSE", "practical_example ngoài phạm vi [0, 1].")

                    calc_sum = round_sum_scores([
                        ai_item.technical_accuracy,
                        ai_item.completeness,
                        ai_item.reasoning_clarity,
                        ai_item.relevance,
                        ai_item.practical_example,
                    ])
                    # STRICT RULE: discrepancy >= 0.01 is immediately rejected as INVALID_PROVIDER_RESPONSE
                    if abs(round_delta(ai_item.total_score, calc_sum)) >= 0.01:
                        raise ValueError(
                            "INVALID_PROVIDER_RESPONSE",
                            f"total_score ({ai_item.total_score}) không bằng tổng thành phần ({calc_sum}).",
                        )

                    category_totals[cat].append(calc_sum)
                    db_evals.append(
                        InterviewResponseEvaluation(
                            id=uuid.uuid4(),
                            interview_evaluation_id=eval_id,
                            interview_response_id=r.id,
                            technical_accuracy=round_score(ai_item.technical_accuracy),
                            completeness=round_score(ai_item.completeness),
                            reasoning_clarity=round_score(ai_item.reasoning_clarity),
                            relevance=round_score(ai_item.relevance),
                            practical_example=round_score(ai_item.practical_example),
                            total_score=calc_sum,
                            feedback=ai_item.feedback,
                            strengths=ai_item.strengths,
                            missing_points=ai_item.missing_points,
                            suggested_answer=ai_item.suggested_answer,
                            study_topics=ai_item.study_topics,
                            confidence=ai_item.confidence.value,
                        )
                    )

            if len(db_evals) != 10:
                raise ValueError("INVALID_PROVIDER_RESPONSE", "Không đủ 10 kết quả đánh giá.")

            # Compute overall stats using centralized Decimal aggregation & ROUND_HALF_UP contract
            session_total_score = round_sum_scores(e.total_score for e in db_evals)
            session_average_score = round_average_score(session_total_score, 10)
            answered_count = len(answered_items)
            skipped_count = 10 - answered_count

            category_scores = {
                cat: round_average_values(scores)
                for cat, scores in category_totals.items()
                if len(scores) > 0
            }
            # Backend strictly determines readiness level based on total score
            readiness_level = compute_readiness_level(session_total_score)

            # Final Transaction: delete retry rows, add evaluations, update evaluation record
            await db.execute(
                delete(InterviewResponseEvaluation).where(
                    InterviewResponseEvaluation.interview_evaluation_id == eval_id
                )
            )
            db.add_all(db_evals)

            stmt = (
                update(InterviewEvaluation)
                .where(InterviewEvaluation.id == eval_id)
                .values(
                    status=EvaluationStatus.evaluated,
                    total_score=session_total_score,
                    average_score=session_average_score,
                    answered_count=answered_count,
                    skipped_count=skipped_count,
                    category_scores=category_scores,
                    overall_summary=overall_summary,
                    key_strengths=key_strengths,
                    knowledge_gaps=knowledge_gaps,
                    priority_improvements=priority_improvements,
                    recommended_study_topics=recommended_study_topics,
                    short_term_study_plan=short_term_study_plan,
                    next_interview_advice=next_interview_advice,
                    readiness_level=readiness_level.value,
                    evaluated_at=func.now(),
                    error_code=None,
                    error_message=None,
                    updated_at=func.now(),
                )
            )
            await db.execute(stmt)
            await db.commit()

        except ValueError as ve:
            await db.rollback()
            code, _ = ve.args[0], ve.args[1]
            safe_msg = SAFE_ERROR_MESSAGES.get(code, "Dữ liệu kết quả đánh giá từ nhà cung cấp AI không hợp lệ.")
            try:
                stmt = (
                    update(InterviewEvaluation)
                    .where(InterviewEvaluation.id == eval_id)
                    .values(
                        status=EvaluationStatus.evaluation_failed,
                        error_code=code,
                        error_message=safe_msg,
                        updated_at=func.now(),
                    )
                )
                await db.execute(stmt)
                await db.commit()
            except Exception:
                await db.rollback()
                logger.exception("Failed to recover evaluation state (ValueError)")
                raise HTTPException(status_code=500, detail="Lỗi máy chủ nội bộ.")

        except Exception:
            await db.rollback()
            logger.exception("Unexpected error saving interview evaluation")
            try:
                stmt = (
                    update(InterviewEvaluation)
                    .where(InterviewEvaluation.id == eval_id)
                    .values(
                        status=EvaluationStatus.evaluation_failed,
                        error_code="INTERNAL_ANALYSIS_ERROR",
                        error_message="Lỗi hệ thống trong quá trình lưu kết quả đánh giá.",
                        updated_at=func.now(),
                    )
                )
                await db.execute(stmt)
                await db.commit()
            except Exception:
                await db.rollback()
                logger.exception("Failed to recover evaluation state (Exception)")
                raise HTTPException(status_code=500, detail="Lỗi máy chủ nội bộ.")

        # Reload full record with responses
        res = (
            await db.execute(
                select(InterviewEvaluation)
                .options(selectinload(InterviewEvaluation.response_evaluations))
                .where(InterviewEvaluation.id == eval_id)
            )
        ).scalars().first()
        return res

    @staticmethod
    async def get_evaluation(
        db: AsyncSession, session_id: uuid.UUID
    ) -> InterviewEvaluation:
        record = (
            await db.execute(
                select(InterviewEvaluation)
                .options(selectinload(InterviewEvaluation.response_evaluations))
                .where(InterviewEvaluation.interview_session_id == session_id)
            )
        ).scalars().first()

        if not record:
            raise HTTPException(
                status_code=404, detail="Không tìm thấy kết quả đánh giá cho phiên này."
            )

        return record

    @classmethod
    async def build_response(
        cls, db: AsyncSession, eval_record: InterviewEvaluation
    ):
        from app.schemas.interview_evaluation import (
            InterviewEvaluationResponse,
            ResponseEvaluationDetail,
        )

        if eval_record.status != EvaluationStatus.evaluated:
            return InterviewEvaluationResponse(
                id=eval_record.id,
                interview_session_id=eval_record.interview_session_id,
                status=eval_record.status,
                provider=eval_record.provider,
                model=eval_record.model,
                prompt_version=eval_record.prompt_version,
                schema_version=eval_record.schema_version,
                total_score=None,
                average_score=None,
                answered_count=None,
                skipped_count=None,
                category_scores=None,
                overall_summary=None,
                key_strengths=None,
                knowledge_gaps=None,
                priority_improvements=None,
                recommended_study_topics=None,
                short_term_study_plan=None,
                next_interview_advice=None,
                readiness_level=None,
                responses=[],
                error_code=eval_record.error_code,
                error_message=eval_record.error_message,
                created_at=eval_record.created_at,
                updated_at=eval_record.updated_at,
                evaluated_at=eval_record.evaluated_at,
            )

        resp_evals = (
            await db.execute(
                select(InterviewResponseEvaluation)
                .options(
                    selectinload(InterviewResponseEvaluation.response)
                    .selectinload(InterviewResponse.question)
                )
                .where(
                    InterviewResponseEvaluation.interview_evaluation_id
                    == eval_record.id
                )
            )
        ).scalars().all()

        resp_evals = sorted(
            resp_evals, key=lambda x: x.response.question.order_index
        )

        def to_float(val):
            return float(val) if val is not None else None

        detail_items = []
        for re in resp_evals:
            q = re.response.question
            r = re.response
            detail_items.append(
                ResponseEvaluationDetail(
                    interview_response_id=r.id,
                    question_order=q.order_index,
                    question_text=q.question_text,
                    category=q.category,
                    difficulty=q.difficulty,
                    is_skipped=r.is_skipped,
                    technical_accuracy=to_float(re.technical_accuracy),
                    completeness=to_float(re.completeness),
                    reasoning_clarity=to_float(re.reasoning_clarity),
                    relevance=to_float(re.relevance),
                    practical_example=to_float(re.practical_example),
                    total_score=to_float(re.total_score),
                    feedback=re.feedback,
                    strengths=re.strengths or [],
                    missing_points=re.missing_points or [],
                    suggested_answer=re.suggested_answer,
                    study_topics=re.study_topics or [],
                    confidence=re.confidence,
                )
            )

        cat_scores = None
        if eval_record.category_scores:
            cat_scores = {k: float(v) for k, v in eval_record.category_scores.items()}

        return InterviewEvaluationResponse(
            id=eval_record.id,
            interview_session_id=eval_record.interview_session_id,
            status=eval_record.status,
            provider=eval_record.provider,
            model=eval_record.model,
            prompt_version=eval_record.prompt_version,
            schema_version=eval_record.schema_version,
            total_score=to_float(eval_record.total_score),
            average_score=to_float(eval_record.average_score),
            answered_count=eval_record.answered_count,
            skipped_count=eval_record.skipped_count,
            category_scores=cat_scores,
            overall_summary=eval_record.overall_summary,
            key_strengths=eval_record.key_strengths,
            knowledge_gaps=eval_record.knowledge_gaps,
            priority_improvements=eval_record.priority_improvements,
            recommended_study_topics=eval_record.recommended_study_topics,
            short_term_study_plan=eval_record.short_term_study_plan,
            next_interview_advice=eval_record.next_interview_advice,
            readiness_level=eval_record.readiness_level,
            responses=detail_items,
            error_code=eval_record.error_code,
            error_message=eval_record.error_message,
            created_at=eval_record.created_at,
            updated_at=eval_record.updated_at,
            evaluated_at=eval_record.evaluated_at,
        )
