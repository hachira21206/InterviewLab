import math
import uuid
from typing import Dict, List, Optional
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from app.models.job_application import JobApplication
from app.models.interview_session import InterviewSession
from app.models.interview_evaluation import InterviewEvaluation, ReadinessLevel
from app.models.interview_question import QuestionCategory
from app.schemas.interview_progress import (
    ComparisonStatus,
    ReadinessDirection,
    InterviewProgressTrendItem,
    InterviewProgressLatestItem,
    InterviewProgressDelta,
    InterviewProgressComparison,
    CategoryProgressItem,
    InterviewProgressReportResponse,
)
from app.core.rounding import round_score, round_delta

READINESS_RANK = {
    ReadinessLevel.needs_foundation: 1,
    ReadinessLevel.developing: 2,
    ReadinessLevel.intern_ready: 3,
    ReadinessLevel.strong_intern_candidate: 4,
}


def _compute_delta(
    cur: InterviewProgressTrendItem, base: InterviewProgressTrendItem
) -> InterviewProgressDelta:
    total_score_delta = round_delta(cur.total_score, base.total_score)
    average_score_delta = round_delta(cur.average_score, base.average_score)
    answered_count_delta = cur.answered_count - base.answered_count
    skipped_count_delta = cur.skipped_count - base.skipped_count
    readiness_changed = cur.readiness_level != base.readiness_level

    cur_rank = READINESS_RANK[cur.readiness_level]
    base_rank = READINESS_RANK[base.readiness_level]
    if cur_rank > base_rank:
        readiness_dir = ReadinessDirection.improved
    elif cur_rank < base_rank:
        readiness_dir = ReadinessDirection.declined
    else:
        readiness_dir = ReadinessDirection.unchanged

    return InterviewProgressDelta(
        total_score_delta=total_score_delta,
        average_score_delta=average_score_delta,
        answered_count_delta=answered_count_delta,
        skipped_count_delta=skipped_count_delta,
        readiness_changed=readiness_changed,
        readiness_direction=readiness_dir,
    )


