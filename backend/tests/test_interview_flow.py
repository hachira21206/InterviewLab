import pytest
import pytest_asyncio
import uuid
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func
from sqlalchemy.exc import IntegrityError
from app.models.cv_document import CVDocument, CVStatus
from app.models.job_application import JobApplication
from app.models.application_analysis import ApplicationAnalysis, AnalysisStatus
from app.models.interview_session import InterviewSession, SessionStatus
from app.models.interview_question import InterviewQuestion, QuestionCategory, QuestionDifficulty, QuestionSource
from app.models.interview_response import InterviewResponse
from app.db.session import SessionLocal

@pytest_asyncio.fixture
async def setup_interview_data():
    doc_id = uuid.uuid4()
    app_id = uuid.uuid4()
    analysis_id = uuid.uuid4()
    session_id = uuid.uuid4()
    question_ids = []

    async with SessionLocal() as db:
        doc = CVDocument(
            id=doc_id,
            original_filename="test_flow.pdf",
            storage_key=f"k_{doc_id}",
            media_type="application/pdf",
            size_bytes=100,
            sha256="abc",
            status=CVStatus.extracted,
            extracted_text="Some cv text"
        )
        db.add(doc)

        job_app = JobApplication(
            id=app_id,
            cv_document_id=doc_id,
            target_role="Backend Developer Intern",
            job_description="Some JD"
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
            analysis_data={"summary_vi": "Mock", "technical_skills": [], "projects": []}
        )
        db.add(analysis)

        session = InterviewSession(
            id=session_id,
            job_application_id=app_id,
            status=SessionStatus.ready,
            provider="groq",
            model="llama",
            prompt_version="1",
            schema_version="1"
        )
        db.add(session)

        cats = [
            QuestionCategory.backend_fundamentals, QuestionCategory.backend_fundamentals,
            QuestionCategory.cv_project_experience, QuestionCategory.cv_project_experience,
            QuestionCategory.database, QuestionCategory.database,
            QuestionCategory.api_web_design, QuestionCategory.api_web_design,
            QuestionCategory.debugging_problem_solving, QuestionCategory.behavioral_teamwork
        ]
        diffs = [QuestionDifficulty.easy] * 4 + [QuestionDifficulty.medium] * 4 + [QuestionDifficulty.hard] * 2

        for i in range(1, 11):
            qid = uuid.uuid4()
            question_ids.append(qid)
            q = InterviewQuestion(
                id=qid,
                interview_session_id=session_id,
                order_index=i,
                question_text=f"Câu hỏi số {i} nội dung chi tiết?",
                category=cats[i-1],
                difficulty=diffs[i-1],
                purpose=f"Mục đích của câu hỏi {i}",
                expected_key_points=["Điểm cốt lõi 1", "Điểm cốt lõi 2"],
                source=QuestionSource.general_backend,
                source_evidence=None
            )
            db.add(q)

        await db.commit()

    try:
        yield {
            "doc_id": doc_id,
            "app_id": app_id,
            "session_id": session_id,
            "question_ids": question_ids
        }
    finally:
        async with SessionLocal() as db:
            await db.execute(delete(InterviewResponse).where(InterviewResponse.interview_session_id == session_id))
            await db.execute(delete(InterviewQuestion).where(InterviewQuestion.interview_session_id == session_id))
            await db.execute(delete(InterviewSession).where(InterviewSession.id == session_id))
            await db.execute(delete(ApplicationAnalysis).where(ApplicationAnalysis.id == analysis_id))
            await db.execute(delete(JobApplication).where(JobApplication.id == app_id))
            await db.execute(delete(CVDocument).where(CVDocument.id == doc_id))
            await db.commit()


@pytest.mark.asyncio
async def test_start_session_not_found(client):
    res = await client.post(f"/api/v1/interview-sessions/{uuid.uuid4()}/start")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_start_session_generating_and_failed(client, setup_interview_data):
    session_id = setup_interview_data["session_id"]
    async with SessionLocal() as db:
        session = await db.get(InterviewSession, session_id)
        session.status = SessionStatus.generating
        await db.commit()

    res = await client.post(f"/api/v1/interview-sessions/{session_id}/start")
    assert res.status_code == 409

    async with SessionLocal() as db:
        session = await db.get(InterviewSession, session_id)
        session.status = SessionStatus.generation_failed
        await db.commit()

    res2 = await client.post(f"/api/v1/interview-sessions/{session_id}/start")
    assert res2.status_code == 409


