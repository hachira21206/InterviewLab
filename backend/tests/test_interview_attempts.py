import pytest
import pytest_asyncio
import asyncio
import uuid
from sqlalchemy import select, delete, func
from sqlalchemy.exc import IntegrityError
from app.db.session import SessionLocal

from app.models.cv_document import CVDocument, CVStatus
from app.models.job_application import JobApplication
from app.models.application_analysis import ApplicationAnalysis, AnalysisStatus
from app.models.interview_session import InterviewSession, SessionStatus
from app.models.interview_question import InterviewQuestion, QuestionCategory, QuestionDifficulty, QuestionSource
from app.models.interview_response import InterviewResponse
from app.models.interview_evaluation import (
    InterviewEvaluation,
    InterviewResponseEvaluation,
    EvaluationStatus,
    ReadinessLevel,
    EvaluationConfidence,
)
from app.services.analysis_provider import FakeAnalysisProvider
from app.core.config import settings


@pytest_asyncio.fixture(autouse=True)
def mock_ai_provider(monkeypatch):
    import app.services.interview_session
    import app.services.interview_evaluation

    fake = FakeAnalysisProvider()
    monkeypatch.setattr(settings, "AI_PROVIDER", "groq")
    monkeypatch.setattr(settings, "GROQ_API_KEY", "fake_key_task08")

    def fake_get_provider():
        from app.core.exceptions import ProviderConfigurationError
        if settings.AI_PROVIDER == "groq" and not settings.GROQ_API_KEY:
            raise ProviderConfigurationError("Chưa cấu hình GROQ_API_KEY")
        if settings.AI_PROVIDER != "groq":
            raise ProviderConfigurationError(f"Provider không hỗ trợ: {settings.AI_PROVIDER}")
        return fake

    monkeypatch.setattr(app.services.interview_session, "get_analysis_provider", fake_get_provider)
    monkeypatch.setattr(app.services.interview_evaluation, "get_analysis_provider", fake_get_provider)
    return fake


@pytest_asyncio.fixture
async def sample_application():
    doc_id = uuid.uuid4()
    app_id = uuid.uuid4()
    analysis_id = uuid.uuid4()

    async with SessionLocal() as db:
        doc = CVDocument(
            id=doc_id,
            original_filename="cv_attempts.pdf",
            storage_key=f"k_{doc_id}",
            media_type="application/pdf",
            size_bytes=100,
            sha256="abc_attempts",
            status=CVStatus.extracted,
            extracted_text="Python FastAPI PostgreSQL Docker Developer"
        )
        db.add(doc)

        job_app = JobApplication(
            id=app_id,
            cv_document_id=doc_id,
            target_role="Backend Developer Intern",
            job_description="Junior/Intern Backend Developer"
        )
        db.add(job_app)

        analysis = ApplicationAnalysis(
            id=analysis_id,
            job_application_id=app_id,
            status=AnalysisStatus.completed,
            provider="groq",
            model="llama",
            schema_version="1",
            prompt_version="1",
            analysis_data={
                "summary_vi": "Ứng viên có kiến thức nền tảng tốt.",
                "candidate_level": "junior_ready",
                "technical_skills": [],
                "projects": [],
                "education": [],
                "strengths": [],
                "gaps": [],
                "matched_requirements": [],
                "missing_requirements": [],
                "recommended_interview_topics": [],
                "language_detected": "vi",
                "warnings": []
            }
        )
        db.add(analysis)
        await db.commit()

    try:
        yield {
            "app_id": app_id,
            "doc_id": doc_id,
            "analysis_id": analysis_id,
        }
    finally:
        async with SessionLocal() as db:
            session_ids = (await db.execute(
                select(InterviewSession.id).where(InterviewSession.job_application_id == app_id)
            )).scalars().all()

            if session_ids:
                eval_ids = (await db.execute(
                    select(InterviewEvaluation.id).where(InterviewEvaluation.interview_session_id.in_(session_ids))
                )).scalars().all()
                if eval_ids:
                    await db.execute(
                        delete(InterviewResponseEvaluation).where(
                            InterviewResponseEvaluation.interview_evaluation_id.in_(eval_ids)
                        )
                    )
                    await db.execute(
                        delete(InterviewEvaluation).where(
                            InterviewEvaluation.id.in_(eval_ids)
                        )
                    )
                await db.execute(delete(InterviewResponse).where(InterviewResponse.interview_session_id.in_(session_ids)))
                await db.execute(delete(InterviewQuestion).where(InterviewQuestion.interview_session_id.in_(session_ids)))
                await db.execute(delete(InterviewSession).where(InterviewSession.job_application_id == app_id))

            await db.execute(delete(ApplicationAnalysis).where(ApplicationAnalysis.id == analysis_id))
            await db.execute(delete(JobApplication).where(JobApplication.id == app_id))
            await db.execute(delete(CVDocument).where(CVDocument.id == doc_id))
            await db.commit()


