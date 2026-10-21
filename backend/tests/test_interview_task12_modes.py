import uuid
import pytest
from sqlalchemy import select, func, delete
from httpx import AsyncClient

from app.db.session import SessionLocal
from app.models.job_application import JobApplication
from app.models.cv_document import CVDocument, CVStatus
from app.models.application_analysis import ApplicationAnalysis, AnalysisStatus
from app.models.interview_session import InterviewSession, SessionStatus, PracticeMode
from app.models.interview_question import InterviewQuestion, QuestionCategory, QuestionDifficulty, QuestionSource
from app.models.interview_response import InterviewResponse
from app.models.interview_evaluation import InterviewEvaluation, InterviewResponseEvaluation, EvaluationStatus
from app.schemas.interview_questions import InterviewQuestionSet, InterviewQuestionGenerated
from app.core.config import settings
from app.services.analysis_provider import (
    get_analysis_provider,
    FakeAnalysisProvider,
    InterviewQuestionsResult,
    InterviewEvaluationResult
)


@pytest.fixture
def mock_ai_provider(monkeypatch):
    import app.services.interview_session
    import app.services.interview_evaluation
    provider = FakeAnalysisProvider()
    monkeypatch.setattr(settings, "AI_PROVIDER", "groq")
    monkeypatch.setattr(settings, "GROQ_API_KEY", "fake_key_task12")
    monkeypatch.setattr(app.services.interview_session, "get_analysis_provider", lambda: provider)
    monkeypatch.setattr(app.services.interview_evaluation, "get_analysis_provider", lambda: provider)
    return provider


