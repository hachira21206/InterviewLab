import math
import uuid
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, delete, text
from sqlalchemy.orm import selectinload

from app.main import app as fastapi_app
from app.db.session import SessionLocal
from app.models.cv_document import CVDocument, CVStatus
from app.models.job_application import JobApplication
from app.models.application_analysis import ApplicationAnalysis, AnalysisStatus
from app.models.interview_session import InterviewSession, SessionStatus
from app.models.interview_evaluation import (
    InterviewEvaluation,
    EvaluationStatus,
    ReadinessLevel,
)
from app.models.interview_question import QuestionCategory
from app.services.analysis_provider import FakeAnalysisProvider
from app.schemas.interview_progress import ComparisonStatus, ReadinessDirection


@pytest_asyncio.fixture
async def sample_app():
    doc_id = uuid.uuid4()
    app_id = uuid.uuid4()

    async with SessionLocal() as db:
        doc = CVDocument(
            id=doc_id,
            original_filename="cv_prog.pdf",
            storage_key=f"k_{doc_id}",
            media_type="application/pdf",
            size_bytes=100,
            sha256=f"hash_{doc_id}",
            status=CVStatus.extracted,
            extracted_text="Python Backend Engineer Developer",
        )
        db.add(doc)

        job_app = JobApplication(
            id=app_id,
            cv_document_id=doc_id,
            target_role="Backend Developer Intern",
            job_description="Junior Python Engineer",
        )
        db.add(job_app)
        await db.commit()

    try:
        yield {"app_id": app_id, "doc_id": doc_id}
    finally:
        async with SessionLocal() as db:
            # Clean targeted data only
            s_ids = (
                await db.execute(
                    select(InterviewSession.id).where(
                        InterviewSession.job_application_id == app_id
                    )
                )
            ).scalars().all()
            if s_ids:
                await db.execute(
                    delete(InterviewEvaluation).where(
                        InterviewEvaluation.interview_session_id.in_(s_ids)
                    )
                )
                await db.execute(
                    delete(InterviewSession).where(
                        InterviewSession.job_application_id == app_id
                    )
                )
            await db.execute(
                delete(JobApplication).where(JobApplication.id == app_id)
            )
            await db.execute(delete(CVDocument).where(CVDocument.id == doc_id))
            await db.commit()


async def create_attempt_with_eval(
    app_id: uuid.UUID,
    attempt_num: int,
    session_status: str = "completed",
    eval_status: str = "evaluated",
    total_score: float = 75.0,
    average_score: float = 7.5,
    answered_count: int = 8,
    skipped_count: int = 2,
    readiness_level: str = "intern_ready",
    category_scores: dict = None,
):
    session_id = uuid.uuid4()
    eval_id = uuid.uuid4()
    if category_scores is None:
        category_scores = {
            "backend_fundamentals": 7.0,
            "database": 8.0,
        }

    async with SessionLocal() as db:
        session = InterviewSession(
            id=session_id,
            job_application_id=app_id,
            attempt_number=attempt_num,
            status=session_status,
            provider="groq",
            model="llama",
            prompt_version="1.0",
            schema_version="1.0",
        )
        db.add(session)
        await db.flush()

        if eval_status != "none":
            evaluation = InterviewEvaluation(
                id=eval_id,
                interview_session_id=session_id,
                status=eval_status,
                provider="groq",
                model="llama",
                prompt_version="1.0",
                schema_version="1.0",
                total_score=total_score if eval_status == "evaluated" else None,
                average_score=average_score if eval_status == "evaluated" else None,
                answered_count=answered_count if eval_status == "evaluated" else None,
                skipped_count=skipped_count if eval_status == "evaluated" else None,
                readiness_level=readiness_level if eval_status == "evaluated" else None,
                category_scores=category_scores if eval_status == "evaluated" else None,
            )
            db.add(evaluation)
        await db.commit()

    return session_id


@pytest.mark.asyncio
async def test_progress_application_not_found():
    non_existent = uuid.uuid4()
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get(f"/api/v1/job-applications/{non_existent}/interview-progress")
        assert res.status_code == 404
        assert res.json()["detail"] == "Không tìm thấy hồ sơ ứng tuyển."