async def simulate_complete_and_evaluate_session(session_id: uuid.UUID):
    """Helper to simulate 10 responses and evaluation for a session."""
    async with SessionLocal() as db:
        questions = (await db.execute(
            select(InterviewQuestion).where(InterviewQuestion.interview_session_id == session_id).order_by(InterviewQuestion.order_index)
        )).scalars().all()

        for q in questions:
            resp = InterviewResponse(
                id=uuid.uuid4(),
                interview_session_id=session_id,
                interview_question_id=q.id,
                answer_text=f"Câu trả lời cho câu {q.order_index}.",
                is_skipped=False,
            )
            db.add(resp)

        sess = await db.get(InterviewSession, session_id)
        sess.status = SessionStatus.completed
        sess.completed_at = func.now()

        eval_rec = InterviewEvaluation(
            id=uuid.uuid4(),
            interview_session_id=session_id,
            status=EvaluationStatus.evaluated.value,
            provider="groq",
            model="llama",
            prompt_version="1",
            schema_version="1",
            readiness_level=ReadinessLevel.intern_ready.value,
            total_score=80.0,
            average_score=8.0,
            answered_count=10,
            skipped_count=0,
            overall_summary="Đánh giá tốt.",
            evaluated_at=func.now(),
        )
        db.add(eval_rec)
        await db.commit()


# 1. Test sequential attempts 1, 2, and 3
@pytest.mark.asyncio
async def test_sequential_attempts_1_2_3(client, sample_application):
    app_id = sample_application["app_id"]

    # Attempt 1
    res1 = await client.post(f"/api/v1/job-applications/{app_id}/interview-sessions/attempts", json={"consent_to_external_ai": True})
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["attempt_number"] == 1
    assert data1["status"] == "ready"
    assert len(data1["questions"]) == 10
    session_1_id = uuid.UUID(data1["id"])

    # Simulate completion of attempt 1
    await simulate_complete_and_evaluate_session(session_1_id)

    # Attempt 2
    res2 = await client.post(f"/api/v1/job-applications/{app_id}/interview-sessions/attempts", json={"consent_to_external_ai": True})
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["attempt_number"] == 2
    assert data2["status"] == "ready"
    assert data2["id"] != str(session_1_id)
    session_2_id = uuid.UUID(data2["id"])

    # Simulate completion of attempt 2
    await simulate_complete_and_evaluate_session(session_2_id)

    # Attempt 3
    res3 = await client.post(f"/api/v1/job-applications/{app_id}/interview-sessions/attempts", json={"consent_to_external_ai": True})
    assert res3.status_code == 200
    data3 = res3.json()
    assert data3["attempt_number"] == 3
    assert data3["status"] == "ready"
    assert data3["id"] not in (str(session_1_id), str(session_2_id))


# 2. Test old attempt questions, responses, and evaluation are preserved
@pytest.mark.asyncio
async def test_old_attempt_questions_responses_evaluation_preserved(client, sample_application):
    app_id = sample_application["app_id"]

    # Create & complete Attempt 1
    res1 = await client.post(f"/api/v1/job-applications/{app_id}/interview-sessions/attempts", json={"consent_to_external_ai": True})
    session_1_id = uuid.UUID(res1.json()["id"])
    await simulate_complete_and_evaluate_session(session_1_id)

    # Check Attempt 1 evaluation
    res_eval1 = await client.get(f"/api/v1/interview-sessions/{session_1_id}/evaluation")
    assert res_eval1.status_code == 200
    assert res_eval1.json()["total_score"] == 80.0

    # Create Attempt 2
    res2 = await client.post(f"/api/v1/job-applications/{app_id}/interview-sessions/attempts", json={"consent_to_external_ai": True})
    session_2_id = uuid.UUID(res2.json()["id"])

    # Verify Attempt 1 evaluation and questions are still completely unchanged
    res_eval1_after = await client.get(f"/api/v1/interview-sessions/{session_1_id}/evaluation")
    assert res_eval1_after.status_code == 200
    assert res_eval1_after.json()["total_score"] == 80.0

    async with SessionLocal() as db:
        q_count_1 = (await db.execute(
            select(func.count(InterviewQuestion.id)).where(InterviewQuestion.interview_session_id == session_1_id)
        )).scalar()
        assert q_count_1 == 10

        q_count_2 = (await db.execute(
            select(func.count(InterviewQuestion.id)).where(InterviewQuestion.interview_session_id == session_2_id)
        )).scalar()
        assert q_count_2 == 10


