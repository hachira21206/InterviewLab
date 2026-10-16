import os
import uuid
import pytest
import pytest_asyncio
import io
import zipfile
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.cv_document import CVDocument
from app.services.storage import StorageService

VALID_PDF = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n"

def create_valid_docx() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("[Content_Types].xml", "<Types></Types>")
        zf.writestr("word/document.xml", "<w:document></w:document>")
    return buf.getvalue()

VALID_DOCX = create_valid_docx()

@pytest.fixture
def test_marker():
    """Provides a unique string marker for filenames to easily identify test data."""
    return f"test_{uuid.uuid4().hex}"

@pytest.fixture
def mock_storage(tmp_path, monkeypatch):
    """Fixture to cleanly override StorageService root"""
    def mock_init(self):
        self.storage_root = tmp_path
        os.makedirs(self.storage_root, exist_ok=True)
    monkeypatch.setattr(StorageService, "__init__", mock_init)
    return tmp_path

@pytest_asyncio.fixture(autouse=True)
async def cleanup_db(async_session: AsyncSession, test_marker: str):
    """Automatically cleans up any DB rows containing the marker in the filename."""
    yield
    # Teardown: delete all rows created by this test
    result = await async_session.execute(
        select(CVDocument).where(CVDocument.original_filename.contains(test_marker))
    )
    rows = result.scalars().all()
    for row in rows:
        await async_session.delete(row)
    if rows:
        await async_session.commit()