class InterviewProgressService:
    @staticmethod
    async def get_progress_report(
        db: AsyncSession, application_id: uuid.UUID
    ) -> InterviewProgressReportResponse:
        # 1. Verify JobApplication existence
        app_stmt = select(JobApplication).where(JobApplication.id == application_id)
        app_res = await db.execute(app_stmt)
        job_app = app_res.scalar_one_or_none()
        if not job_app:
            raise HTTPException(
                status_code=404, detail="Không tìm thấy hồ sơ ứng tuyển."
            )

        # 2. Query all interview sessions with joined evaluation to prevent N+1 queries
        stmt = (
            select(InterviewSession)
            .options(joinedload(InterviewSession.evaluation))
            .where(InterviewSession.job_application_id == application_id)
            .order_by(InterviewSession.attempt_number.asc())
        )
        res = await db.execute(stmt)
        sessions = res.scalars().all()

        total_attempts = len(sessions)
        completed_attempts = sum(1 for s in sessions if s.status == "completed")

        # 3. Filter valid evaluated sessions
        valid_trend_items: List[InterviewProgressTrendItem] = []
        valid_categories = {c.value for c in QuestionCategory}

        for s in sessions:
            if s.status != "completed":
                continue
            eval_record = s.evaluation
            if not eval_record or eval_record.status != "evaluated":
                continue
            if eval_record.total_score is None or eval_record.average_score is None:
                continue
            if eval_record.readiness_level is None:
                continue

            try:
                t_score = round_score(eval_record.total_score)
                a_score = round_score(eval_record.average_score)
            except (TypeError, ValueError):
                continue

            if math.isnan(t_score) or math.isinf(t_score) or not (0.0 <= t_score <= 100.0):
                continue
            if math.isnan(a_score) or math.isinf(a_score) or not (0.0 <= a_score <= 10.0):
                continue
            if eval_record.readiness_level not in [r.value for r in ReadinessLevel]:
                continue

            r_level = ReadinessLevel(eval_record.readiness_level)
            ans_count = eval_record.answered_count
            skip_count = eval_record.skipped_count
            if ans_count is None or skip_count is None:
                continue
            if not (0 <= ans_count <= 10 and 0 <= skip_count <= 10 and ans_count + skip_count == 10):
                continue

            # Parse and validate category_scores safely (0.0 is valid)
            cat_scores: Dict[str, float] = {}
            if isinstance(eval_record.category_scores, dict):
                for k, v in eval_record.category_scores.items():
                    if k in valid_categories and v is not None:
                        try:
                            score_val = round_score(v)
                            if (
                                not math.isnan(score_val)
                                and not math.isinf(score_val)
                                and 0.0 <= score_val <= 10.0
                            ):
                                cat_scores[k] = score_val
                        except (TypeError, ValueError):
                            pass

            trend_item = InterviewProgressTrendItem(
                session_id=s.id,
                attempt_number=s.attempt_number,
                total_score=t_score,
                average_score=a_score,
                answered_count=ans_count,
                skipped_count=skip_count,
                readiness_level=r_level,
                category_scores=cat_scores,
                completed_at=s.completed_at,
                evaluated_at=eval_record.evaluated_at,
            )
            valid_trend_items.append(trend_item)

        evaluated_attempts = len(valid_trend_items)

        # 4. Compute latest item
        latest: Optional[InterviewProgressLatestItem] = None
        if evaluated_attempts >= 1:
            last_trend = valid_trend_items[-1]
            latest = InterviewProgressLatestItem(
                session_id=last_trend.session_id,
                attempt_number=last_trend.attempt_number,
                total_score=last_trend.total_score,
                average_score=last_trend.average_score,
                readiness_level=last_trend.readiness_level,
            )

        # 5. Compute comparison
        if evaluated_attempts == 0:
            comparison = InterviewProgressComparison(
                status=ComparisonStatus.no_data,
                latest_vs_previous=None,
                latest_vs_first=None,
            )
        elif evaluated_attempts == 1:
            comparison = InterviewProgressComparison(
                status=ComparisonStatus.insufficient_data,
                latest_vs_previous=None,
                latest_vs_first=None,
            )
        else:
            cur_item = valid_trend_items[-1]
            prev_item = valid_trend_items[-2]
            first_item = valid_trend_items[0]

            latest_vs_previous = _compute_delta(cur_item, prev_item)
            latest_vs_first = _compute_delta(cur_item, first_item)

            if latest_vs_previous.total_score_delta >= 0.01:
                comp_status = ComparisonStatus.improved
            elif latest_vs_previous.total_score_delta <= -0.01:
                comp_status = ComparisonStatus.declined
            else:
                comp_status = ComparisonStatus.unchanged

            comparison = InterviewProgressComparison(
                status=comp_status,
                latest_vs_previous=latest_vs_previous,
                latest_vs_first=latest_vs_first,
            )

        # 6. Compute category_progress
        category_progress: List[CategoryProgressItem] = []
        if evaluated_attempts >= 1:
            for cat in QuestionCategory:
                cat_key = cat.value
                cat_scores = [
                    item.category_scores[cat_key]
                    for item in valid_trend_items
                    if cat_key in item.category_scores
                ]
                if not cat_scores:
                    continue

                attempts_with_data = len(cat_scores)
                if attempts_with_data == 1:
                    item_score = round_score(cat_scores[0])
                    category_progress.append(
                        CategoryProgressItem(
                            category=cat_key,
                            first_score=item_score,
                            previous_score=None,
                            latest_score=item_score,
                            latest_vs_previous_delta=None,
                            latest_vs_first_delta=None,
                            attempts_with_data=1,
                        )
                    )
                else:
                    f_score = round_score(cat_scores[0])
                    prev_score = round_score(cat_scores[-2])
                    l_score = round_score(cat_scores[-1])
                    prev_delta = round_delta(l_score, prev_score)
                    first_delta = round_delta(l_score, f_score)
                    category_progress.append(
                        CategoryProgressItem(
                            category=cat_key,
                            first_score=f_score,
                            previous_score=prev_score,
                            latest_score=l_score,
                            latest_vs_previous_delta=prev_delta,
                            latest_vs_first_delta=first_delta,
                            attempts_with_data=attempts_with_data,
                        )
                    )

        return InterviewProgressReportResponse(
            job_application_id=application_id,
            total_attempts=total_attempts,
            completed_attempts=completed_attempts,
            evaluated_attempts=evaluated_attempts,
            trend=valid_trend_items,
            latest=latest,
            comparison=comparison,
            category_progress=category_progress,
        )