@pytest.fixture
async def sample_application():
    doc_id = uuid.uuid4()
    app_id = uuid.uuid4()
    analysis_id = uuid.uuid4()

    async with SessionLocal() as db:
        doc = CVDocument(
            id=doc_id,
            original_filename="cv_modes.pdf",
            storage_key=f"k_{doc_id}",
            media_type="application/pdf",
            size_bytes=100,
            sha256="abc_modes",
            status=CVStatus.extracted,
            extracted_text="Python FastAPI PostgreSQL Docker Developer"
        )
        db.add(doc)

        job_app = JobApplication(
            id=app_id,
            cv_document_id=doc_id,
            target_role="Backend Developer Intern",
            job_description="Junior/Intern Backend Developer with Python and PostgreSQL knowledge"
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
                "summary_vi": "Ứng viên có kiến thức nền tảng Backend.",
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

    yield {"app_id": app_id, "doc_id": doc_id, "analysis_id": analysis_id}

    async with SessionLocal() as db:
        session_ids = (await db.execute(
            select(InterviewSession.id).where(InterviewSession.job_application_id == app_id)
        )).scalars().all()

        if session_ids:
            eval_ids = (await db.execute(
                select(InterviewEvaluation.id).where(InterviewEvaluation.interview_session_id.in_(session_ids))
            )).scalars().all()
            if eval_ids:
                await db.execute(delete(InterviewResponseEvaluation).where(InterviewResponseEvaluation.interview_evaluation_id.in_(eval_ids)))
                await db.execute(delete(InterviewEvaluation).where(InterviewEvaluation.id.in_(eval_ids)))

            await db.execute(delete(InterviewResponse).where(InterviewResponse.interview_session_id.in_(session_ids)))
            await db.execute(delete(InterviewQuestion).where(InterviewQuestion.interview_session_id.in_(session_ids)))
            await db.execute(delete(InterviewSession).where(InterviewSession.id.in_(session_ids)))

        await db.execute(delete(ApplicationAnalysis).where(ApplicationAnalysis.id == analysis_id))
        await db.execute(delete(JobApplication).where(JobApplication.id == app_id))
        await db.execute(delete(CVDocument).where(CVDocument.id == doc_id))
        await db.commit()


@pytest.mark.asyncio
async def test_full_mock_maintains_exact_behavior(client: AsyncClient, sample_application, mock_ai_provider):
    app_id = sample_application["app_id"]

    res = await client.post(
        f"/api/v1/job-applications/{app_id}/interview-sessions",
        json={"consent_to_external_ai": True, "practice_mode": "full_mock"}
    )
    assert res.status_code == 200, res.text
    data = res.json()

    assert data["practice_mode"] == "full_mock"
    assert data["focus_category"] is None
    assert data["practice_mode_label"] == "Phỏng vấn tổng hợp"
    assert data["focus_category_label"] is None
    assert data["mode_display_title"] == "Lần 1 · Phỏng vấn tổng hợp"
    assert len(data["questions"]) == 10

    # Verify no leakage of expected_key_points
    for q in data["questions"]:
        assert "expected_key_points" not in q
        assert "source_evidence" not in q


@pytest.mark.asyncio
async def test_focus_category_valid_distribution(client: AsyncClient, sample_application, mock_ai_provider):
    app_id = sample_application["app_id"]

    res = await client.post(
        f"/api/v1/job-applications/{app_id}/interview-sessions",
        json={
            "consent_to_external_ai": True,
            "practice_mode": "focus_category",
            "focus_category": "database"
        }
    )
    assert res.status_code == 200, res.text
    data = res.json()

    assert data["practice_mode"] == "focus_category"
    assert data["focus_category"] == "database"
    assert data["practice_mode_label"] == "Luyện theo chuyên đề"
    assert data["focus_category_label"] == "Cơ sở dữ liệu & SQL"
    assert data["mode_display_title"] == "Lần 1 · Luyện Database"
    assert len(data["questions"]) == 10

    # Count categories and difficulties
    cats = [q["category"] for q in data["questions"]]
    diffs = [q["difficulty"] for q in data["questions"]]

    assert cats.count("database") == 5
    for other_cat in [
        "backend_fundamentals", "cv_project_experience",
        "api_web_design", "debugging_problem_solving", "behavioral_teamwork"
    ]:
        assert cats.count(other_cat) == 1

    assert diffs.count("easy") == 4
    assert diffs.count("medium") == 4
    assert diffs.count("hard") == 2

    # Database questions difficulty breakdown
    db_diffs = [q["difficulty"] for q in data["questions"] if q["category"] == "database"]
    assert db_diffs.count("easy") == 2
    assert db_diffs.count("medium") == 2
    assert db_diffs.count("hard") == 1


@pytest.mark.asyncio
async def test_focus_category_validation_errors(client: AsyncClient, sample_application, mock_ai_provider):
    app_id = sample_application["app_id"]

    # 1. Invalid category string
    res1 = await client.post(
        f"/api/v1/job-applications/{app_id}/interview-sessions",
        json={
            "consent_to_external_ai": True,
            "practice_mode": "focus_category",
            "focus_category": "non_existent_category"
        }
    )
    assert res1.status_code == 422

    # 2. Missing focus_category in focus mode
    res2 = await client.post(
        f"/api/v1/job-applications/{app_id}/interview-sessions",
        json={
            "consent_to_external_ai": True,
            "practice_mode": "focus_category"
        }
    )
    assert res2.status_code == 422

    # 3. full_mock with focus_category
    res3 = await client.post(
        f"/api/v1/job-applications/{app_id}/interview-sessions",
        json={
            "consent_to_external_ai": True,
            "practice_mode": "full_mock",
            "focus_category": "database"
        }
    )
    assert res3.status_code == 422

    # 4. weakness_recovery with client-specified focus_category
    res4 = await client.post(
        f"/api/v1/job-applications/{app_id}/interview-sessions",
        json={
            "consent_to_external_ai": True,
            "practice_mode": "weakness_recovery",
            "focus_category": "database"
        }
    )
    assert res4.status_code == 422


@pytest.mark.asyncio
async def test_weakness_recovery_insufficient_history_returns_409(client: AsyncClient, sample_application, mock_ai_provider):
    app_id = sample_application["app_id"]

    initial_calls = mock_ai_provider.call_count

    res = await client.post(
        f"/api/v1/job-applications/{app_id}/interview-sessions",
        json={
            "consent_to_external_ai": True,
            "practice_mode": "weakness_recovery"
        }
    )
    assert res.status_code == 409
    assert "Chưa có đủ lịch sử đánh giá" in res.json()["detail"]

    # Verify AI provider was NEVER called
    assert mock_ai_provider.call_count == initial_calls

    # Verify no dirty session row was created
    async with SessionLocal() as db:
        sessions = (await db.execute(
            select(InterviewSession).where(InterviewSession.job_application_id == app_id)
        )).scalars().all()
        assert len(sessions) == 0


@pytest.mark.asyncio
async def test_weakness_recommendation_endpoint(client: AsyncClient, sample_application):
    app_id = sample_application["app_id"]

    # 1. Before any evaluated session: recommendation is not available
    res1 = await client.get(f"/api/v1/job-applications/{app_id}/interview-sessions/weakness-recommendation")
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["available"] is False
    assert data1["category"] is None
    assert data1["evaluated_sessions_count"] == 0

    # 2. Insert a completed session with evaluation
    async with SessionLocal() as db:
        sess = InterviewSession(
            id=uuid.uuid4(),
            job_application_id=app_id,
            attempt_number=1,
            status=SessionStatus.completed,
            practice_mode="full_mock",
            provider="groq",
            model="llama",
            prompt_version="1.0.0",
            schema_version="1.0.0"
        )
        db.add(sess)
        await db.flush()

        eval_rec = InterviewEvaluation(
            id=uuid.uuid4(),
            interview_session_id=sess.id,
            status=EvaluationStatus.evaluated,
            provider="groq",
            model="llama",
            prompt_version="1.0.0",
            schema_version="1.0.0",
            total_score=65.0,
            average_score=6.5,
            category_scores={
                "backend_fundamentals": 7.0,
                "cv_project_experience": 8.0,
                "database": 4.5,
                "api_web_design": 6.0,
                "debugging_problem_solving": 7.5,
                "behavioral_teamwork": 8.5
            }
        )
        db.add(eval_rec)
        await db.commit()

    res2 = await client.get(f"/api/v1/job-applications/{app_id}/interview-sessions/weakness-recommendation")
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["available"] is True
    assert data2["category"] == "database"
    assert data2["category_label"] == "Cơ sở dữ liệu & SQL"
    assert data2["average_score"] == 4.5
    assert data2["evaluated_sessions_count"] == 1


@pytest.mark.asyncio
async def test_weakness_recovery_selects_lowest_category_and_tie_breaking(client: AsyncClient, sample_application, mock_ai_provider):
    app_id = sample_application["app_id"]

    # 1. Setup completed session where api_web_design has the lowest score (3.5)
    async with SessionLocal() as db:
        sess = InterviewSession(
            id=uuid.uuid4(),
            job_application_id=app_id,
            attempt_number=1,
            status=SessionStatus.completed,
            practice_mode="full_mock",
            provider="groq",
            model="llama",
            prompt_version="1.0.0",
            schema_version="1.0.0"
        )
        db.add(sess)
        await db.flush()

        eval_rec = InterviewEvaluation(
            id=uuid.uuid4(),
            interview_session_id=sess.id,
            status=EvaluationStatus.evaluated,
            provider="groq",
            model="llama",
            prompt_version="1.0.0",
            schema_version="1.0.0",
            total_score=60.0,
            average_score=6.0,
            category_scores={
                "backend_fundamentals": 6.0,
                "cv_project_experience": 8.0,
                "database": 5.0,
                "api_web_design": 3.5,
                "debugging_problem_solving": 7.0,
                "behavioral_teamwork": 8.0
            }
        )
        db.add(eval_rec)
        await db.commit()

    # Create new attempt using weakness_recovery
    res = await client.post(
        f"/api/v1/job-applications/{app_id}/interview-sessions/attempts",
        json={
            "consent_to_external_ai": True,
            "practice_mode": "weakness_recovery"
        }
    )
    assert res.status_code == 200, res.text
    data = res.json()

    assert data["attempt_number"] == 2
    assert data["practice_mode"] == "weakness_recovery"
    assert data["focus_category"] == "api_web_design"
    assert data["practice_mode_label"] == "Luyện bù điểm yếu"
    assert data["mode_display_title"] == "Lần 2 · Bù điểm yếu: API & Web Design"

    # Verify questions focus on api_web_design
    cats = [q["category"] for q in data["questions"]]
    assert cats.count("api_web_design") == 5

    # 2. Test deterministic tie-breaking:
    # If backend_fundamentals and database both tie at 3.0:
    # CATEGORY_TIE_BREAK_PRIORITY prioritizes backend_fundamentals (index 0 < index 1)
    async with SessionLocal() as db:
        # Mark attempt 2 completed with tied scores
        sess2 = (await db.execute(
            select(InterviewSession).where(InterviewSession.id == uuid.UUID(data["id"]))
        )).scalars().first()
        sess2.status = SessionStatus.completed

        eval_rec2 = InterviewEvaluation(
            id=uuid.uuid4(),
            interview_session_id=sess2.id,
            status=EvaluationStatus.evaluated,
            provider="groq",
            model="llama",
            prompt_version="1.0.0",
            schema_version="1.0.0",
            total_score=50.0,
            average_score=5.0,
            category_scores={
                "backend_fundamentals": 3.0,
                "cv_project_experience": 8.0,
                "database": 4.0,
                "api_web_design": 9.0,
                "debugging_problem_solving": 7.0,
                "behavioral_teamwork": 8.0
            }
        )
        db.add(eval_rec2)
        await db.commit()

    res_tie = await client.post(
        f"/api/v1/job-applications/{app_id}/interview-sessions/attempts",
        json={
            "consent_to_external_ai": True,
            "practice_mode": "weakness_recovery"
        }
    )
    assert res_tie.status_code == 200, res_tie.text
    data_tie = res_tie.json()

    # backend_fundamentals has tie-break priority over database
    assert data_tie["attempt_number"] == 3
    assert data_tie["practice_mode"] == "weakness_recovery"
    assert data_tie["focus_category"] == "backend_fundamentals"
    assert data_tie["mode_display_title"] == "Lần 3 · Bù điểm yếu: Nền tảng Backend"


@pytest.mark.asyncio
async def test_provider_invalid_distribution_safely_fails(client: AsyncClient, sample_application, mock_ai_provider):
    app_id = sample_application["app_id"]

    # Configure mock provider to return an invalid distribution (all 10 database questions)
    bad_questions = []
    for i in range(10):
        bad_questions.append(InterviewQuestionGenerated(
            question_text=f"Question text {i} for testing",
            category=QuestionCategory.database,
            difficulty=QuestionDifficulty.easy,
            purpose="Testing purpose",
            expected_key_points=["Key point 1"],
            source=QuestionSource.general_backend,
            source_evidence=None
        ))
    mock_ai_provider.mock_questions_result = InterviewQuestionsResult(
        data=InterviewQuestionSet(questions=bad_questions),
        error_code=None,
        error_message=None
    )

    res = await client.post(
        f"/api/v1/job-applications/{app_id}/interview-sessions",
        json={
            "consent_to_external_ai": True,
            "practice_mode": "focus_category",
            "focus_category": "database"
        }
    )
    # The endpoint catches the error and marks session as generation_failed
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "generation_failed"
    assert data["error_code"] == "INVALID_PROVIDER_RESPONSE"


@pytest.mark.asyncio
async def test_history_contains_mode_and_display_title(client: AsyncClient, sample_application, mock_ai_provider):
    app_id = sample_application["app_id"]

    # Create session 1: full mock
    res1 = await client.post(
        f"/api/v1/job-applications/{app_id}/interview-sessions",
        json={"consent_to_external_ai": True, "practice_mode": "full_mock"}
    )
    assert res1.status_code == 200
    s1_id = res1.json()["id"]

    # Mark session 1 completed with evaluation
    async with SessionLocal() as db:
        s1 = (await db.execute(select(InterviewSession).where(InterviewSession.id == uuid.UUID(s1_id)))).scalars().first()
        s1.status = SessionStatus.completed
        eval_rec = InterviewEvaluation(
            id=uuid.uuid4(),
            interview_session_id=s1.id,
            status=EvaluationStatus.evaluated,
            provider="groq",
            model="llama",
            prompt_version="1.0.0",
            schema_version="1.0.0",
            total_score=70.0,
            average_score=7.0,
            category_scores={
                "backend_fundamentals": 7.0,
                "cv_project_experience": 8.0,
                "database": 5.0,
                "api_web_design": 6.0,
                "debugging_problem_solving": 7.0,
                "behavioral_teamwork": 8.0
            }
        )
        db.add(eval_rec)
        await db.commit()

    # Create session 2: focus_category (database)
    res2 = await client.post(
        f"/api/v1/job-applications/{app_id}/interview-sessions/attempts",
        json={"consent_to_external_ai": True, "practice_mode": "focus_category", "focus_category": "database"}
    )
    assert res2.status_code == 200

    # Fetch history
    h_res = await client.get(f"/api/v1/job-applications/{app_id}/interview-sessions")
    assert h_res.status_code == 200
    history = h_res.json()["items"]
    assert len(history) == 2

    # Latest attempt is attempt 2
    assert history[0]["attempt_number"] == 2
    assert history[0]["practice_mode"] == "focus_category"
    assert history[0]["focus_category"] == "database"
    assert history[0]["mode_display_title"] == "Lần 2 · Luyện Database"

    # Older attempt is attempt 1
    assert history[1]["attempt_number"] == 1
    assert history[1]["practice_mode"] == "full_mock"
    assert history[1]["focus_category"] is None
    assert history[1]["mode_display_title"] == "Lần 1 · Phỏng vấn tổng hợp"


@pytest.mark.asyncio
async def test_concurrent_attempt_creation_with_focus_mode(client: AsyncClient, sample_application, mock_ai_provider):
    import asyncio
    app_id = sample_application["app_id"]
    barrier = asyncio.Barrier(2)

    async def call_attempt():
        await barrier.wait()
        return await client.post(
            f"/api/v1/job-applications/{app_id}/interview-sessions/attempts",
            json={
                "consent_to_external_ai": True,
                "practice_mode": "focus_category",
                "focus_category": "database"
            }
        )

    res_a, res_b = await asyncio.gather(call_attempt(), call_attempt())
    statuses = sorted([res_a.status_code, res_b.status_code])
    assert statuses == [200, 409], f"Expected [200, 409] but got {[res_a.status_code, res_b.status_code]}"

    # Provider should only be called once
    assert mock_ai_provider.call_count == 1


@pytest.mark.asyncio
async def test_sentinel_isolation_and_id_specific_cleanup(client: AsyncClient, mock_ai_provider):
    sentinel_doc_id = uuid.uuid4()
    sentinel_app_id = uuid.uuid4()
    sentinel_analysis_id = uuid.uuid4()
    sentinel_session_id = uuid.uuid4()
    sentinel_eval_id = uuid.uuid4()

    target_doc_id = uuid.uuid4()
    target_app_id = uuid.uuid4()
    target_analysis_id = uuid.uuid4()
    target_session_id = uuid.uuid4()

    try:
        async with SessionLocal() as db:
            s_doc = CVDocument(id=sentinel_doc_id, original_filename="s.pdf", storage_key=f"k_{sentinel_doc_id}", media_type="application/pdf", size_bytes=100, sha256="s_sha", status=CVStatus.extracted, extracted_text="Sentinel text")
            db.add(s_doc)
            s_app = JobApplication(id=sentinel_app_id, cv_document_id=sentinel_doc_id, target_role="Backend Developer Intern", job_description="Sentinel JD")
            db.add(s_app)
            s_analysis = ApplicationAnalysis(id=sentinel_analysis_id, job_application_id=sentinel_app_id, status=AnalysisStatus.completed, provider="groq", model="llama", schema_version="1", prompt_version="1", analysis_data={"summary_vi": "Sentinel", "candidate_level": "junior_ready", "technical_skills": [], "projects": [], "education": []})
            db.add(s_analysis)
            s_sess = InterviewSession(id=sentinel_session_id, job_application_id=sentinel_app_id, attempt_number=1, status=SessionStatus.completed, practice_mode="full_mock", provider="groq", model="llama", prompt_version="1", schema_version="1")
            db.add(s_sess)
            s_eval = InterviewEvaluation(id=sentinel_eval_id, interview_session_id=sentinel_session_id, status=EvaluationStatus.evaluated, provider="groq", model="llama", prompt_version="1", schema_version="1", total_score=80.0, average_score=8.0, category_scores={"database": 8.0})
            db.add(s_eval)

            t_doc = CVDocument(id=target_doc_id, original_filename="t.pdf", storage_key=f"k_{target_doc_id}", media_type="application/pdf", size_bytes=100, sha256="t_sha", status=CVStatus.extracted, extracted_text="Target text")
            db.add(t_doc)
            t_app = JobApplication(id=target_app_id, cv_document_id=target_doc_id, target_role="Backend Developer Intern", job_description="Target JD")
            db.add(t_app)
            t_analysis = ApplicationAnalysis(id=target_analysis_id, job_application_id=target_app_id, status=AnalysisStatus.completed, provider="groq", model="llama", schema_version="1", prompt_version="1", analysis_data={"summary_vi": "Target", "candidate_level": "junior_ready", "technical_skills": [], "projects": [], "education": []})
            db.add(t_analysis)
            t_sess = InterviewSession(id=target_session_id, job_application_id=target_app_id, attempt_number=1, status=SessionStatus.ready, practice_mode="focus_category", focus_category="database", provider="groq", model="llama", prompt_version="1", schema_version="1")
            db.add(t_sess)

            await db.commit()

        # Perform targeted cleanup of target cluster by ID
        async with SessionLocal() as db:
            await db.execute(delete(InterviewQuestion).where(InterviewQuestion.interview_session_id == target_session_id))
            await db.execute(delete(InterviewSession).where(InterviewSession.id == target_session_id))
            await db.execute(delete(ApplicationAnalysis).where(ApplicationAnalysis.id == target_analysis_id))
            await db.execute(delete(JobApplication).where(JobApplication.id == target_app_id))
            await db.execute(delete(CVDocument).where(CVDocument.id == target_doc_id))
            await db.commit()

        # Confirm all target data is deleted
        async with SessionLocal() as db:
            assert (await db.execute(select(func.count()).select_from(JobApplication).where(JobApplication.id == target_app_id))).scalar() == 0
            assert (await db.execute(select(func.count()).select_from(CVDocument).where(CVDocument.id == target_doc_id))).scalar() == 0
            assert (await db.execute(select(func.count()).select_from(InterviewSession).where(InterviewSession.id == target_session_id))).scalar() == 0

            # Confirm sentinel data is completely intact
            assert (await db.execute(select(func.count()).select_from(JobApplication).where(JobApplication.id == sentinel_app_id))).scalar() == 1
            assert (await db.execute(select(func.count()).select_from(InterviewSession).where(InterviewSession.id == sentinel_session_id))).scalar() == 1
            assert (await db.execute(select(func.count()).select_from(InterviewEvaluation).where(InterviewEvaluation.id == sentinel_eval_id))).scalar() == 1

    finally:
        async with SessionLocal() as db:
            await db.execute(delete(InterviewEvaluation).where(InterviewEvaluation.id == sentinel_eval_id))
            await db.execute(delete(InterviewSession).where(InterviewSession.id == sentinel_session_id))
            await db.execute(delete(ApplicationAnalysis).where(ApplicationAnalysis.id == sentinel_analysis_id))
            await db.execute(delete(JobApplication).where(JobApplication.id == sentinel_app_id))
            await db.execute(delete(CVDocument).where(CVDocument.id == sentinel_doc_id))

            await db.execute(delete(InterviewSession).where(InterviewSession.id == target_session_id))
            await db.execute(delete(ApplicationAnalysis).where(ApplicationAnalysis.id == target_analysis_id))
            await db.execute(delete(JobApplication).where(JobApplication.id == target_app_id))
            await db.execute(delete(CVDocument).where(CVDocument.id == target_doc_id))
            await db.commit()


@pytest.mark.asyncio
@pytest.mark.parametrize("mode,focus_cat", [
    ("full_mock", None),
    ("focus_category", "database"),
    ("weakness_recovery", None),
])
async def test_budget_exceeded_new_attempt_creates_no_row_and_calls_no_provider(
    client: AsyncClient, sample_application, mock_ai_provider, monkeypatch, mode, focus_cat
):
    from app.core.config import settings
    app_id = sample_application["app_id"]

    # For weakness_recovery, add evaluation history so it passes evaluation check
    if mode == "weakness_recovery":
        async with SessionLocal() as db:
            sess = InterviewSession(id=uuid.uuid4(), job_application_id=app_id, attempt_number=1, status=SessionStatus.completed, practice_mode="full_mock", provider="groq", model="llama", prompt_version="1", schema_version="1")
            db.add(sess)
            await db.flush()
            eval_rec = InterviewEvaluation(id=uuid.uuid4(), interview_session_id=sess.id, status=EvaluationStatus.evaluated, provider="groq", model="llama", prompt_version="1", schema_version="1", total_score=50.0, average_score=5.0, category_scores={"database": 4.0, "backend_fundamentals": 6.0})
            db.add(eval_rec)
            await db.commit()

    # Monkeypatch max input chars to very small value to exceed budget
    monkeypatch.setattr(settings, "AI_MAX_INTERVIEW_INPUT_CHARS", 10)
    initial_calls = mock_ai_provider.call_count

    payload = {"consent_to_external_ai": True, "practice_mode": mode}
    if focus_cat:
        payload["focus_category"] = focus_cat

    res = await client.post(
        f"/api/v1/job-applications/{app_id}/interview-sessions/attempts",
        json=payload
    )
    assert res.status_code == 409
    assert "quá lớn" in res.json()["detail"]

    # Provider call count must remain unchanged
    assert mock_ai_provider.call_count == initial_calls

    # No new InterviewSession or InterviewQuestion created
    async with SessionLocal() as db:
        if mode == "weakness_recovery":
            sessions = (await db.execute(select(InterviewSession).where(InterviewSession.job_application_id == app_id))).scalars().all()
            assert len(sessions) == 1
            assert sessions[0].status == SessionStatus.completed
        else:
            sessions = (await db.execute(select(InterviewSession).where(InterviewSession.job_application_id == app_id))).scalars().all()
            assert len(sessions) == 0

        questions = (await db.execute(select(InterviewQuestion))).scalars().all()
        assert len(questions) == 0


@pytest.mark.asyncio
async def test_budget_exceeded_retry_generation_failed_preserves_error_state(
    client: AsyncClient, sample_application, mock_ai_provider, monkeypatch
):
    from app.core.config import settings
    app_id = sample_application["app_id"]
    failed_session_id = uuid.uuid4()

    # Create session in generation_failed state
    async with SessionLocal() as db:
        sess = InterviewSession(
            id=failed_session_id,
            job_application_id=app_id,
            attempt_number=1,
            status=SessionStatus.generation_failed,
            practice_mode="focus_category",
            focus_category="database",
            error_code="ORIGINAL_ERROR",
            error_message="Original failure explanation",
            provider="groq",
            model="llama",
            prompt_version="1",
            schema_version="1"
        )
        db.add(sess)
        await db.commit()

    monkeypatch.setattr(settings, "AI_MAX_INTERVIEW_INPUT_CHARS", 10)
    initial_calls = mock_ai_provider.call_count

    # Retry on the existing session endpoint
    res = await client.post(
        f"/api/v1/job-applications/{app_id}/interview-sessions",
        json={"consent_to_external_ai": True}
    )
    assert res.status_code == 409
    assert "quá lớn" in res.json()["detail"]

    # Provider call count must remain unchanged (0 new calls)
    assert mock_ai_provider.call_count == initial_calls

    # Must preserve generation_failed status, error_code, error_message
    async with SessionLocal() as db:
        sess = (await db.execute(select(InterviewSession).where(InterviewSession.id == failed_session_id))).scalars().first()
        assert sess.status == SessionStatus.generation_failed
        assert sess.error_code == "ORIGINAL_ERROR"
        assert sess.error_message == "Original failure explanation"
        assert sess.attempt_number == 1
        assert sess.practice_mode == "focus_category"
        assert sess.focus_category == "database"


@pytest.mark.asyncio
async def test_budget_pass_claims_and_calls_provider_once(
    client: AsyncClient, sample_application, mock_ai_provider
):
    app_id = sample_application["app_id"]
    initial_calls = mock_ai_provider.call_count

    res = await client.post(
        f"/api/v1/job-applications/{app_id}/interview-sessions",
        json={"consent_to_external_ai": True, "practice_mode": "full_mock"}
    )
    assert res.status_code == 200
    assert res.json()["status"] == "ready"
    assert mock_ai_provider.call_count == initial_calls + 1