# 3. Cannot create attempt when active session is ready
@pytest.mark.asyncio
async def test_cannot_create_attempt_when_session_ready(client, sample_application):
    app_id = sample_application["app_id"]

    res1 = await client.post(f"/api/v1/job-applications/{app_id}/interview-sessions/attempts", json={"consent_to_external_ai": True})
    assert res1.status_code == 200
    assert res1.json()["status"] == "ready"

    # Attempt to create another while attempt 1 is ready -> 409
    res2 = await client.post(f"/api/v1/job-applications/{app_id}/interview-sessions/attempts", json={"consent_to_external_ai": True})
    assert res2.status_code == 409
    assert "Đang có phiên phỏng vấn chưa hoàn thành" in res2.json()["detail"]


# 4. Cannot create attempt when active session is in_progress
@pytest.mark.asyncio
async def test_cannot_create_attempt_when_session_in_progress(client, sample_application):
    app_id = sample_application["app_id"]

    res1 = await client.post(f"/api/v1/job-applications/{app_id}/interview-sessions/attempts", json={"consent_to_external_ai": True})
    session_id = res1.json()["id"]

    # Start session
    start_res = await client.post(f"/api/v1/interview-sessions/{session_id}/start")
    assert start_res.status_code == 200
    assert start_res.json()["status"] == "in_progress"

    # Attempt to create another while in_progress -> 409
    res2 = await client.post(f"/api/v1/job-applications/{app_id}/interview-sessions/attempts", json={"consent_to_external_ai": True})
    assert res2.status_code == 409
    assert "Đang có phiên phỏng vấn chưa hoàn thành" in res2.json()["detail"]


# 5. Retry generation_failed reuses the same attempt_number
@pytest.mark.asyncio
async def test_retry_on_generation_failed_reuses_attempt_number(client, sample_application):
    app_id = sample_application["app_id"]

    # Create attempt 1 then set it to generation_failed
    res1 = await client.post(f"/api/v1/job-applications/{app_id}/interview-sessions/attempts", json={"consent_to_external_ai": True})
    session_id = uuid.UUID(res1.json()["id"])

    async with SessionLocal() as db:
        sess = await db.get(InterviewSession, session_id)
        sess.status = SessionStatus.generation_failed
        sess.error_code = "RATE_LIMITED"
        sess.error_message = "Mock rate limited"
        await db.commit()

    # Retry attempt via legacy create_or_retry endpoint
    retry_res = await client.post(f"/api/v1/job-applications/{app_id}/interview-sessions", json={"consent_to_external_ai": True})
    assert retry_res.status_code == 200
    data = retry_res.json()
    assert data["id"] == str(session_id)
    assert data["attempt_number"] == 1
    assert data["status"] == "ready"

    # Confirm there is still only 1 session in DB
    async with SessionLocal() as db:
        count = (await db.execute(
            select(func.count(InterviewSession.id)).where(InterviewSession.job_application_id == app_id)
        )).scalar()
        assert count == 1


# 6. Concurrent attempt creation: exactly one succeeds, one 409, provider called once
@pytest.mark.asyncio
async def test_concurrent_attempt_creation(client, sample_application, mock_ai_provider):
    app_id = sample_application["app_id"]

    barrier = asyncio.Barrier(2)

    async def call_attempt():
        await barrier.wait()
        return await client.post(f"/api/v1/job-applications/{app_id}/interview-sessions/attempts", json={"consent_to_external_ai": True})

    res_a, res_b = await asyncio.gather(call_attempt(), call_attempt())

    statuses = sorted([res_a.status_code, res_b.status_code])
    assert statuses == [200, 409], f"Expected [200, 409] but got {[res_a.status_code, res_b.status_code]}"

    # Provider should be called exactly once
    assert mock_ai_provider.call_count == 1

    # Exactly one session created in DB
    async with SessionLocal() as db:
        count = (await db.execute(
            select(func.count(InterviewSession.id)).where(InterviewSession.job_application_id == app_id)
        )).scalar()
        assert count == 1


# 7. Database UNIQUE(job_application_id, attempt_number) constraint
@pytest.mark.asyncio
async def test_unique_job_app_attempt_number_constraint(sample_application):
    app_id = sample_application["app_id"]

    async with SessionLocal() as db:
        s1 = InterviewSession(
            id=uuid.uuid4(),
            job_application_id=app_id,
            attempt_number=1,
            status=SessionStatus.completed,
            provider="groq",
            model="llama",
            prompt_version="1",
            schema_version="1",
        )
        db.add(s1)
        await db.commit()

        s2 = InterviewSession(
            id=uuid.uuid4(),
            job_application_id=app_id,
            attempt_number=1,  # Duplicate attempt number!
            status=SessionStatus.completed,
            provider="groq",
            model="llama",
            prompt_version="1",
            schema_version="1",
        )
        db.add(s2)
        with pytest.raises(IntegrityError):
            await db.commit()
        await db.rollback()


