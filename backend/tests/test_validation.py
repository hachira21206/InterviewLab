import os
import io
import zipfile
import pytest
import hashlib
from pathlib import Path
from app.services.validation import FileValidator, FileValidationError
from app.services.storage import StorageService
import tempfile
import asyncio

@pytest.mark.asyncio
async def test_sha256_calculation(tmp_path, monkeypatch):
    content = b"hello world this is a test content"
    expected_hash = hashlib.sha256(content).hexdigest()
    
    # Mock storage to use tmp_path
    def mock_init(self):
        self.storage_root = tmp_path
        os.makedirs(self.storage_root, exist_ok=True)
    monkeypatch.setattr(StorageService, "__init__", mock_init)
    
    storage = StorageService()
    temp_path = None
    
    with tempfile.SpooledTemporaryFile() as f:
        f.write(content)
        f.seek(0)
        from fastapi import UploadFile
        uf = UploadFile(file=f, filename="test.pdf")
        
        try:
            temp_path, sha256_hash, size = await storage.save_temp_file(uf)
            assert sha256_hash == expected_hash
        finally:
            if temp_path:
                await storage.delete_temp_file(temp_path)
            
    assert not list(tmp_path.glob("*")), "Temp directory must be empty after cleanup"

def test_validate_filename_length():
    with pytest.raises(FileValidationError, match="exceeds 255 characters"):
        FileValidator.validate_filename("a" * 252 + ".pdf")
        
    assert FileValidator.validate_filename("a" * 251 + ".pdf") == ".pdf"

def test_validate_filename_control_characters():
    # True control characters
    with pytest.raises(FileValidationError, match="control characters"):
        FileValidator.validate_filename("test\x00.pdf")
    with pytest.raises(FileValidationError, match="control characters"):
        FileValidator.validate_filename("test\n.pdf")
    with pytest.raises(FileValidationError, match="control characters"):
        FileValidator.validate_filename("test\r.pdf")
        
    # Literals should NOT fail control character check (but should pass entirely)
    assert FileValidator.validate_filename("test%00.pdf") == ".pdf"
    assert FileValidator.validate_filename("test%0A.pdf") == ".pdf"

def test_validate_filename_traversal():
    with pytest.raises(FileValidationError, match="cannot contain path separators"):
        FileValidator.validate_filename("../cv.pdf")
    with pytest.raises(FileValidationError, match="cannot contain path separators"):
        FileValidator.validate_filename("..\\cv.pdf")
        
    # Without separators but with dots, check traversal protection logic
    # Our validator blocks '/' and '\\', so '..' alone without separators is caught by the backup '..' check.
    with pytest.raises(FileValidationError, match="path traversal patterns"):
        FileValidator.validate_filename("my..cv.pdf")
    
    # Allowed dots
    assert FileValidator.validate_filename("my.cv.pdf") == ".pdf"

def test_validate_mime_type():
    FileValidator.validate_mime_type(".pdf", "application/pdf")
    FileValidator.validate_mime_type(".docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    
    with pytest.raises(FileValidationError, match="MIME type mismatch"):
        FileValidator.validate_mime_type(".pdf", "text/plain")

def test_validate_docx_traversal(tmp_path):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("[Content_Types].xml", "<Types></Types>")
        zf.writestr("word/document.xml", "<w:document></w:document>")
        zf.writestr("../dangerous.txt", "bad")
        
    test_file = tmp_path / "test.docx"
    test_file.write_bytes(buf.getvalue())
    
    with pytest.raises(FileValidationError, match="Dangerous path found"):
        FileValidator.validate_file_content(test_file, ".docx")

def test_validate_docx_absolute_path(tmp_path):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("[Content_Types].xml", "<Types></Types>")
        zf.writestr("word/document.xml", "<w:document></w:document>")
        zf.writestr("/root.txt", "bad") # absolute
        
    test_file = tmp_path / "test.docx"
    test_file.write_bytes(buf.getvalue())
    
    with pytest.raises(FileValidationError, match="Dangerous path found"):
        FileValidator.validate_file_content(test_file, ".docx")

def test_validate_docx_absolute_path_windows(tmp_path):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("[Content_Types].xml", "<Types></Types>")
        zf.writestr("word/document.xml", "<w:document></w:document>")
        zf.writestr("C:\\root.txt", "bad")
        
    test_file = tmp_path / "test.docx"
    test_file.write_bytes(buf.getvalue())
    
    with pytest.raises(FileValidationError, match="Dangerous path found"):
        FileValidator.validate_file_content(test_file, ".docx")

def test_validate_docx_traversal_backslash(tmp_path):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("[Content_Types].xml", "<Types></Types>")
        zf.writestr("word/document.xml", "<w:document></w:document>")
        zf.writestr("..\\dangerous.txt", "bad")
        
    test_file = tmp_path / "test.docx"
    test_file.write_bytes(buf.getvalue())
    
    with pytest.raises(FileValidationError, match="Dangerous path found"):
        FileValidator.validate_file_content(test_file, ".docx")

def test_validate_docx_too_many_entries(tmp_path):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("[Content_Types].xml", "<Types></Types>")
        zf.writestr("word/document.xml", "<w:document></w:document>")
        for i in range(1005):
            zf.writestr(f"file_{i}.txt", "a")
            
    test_file = tmp_path / "test.docx"
    test_file.write_bytes(buf.getvalue())
    
    with pytest.raises(FileValidationError, match="Too many files in ZIP"):
        FileValidator.validate_file_content(test_file, ".docx")

def test_validate_docx_zip_bomb(tmp_path):
    buf = io.BytesIO()
    
    # Create a sparse file on disk to avoid RAM usage
    sparse_file = tmp_path / "huge.txt"
    with open(sparse_file, "wb") as f:
        f.truncate(51 * 1024 * 1024)
        
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", "<Types></Types>")
        zf.writestr("word/document.xml", "<w:document></w:document>")
        zf.write(sparse_file, "huge.txt")
            
    test_file = tmp_path / "test.docx"
    test_file.write_bytes(buf.getvalue())
    
    with pytest.raises(FileValidationError, match="Uncompressed size too large"):
        FileValidator.validate_file_content(test_file, ".docx")
