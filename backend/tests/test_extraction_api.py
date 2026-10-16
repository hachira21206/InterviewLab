import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from app.models.cv_document import CVDocument, CVStatus
from app.services.storage import StorageService
import uuid
import os

VALID_PDF = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n"

@pytest.fixture
def mock_storage(tmp_path, monkeypatch):
    def mock_init(self):
        self.storage_root = tmp_path
        os.makedirs(self.storage_root, exist_ok=True)
    monkeypatch.setattr(StorageService, "__init__", mock_init)
    return tmp_path

@pytest_asyncio.fixture
async def cleanup_docs(async_session: AsyncSession, mock_storage):
    docs = []
    yield docs
    # Finally block
    for doc_id in docs:
        try:
            doc = (await async_session.execute(select(CVDocument).where(CVDocument.id == doc_id))).scalars().first()
            storage_key = None
            if doc:
                storage_key = doc.storage_key
                file_path = mock_storage / storage_key
                if file_path.exists():
                    file_path.unlink()
                await async_session.execute(delete(CVDocument).where(CVDocument.id == doc_id))
                await async_session.commit()
            
            # Post-cleanup assertions
            deleted_doc = (await async_session.execute(select(CVDocument).where(CVDocument.id == doc_id))).scalars().first()
            assert deleted_doc is None, f"Cleanup failed: Document {doc_id} still exists in DB."
            if storage_key:
                assert not (mock_storage / storage_key).exists(), f"Cleanup failed: File {storage_key} still exists."
        except Exception as e:
            await async_session.rollback()
            pytest.fail(f"Fixture teardown failed for doc {doc_id}: {str(e)}")

@pytest.mark.asyncio
async def test_extract_not_found(client, cleanup_docs):
    res = await client.post(f"/api/v1/cv-documents/{uuid.uuid4()}/extract")
    assert res.status_code == 404

@pytest.mark.asyncio
async def test_extract_success(client, async_session, mock_storage, monkeypatch, cleanup_docs):
    call_count = 0
    async def mock_extract(*args):
        nonlocal call_count
        call_count += 1
        return "Extracted Content"
    monkeypatch.setattr("app.services.extractor.CVTextExtractor.extract_text", mock_extract)
    
    marker = f"test_{uuid.uuid4().hex}"
    upload_res = await client.post("/api/v1/cv-documents", files={"file": (f"{marker}.pdf", VALID_PDF, "application/pdf")})
    assert upload_res.status_code == 201
    doc_id = upload_res.json()["id"]
    cleanup_docs.append(doc_id)
    
    # Extract
    ext_res = await client.post(f"/api/v1/cv-documents/{doc_id}/extract")
    assert ext_res.status_code == 200
    data = ext_res.json()
    assert data["status"] == "extracted"
    assert data["extracted_text"] == "Extracted Content"
    assert "storage_key" not in data
    assert call_count == 1
    
    # Idempotent extract
    ext_res_2 = await client.post(f"/api/v1/cv-documents/{doc_id}/extract")
    assert ext_res_2.status_code == 200
    assert ext_res_2.json()["status"] == "extracted"
    assert call_count == 1 # Extractor NOT called again

@pytest.mark.asyncio
async def test_extract_currently_extracting(client, async_session, mock_storage, cleanup_docs):
    doc_id = uuid.uuid4()
    doc = CVDocument(id=doc_id, original_filename="test.pdf", storage_key=f"test_key_{doc_id}", media_type="application/pdf", size_bytes=100, sha256="abc", status=CVStatus.extracting)
    async_session.add(doc)
    await async_session.commit()
    cleanup_docs.append(doc_id)
    
    res = await client.post(f"/api/v1/cv-documents/{doc_id}/extract")
    assert res.status_code == 409

@pytest.mark.asyncio
async def test_extraction_failed_retry_success(client, async_session, mock_storage, monkeypatch, cleanup_docs):
    doc_id = uuid.uuid4()
    storage_key = f"test_key_{doc_id}"
    (mock_storage / storage_key).write_bytes(VALID_PDF)
    doc = CVDocument(id=doc_id, original_filename="test.pdf", storage_key=storage_key, media_type="application/pdf", size_bytes=100, sha256="abc", status=CVStatus.extraction_failed)
    async_session.add(doc)
    await async_session.commit()
    cleanup_docs.append(doc_id)
    
    async def mock_extract(*args):
        return "Recovered Content"
    monkeypatch.setattr("app.services.extractor.CVTextExtractor.extract_text", mock_extract)
    
    res = await client.post(f"/api/v1/cv-documents/{doc_id}/extract")
    assert res.status_code == 200
    assert res.json()["status"] == "extracted"
    assert res.json()["extracted_text"] == "Recovered Content"

@pytest.mark.asyncio
async def test_extract_missing_file(client, async_session, mock_storage, cleanup_docs):
    doc_id = uuid.uuid4()
    doc = CVDocument(id=doc_id, original_filename="test.pdf", storage_key=f"missing_key_{doc_id}", media_type="application/pdf", size_bytes=100, sha256="abc", status=CVStatus.uploaded)
    async_session.add(doc)
    await async_session.commit()
    cleanup_docs.append(doc_id)
    
    res = await client.post(f"/api/v1/cv-documents/{doc_id}/extract")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "extraction_failed"
    assert data["extraction_error"] == "Lỗi hệ thống lưu trữ."