# 8. PostgreSQL partial unique index prevents two active attempts
@pytest.mark.asyncio
async def test_partial_unique_index_prevents_two_active_attempts(sample_application):
    app_id = sample_application["app_id"]

    async with SessionLocal() as db:
        s1 = InterviewSession(
            id=uuid.uuid4(),
            job_application_id=app_id,
            attempt_number=1,
            status=SessionStatus.ready,
            provider="groq",
            model="llama",
            prompt_version="1",
            schema_version="1",
        )
        db.add(s1)
        await db.commit()

        s2 = InterviewSession(
            id=uuid.uuid4(),
            job_application_id=app_id,
            attempt_number=2,  # Different attempt number but both are active!
            status=SessionStatus.generating,
            provider="groq",
            model="llama",
            prompt_version="1",
            schema_version="1",
        )
        db.add(s2)
        with pytest.raises(IntegrityError):
            await db.commit()
        await db.rollback()


# 9. History ordering and pagination
@pytest.mark.asyncio
async def test_history_ordering_and_pagination(client, sample_application):
    app_id = sample_application["app_id"]

    # Create 3 completed attempts
    for i in range(1, 4):
        res = await client.post(f"/api/v1/job-applications/{app_id}/interview-sessions/attempts", json={"consent_to_external_ai": True})
        session_id = uuid.UUID(res.json()["id"])
        await simulate_complete_and_evaluate_session(session_id)

    # 1. Full list: check descending attempt_number
    res_full = await client.get(f"/api/v1/job-applications/{app_id}/interview-sessions")
    assert res_full.status_code == 200
    data_full = res_full.json()
    assert data_full["total"] == 3
    assert len(data_full["items"]) == 3
    assert [item["attempt_number"] for item in data_full["items"]] == [3, 2, 1]

    # Verify each history item summary fields
    for item in data_full["items"]:
        assert item["status"] == "completed"
        assert item["question_count"] == 10
        assert item["answered_count"] == 10
        assert item["skipped_count"] == 0
        assert item["total_score"] == 80.0
        assert item["average_score"] == 8.0
        assert item["readiness_level"] == "intern_ready"
        assert item["completed_at"] is not None
        assert item["evaluated_at"] is not None
        # Sensitive fields must NOT exist
        assert "expected_key_points" not in item
        assert "purpose" not in item
        assert "source" not in item
        assert "source_evidence" not in item
        assert "answer_text" not in item

    # 2. Pagination: limit=2, offset=0
    res_page1 = await client.get(f"/api/v1/job-applications/{app_id}/interview-sessions?limit=2&offset=0")
    assert res_page1.status_code == 200
    data_page1 = res_page1.json()
    assert len(data_page1["items"]) == 2
    assert [item["attempt_number"] for item in data_page1["items"]] == [3, 2]

    # 3. Pagination: limit=2, offset=2
    res_page2 = await client.get(f"/api/v1/job-applications/{app_id}/interview-sessions?limit=2&offset=2")
    assert res_page2.status_code == 200
    data_page2 = res_page2.json()
    assert len(data_page2["items"]) == 1
    assert [item["attempt_number"] for item in data_page2["items"]] == [1]


# 10. Current session semantics (prioritizes active, falls back to latest completed)
@pytest.mark.asyncio
async def test_current_session_semantics(client, sample_application):
    app_id = sample_application["app_id"]

    # When no session exists -> 404
    res_none = await client.get(f"/api/v1/job-applications/{app_id}/interview-sessions/current")
    assert res_none.status_code == 404

    # Create attempt 1 and complete it
    res1 = await client.post(f"/api/v1/job-applications/{app_id}/interview-sessions/attempts", json={"consent_to_external_ai": True})
    session_1_id = uuid.UUID(res1.json()["id"])
    await simulate_complete_and_evaluate_session(session_1_id)

    # When all completed, current returns latest completed attempt
    res_cur1 = await client.get(f"/api/v1/job-applications/{app_id}/interview-sessions/current")
    assert res_cur1.status_code == 200
    assert res_cur1.json()["attempt_number"] == 1
    assert res_cur1.json()["status"] == "completed"

    # Create attempt 2 (status=ready, active)
    res2 = await client.post(f"/api/v1/job-applications/{app_id}/interview-sessions/attempts", json={"consent_to_external_ai": True})
    session_2_id = res2.json()["id"]

    # Current must prioritize active attempt 2!
    res_cur2 = await client.get(f"/api/v1/job-applications/{app_id}/interview-sessions/current")
    assert res_cur2.status_code == 200
    assert res_cur2.json()["attempt_number"] == 2
    assert res_cur2.json()["id"] == session_2_id
    assert res_cur2.json()["status"] == "ready"