@pytest.mark.asyncio
async def test_progress_application_no_attempts(sample_app):
    app_id = sample_app["app_id"]
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get(f"/api/v1/job-applications/{app_id}/interview-progress")
        assert res.status_code == 200
        data = res.json()
        assert data["job_application_id"] == str(app_id)
        assert data["total_attempts"] == 0
        assert data["completed_attempts"] == 0
        assert data["evaluated_attempts"] == 0
        assert data["trend"] == []
        assert data["latest"] is None
        assert data["comparison"]["status"] == "no_data"
        assert data["comparison"]["latest_vs_previous"] is None
        assert data["comparison"]["latest_vs_first"] is None
        assert data["category_progress"] == []


@pytest.mark.asyncio
async def test_progress_attempt_not_completed(sample_app):
    app_id = sample_app["app_id"]
    await create_attempt_with_eval(app_id, 1, session_status="in_progress", eval_status="none")
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get(f"/api/v1/job-applications/{app_id}/interview-progress")
        assert res.status_code == 200
        data = res.json()
        assert data["total_attempts"] == 1
        assert data["completed_attempts"] == 0
        assert data["evaluated_attempts"] == 0
        assert data["trend"] == []
        assert data["comparison"]["status"] == "no_data"


@pytest.mark.asyncio
async def test_progress_completed_not_evaluated(sample_app):
    app_id = sample_app["app_id"]
    # 1 attempt completed but eval is pending
    await create_attempt_with_eval(app_id, 1, session_status="completed", eval_status="pending")
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get(f"/api/v1/job-applications/{app_id}/interview-progress")
        assert res.status_code == 200
        data = res.json()
        assert data["total_attempts"] == 1
        assert data["completed_attempts"] == 1
        assert data["evaluated_attempts"] == 0
        assert data["trend"] == []
        assert data["comparison"]["status"] == "no_data"


@pytest.mark.asyncio
async def test_progress_single_evaluation(sample_app):
    app_id = sample_app["app_id"]
    await create_attempt_with_eval(
        app_id,
        1,
        total_score=68.5,
        average_score=6.85,
        readiness_level="developing",
        category_scores={"database": 7.0},
    )
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get(f"/api/v1/job-applications/{app_id}/interview-progress")
        assert res.status_code == 200
        data = res.json()
        assert data["total_attempts"] == 1
        assert data["completed_attempts"] == 1
        assert data["evaluated_attempts"] == 1
        assert len(data["trend"]) == 1
        assert data["latest"]["attempt_number"] == 1
        assert data["latest"]["total_score"] == 68.5
        assert data["comparison"]["status"] == "insufficient_data"
        assert data["comparison"]["latest_vs_previous"] is None
        assert data["comparison"]["latest_vs_first"] is None
        assert len(data["category_progress"]) == 1
        cat_p = data["category_progress"][0]
        assert cat_p["category"] == "database"
        assert cat_p["first_score"] == 7.0
        assert cat_p["latest_score"] == 7.0
        assert cat_p["previous_score"] is None
        assert cat_p["latest_vs_previous_delta"] is None
        assert cat_p["latest_vs_first_delta"] is None
        assert cat_p["attempts_with_data"] == 1


@pytest.mark.asyncio
async def test_progress_two_evaluations_improved(sample_app):
    app_id = sample_app["app_id"]
    await create_attempt_with_eval(app_id, 1, total_score=60.0, average_score=6.0, readiness_level="needs_foundation")
    await create_attempt_with_eval(app_id, 2, total_score=75.5, average_score=7.55, readiness_level="intern_ready")

    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get(f"/api/v1/job-applications/{app_id}/interview-progress")
        assert res.status_code == 200
        data = res.json()
        assert data["evaluated_attempts"] == 2
        assert data["comparison"]["status"] == "improved"
        prev_delta = data["comparison"]["latest_vs_previous"]
        assert prev_delta["total_score_delta"] == 15.5
        assert prev_delta["average_score_delta"] == 1.55
        assert prev_delta["readiness_changed"] is True
        assert prev_delta["readiness_direction"] == "improved"