@pytest.mark.asyncio
async def test_extract_file_traversal(client, async_session, mock_storage, cleanup_docs):
    doc_id = uuid.uuid4()
    doc = CVDocument(id=doc_id, original_filename="test.pdf", storage_key="../test_key", media_type="application/pdf", size_bytes=100, sha256="abc", status=CVStatus.uploaded)
    async_session.add(doc)
    await async_session.commit()
    cleanup_docs.append(doc_id)
    
    res = await client.post(f"/api/v1/cv-documents/{doc_id}/extract")
    assert res.status_code == 200
    assert res.json()["status"] == "extraction_failed"

@pytest.mark.asyncio
async def test_extract_exception_fallback(client, async_session, mock_storage, monkeypatch, cleanup_docs):
    async def mock_extract(*args):
        raise Exception("Random unexpected error with /fake/path/to/file")
    monkeypatch.setattr("app.services.extractor.CVTextExtractor.extract_text", mock_extract)
    
    marker = f"test_{uuid.uuid4().hex}"
    upload_res = await client.post("/api/v1/cv-documents", files={"file": (f"{marker}.pdf", VALID_PDF, "application/pdf")})
    doc_id = upload_res.json()["id"]
    cleanup_docs.append(doc_id)
    
    ext_res = await client.post(f"/api/v1/cv-documents/{doc_id}/extract")
    assert ext_res.status_code == 200
    assert ext_res.json()["status"] == "extraction_failed"
    assert ext_res.json()["extraction_error"] == "Lỗi trích xuất không xác định."
    assert "fake/path" not in str(ext_res.json())
    
    # Original file is still there
    doc = (await async_session.execute(select(CVDocument).where(CVDocument.id == doc_id))).scalars().first()
    assert (mock_storage / doc.storage_key).exists()

@pytest.mark.asyncio
async def test_extract_commit_extracting_fails(client, async_session, mock_storage, monkeypatch, cleanup_docs):
    doc_id = uuid.uuid4()
    storage_key = f"test_key_{doc_id}"
    (mock_storage / storage_key).write_bytes(VALID_PDF)
    doc = CVDocument(id=doc_id, original_filename="test.pdf", storage_key=storage_key, media_type="application/pdf", size_bytes=100, sha256="abc", status=CVStatus.uploaded)
    async_session.add(doc)
    await async_session.commit()
    cleanup_docs.append(doc_id)
    
    commit_calls = 0
    original_commit = AsyncSession.commit
    async def mock_commit(self):
        nonlocal commit_calls
        commit_calls += 1
        # The first commit in extract_document is the extracting commit
        if commit_calls == 1:
            raise Exception("DB Error on extracting commit")
        await original_commit(self)
    monkeypatch.setattr(AsyncSession, "commit", mock_commit)
    
    res = await client.post(f"/api/v1/cv-documents/{doc_id}/extract")
    assert res.status_code == 500
    assert res.json()["detail"] == "Lỗi lưu trạng thái CSDL."

@pytest.mark.asyncio
async def test_extract_commit_final_fails(client, async_session, mock_storage, monkeypatch, cleanup_docs):
    doc_id = uuid.uuid4()
    storage_key = f"test_key_{doc_id}"
    (mock_storage / storage_key).write_bytes(VALID_PDF)
    doc = CVDocument(id=doc_id, original_filename="test.pdf", storage_key=storage_key, media_type="application/pdf", size_bytes=100, sha256="abc", status=CVStatus.uploaded)
    async_session.add(doc)
    await async_session.commit()
    cleanup_docs.append(doc_id)
    
    async def mock_extract(*args):
        return "Valid extracted text"
    monkeypatch.setattr("app.services.extractor.CVTextExtractor.extract_text", mock_extract)
    
    original_commit = AsyncSession.commit
    async def mock_commit(self):
        # Fail ONLY on final extracted commit
        if any(d.status == CVStatus.extracted for d in self.dirty):
            raise Exception("DB Error Final")
        await original_commit(self)
    monkeypatch.setattr(AsyncSession, "commit", mock_commit)
    
    res = await client.post(f"/api/v1/cv-documents/{doc_id}/extract")
    assert res.status_code == 500
    assert res.json()["detail"] == "Lỗi lưu kết quả trích xuất vào CSDL."
    
    # Check recovery status directly via clean db connection
    await async_session.refresh(doc)
    assert doc.status == CVStatus.extraction_failed
    assert doc.extraction_error == "Lỗi lưu kết quả, vui lòng thử lại."

@pytest.mark.asyncio
async def test_extract_commit_recovery_fails(client, async_session, mock_storage, monkeypatch, cleanup_docs):
    doc_id = uuid.uuid4()
    storage_key = f"test_key_{doc_id}"
    (mock_storage / storage_key).write_bytes(VALID_PDF)
    doc = CVDocument(id=doc_id, original_filename="test.pdf", storage_key=storage_key, media_type="application/pdf", size_bytes=100, sha256="abc", status=CVStatus.uploaded)
    async_session.add(doc)
    await async_session.commit()
    cleanup_docs.append(doc_id)
    
    async def mock_extract(*args):
        return "Valid extracted text"
    monkeypatch.setattr("app.services.extractor.CVTextExtractor.extract_text", mock_extract)
    
    original_commit = AsyncSession.commit
    async def mock_commit(self):
        # Fail on final extracted commit AND recovery extraction_failed commit
        if any(d.status in (CVStatus.extracted, CVStatus.extraction_failed) for d in self.dirty):
            raise Exception("DB Error Total")
        await original_commit(self)
    monkeypatch.setattr(AsyncSession, "commit", mock_commit)
    
    res = await client.post(f"/api/v1/cv-documents/{doc_id}/extract")
    assert res.status_code == 500
    assert res.json()["detail"] == "Lỗi hệ thống nghiêm trọng khi lưu trạng thái."