# 11. Cascade delete JobApplication deletes all attempts and child records
@pytest.mark.asyncio
async def test_cascade_delete_job_application_deletes_all_attempts(client, sample_application):
    app_id = sample_application["app_id"]

    res1 = await client.post(f"/api/v1/job-applications/{app_id}/interview-sessions/attempts", json={"consent_to_external_ai": True})
    session_1_id = uuid.UUID(res1.json()["id"])
    await simulate_complete_and_evaluate_session(session_1_id)

    res2 = await client.post(f"/api/v1/job-applications/{app_id}/interview-sessions/attempts", json={"consent_to_external_ai": True})
    session_2_id = uuid.UUID(res2.json()["id"])
    await simulate_complete_and_evaluate_session(session_2_id)

    # Delete JobApplication
    async with SessionLocal() as db:
        await db.execute(delete(JobApplication).where(JobApplication.id == app_id))
        await db.commit()

        # Confirm all attempts and children are deleted by ON DELETE CASCADE
        sessions_count = (await db.execute(
            select(func.count(InterviewSession.id)).where(InterviewSession.job_application_id == app_id)
        )).scalar()
        assert sessions_count == 0

        evals_count = (await db.execute(
            select(func.count(InterviewEvaluation.id)).where(InterviewEvaluation.interview_session_id.in_([session_1_id, session_2_id]))
        )).scalar()
        assert evals_count == 0

        q_count = (await db.execute(
            select(func.count(InterviewQuestion.id)).where(InterviewQuestion.interview_session_id.in_([session_1_id, session_2_id]))
        )).scalar()
        assert q_count == 0


# 12. Public responses must never leak secret markers or sensitive keys
@pytest.mark.asyncio
async def test_no_sensitive_leakage_in_public_responses_and_history(client, sample_application):
    app_id = sample_application["app_id"]

    res = await client.post(f"/api/v1/job-applications/{app_id}/interview-sessions/attempts", json={"consent_to_external_ai": True})
    session_id = uuid.UUID(res.json()["id"])
    await simulate_complete_and_evaluate_session(session_id)

    # History response
    hist_res = await client.get(f"/api/v1/job-applications/{app_id}/interview-sessions")
    hist_text = hist_res.text
    assert "expected_key_points" not in hist_text
    assert "source_evidence" not in hist_text
    assert "answer_text" not in hist_text

    # Current response
    cur_res = await client.get(f"/api/v1/job-applications/{app_id}/interview-sessions/current")
    cur_text = cur_res.text
    assert "expected_key_points" not in cur_text
    assert "source_evidence" not in cur_text


