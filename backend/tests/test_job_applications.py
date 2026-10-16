import pytest
import pytest_asyncio
import uuid
import os
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.job_application import JobApplication
from app.models.cv_document import CVDocument, CVStatus
from app.services.storage import StorageService

VALID_PDF = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n"

@pytest.fixture
def mock_storage(tmp_path, monkeypatch):
    def mock_init(self):
        self.storage_root = tmp_path
        os.makedirs(self.storage_root, exist_ok=True)
    monkeypatch.setattr(StorageService, "__init__", mock_init)
    return tmp_path

@pytest_asyncio.fixture
async def cleanup_job_apps(async_session: AsyncSession):
    cv_ids = []
    app_ids = []
    
    class CleanupContext:
        def add_cv(self, id):
            cv_ids.append(id)
        def add_app(self, id):
            app_ids.append(id)
            
    yield CleanupContext()
    
    # Teardown in correct FK order
    for app_id in app_ids:
        try:
            await async_session.execute(delete(JobApplication).where(JobApplication.id == app_id))
            await async_session.commit()
            chk = (await async_session.execute(select(JobApplication).where(JobApplication.id == app_id))).scalars().first()
            assert chk is None, f"Cleanup failed: App {app_id} still exists"
        except Exception as e:
            await async_session.rollback()
            pytest.fail(f"Cleanup App {app_id} failed: {e}")
            
    for cv_id in cv_ids:
        try:
            await async_session.execute(delete(CVDocument).where(CVDocument.id == cv_id))
            await async_session.commit()
            chk = (await async_session.execute(select(CVDocument).where(CVDocument.id == cv_id))).scalars().first()
            assert chk is None, f"Cleanup failed: CV {cv_id} still exists"
        except Exception as e:
            await async_session.rollback()
            pytest.fail(f"Cleanup CV {cv_id} failed: {e}")

@pytest_asyncio.fixture
async def extracted_cv(async_session: AsyncSession, cleanup_job_apps):
    doc_id = uuid.uuid4()
    doc = CVDocument(id=doc_id, original_filename="test.pdf", storage_key=f"k_{doc_id}", media_type="application/pdf", size_bytes=10, sha256="abc", status=CVStatus.extracted)
    async_session.add(doc)
    await async_session.commit()
    cleanup_job_apps.add_cv(doc_id)
    return doc_id

@pytest.mark.asyncio
async def test_create_valid_application(client, extracted_cv, cleanup_job_apps):
    data = {
        "cv_document_id": str(extracted_cv),
        "target_role": "Backend Developer Intern",
        "job_description": "Một JD mẫu bằng tiếng Việt có ít nhất 50 ký tự để vượt qua validation backend thành công mỹ mãn nhé. English also supported in JD."
    }
    res = await client.post("/api/v1/job-applications", json=data)
    assert res.status_code == 201
    json_data = res.json()
    assert json_data["target_role"] == "Backend Developer Intern"
    assert json_data["interview_language"] == "vi"
    assert "storage_key" not in res.text
    cleanup_job_apps.add_app(uuid.UUID(json_data["id"]))

@pytest.mark.asyncio
async def test_create_no_jd(client, extracted_cv, cleanup_job_apps):
    data = {
        "cv_document_id": str(extracted_cv),
        "target_role": "Backend Developer Intern"
    }
    res = await client.post("/api/v1/job-applications", json=data)
    assert res.status_code == 201
    json_data = res.json()
    assert json_data["job_description"] is None
    cleanup_job_apps.add_app(uuid.UUID(json_data["id"]))

@pytest.mark.asyncio
async def test_create_invalid_role(client, extracted_cv):
    data = {
        "cv_document_id": str(extracted_cv),
        "target_role": "Frontend Developer Intern"
    }
    res = await client.post("/api/v1/job-applications", json=data)
    assert res.status_code == 422
    assert "Backend Developer Intern" in res.text

@pytest.mark.asyncio
async def test_create_short_jd(client, extracted_cv):
    data = {
        "cv_document_id": str(extracted_cv),
        "target_role": "Backend Developer Intern",
        "job_description": "Ngắn."
    }
    res = await client.post("/api/v1/job-applications", json=data)
    assert res.status_code == 422
    assert "50 ký tự" in res.text

