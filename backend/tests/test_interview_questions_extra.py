import pytest
import pytest_asyncio
import uuid
import httpx
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete, select, text
from sqlalchemy.exc import IntegrityError
from app.models.cv_document import CVDocument, CVStatus
from app.models.job_application import JobApplication
from app.models.application_analysis import ApplicationAnalysis, AnalysisStatus
from app.models.interview_session import InterviewSession, SessionStatus
from app.models.interview_question import InterviewQuestion
from app.services.analysis_provider import FakeAnalysisProvider, InterviewQuestionsResult, GroqAnalysisProvider, AnalysisInput
from app.schemas.interview_questions import InterviewQuestionSet, InterviewQuestionGenerated
from app.core.config import settings
from app.db.session import SessionLocal

@pytest_asyncio.fixture(autouse=True)
def mock_ai_provider(monkeypatch):
    import app.services.interview_session
    fake = FakeAnalysisProvider()
    monkeypatch.setattr(settings, "GROQ_API_KEY", "fake_key")
    def fake_get_provider():
        return fake
    monkeypatch.setattr(app.services.interview_session, "get_analysis_provider", fake_get_provider)
    return fake

@pytest_asyncio.fixture
async def sample_application_ready():
    async with SessionLocal() as async_session:
        doc_id = uuid.uuid4()
        doc = CVDocument(id=doc_id, original_filename="test_extra.pdf", storage_key=f"k_{doc_id}", media_type="application/pdf", size_bytes=100, sha256="abc", status=CVStatus.extracted, extracted_text="Some cv text")
        async_session.add(doc)
        app_id = uuid.uuid4()
        job_app = JobApplication(id=app_id, cv_document_id=doc_id, target_role="Backend Developer Intern", job_description="Some JD")
        async_session.add(job_app)
        
        analysis_id = uuid.uuid4()
        analysis = ApplicationAnalysis(id=analysis_id, job_application_id=app_id, status=AnalysisStatus.completed, provider="g", model="m", schema_version="1", prompt_version="1", analysis_data={
            "summary_vi": "Mock summary",
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
        })
        async_session.add(analysis)
        
        await async_session.commit()
    
    try:
        yield app_id
    finally:
        async with SessionLocal() as async_session:
            await async_session.execute(delete(InterviewQuestion).where(InterviewQuestion.interview_session_id.in_(
                select(InterviewSession.id).where(InterviewSession.job_application_id == app_id)
            )))
            await async_session.execute(delete(InterviewSession).where(InterviewSession.job_application_id == app_id))
            await async_session.execute(delete(ApplicationAnalysis).where(ApplicationAnalysis.job_application_id == app_id))
            await async_session.execute(delete(JobApplication).where(JobApplication.id == app_id))
            await async_session.execute(delete(CVDocument).where(CVDocument.id == doc_id))
            await async_session.commit()

def generate_mock_questions():
    from app.models.interview_question import QuestionCategory, QuestionDifficulty, QuestionSource
    questions = []
    cats = [
        "backend_fundamentals", "backend_fundamentals",
        "cv_project_experience", "cv_project_experience",
        "database", "database",
        "api_web_design", "api_web_design",
        "debugging_problem_solving", "behavioral_teamwork"
    ]
    diffs = ["easy"] * 4 + ["medium"] * 4 + ["hard"] * 2
    for i in range(10):
        q = InterviewQuestionGenerated(
            question_text=f"Valid question text {i}",
            category=QuestionCategory(cats[i]),
            difficulty=QuestionDifficulty(diffs[i]),
            purpose="Valid purpose text for this question",
            expected_key_points=["Key point 1"],
            source=QuestionSource.general_backend,
            source_evidence="evidence" if cats[i] == "cv_project_experience" else None
        )
        questions.append(q)
    return InterviewQuestionSet(questions=questions)

@pytest.mark.asyncio
async def test_missing_consent(client, sample_application_ready):
    res = await client.post(f"/api/v1/job-applications/{sample_application_ready}/interview-sessions", json={})
    assert res.status_code == 422

@pytest.mark.asyncio
async def test_analysis_pending(client, sample_application_ready):
    async with SessionLocal() as session:
        analysis = (await session.execute(select(ApplicationAnalysis).where(ApplicationAnalysis.job_application_id == sample_application_ready))).scalars().first()
        analysis.status = AnalysisStatus.pending
        await session.commit()
    res = await client.post(f"/api/v1/job-applications/{sample_application_ready}/interview-sessions", json={"consent_to_external_ai": True})
    assert res.status_code == 409

@pytest.mark.asyncio
async def test_budget_exceeded(client, sample_application_ready, monkeypatch):
    import app.services.interview_session
    import app.services.interview_session
    monkeypatch.setattr(app.services.interview_session, "INTERVIEW_SYSTEM_PROMPT", "x" * 50000)
    res = await client.post(f"/api/v1/job-applications/{sample_application_ready}/interview-sessions", json={"consent_to_external_ai": True})
    assert res.status_code == 409

@pytest.mark.asyncio
async def test_existing_generating(client, sample_application_ready, mock_ai_provider):
    async with SessionLocal() as session:
        sess = InterviewSession(job_application_id=sample_application_ready, status=SessionStatus.generating, provider="p", model="m", prompt_version="1", schema_version="1")
        session.add(sess)
        await session.commit()
    res = await client.post(f"/api/v1/job-applications/{sample_application_ready}/interview-sessions", json={"consent_to_external_ai": True})
    assert res.status_code == 409