# 13. Sentinel isolation test across applications
@pytest.mark.asyncio
async def test_sentinel_isolation_across_applications(client, sample_application):
    target_app_id = sample_application["app_id"]

    # 1. Create a sentinel application with 2 attempts
    sentinel_doc_id = uuid.uuid4()
    sentinel_app_id = uuid.uuid4()
    sentinel_analysis_id = uuid.uuid4()

    async with SessionLocal() as db:
        doc = CVDocument(
            id=sentinel_doc_id,
            original_filename="sentinel.pdf",
            storage_key=f"k_{sentinel_doc_id}",
            media_type="application/pdf",
            size_bytes=100,
            sha256="sha_sentinel",
            status=CVStatus.extracted,
            extracted_text="Sentinel CV"
        )
        db.add(doc)
        job_app = JobApplication(
            id=sentinel_app_id,
            cv_document_id=sentinel_doc_id,
            target_role="Backend Intern",
            job_description="Sentinel JD"
        )
        db.add(job_app)
        valid_sentinel_analysis = {
            "summary_vi": "Sentinel candidate analysis summary",
            "candidate_level": "junior_ready",
            "technical_skills": [],
            "projects": [],
            "education": [],
            "strengths": [],
            "gaps": [],
            "matched_requirements": [],
            "missing_requirements": [],
            "recommended_interview_topics": [],
            "language_detected": "vi",
            "warnings": []
        }
        analysis = ApplicationAnalysis(
            id=sentinel_analysis_id,
            job_application_id=sentinel_app_id,
            status=AnalysisStatus.completed,
            provider="groq",
            model="llama",
            schema_version="1",
            prompt_version="1",
            analysis_data=valid_sentinel_analysis
        )
        db.add(analysis)
        await db.commit()

    sentinel_s1_id = None
    sentinel_s2_id = None
    try:
        # Create attempt 1 and 2 for sentinel
        res_s1 = await client.post(f"/api/v1/job-applications/{sentinel_app_id}/interview-sessions/attempts", json={"consent_to_external_ai": True})
        assert res_s1.status_code == 200, f"res_s1 failed: {res_s1.text}"
        sentinel_s1_id = uuid.UUID(res_s1.json()["id"])
        await simulate_complete_and_evaluate_session(sentinel_s1_id)

        res_s2 = await client.post(f"/api/v1/job-applications/{sentinel_app_id}/interview-sessions/attempts", json={"consent_to_external_ai": True})
        assert res_s2.status_code == 200, f"res_s2 failed: {res_s2.text}"
        sentinel_s2_id = uuid.UUID(res_s2.json()["id"])
        await simulate_complete_and_evaluate_session(sentinel_s2_id)

        # Create attempt for target application
        res_t1 = await client.post(f"/api/v1/job-applications/{target_app_id}/interview-sessions/attempts", json={"consent_to_external_ai": True})
        assert res_t1.status_code == 200, f"res_t1 failed: {res_t1.text}"
        target_s1_id = uuid.UUID(res_t1.json()["id"])
        await simulate_complete_and_evaluate_session(target_s1_id)

        # Simulate cleanup of target application ONLY
        async with SessionLocal() as db:
            eval_ids = (await db.execute(
                select(InterviewEvaluation.id).where(InterviewEvaluation.interview_session_id == target_s1_id)
            )).scalars().all()
            if eval_ids:
                await db.execute(delete(InterviewResponseEvaluation).where(InterviewResponseEvaluation.interview_evaluation_id.in_(eval_ids)))
                await db.execute(delete(InterviewEvaluation).where(InterviewEvaluation.id.in_(eval_ids)))
            await db.execute(delete(InterviewResponse).where(InterviewResponse.interview_session_id == target_s1_id))
            await db.execute(delete(InterviewQuestion).where(InterviewQuestion.interview_session_id == target_s1_id))
            await db.execute(delete(InterviewSession).where(InterviewSession.id == target_s1_id))
            await db.commit()

        # Sentinel attempts and history must remain completely unaffected!
        sentinel_hist = await client.get(f"/api/v1/job-applications/{sentinel_app_id}/interview-sessions")
        assert sentinel_hist.status_code == 200
        assert sentinel_hist.json()["total"] == 2
        assert [item["attempt_number"] for item in sentinel_hist.json()["items"]] == [2, 1]

    finally:
        # Clean sentinel data by exact IDs
        async with SessionLocal() as db:
            s_ids = [s for s in [sentinel_s1_id, sentinel_s2_id] if s is not None]
            if s_ids:
                e_ids = (await db.execute(
                    select(InterviewEvaluation.id).where(InterviewEvaluation.interview_session_id.in_(s_ids))
                )).scalars().all()
                if e_ids:
                    await db.execute(delete(InterviewResponseEvaluation).where(InterviewResponseEvaluation.interview_evaluation_id.in_(e_ids)))
                    await db.execute(delete(InterviewEvaluation).where(InterviewEvaluation.id.in_(e_ids)))
                await db.execute(delete(InterviewResponse).where(InterviewResponse.interview_session_id.in_(s_ids)))
                await db.execute(delete(InterviewQuestion).where(InterviewQuestion.interview_session_id.in_(s_ids)))
            await db.execute(delete(InterviewSession).where(InterviewSession.job_application_id == sentinel_app_id))
            await db.execute(delete(ApplicationAnalysis).where(ApplicationAnalysis.id == sentinel_analysis_id))
            await db.execute(delete(JobApplication).where(JobApplication.id == sentinel_app_id))
            await db.execute(delete(CVDocument).where(CVDocument.id == sentinel_doc_id))
            await db.commit()


# ==============================================================================
# Task 08A Tests: Provider Precedence, Schema Strictness, Concurrency
# ==============================================================================