@pytest.mark.asyncio
async def test_create_long_jd(client, extracted_cv):
    data = {
        "cv_document_id": str(extracted_cv),
        "target_role": "Backend Developer Intern",
        "job_description": "A" * 20001
    }
    res = await client.post("/api/v1/job-applications", json=data)
    assert res.status_code == 422
    assert "20000" in res.text

@pytest.mark.asyncio
async def test_create_cv_not_found(client):
    data = {
        "cv_document_id": str(uuid.uuid4()),
        "target_role": "Backend Developer Intern"
    }
    res = await client.post("/api/v1/job-applications", json=data)
    assert res.status_code == 404

@pytest.mark.asyncio
async def test_create_cv_extracting(client, async_session, cleanup_job_apps):
    doc_id = uuid.uuid4()
    doc = CVDocument(id=doc_id, original_filename="test.pdf", storage_key=f"k_{doc_id}", media_type="application/pdf", size_bytes=10, sha256="abc", status=CVStatus.extracting)
    async_session.add(doc)
    await async_session.commit()
    cleanup_job_apps.add_cv(doc_id)
    
    data = {
        "cv_document_id": str(doc_id),
        "target_role": "Backend Developer Intern"
    }
    res = await client.post("/api/v1/job-applications", json=data)
    assert res.status_code == 409

@pytest.mark.asyncio
async def test_create_cv_extraction_failed(client, async_session, cleanup_job_apps):
    doc_id = uuid.uuid4()
    doc = CVDocument(id=doc_id, original_filename="test.pdf", storage_key=f"k_{doc_id}", media_type="application/pdf", size_bytes=10, sha256="abc", status=CVStatus.extraction_failed)
    async_session.add(doc)
    await async_session.commit()
    cleanup_job_apps.add_cv(doc_id)
    
    data = {
        "cv_document_id": str(doc_id),
        "target_role": "Backend Developer Intern"
    }
    res = await client.post("/api/v1/job-applications", json=data)
    assert res.status_code == 409

@pytest.mark.asyncio
async def test_create_normalize_jd(client, extracted_cv, cleanup_job_apps):
    # NUL char, CRLF, excessive tabs
    jd_raw = "Đây là JD có ký tự đặc biệt.\x00\x08 Xuống dòng\r\nCRLF nè.    Nhiều tab \t\t\t\t Kết thúc dài hơn 50 ký tự."
    data = {
        "cv_document_id": str(extracted_cv),
        "target_role": "Backend Developer Intern",
        "job_description": jd_raw
    }
    res = await client.post("/api/v1/job-applications", json=data)
    assert res.status_code == 201
    json_data = res.json()
    cleanup_job_apps.add_app(uuid.UUID(json_data["id"]))
    
    jd_normalized = json_data["job_description"]
    assert "\x00" not in jd_normalized
    assert "\r\n" not in jd_normalized
    assert "\n" in jd_normalized
    assert " \t " not in jd_normalized

@pytest.mark.asyncio
async def test_client_cannot_set_interview_language(client, extracted_cv):
    data = {
        "cv_document_id": str(extracted_cv),
        "target_role": "Backend Developer Intern",
        "interview_language": "en"
    }
    res = await client.post("/api/v1/job-applications", json=data)
    assert res.status_code == 422
    assert "Extra inputs are not permitted" in res.text