@pytest.mark.asyncio
async def test_progress_two_evaluations_declined(sample_app):
    app_id = sample_app["app_id"]
    await create_attempt_with_eval(app_id, 1, total_score=80.0, average_score=8.0, readiness_level="intern_ready")
    await create_attempt_with_eval(app_id, 2, total_score=70.0, average_score=7.0, readiness_level="developing")

    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get(f"/api/v1/job-applications/{app_id}/interview-progress")
        assert res.status_code == 200
        data = res.json()
        assert data["comparison"]["status"] == "declined"
        prev_delta = data["comparison"]["latest_vs_previous"]
        assert prev_delta["total_score_delta"] == -10.0
        assert prev_delta["readiness_direction"] == "declined"


@pytest.mark.asyncio
async def test_progress_two_evaluations_unchanged(sample_app):
    app_id = sample_app["app_id"]
    await create_attempt_with_eval(app_id, 1, total_score=75.00, average_score=7.5, readiness_level="intern_ready")
    await create_attempt_with_eval(app_id, 2, total_score=75.00, average_score=7.5, readiness_level="intern_ready")

    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get(f"/api/v1/job-applications/{app_id}/interview-progress")
        assert res.status_code == 200
        data = res.json()
        assert data["comparison"]["status"] == "unchanged"
        assert abs(data["comparison"]["latest_vs_previous"]["total_score_delta"]) < 0.01
        assert data["comparison"]["latest_vs_previous"]["readiness_direction"] == "unchanged"


@pytest.mark.asyncio
async def test_progress_non_consecutive_attempts(sample_app):
    app_id = sample_app["app_id"]
    # Attempt 1 evaluated, attempt 2 in_progress (un-evaluated), attempt 3 evaluated
    await create_attempt_with_eval(app_id, 1, total_score=50.0, average_score=5.0)
    await create_attempt_with_eval(app_id, 2, session_status="in_progress", eval_status="none")
    await create_attempt_with_eval(app_id, 3, total_score=70.0, average_score=7.0)

    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get(f"/api/v1/job-applications/{app_id}/interview-progress")
        assert res.status_code == 200
        data = res.json()
        assert data["total_attempts"] == 3
        assert data["completed_attempts"] == 2
        assert data["evaluated_attempts"] == 2
        assert data["latest"]["attempt_number"] == 3
        assert data["comparison"]["latest_vs_previous"]["total_score_delta"] == 20.0


@pytest.mark.asyncio
async def test_progress_latest_previous_first_correctness(sample_app):
    app_id = sample_app["app_id"]
    await create_attempt_with_eval(app_id, 1, total_score=50.0, average_score=5.0, answered_count=6, skipped_count=4)
    await create_attempt_with_eval(app_id, 2, total_score=65.0, average_score=6.5, answered_count=8, skipped_count=2)
    await create_attempt_with_eval(app_id, 4, total_score=85.0, average_score=8.5, answered_count=10, skipped_count=0)

    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get(f"/api/v1/job-applications/{app_id}/interview-progress")
        assert res.status_code == 200
        data = res.json()
        assert data["latest"]["attempt_number"] == 4
        # vs previous (attempt 2)
        assert data["comparison"]["latest_vs_previous"]["total_score_delta"] == 20.0
        assert data["comparison"]["latest_vs_previous"]["answered_count_delta"] == 2
        # vs first (attempt 1)
        assert data["comparison"]["latest_vs_first"]["total_score_delta"] == 35.0
        assert data["comparison"]["latest_vs_first"]["answered_count_delta"] == 4


@pytest.mark.asyncio
async def test_progress_deltas_rounded_two_decimals(sample_app):
    app_id = sample_app["app_id"]
    await create_attempt_with_eval(app_id, 1, total_score=33.33, average_score=3.33)
    await create_attempt_with_eval(app_id, 2, total_score=66.67, average_score=6.67)

    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get(f"/api/v1/job-applications/{app_id}/interview-progress")
        assert res.status_code == 200
        data = res.json()
        prev_delta = data["comparison"]["latest_vs_previous"]
        assert prev_delta["total_score_delta"] == 33.34
        assert prev_delta["average_score_delta"] == 3.34