# 1. Ready session returns without API key and without calling provider
@pytest.mark.asyncio
async def test_provider_precedence_ready_session_returns_without_api_key(client, sample_application, mock_ai_provider, monkeypatch):
    app_id = sample_application["app_id"]
    # Create initial ready session using valid fake provider
    res = await client.post(f"/api/v1/job-applications/{app_id}/interview-sessions/attempts", json={"consent_to_external_ai": True})
    assert res.status_code == 200
    assert res.json()["status"] == "ready"
    initial_call_count = mock_ai_provider.call_count

    # Empty API key
    monkeypatch.setattr(settings, "GROQ_API_KEY", "")

    # Legacy endpoint should return 200 ready session without touching provider
    res2 = await client.post(f"/api/v1/job-applications/{app_id}/interview-sessions", json={"consent_to_external_ai": True})
    assert res2.status_code == 200
    assert res2.json()["id"] == res.json()["id"]
    assert res2.json()["status"] == "ready"
    assert mock_ai_provider.call_count == initial_call_count


# 2. Attempts endpoint returns 409 when ready even if API key is empty
@pytest.mark.asyncio
async def test_provider_precedence_attempts_returns_409_when_ready_and_api_key_empty(client, sample_application, monkeypatch):
    app_id = sample_application["app_id"]
    res = await client.post(f"/api/v1/job-applications/{app_id}/interview-sessions/attempts", json={"consent_to_external_ai": True})
    assert res.status_code == 200

    monkeypatch.setattr(settings, "GROQ_API_KEY", "")

    res2 = await client.post(f"/api/v1/job-applications/{app_id}/interview-sessions/attempts", json={"consent_to_external_ai": True})
    assert res2.status_code == 409
    assert "Đang có phiên phỏng vấn chưa hoàn thành" in res2.json()["detail"]


# 3. Attempts endpoint returns 409 when in_progress or generating even if API key is empty
@pytest.mark.asyncio
async def test_provider_precedence_attempts_returns_409_when_active_and_api_key_empty(client, sample_application, monkeypatch):
    app_id = sample_application["app_id"]
    res = await client.post(f"/api/v1/job-applications/{app_id}/interview-sessions/attempts", json={"consent_to_external_ai": True})
    session_id = res.json()["id"]

    start_res = await client.post(f"/api/v1/interview-sessions/{session_id}/start")
    assert start_res.status_code == 200

    monkeypatch.setattr(settings, "GROQ_API_KEY", "")

    res2 = await client.post(f"/api/v1/job-applications/{app_id}/interview-sessions/attempts", json={"consent_to_external_ai": True})
    assert res2.status_code == 409
    assert "Đang có phiên phỏng vấn chưa hoàn thành" in res2.json()["detail"]


# 4. Nonexistent app returns 404 even if API key is empty (not masked by 503)
@pytest.mark.asyncio
async def test_provider_precedence_nonexistent_app_returns_404_when_api_key_empty(client, monkeypatch):
    monkeypatch.setattr(settings, "GROQ_API_KEY", "")
    random_app_id = uuid.uuid4()
    res = await client.post(f"/api/v1/job-applications/{random_app_id}/interview-sessions/attempts", json={"consent_to_external_ai": True})
    assert res.status_code == 404
    assert "Không tìm thấy hồ sơ ứng tuyển" in res.json()["detail"]


# 5. Incomplete analysis returns 409 even if API key is empty (not masked by 503)
@pytest.mark.asyncio
async def test_provider_precedence_incomplete_analysis_returns_409_when_api_key_empty(client, sample_application, monkeypatch):
    app_id = sample_application["app_id"]
    analysis_id = sample_application["analysis_id"]

    # Set analysis to pending
    async with SessionLocal() as db:
        analysis = await db.get(ApplicationAnalysis, analysis_id)
        analysis.status = AnalysisStatus.pending
        await db.commit()

    monkeypatch.setattr(settings, "GROQ_API_KEY", "")

    try:
        res = await client.post(f"/api/v1/job-applications/{app_id}/interview-sessions/attempts", json={"consent_to_external_ai": True})
        assert res.status_code == 409
        assert "CV chưa được phân tích thành công" in res.json()["detail"]
    finally:
        async with SessionLocal() as db:
            analysis = await db.get(ApplicationAnalysis, analysis_id)
            analysis.status = AnalysisStatus.completed
            await db.commit()


# 6. Retry generation_failed with missing API key returns 503 and preserves row status and error
@pytest.mark.asyncio
async def test_provider_precedence_retry_generation_failed_missing_api_key_returns_503_and_preserves_row(client, sample_application, monkeypatch):
    app_id = sample_application["app_id"]
    res = await client.post(f"/api/v1/job-applications/{app_id}/interview-sessions/attempts", json={"consent_to_external_ai": True})
    session_id = uuid.UUID(res.json()["id"])

    async with SessionLocal() as db:
        sess = await db.get(InterviewSession, session_id)
        sess.status = SessionStatus.generation_failed
        sess.error_code = "ORIGINAL_ERROR"
        sess.error_message = "Original failure message"
        await db.commit()

    monkeypatch.setattr(settings, "GROQ_API_KEY", "")

    retry_res = await client.post(f"/api/v1/job-applications/{app_id}/interview-sessions", json={"consent_to_external_ai": True})
    assert retry_res.status_code == 503
    assert "Chưa cấu hình GROQ_API_KEY" in retry_res.json()["detail"]

    # Verify DB row is still generation_failed with original error intact
    async with SessionLocal() as db:
        sess = await db.get(InterviewSession, session_id)
        assert sess.status == SessionStatus.generation_failed
        assert sess.error_code == "ORIGINAL_ERROR"
        assert sess.error_message == "Original failure message"