@pytest.mark.asyncio
async def test_upload_valid_pdf_integration(client, async_session: AsyncSession, mock_storage, test_marker):
    filename = f"{test_marker}.pdf"
    response = await client.post(
        "/api/v1/cv-documents",
        files={"file": (filename, VALID_PDF, "application/pdf")}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["original_filename"] == filename
    assert data["media_type"] == "application/pdf"
    assert "storage_key" not in data
    assert "path" not in data
    
    doc_id = data["id"]
    result = await async_session.execute(select(CVDocument).where(CVDocument.id == doc_id))
    doc = result.scalars().first()
    assert doc is not None
    assert (mock_storage / doc.storage_key).exists()

@pytest.mark.asyncio
async def test_upload_valid_docx_integration(client, async_session: AsyncSession, mock_storage, test_marker):
    filename = f"{test_marker}.docx"
    response = await client.post(
        "/api/v1/cv-documents",
        files={"file": (filename, VALID_DOCX, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    )
    assert response.status_code == 201

@pytest.mark.asyncio
async def test_upload_invalid_extension(client, mock_storage, test_marker):
    response = await client.post(
        "/api/v1/cv-documents",
        files={"file": (f"{test_marker}.txt", b"hello world", "text/plain")}
    )
    assert response.status_code == 400
    assert not list(mock_storage.glob("*"))

@pytest.mark.asyncio
async def test_upload_empty_file(client, mock_storage, test_marker):
    response = await client.post(
        "/api/v1/cv-documents",
        files={"file": (f"{test_marker}.pdf", b"", "application/pdf")}
    )
    assert response.status_code == 400
    assert not list(mock_storage.glob("*"))

@pytest.mark.asyncio
async def test_upload_fake_pdf(client, mock_storage, test_marker):
    response = await client.post(
        "/api/v1/cv-documents",
        files={"file": (f"{test_marker}.pdf", b"this is not a pdf", "application/pdf")}
    )
    assert response.status_code == 415
    assert not list(mock_storage.glob("*"))

@pytest.mark.asyncio
async def test_upload_pdf_garbage_prefix(client, mock_storage, test_marker):
    response = await client.post(
        "/api/v1/cv-documents",
        files={"file": (f"{test_marker}.pdf", b"garbage%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n", "application/pdf")}
    )
    assert response.status_code == 415
    assert not list(mock_storage.glob("*"))

@pytest.mark.asyncio
async def test_upload_too_large(client, mock_storage, test_marker):
    large_content = b"a" * (5 * 1024 * 1024 + 10)
    response = await client.post(
        "/api/v1/cv-documents",
        files={"file": (f"{test_marker}_large.pdf", large_content, "application/pdf")}
    )
    assert response.status_code == 413
    assert not list(mock_storage.glob("*"))

@pytest.mark.asyncio
async def test_upload_docx_not_zip(client, mock_storage, test_marker):
    response = await client.post(
        "/api/v1/cv-documents",
        files={"file": (f"{test_marker}.docx", b"not a zip", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    )
    assert response.status_code == 415
    assert not list(mock_storage.glob("*"))

@pytest.mark.asyncio
async def test_upload_docx_missing_xml(client, mock_storage, test_marker):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("random.txt", "hello")
    
    response = await client.post(
        "/api/v1/cv-documents",
        files={"file": (f"{test_marker}.docx", buf.getvalue(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    )
    assert response.status_code == 415
    assert not list(mock_storage.glob("*"))

@pytest.mark.asyncio
async def test_upload_docx_traversal(client, mock_storage, test_marker):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("[Content_Types].xml", "<Types></Types>")
        zf.writestr("word/document.xml", "<w:document></w:document>")
        zf.writestr("../dangerous.txt", "bad")
    
    response = await client.post(
        "/api/v1/cv-documents",
        files={"file": (f"{test_marker}.docx", buf.getvalue(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    )
    assert response.status_code == 415
    assert not list(mock_storage.glob("*"))

@pytest.mark.asyncio
async def test_upload_mime_mismatch(client, mock_storage, test_marker):
    response = await client.post(
        "/api/v1/cv-documents",
        files={"file": (f"{test_marker}.pdf", VALID_PDF, "text/plain")} 
    )
    assert response.status_code == 415
    assert not list(mock_storage.glob("*"))

@pytest.mark.asyncio
async def test_upload_filename_traversal(client, mock_storage, test_marker):
    response = await client.post(
        "/api/v1/cv-documents",
        files={"file": (f"../{test_marker}.pdf", VALID_PDF, "application/pdf")}
    )
    assert response.status_code == 400
    assert not list(mock_storage.glob("*"))

@pytest.mark.asyncio
async def test_upload_filename_traversal_windows(client, mock_storage, test_marker):
    response = await client.post(
        "/api/v1/cv-documents",
        files={"file": (f"..\\{test_marker}.pdf", VALID_PDF, "application/pdf")}
    )
    assert response.status_code == 400
    assert not list(mock_storage.glob("*"))
    
@pytest.mark.asyncio
async def test_upload_filename_control_char(client, mock_storage, test_marker):
    body = f'--boundary\r\nContent-Disposition: form-data; name="file"; filename="{test_marker}\n.pdf"\r\nContent-Type: application/pdf\r\n\r\n%PDF-1.4\n\r\n--boundary--\r\n'.encode('utf-8')
    headers = {'Content-Type': 'multipart/form-data; boundary=boundary'}
    response = await client.post("/api/v1/cv-documents", content=body, headers=headers)
    assert response.status_code == 400
    assert not list(mock_storage.glob("*"))

@pytest.mark.asyncio
async def test_upload_filename_too_long(client, mock_storage, test_marker):
    long_name = "a" * 252 + ".pdf" 
    response = await client.post(
        "/api/v1/cv-documents",
        files={"file": (long_name, VALID_PDF, "application/pdf")}
    )
    assert response.status_code == 400
    assert not list(mock_storage.glob("*"))

@pytest.mark.asyncio
async def test_upload_filename_unicode(client, mock_storage, test_marker):
    response = await client.post(
        "/api/v1/cv-documents",
        files={"file": (f"hồ sơ_xin_việc_2026_{test_marker}.pdf", VALID_PDF, "application/pdf")}
    )
    assert response.status_code == 201

@pytest.mark.asyncio
async def test_upload_filename_multiple_dots(client, mock_storage, test_marker):
    response = await client.post(
        "/api/v1/cv-documents",
        files={"file": (f"my.cv.v2.final_{test_marker}.pdf", VALID_PDF, "application/pdf")}
    )
    assert response.status_code == 201

@pytest.mark.asyncio
async def test_get_document_metadata(client, async_session: AsyncSession, mock_storage, test_marker):
    post_response = await client.post(
        "/api/v1/cv-documents",
        files={"file": (f"get_{test_marker}.docx", VALID_DOCX, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    )
    assert post_response.status_code == 201
    doc_id = post_response.json()["id"]
    
    get_response = await client.get(f"/api/v1/cv-documents/{doc_id}")
    assert get_response.status_code == 200
    assert get_response.json()["original_filename"] == f"get_{test_marker}.docx"

@pytest.mark.asyncio
async def test_get_nonexistent_document(client):
    response = await client.get(f"/api/v1/cv-documents/{uuid.uuid4()}")
    assert response.status_code == 404

@pytest.mark.asyncio
async def test_db_flush_failure_rollback(client, async_session: AsyncSession, mock_storage, test_marker, monkeypatch):
    from app.repositories.cv_document import CVDocumentRepository
    original_create = CVDocumentRepository.create
    
    async def mock_create(self, cv_in):
        # We can just raise an exception to simulate flush failure
        raise Exception("Simulated DB flush failure")
        
    monkeypatch.setattr("app.repositories.cv_document.CVDocumentRepository.create", mock_create)
    
    response = await client.post(
        "/api/v1/cv-documents",
        files={"file": (f"{test_marker}.pdf", VALID_PDF, "application/pdf")}
    )
    assert response.status_code == 500
    assert not list(mock_storage.glob("*")) # No temp or final file
    
    result = await async_session.execute(select(CVDocument).where(CVDocument.original_filename == f"{test_marker}.pdf"))
    assert result.scalars().first() is None

@pytest.mark.asyncio
async def test_db_commit_failure_rollback(client, async_session: AsyncSession, mock_storage, test_marker, monkeypatch):
    async def mock_commit():
        raise Exception("Simulated DB commit failure")
    monkeypatch.setattr("sqlalchemy.ext.asyncio.AsyncSession.commit", mock_commit)
    
    response = await client.post(
        "/api/v1/cv-documents",
        files={"file": (f"{test_marker}.pdf", VALID_PDF, "application/pdf")}
    )
    assert response.status_code == 500
    assert not list(mock_storage.glob("*")) # No files should remain
    
    # DB flush might have added the row, but session rolled back (or should have)
    # Check if DB has it
    result = await async_session.execute(select(CVDocument).where(CVDocument.original_filename == f"{test_marker}.pdf"))
    assert result.scalars().first() is None

@pytest.mark.asyncio
async def test_storage_finalize_failure(client, async_session: AsyncSession, mock_storage, test_marker, monkeypatch):
    async def mock_finalize(*args, **kwargs):
        raise Exception("Simulated Storage Error")
    monkeypatch.setattr(StorageService, "finalize_file", mock_finalize)
    
    response = await client.post(
        "/api/v1/cv-documents",
        files={"file": (f"{test_marker}.pdf", VALID_PDF, "application/pdf")}
    )
    assert response.status_code == 500
    assert not list(mock_storage.glob("*"))
    
    result = await async_session.execute(select(CVDocument).where(CVDocument.original_filename == f"{test_marker}.pdf"))
    assert result.scalars().first() is None