@pytest.mark.asyncio
async def test_start_ready_success(client, setup_interview_data):
    session_id = setup_interview_data["session_id"]
    res = await client.post(f"/api/v1/interview-sessions/{session_id}/start")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "in_progress"
    assert data["started_at"] is not None
    assert data["current_question"]["order_index"] == 1
    assert data["completed_count"] == 0
    assert data["progress_percent"] == 0.0


@pytest.mark.asyncio
async def test_start_in_progress_idempotent(client, setup_interview_data):
    session_id = setup_interview_data["session_id"]
    res1 = await client.post(f"/api/v1/interview-sessions/{session_id}/start")
    assert res1.status_code == 200

    res2 = await client.post(f"/api/v1/interview-sessions/{session_id}/start")
    assert res2.status_code == 200
    assert res2.json()["status"] == "in_progress"


@pytest.mark.asyncio
async def test_start_completed_idempotent(client, setup_interview_data):
    session_id = setup_interview_data["session_id"]
    async with SessionLocal() as db:
        session = await db.get(InterviewSession, session_id)
        session.status = SessionStatus.completed
        await db.commit()

    res = await client.post(f"/api/v1/interview-sessions/{session_id}/start")
    assert res.status_code == 200
    assert res.json()["status"] == "completed"


@pytest.mark.asyncio
async def test_start_ready_not_enough_questions(client, setup_interview_data):
    session_id = setup_interview_data["session_id"]
    first_qid = setup_interview_data["question_ids"][0]
    async with SessionLocal() as db:
        await db.execute(delete(InterviewQuestion).where(InterviewQuestion.id == first_qid))
        await db.commit()

    res = await client.post(f"/api/v1/interview-sessions/{session_id}/start")
    assert res.status_code == 409