# 7. No attempt with missing API key returns 503 and does NOT create row
@pytest.mark.asyncio
async def test_provider_precedence_no_attempt_missing_api_key_returns_503_and_no_row_created(client, sample_application, monkeypatch):
    app_id = sample_application["app_id"]
    monkeypatch.setattr(settings, "GROQ_API_KEY", "")

    res = await client.post(f"/api/v1/job-applications/{app_id}/interview-sessions/attempts", json={"consent_to_external_ai": True})
    assert res.status_code == 503
    assert "Chưa cấu hình GROQ_API_KEY" in res.json()["detail"]

    # Verify no row created
    async with SessionLocal() as db:
        count = (await db.execute(
            select(func.count(InterviewSession.id)).where(InterviewSession.job_application_id == app_id)
        )).scalar()
        assert count == 0


# 8. CreateSessionRequest extra fields return 422
@pytest.mark.asyncio
async def test_create_session_request_extra_field_returns_422(client, sample_application):
    app_id = sample_application["app_id"]
    res = await client.post(
        f"/api/v1/job-applications/{app_id}/interview-sessions/attempts",
        json={"consent_to_external_ai": True, "extra_unexpected_field": "disallowed"}
    )
    assert res.status_code == 422


# 9. InterviewHistory schemas strict validation
def test_interview_history_schemas_strict_validation():
    from pydantic import ValidationError
    from app.schemas.interview_questions import InterviewHistoryItem, InterviewHistoryListResponse
    from datetime import datetime, timezone

    valid_payload = {
        "id": uuid.uuid4(),
        "job_application_id": uuid.uuid4(),
        "attempt_number": 1,
        "status": "completed",
        "question_count": 10,
        "answered_count": 8,
        "skipped_count": 2,
        "readiness_level": "intern_ready",
        "total_score": 85.5,
        "average_score": 8.55,
        "created_at": datetime.now(timezone.utc),
        "completed_at": datetime.now(timezone.utc),
        "evaluated_at": datetime.now(timezone.utc)
    }
    item = InterviewHistoryItem(**valid_payload)
    assert item.attempt_number == 1
    assert item.readiness_level == ReadinessLevel.intern_ready

    # Extra field forbidden on item
    with pytest.raises(ValidationError):
        InterviewHistoryItem(**{**valid_payload, "extra_field": "invalid"})

    # Invalid question count > 10
    with pytest.raises(ValidationError):
        InterviewHistoryItem(**{**valid_payload, "question_count": 11})

    # Invalid attempt_number < 1
    with pytest.raises(ValidationError):
        InterviewHistoryItem(**{**valid_payload, "attempt_number": 0})

    # Extra field forbidden on list response
    with pytest.raises(ValidationError):
        InterviewHistoryListResponse(
            items=[item],
            total=1,
            limit=20,
            offset=0,
            forbidden_extra="bad"
        )

    # Limit > 50 rejected
    with pytest.raises(ValidationError):
        InterviewHistoryListResponse(
            items=[item],
            total=1,
            limit=51,
            offset=0
        )


# 10. Concurrent create attempts: exactly 1 succeeds, 1 409, provider called once
@pytest.mark.asyncio
async def test_concurrent_create_attempts_single_success_single_provider_call(client, sample_application, mock_ai_provider):
    app_id = sample_application["app_id"]
    initial_calls = mock_ai_provider.call_count

    res1, res2 = await asyncio.gather(
        client.post(f"/api/v1/job-applications/{app_id}/interview-sessions/attempts", json={"consent_to_external_ai": True}),
        client.post(f"/api/v1/job-applications/{app_id}/interview-sessions/attempts", json={"consent_to_external_ai": True}),
        return_exceptions=False
    )

    statuses = [res1.status_code, res2.status_code]
    assert 200 in statuses
    assert 409 in statuses
    assert mock_ai_provider.call_count == initial_calls + 1


# 14. Zero-orphan verification at the end
@pytest.mark.asyncio
async def test_all_tables_zero_orphan_after_attempts_test(client):
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