@pytest.mark.asyncio
async def test_progress_zero_score_handled_validly(sample_app):
    app_id = sample_app["app_id"]
    await create_attempt_with_eval(
        app_id, 1, total_score=0.0, average_score=0.0, answered_count=0, skipped_count=10,
        category_scores={"database": 0.0}
    )
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get(f"/api/v1/job-applications/{app_id}/interview-progress")
        assert res.status_code == 200
        data = res.json()
        assert data["evaluated_attempts"] == 1
        assert data["latest"]["total_score"] == 0.0
        assert len(data["category_progress"]) == 1
        assert data["category_progress"][0]["latest_score"] == 0.0


@pytest.mark.asyncio
async def test_progress_readiness_direction(sample_app):
    app_id = sample_app["app_id"]
    await create_attempt_with_eval(app_id, 1, readiness_level="developing")
    await create_attempt_with_eval(app_id, 2, readiness_level="intern_ready")
    await create_attempt_with_eval(app_id, 3, readiness_level="developing")

    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get(f"/api/v1/job-applications/{app_id}/interview-progress")
        assert res.status_code == 200
        data = res.json()
        # latest (developing) vs previous (intern_ready) -> declined
        assert data["comparison"]["latest_vs_previous"]["readiness_direction"] == "declined"
        # latest (developing) vs first (developing) -> unchanged
        assert data["comparison"]["latest_vs_first"]["readiness_direction"] == "unchanged"


@pytest.mark.asyncio
async def test_progress_missing_category_in_one_attempt(sample_app):
    app_id = sample_app["app_id"]
    # Attempt 1 has database and backend_fundamentals
    await create_attempt_with_eval(
        app_id, 1, category_scores={"database": 6.0, "backend_fundamentals": 7.0}
    )
    # Attempt 2 has only backend_fundamentals (database is missing)
    await create_attempt_with_eval(
        app_id, 2, category_scores={"backend_fundamentals": 8.0}
    )

    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get(f"/api/v1/job-applications/{app_id}/interview-progress")
        assert res.status_code == 200
        data = res.json()
        cat_map = {c["category"]: c for c in data["category_progress"]}
        assert "database" in cat_map
        assert cat_map["database"]["attempts_with_data"] == 1
        assert cat_map["database"]["first_score"] == 6.0
        assert cat_map["database"]["latest_score"] == 6.0
        assert cat_map["database"]["latest_vs_previous_delta"] is None

        assert "backend_fundamentals" in cat_map
        assert cat_map["backend_fundamentals"]["attempts_with_data"] == 2
        assert cat_map["backend_fundamentals"]["latest_vs_previous_delta"] == 1.0


@pytest.mark.asyncio
async def test_progress_category_deltas_correct(sample_app):
    app_id = sample_app["app_id"]
    await create_attempt_with_eval(app_id, 1, category_scores={"database": 5.0})
    await create_attempt_with_eval(app_id, 2, category_scores={"database": 7.0})
    await create_attempt_with_eval(app_id, 3, category_scores={"database": 9.5})

    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get(f"/api/v1/job-applications/{app_id}/interview-progress")
        assert res.status_code == 200
        data = res.json()
        db_prog = [c for c in data["category_progress"] if c["category"] == "database"][0]
        assert db_prog["first_score"] == 5.0
        assert db_prog["previous_score"] == 7.0
        assert db_prog["latest_score"] == 9.5
        assert db_prog["latest_vs_previous_delta"] == 2.5
        assert db_prog["latest_vs_first_delta"] == 4.5
        assert db_prog["attempts_with_data"] == 3


@pytest.mark.asyncio
async def test_progress_no_n_plus_one_queries(sample_app):
    app_id = sample_app["app_id"]
    # Create 5 attempts
    for i in range(1, 6):
        await create_attempt_with_eval(app_id, i)

    # Monitor query count
    from app.services.interview_progress_service import InterviewProgressService
    query_count = 0

    def query_counter(conn, cursor, statement, parameters, context, executemany):
        nonlocal query_count
        query_count += 1

    from app.db.session import engine
    from sqlalchemy import event

    event.listen(engine.sync_engine, "before_cursor_execute", query_counter)
    try:
        async with SessionLocal() as db:
            report = await InterviewProgressService.get_progress_report(db, app_id)
            assert report.evaluated_attempts == 5
            # Exactly 2 queries: 1 for JobApplication check, 1 for InterviewSession + joinedload InterviewEvaluation
            assert query_count == 2, f"Expected 2 queries, got {query_count}"
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", query_counter)