@pytest.mark.asyncio
async def test_get_application(client, extracted_cv, cleanup_job_apps):
    data = {
        "cv_document_id": str(extracted_cv),
        "target_role": "Backend Developer Intern"
    }
    res = await client.post("/api/v1/job-applications", json=data)
    app_id = res.json()["id"]
    cleanup_job_apps.add_app(uuid.UUID(app_id))
    
    get_res = await client.get(f"/api/v1/job-applications/{app_id}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == app_id
    assert "cv_document" in get_res.json()
    assert "storage_key" not in get_res.text
    
@pytest.mark.asyncio
async def test_get_application_not_found(client):
    res = await client.get(f"/api/v1/job-applications/{uuid.uuid4()}")
    assert res.status_code == 404

@pytest.mark.asyncio
async def test_patch_application(client, extracted_cv, cleanup_job_apps):
    data = {
        "cv_document_id": str(extracted_cv),
        "target_role": "Backend Developer Intern"
    }
    res = await client.post("/api/v1/job-applications", json=data)
    app_id = res.json()["id"]
    cleanup_job_apps.add_app(uuid.UUID(app_id))
    
    patch_res = await client.patch(f"/api/v1/job-applications/{app_id}", json={
        "job_description": "Cập nhật JD mới dài hơn 50 ký tự. " * 3
    })
    assert patch_res.status_code == 200
    assert patch_res.json()["job_description"] is not None

@pytest.mark.asyncio
async def test_patch_application_remove_jd(client, extracted_cv, cleanup_job_apps):
    data = {
        "cv_document_id": str(extracted_cv),
        "target_role": "Backend Developer Intern",
        "job_description": "Đây là một JD ban đầu dài hơn 50 ký tự được cung cấp khi tạo mới hồ sơ ứng tuyển."
    }
    res = await client.post("/api/v1/job-applications", json=data)
    app_id = res.json()["id"]
    cleanup_job_apps.add_app(uuid.UUID(app_id))
    
    # Remove JD via empty string (which normalizes to None)
    patch_res = await client.patch(f"/api/v1/job-applications/{app_id}", json={
        "job_description": "   \n\t "
    })
    assert patch_res.status_code == 200
    assert patch_res.json()["job_description"] is None

@pytest.mark.asyncio
async def test_patch_application_empty_json(client, extracted_cv, cleanup_job_apps):
    data = {
        "cv_document_id": str(extracted_cv),
        "target_role": "Backend Developer Intern",
        "job_description": "Đây là một JD ban đầu dài hơn 50 ký tự được cung cấp khi tạo mới hồ sơ ứng tuyển."
    }
    res = await client.post("/api/v1/job-applications", json=data)
    app_id = res.json()["id"]
    cleanup_job_apps.add_app(uuid.UUID(app_id))
    
    # Empty JSON should do nothing
    patch_res = await client.patch(f"/api/v1/job-applications/{app_id}", json={})
    assert patch_res.status_code == 200
    assert patch_res.json()["job_description"] is not None

@pytest.mark.asyncio
async def test_patch_application_forbid_fields(client, extracted_cv, cleanup_job_apps):
    data = {
        "cv_document_id": str(extracted_cv),
        "target_role": "Backend Developer Intern"
    }
    res = await client.post("/api/v1/job-applications", json=data)
    app_id = res.json()["id"]
    cleanup_job_apps.add_app(uuid.UUID(app_id))
    
    patch_res = await client.patch(f"/api/v1/job-applications/{app_id}", json={
        "target_role": "Frontend"
    })
    assert patch_res.status_code == 422
    
    patch_res2 = await client.patch(f"/api/v1/job-applications/{app_id}", json={
        "cv_document_id": str(uuid.uuid4())
    })
    assert patch_res2.status_code == 422

@pytest.mark.asyncio
async def test_commit_failure_rollback(client, extracted_cv, monkeypatch, cleanup_job_apps, async_session):
    from sqlalchemy.ext.asyncio import AsyncSession
    original_commit = AsyncSession.commit
    
    commit_calls = 0
    async def mock_commit(self):
        nonlocal commit_calls
        commit_calls += 1
        if commit_calls == 1:
            raise Exception("Mock DB Failure")
        await original_commit(self)
        
    monkeypatch.setattr(AsyncSession, "commit", mock_commit)
    
    data = {
        "cv_document_id": str(extracted_cv),
        "target_role": "Backend Developer Intern",
        "job_description": "JD dài 50 kí tự để test commit failure rollback thành công."
    }
    res = await client.post("/api/v1/job-applications", json=data)
    assert res.status_code == 500
    
    # Verify no new row
    chk = (await async_session.execute(select(JobApplication).where(JobApplication.cv_document_id == extracted_cv))).scalars().all()
    assert len(chk) == 0

@pytest.mark.asyncio
async def test_patch_commit_failure_rollback(client, extracted_cv, monkeypatch, cleanup_job_apps, async_session):
    data = {
        "cv_document_id": str(extracted_cv),
        "target_role": "Backend Developer Intern",
        "job_description": "JD ban đầu dài hơn 50 kí tự để test patch rollback."
    }
    res = await client.post("/api/v1/job-applications", json=data)
    app_id = res.json()["id"]
    cleanup_job_apps.add_app(uuid.UUID(app_id))
    
    from sqlalchemy.ext.asyncio import AsyncSession
    original_commit = AsyncSession.commit
    
    async def mock_commit(self):
        raise Exception("Mock DB Failure")
        
    monkeypatch.setattr(AsyncSession, "commit", mock_commit)
    
    patch_res = await client.patch(f"/api/v1/job-applications/{app_id}", json={
        "job_description": "JD mới dài hơn 50 kí tự được cập nhật qua api patch."
    })
    assert patch_res.status_code == 500
    
    # Undo monkeypatch to check db
    monkeypatch.undo()
    
    chk = (await async_session.execute(select(JobApplication).where(JobApplication.id == uuid.UUID(app_id)))).scalars().first()
    assert chk.job_description == "JD ban đầu dài hơn 50 kí tự để test patch rollback."

@pytest.mark.asyncio
async def test_database_cascade_delete(async_session, cleanup_job_apps):
    doc_id = uuid.uuid4()
    doc = CVDocument(id=doc_id, original_filename="test.pdf", storage_key=f"k_{doc_id}", media_type="application/pdf", size_bytes=10, sha256="abc", status=CVStatus.extracted)
    async_session.add(doc)
    await async_session.commit()
    cleanup_job_apps.add_cv(doc_id)
    
    app = JobApplication(cv_document_id=doc_id, target_role="Backend Developer Intern")
    async_session.add(app)
    await async_session.commit()
    await async_session.refresh(app)
    app_id = app.id
    
    # Assert DB defaults were applied
    assert app.interview_language == "vi"
    assert app.created_at is not None
    
    # Now delete CV
    await async_session.execute(delete(CVDocument).where(CVDocument.id == doc_id))
    await async_session.commit()
    
    # Assert App is gone
    chk = (await async_session.execute(select(JobApplication).where(JobApplication.id == app_id))).scalars().first()
    assert chk is None


@pytest.mark.asyncio
async def test_list_applications(client, extracted_cv, cleanup_job_apps):
    data1 = {
        "cv_document_id": str(extracted_cv),
        "target_role": "Backend Developer Intern",
    }
    res1 = await client.post("/api/v1/job-applications", json=data1)
    assert res1.status_code == 201
    app1_id = res1.json()["id"]
    cleanup_job_apps.add_app(uuid.UUID(app1_id))

    list_res = await client.get("/api/v1/job-applications?limit=10")
    assert list_res.status_code == 200
    items = list_res.json()
    assert isinstance(items, list)
    assert any(item["id"] == app1_id for item in items)
    matched = next(item for item in items if item["id"] == app1_id)
    assert matched["cv_document"]["original_filename"] == "test.pdf"
    assert "storage_key" not in list_res.text


@pytest.mark.asyncio
async def test_update_cv_extracted_text(client, extracted_cv):
    # Too short -> 422
    short_res = await client.patch(
        f"/api/v1/cv-documents/{extracted_cv}/extracted-text",
        json={"extracted_text": "Quá ngắn"},
    )
    assert short_res.status_code == 422

    # Valid update -> 200
    updated_text = (
        "Nguyễn Văn An - Backend Developer Intern.\n"
        "Kỹ năng: Python, FastAPI, PostgreSQL, Docker, RESTful API, Git."
    )
    ok_res = await client.patch(
        f"/api/v1/cv-documents/{extracted_cv}/extracted-text",
        json={"extracted_text": updated_text},
    )
    assert ok_res.status_code == 200
    assert ok_res.json()["extracted_text"] == updated_text