@pytest.mark.asyncio
async def test_answer_empty(client, setup_interview_data):
    session_id = setup_interview_data["session_id"]
    q1 = setup_interview_data["question_ids"][0]
    await client.post(f"/api/v1/interview-sessions/{session_id}/start")

    res = await client.put(
        f"/api/v1/interview-sessions/{session_id}/questions/{q1}/response",
        json={"answer_text": "", "is_skipped": False}
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_answer_whitespace(client, setup_interview_data):
    session_id = setup_interview_data["session_id"]
    q1 = setup_interview_data["question_ids"][0]
    await client.post(f"/api/v1/interview-sessions/{session_id}/start")

    res = await client.put(
        f"/api/v1/interview-sessions/{session_id}/questions/{q1}/response",
        json={"answer_text": "   \n\t   ", "is_skipped": False}
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_answer_too_long(client, setup_interview_data):
    session_id = setup_interview_data["session_id"]
    q1 = setup_interview_data["question_ids"][0]
    await client.post(f"/api/v1/interview-sessions/{session_id}/start")

    res = await client.put(
        f"/api/v1/interview-sessions/{session_id}/questions/{q1}/response",
        json={"answer_text": "a" * 10001, "is_skipped": False}
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_skip_valid(client, setup_interview_data):
    session_id = setup_interview_data["session_id"]
    q1 = setup_interview_data["question_ids"][0]
    await client.post(f"/api/v1/interview-sessions/{session_id}/start")

    res = await client.put(
        f"/api/v1/interview-sessions/{session_id}/questions/{q1}/response",
        json={"answer_text": None, "is_skipped": True}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["completed_count"] == 1
    assert data["current_question"]["order_index"] == 2
    assert len(data["responses"]) == 1
    assert data["responses"][0]["is_skipped"] is True
    assert data["responses"][0]["answer_text"] is None


@pytest.mark.asyncio
async def test_skip_with_answer_rejected(client, setup_interview_data):
    session_id = setup_interview_data["session_id"]
    q1 = setup_interview_data["question_ids"][0]
    await client.post(f"/api/v1/interview-sessions/{session_id}/start")

    res = await client.put(
        f"/api/v1/interview-sessions/{session_id}/questions/{q1}/response",
        json={"answer_text": "Vẫn gửi answer khi skip", "is_skipped": True}
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_answer_null_without_skip_rejected(client, setup_interview_data):
    session_id = setup_interview_data["session_id"]
    q1 = setup_interview_data["question_ids"][0]
    await client.post(f"/api/v1/interview-sessions/{session_id}/start")

    res = await client.put(
        f"/api/v1/interview-sessions/{session_id}/questions/{q1}/response",
        json={"answer_text": None, "is_skipped": False}
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_question_not_belonging_to_session(client, setup_interview_data):
    session_id = setup_interview_data["session_id"]
    await client.post(f"/api/v1/interview-sessions/{session_id}/start")

    res = await client.put(
        f"/api/v1/interview-sessions/{session_id}/questions/{uuid.uuid4()}/response",
        json={"answer_text": "Câu hỏi không tồn tại", "is_skipped": False}
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_submit_out_of_order(client, setup_interview_data):
    session_id = setup_interview_data["session_id"]
    q2 = setup_interview_data["question_ids"][1]
    await client.post(f"/api/v1/interview-sessions/{session_id}/start")

    # Trying to submit question 2 when question 1 is not answered
    res = await client.put(
        f"/api/v1/interview-sessions/{session_id}/questions/{q2}/response",
        json={"answer_text": "Nhảy cóc câu 2", "is_skipped": False}
    )
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_submit_current_question(client, setup_interview_data):
    session_id = setup_interview_data["session_id"]
    q1 = setup_interview_data["question_ids"][0]
    await client.post(f"/api/v1/interview-sessions/{session_id}/start")

    res = await client.put(
        f"/api/v1/interview-sessions/{session_id}/questions/{q1}/response",
        json={"answer_text": "Trả lời câu 1: Index trong DB giúp tìm kiếm nhanh hơn.", "is_skipped": False}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["completed_count"] == 1
    assert data["current_question"]["order_index"] == 2
    assert data["responses"][0]["answer_text"] == "Trả lời câu 1: Index trong DB giúp tìm kiếm nhanh hơn."
    assert data["responses"][0]["is_skipped"] is False


@pytest.mark.asyncio
async def test_update_response_before_completed(client, setup_interview_data):
    session_id = setup_interview_data["session_id"]
    q1 = setup_interview_data["question_ids"][0]
    q2 = setup_interview_data["question_ids"][1]
    await client.post(f"/api/v1/interview-sessions/{session_id}/start")

    # Answer question 1
    await client.put(
        f"/api/v1/interview-sessions/{session_id}/questions/{q1}/response",
        json={"answer_text": "Câu trả lời ban đầu câu 1", "is_skipped": False}
    )
    # Answer question 2
    await client.put(
        f"/api/v1/interview-sessions/{session_id}/questions/{q2}/response",
        json={"answer_text": "Câu trả lời câu 2", "is_skipped": False}
    )

    # Now update question 1
    res = await client.put(
        f"/api/v1/interview-sessions/{session_id}/questions/{q1}/response",
        json={"answer_text": "Câu trả lời câu 1 ĐÃ CẬP NHẬT", "is_skipped": False}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["completed_count"] == 2
    # Ensure updated text
    q1_resp = next(r for r in data["responses"] if r["interview_question_id"] == str(q1))
    assert q1_resp["answer_text"] == "Câu trả lời câu 1 ĐÃ CẬP NHẬT"


@pytest.mark.asyncio
async def test_concurrent_submit_same_question(client, setup_interview_data):
    session_id = setup_interview_data["session_id"]
    q1 = setup_interview_data["question_ids"][0]
    await client.post(f"/api/v1/interview-sessions/{session_id}/start")

    t1 = client.put(
        f"/api/v1/interview-sessions/{session_id}/questions/{q1}/response",
        json={"answer_text": "Request A", "is_skipped": False}
    )
    t2 = client.put(
        f"/api/v1/interview-sessions/{session_id}/questions/{q1}/response",
        json={"answer_text": "Request B", "is_skipped": False}
    )

    res1, res2 = await asyncio.gather(t1, t2)
    assert res1.status_code == 200
    assert res2.status_code == 200

    async with SessionLocal() as db:
        responses = (await db.execute(
            select(InterviewResponse).where(InterviewResponse.interview_session_id == session_id)
        )).scalars().all()
        assert len(responses) == 1


@pytest.mark.asyncio
async def test_tenth_question_transitions_completed(client, setup_interview_data):
    session_id = setup_interview_data["session_id"]
    q_ids = setup_interview_data["question_ids"]
    await client.post(f"/api/v1/interview-sessions/{session_id}/start")

    for i in range(9):
        res = await client.put(
            f"/api/v1/interview-sessions/{session_id}/questions/{q_ids[i]}/response",
            json={"answer_text": f"Đáp án câu {i+1}", "is_skipped": False}
        )
        assert res.status_code == 200
        assert res.json()["status"] == "in_progress"

    # Submit question 10
    res10 = await client.put(
        f"/api/v1/interview-sessions/{session_id}/questions/{q_ids[9]}/response",
        json={"answer_text": "Đáp án câu 10", "is_skipped": False}
    )
    assert res10.status_code == 200
    data = res10.json()
    assert data["status"] == "completed"
    assert data["completed_at"] is not None
    assert data["completed_count"] == 10
    assert data["progress_percent"] == 100.0
    assert data["current_question"] is None
    assert len(data["responses"]) == 10


@pytest.mark.asyncio
async def test_concurrent_tenth_question_strict(client, setup_interview_data, monkeypatch):
    import sqlalchemy.ext.asyncio
    original_flush = sqlalchemy.ext.asyncio.AsyncSession.flush
    created_docs = []
    created_apps = []
    created_sessions = []
    try:
        # Run 20 deterministic iterations of the strict race condition test
        for k in range(20):
            iter_doc_id = uuid.uuid4()
            iter_app_id = uuid.uuid4()
            iter_session_id = uuid.uuid4()
            created_docs.append(iter_doc_id)
            created_apps.append(iter_app_id)
            created_sessions.append(iter_session_id)
            iter_q_ids = []

            async with SessionLocal() as db:
                doc = CVDocument(
                    id=iter_doc_id,
                    original_filename=f"cv_{k}.pdf",
                    storage_key=f"k_{iter_doc_id}",
                    media_type="application/pdf",
                    size_bytes=100,
                    sha256="abc",
                    status=CVStatus.extracted,
                    extracted_text="Some cv text"
                )
                db.add(doc)

                app = JobApplication(
                    id=iter_app_id,
                    cv_document_id=iter_doc_id,
                    target_role="Backend Developer Intern",
                    job_description="Some JD"
                )
                db.add(app)

                sess = InterviewSession(
                    id=iter_session_id,
                    job_application_id=iter_app_id,
                    status=SessionStatus.in_progress,
                    started_at=func.now(),
                    provider="groq",
                    model="llama",
                    prompt_version="1",
                    schema_version="1"
                )
                db.add(sess)

                for i in range(1, 11):
                    qid = uuid.uuid4()
                    iter_q_ids.append(qid)
                    q = InterviewQuestion(
                        id=qid,
                        interview_session_id=iter_session_id,
                        order_index=i,
                        question_text=f"Câu hỏi số {i} nội dung chi tiết?",
                        category=QuestionCategory.backend_fundamentals,
                        difficulty=QuestionDifficulty.easy,
                        purpose=f"Mục đích của câu hỏi {i}",
                        expected_key_points=["Điểm 1"],
                        source=QuestionSource.general_backend,
                        source_evidence=None
                    )
                    db.add(q)

                for i in range(9):
                    resp = InterviewResponse(
                        id=uuid.uuid4(),
                        interview_session_id=iter_session_id,
                        interview_question_id=iter_q_ids[i],
                        answer_text=f"Đáp án câu {i+1}",
                        is_skipped=False,
                        answered_at=func.now()
                    )
                    db.add(resp)

                await db.commit()

            q10 = iter_q_ids[9]
            answer_a = f"Answer Winner A iter_{k}"
            answer_b = f"Answer Loser B iter_{k}"

            req_a_at_flush = asyncio.Event()
            req_b_at_flush = asyncio.Event()
            barrier_release = asyncio.Event()

            async def hooked_flush(self, *args, **kwargs):
                is_target_a = False
                is_target_b = False
                for obj in self.new:
                    if isinstance(obj, InterviewResponse) and obj.interview_question_id == q10:
                        if obj.answer_text == answer_a:
                            is_target_a = True
                        elif obj.answer_text == answer_b:
                            is_target_b = True

                if is_target_a:
                    req_a_at_flush.set()
                    await barrier_release.wait()
                elif is_target_b:
                    req_b_at_flush.set()
                    await barrier_release.wait()

                return await original_flush(self, *args, **kwargs)

            monkeypatch.setattr(sqlalchemy.ext.asyncio.AsyncSession, "flush", hooked_flush)

            t1 = asyncio.create_task(
                client.put(
                    f"/api/v1/interview-sessions/{iter_session_id}/questions/{q10}/response",
                    json={"answer_text": answer_a, "is_skipped": False}
                )
            )
            t2 = asyncio.create_task(
                client.put(
                    f"/api/v1/interview-sessions/{iter_session_id}/questions/{q10}/response",
                    json={"answer_text": answer_b, "is_skipped": False}
                )
            )

            # Wait until both requests have validated in_progress session, created InterviewResponse, and reached flush()
            await asyncio.gather(req_a_at_flush.wait(), req_b_at_flush.wait())

            # Release both requests to flush simultaneously
            barrier_release.set()

            res1, res2 = await asyncio.gather(t1, t2)
            statuses = [res1.status_code, res2.status_code]

            assert statuses.count(200) == 1, f"Iteration {k}: expected exactly one 200, got {statuses}"
            assert statuses.count(409) == 1, f"Iteration {k}: expected exactly one 409, got {statuses}"

            monkeypatch.undo()

            async with SessionLocal() as db:
                session = await db.get(InterviewSession, iter_session_id)
                assert session.status == SessionStatus.completed
                assert session.completed_at is not None

                responses = (await db.execute(
                    select(InterviewResponse).where(InterviewResponse.interview_session_id == iter_session_id)
                )).scalars().all()
                assert len(responses) == 10

                resp_10 = next(r for r in responses if r.interview_question_id == q10)
                winner_text = answer_a if res1.status_code == 200 else answer_b
                assert resp_10.answer_text == winner_text

            # After completed, any further PUT must return 409
            res_again = await client.put(
                f"/api/v1/interview-sessions/{iter_session_id}/questions/{q10}/response",
                json={"answer_text": f"Cố sửa sau khi completed iter_{k}", "is_skipped": False}
            )
            assert res_again.status_code == 409
    finally:
        async with SessionLocal() as db:
            for s_id in created_sessions:
                await db.execute(delete(InterviewResponse).where(InterviewResponse.interview_session_id == s_id))
                await db.execute(delete(InterviewQuestion).where(InterviewQuestion.interview_session_id == s_id))
                await db.execute(delete(InterviewSession).where(InterviewSession.id == s_id))
            for a_id in created_apps:
                await db.execute(delete(JobApplication).where(JobApplication.id == a_id))
            for d_id in created_docs:
                await db.execute(delete(CVDocument).where(CVDocument.id == d_id))
            await db.commit()


@pytest.mark.asyncio
async def test_modify_after_completed_rejected(client, setup_interview_data):
    session_id = setup_interview_data["session_id"]
    q_ids = setup_interview_data["question_ids"]
    await client.post(f"/api/v1/interview-sessions/{session_id}/start")

    for i in range(10):
        await client.put(
            f"/api/v1/interview-sessions/{session_id}/questions/{q_ids[i]}/response",
            json={"answer_text": None, "is_skipped": True}
        )

    # Now attempt to modify question 1
    res = await client.put(
        f"/api/v1/interview-sessions/{session_id}/questions/{q_ids[0]}/response",
        json={"answer_text": "Cố sửa sau khi completed", "is_skipped": False}
    )
    assert res.status_code == 409


@pytest.mark.asyncio
async def test_commit_failure_rollback(client, setup_interview_data, monkeypatch):
    session_id = setup_interview_data["session_id"]
    q1 = setup_interview_data["question_ids"][0]
    await client.post(f"/api/v1/interview-sessions/{session_id}/start")

    import sqlalchemy.ext.asyncio.session
    original_commit = sqlalchemy.ext.asyncio.session.AsyncSession.commit

    async def failing_commit(self):
        raise Exception("Database transaction failure during commit")

    monkeypatch.setattr(sqlalchemy.ext.asyncio.session.AsyncSession, "commit", failing_commit)

    res = await client.put(
        f"/api/v1/interview-sessions/{session_id}/questions/{q1}/response",
        json={"answer_text": "Thử submit khi commit lỗi", "is_skipped": False}
    )
    monkeypatch.undo()

    assert res.status_code == 500

    async with SessionLocal() as db:
        responses = (await db.execute(
            select(InterviewResponse).where(InterviewResponse.interview_session_id == session_id)
        )).scalars().all()
        assert len(responses) == 0


@pytest.mark.asyncio
async def test_get_progress_not_started(client, setup_interview_data):
    session_id = setup_interview_data["session_id"]
    res = await client.get(f"/api/v1/interview-sessions/{session_id}/progress")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ready"
    assert data["completed_count"] == 0
    assert data["current_question"]["order_index"] == 1
    assert data["started_at"] is None


@pytest.mark.asyncio
async def test_get_progress_in_progress(client, setup_interview_data):
    session_id = setup_interview_data["session_id"]
    q1 = setup_interview_data["question_ids"][0]
    await client.post(f"/api/v1/interview-sessions/{session_id}/start")
    await client.put(
        f"/api/v1/interview-sessions/{session_id}/questions/{q1}/response",
        json={"answer_text": "Câu 1 trả lời", "is_skipped": False}
    )

    res = await client.get(f"/api/v1/interview-sessions/{session_id}/progress")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "in_progress"
    assert data["completed_count"] == 1
    assert data["current_question"]["order_index"] == 2
    assert len(data["responses"]) == 1


@pytest.mark.asyncio
async def test_get_transcript_completed(client, setup_interview_data):
    session_id = setup_interview_data["session_id"]
    q_ids = setup_interview_data["question_ids"]
    await client.post(f"/api/v1/interview-sessions/{session_id}/start")

    for i in range(10):
        await client.put(
            f"/api/v1/interview-sessions/{session_id}/questions/{q_ids[i]}/response",
            json={"answer_text": f"Trả lời câu {i+1}", "is_skipped": False}
        )

    res = await client.get(f"/api/v1/interview-sessions/{session_id}/progress")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "completed"
    assert data["completed_count"] == 10
    assert len(data["responses"]) == 10
    assert data["current_question"] is None


@pytest.mark.asyncio
async def test_cascade_delete(setup_interview_data):
    app_id = setup_interview_data["app_id"]
    session_id = setup_interview_data["session_id"]
    q1 = setup_interview_data["question_ids"][0]

    async with SessionLocal() as db:
        resp = InterviewResponse(
            id=uuid.uuid4(),
            interview_session_id=session_id,
            interview_question_id=q1,
            answer_text="Test cascade",
            is_skipped=False,
            answered_at=func.now()
        )
        db.add(resp)
        await db.commit()

        # Delete JobApplication via ORM
        app_rec = await db.get(JobApplication, app_id)
        await db.delete(app_rec)
        await db.commit()

        # Check cascading deletion
        rem_sess = await db.get(InterviewSession, session_id)
        assert rem_sess is None

        rem_q = (await db.execute(select(InterviewQuestion).where(InterviewQuestion.interview_session_id == session_id))).scalars().all()
        assert len(rem_q) == 0

        rem_resp = (await db.execute(select(InterviewResponse).where(InterviewResponse.interview_session_id == session_id))).scalars().all()
        assert len(rem_resp) == 0


@pytest.mark.asyncio
async def test_db_check_constraints(setup_interview_data):
    session_id = setup_interview_data["session_id"]
    q1 = setup_interview_data["question_ids"][0]

    async with SessionLocal() as db:
        # Constraint: is_skipped=True AND answer_text is not None
        bad_resp1 = InterviewResponse(
            interview_session_id=session_id,
            interview_question_id=q1,
            answer_text="Should be null when skipped",
            is_skipped=True
        )
        db.add(bad_resp1)
        with pytest.raises(IntegrityError):
            await db.commit()
        await db.rollback()

        # Constraint: is_skipped=False AND answer_text is None
        bad_resp2 = InterviewResponse(
            interview_session_id=session_id,
            interview_question_id=q1,
            answer_text=None,
            is_skipped=False
        )
        db.add(bad_resp2)
        with pytest.raises(IntegrityError):
            await db.commit()
        await db.rollback()

        # Constraint: answer_text only whitespace
        bad_resp3 = InterviewResponse(
            interview_session_id=session_id,
            interview_question_id=q1,
            answer_text="    ",
            is_skipped=False
        )
        db.add(bad_resp3)
        with pytest.raises(IntegrityError):
            await db.commit()
        await db.rollback()

        # Constraint: Invalid status on InterviewSession
        bad_sess = InterviewSession(
            job_application_id=setup_interview_data["app_id"],
            status="invalid_status_value",
            provider="p",
            model="m",
            prompt_version="1",
            schema_version="1"
        )
        db.add(bad_sess)
        with pytest.raises(IntegrityError):
            await db.commit()
        await db.rollback()