@pytest.mark.asyncio
async def test_progress_no_ai_provider_called(sample_app, monkeypatch):
    app_id = sample_app["app_id"]
    await create_attempt_with_eval(app_id, 1)

    call_count = 0
    def spy_get_provider(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return FakeAnalysisProvider()

    import app.services.analysis_provider
    monkeypatch.setattr(app.services.analysis_provider, "get_analysis_provider", spy_get_provider)

    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get(f"/api/v1/job-applications/{app_id}/interview-progress")
        assert res.status_code == 200
        assert call_count == 0, "AI provider should NEVER be called in Task 09"


@pytest.mark.asyncio
async def test_progress_no_sensitive_data_leaked(sample_app):
    app_id = sample_app["app_id"]
    await create_attempt_with_eval(app_id, 1)

    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get(f"/api/v1/job-applications/{app_id}/interview-progress")
        assert res.status_code == 200
        raw_text = res.text
        forbidden_substrings = [
            "expected_key_points",
            "question_text",
            "answer_text",
            "suggested_answer",
            "feedback",
            "missing_points",
            "prompt",
            "Python Backend Engineer Developer",  # CV extracted text
            "Junior Python Engineer",  # JD text
        ]
        for sub in forbidden_substrings:
            assert sub not in raw_text, f"Forbidden sensitive data leaked: {sub}"


@pytest.mark.asyncio
async def test_progress_cascade_delete_does_not_crash(sample_app):
    app_id = sample_app["app_id"]
    s_id = await create_attempt_with_eval(app_id, 1)

    async with SessionLocal() as db:
        await db.execute(delete(InterviewSession).where(InterviewSession.id == s_id))
        await db.commit()

    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get(f"/api/v1/job-applications/{app_id}/interview-progress")
        assert res.status_code == 200
        assert res.json()["total_attempts"] == 0


@pytest.mark.asyncio
async def test_progress_isolation_with_sentinel():
    sentinel_doc_id = uuid.uuid4()
    sentinel_app_id = uuid.uuid4()
    target_doc_id = uuid.uuid4()
    target_app_id = uuid.uuid4()

    async with SessionLocal() as db:
        # Create sentinel application
        db.add(CVDocument(
            id=sentinel_doc_id, original_filename="sentinel.pdf", storage_key=f"k_{sentinel_doc_id}",
            media_type="application/pdf", size_bytes=10, sha256=f"h_{sentinel_doc_id}", status=CVStatus.extracted,
            extracted_text="Sentinel CV"
        ))
        db.add(JobApplication(
            id=sentinel_app_id, cv_document_id=sentinel_doc_id, target_role="Backend Developer Intern"
        ))
        # Create target application
        db.add(CVDocument(
            id=target_doc_id, original_filename="target.pdf", storage_key=f"k_{target_doc_id}",
            media_type="application/pdf", size_bytes=10, sha256=f"h_{target_doc_id}", status=CVStatus.extracted,
            extracted_text="Target CV"
        ))
        db.add(JobApplication(
            id=target_app_id, cv_document_id=target_doc_id, target_role="Backend Developer Intern"
        ))
        await db.commit()

    try:
        # Add attempt to both
        await create_attempt_with_eval(sentinel_app_id, 1, total_score=90.0)
        await create_attempt_with_eval(target_app_id, 1, total_score=60.0)

        # Cleanup only target
        async with SessionLocal() as db:
            s_ids = (await db.execute(select(InterviewSession.id).where(InterviewSession.job_application_id == target_app_id))).scalars().all()
            if s_ids:
                await db.execute(delete(InterviewEvaluation).where(InterviewEvaluation.interview_session_id.in_(s_ids)))
                await db.execute(delete(InterviewSession).where(InterviewSession.job_application_id == target_app_id))
            await db.execute(delete(JobApplication).where(JobApplication.id == target_app_id))
            await db.execute(delete(CVDocument).where(CVDocument.id == target_doc_id))
            await db.commit()

        # Sentinel must still exist and be intact
        transport = ASGITransport(app=fastapi_app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            res = await ac.get(f"/api/v1/job-applications/{sentinel_app_id}/interview-progress")
            assert res.status_code == 200
            assert res.json()["evaluated_attempts"] == 1
            assert res.json()["latest"]["total_score"] == 90.0
    finally:
        async with SessionLocal() as db:
            s_ids = (await db.execute(select(InterviewSession.id).where(InterviewSession.job_application_id == sentinel_app_id))).scalars().all()
            if s_ids:
                await db.execute(delete(InterviewEvaluation).where(InterviewEvaluation.interview_session_id.in_(s_ids)))
                await db.execute(delete(InterviewSession).where(InterviewSession.job_application_id == sentinel_app_id))
            await db.execute(delete(JobApplication).where(JobApplication.id == sentinel_app_id))
            await db.execute(delete(CVDocument).where(CVDocument.id == sentinel_doc_id))
            await db.commit()


@pytest.mark.asyncio
async def test_progress_half_cent_rounding_contract(sample_app):
    """Integration test verifying endpoint interview-progress strictly adheres to ROUND_HALF_UP rounding contract."""
    app_id = sample_app["app_id"]

    # Attempt 1: 26.75 / 10 = 2.675 -> 2.68 (ROUND_HALF_UP)
    # Attempt 2: 72.25 / 10 = 7.225 -> 7.23 (ROUND_HALF_UP)
    await create_attempt_with_eval(
        app_id,
        1,
        total_score=26.75,
        average_score=2.68,
        answered_count=10,
        skipped_count=0,
        readiness_level="needs_foundation",
        category_scores={"backend_fundamentals": 2.68, "database": 2.68},
    )
    await create_attempt_with_eval(
        app_id,
        2,
        total_score=72.25,
        average_score=7.23,
        answered_count=10,
        skipped_count=0,
        readiness_level="intern_ready",
        category_scores={"backend_fundamentals": 7.23, "database": 7.23},
    )

    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get(f"/api/v1/job-applications/{app_id}/interview-progress")
        assert res.status_code == 200
        data = res.json()

        assert data["evaluated_attempts"] == 2
        # Check trend item 1 (26.75 -> 2.68)
        assert data["trend"][0]["total_score"] == 26.75
        assert data["trend"][0]["average_score"] == 2.68
        # Check trend item 2 (72.25 -> 7.23)
        assert data["trend"][1]["total_score"] == 72.25
        assert data["trend"][1]["average_score"] == 7.23

        # Check latest
        assert data["latest"]["total_score"] == 72.25
        assert data["latest"]["average_score"] == 7.23

        # Check comparison deltas
        comp = data["comparison"]
        assert comp["status"] == "improved"
        latest_vs_prev = comp["latest_vs_previous"]
        assert latest_vs_prev["total_score_delta"] == 45.5
        assert latest_vs_prev["average_score_delta"] == 4.55

        # Check category progress deltas
        cat_prog = {item["category"]: item for item in data["category_progress"]}
        assert "backend_fundamentals" in cat_prog
        bf = cat_prog["backend_fundamentals"]
        assert bf["first_score"] == 2.68
        assert bf["previous_score"] == 2.68
        assert bf["latest_score"] == 7.23
        assert bf["latest_vs_previous_delta"] == 4.55
        assert bf["latest_vs_first_delta"] == 4.55


@pytest.mark.asyncio
async def test_all_tables_zero_orphan_after_progress_suite():
    from app.models.interview_response import InterviewResponse
    from app.models.interview_question import InterviewQuestion
    from app.models.interview_evaluation import InterviewResponseEvaluation
    from app.models.application_analysis import ApplicationAnalysis
    from sqlalchemy import func

    async with SessionLocal() as db:
        for model in [
            InterviewResponseEvaluation,
            InterviewEvaluation,
            InterviewResponse,
            InterviewQuestion,
            InterviewSession,
            ApplicationAnalysis,
            JobApplication,
            CVDocument,
        ]:
            count = (await db.execute(select(func.count()).select_from(model))).scalar()
            assert count == 0, f"Table {model.__tablename__} is not empty! Count: {count}"