@pytest.mark.asyncio
async def test_ready_idempotent(client, sample_application_ready, mock_ai_provider):
    mock_ai_provider.mock_questions_result = InterviewQuestionsResult(generate_mock_questions(), None, None, 10, 10)
    res = await client.post(f"/api/v1/job-applications/{sample_application_ready}/interview-sessions", json={"consent_to_external_ai": True})
    assert res.status_code == 200
    assert mock_ai_provider.call_count == 1
    
    res2 = await client.post(f"/api/v1/job-applications/{sample_application_ready}/interview-sessions", json={"consent_to_external_ai": True})
    assert res2.status_code == 200
    assert mock_ai_provider.call_count == 1 # still 1

@pytest.mark.asyncio
async def test_evidence_missing(client, sample_application_ready, mock_ai_provider):
    qs = generate_mock_questions()
    from app.models.interview_question import QuestionSource
    qs.questions[2].source = QuestionSource.cv
    qs.questions[2].source_evidence = None
    mock_ai_provider.mock_questions_result = InterviewQuestionsResult(qs, None, None, 10, 10)
    res = await client.post(f"/api/v1/job-applications/{sample_application_ready}/interview-sessions", json={"consent_to_external_ai": True})
    assert res.status_code == 200
    assert res.json()["status"] == "generation_failed"
    assert res.json()["error_code"] == "INVALID_PROVIDER_RESPONSE"

@pytest.mark.asyncio
async def test_result_data_none(client, sample_application_ready, mock_ai_provider):
    mock_ai_provider.mock_questions_result = InterviewQuestionsResult(None, None, None, 10, 10)
    res = await client.post(f"/api/v1/job-applications/{sample_application_ready}/interview-sessions", json={"consent_to_external_ai": True})
    assert res.status_code == 200
    assert res.json()["status"] == "generation_failed"
    assert res.json()["error_code"] == "INVALID_PROVIDER_RESPONSE"

@pytest.mark.asyncio
async def test_provider_exception(client, sample_application_ready, mock_ai_provider):
    async def failing_generate(*args, **kwargs):
        raise Exception("Fatal provider failure")
    mock_ai_provider.generate_interview_questions = failing_generate
    res = await client.post(f"/api/v1/job-applications/{sample_application_ready}/interview-sessions", json={"consent_to_external_ai": True})
    assert res.status_code == 200
    assert res.json()["status"] == "generation_failed"
    assert res.json()["error_code"] == "INTERNAL_ANALYSIS_ERROR"
    
@pytest.mark.asyncio
async def test_final_commit_failure(client, sample_application_ready, monkeypatch):
    import sqlalchemy.ext.asyncio.session
    original_commit = sqlalchemy.ext.asyncio.session.AsyncSession.commit
    commit_count = 0
    
    async def fully_failing_commit(self):
        nonlocal commit_count
        commit_count += 1
        if commit_count >= 2:
            raise Exception("Total commit fail")
        await original_commit(self)
        
    monkeypatch.setattr(sqlalchemy.ext.asyncio.session.AsyncSession, "commit", fully_failing_commit)
    
    res = await client.post(f"/api/v1/job-applications/{sample_application_ready}/interview-sessions", json={"consent_to_external_ai": True})
    monkeypatch.undo()
    assert res.status_code == 500

@pytest.mark.asyncio
async def test_concurrency(client, sample_application_ready, mock_ai_provider):
    provider_entered = asyncio.Event()
    provider_continue = asyncio.Event()

    async def blocking_generate(input_data):
        mock_ai_provider.call_count += 1
        provider_entered.set()
        await provider_continue.wait()
        return InterviewQuestionsResult(generate_mock_questions(), None, None, 10, 10)

    mock_ai_provider.generate_interview_questions = blocking_generate

    t1 = asyncio.create_task(
        client.post(f"/api/v1/job-applications/{sample_application_ready}/interview-sessions", json={"consent_to_external_ai": True})
    )

    await provider_entered.wait()
    res2 = await client.post(f"/api/v1/job-applications/{sample_application_ready}/interview-sessions", json={"consent_to_external_ai": True})
    assert res2.status_code == 409
    
    provider_continue.set()
    res1 = await t1
    assert res1.status_code == 200
    assert mock_ai_provider.call_count == 1

@pytest.mark.asyncio
async def test_db_checks(sample_application_ready):
    async with SessionLocal() as db:
        sess = InterviewSession(job_application_id=sample_application_ready, status="invalid_status", provider="p", model="m", prompt_version="1", schema_version="1")
        db.add(sess)
        with pytest.raises(IntegrityError):
            await db.commit()
        await db.rollback()

@pytest.mark.asyncio
async def test_cascade(sample_application_ready):
    async with SessionLocal() as db:
        sess = InterviewSession(job_application_id=sample_application_ready, status=SessionStatus.generating, provider="p", model="m", prompt_version="1", schema_version="1")
        db.add(sess)
        await db.commit()
        sess_id = sess.id
        q = InterviewQuestion(interview_session_id=sess_id, order_index=1, question_text="A", category="database", difficulty="easy", purpose="p", expected_key_points=[], source="cv")
        db.add(q)
        await db.commit()
        
        app_rec = await db.get(JobApplication, sample_application_ready)
        await db.delete(app_rec)
        await db.commit()
        
        rem_sess = await db.get(InterviewSession, sess_id)
        assert rem_sess is None
        rem_q = (await db.execute(select(InterviewQuestion).where(InterviewQuestion.interview_session_id == sess_id))).scalars().all()
        assert len(rem_q) == 0

