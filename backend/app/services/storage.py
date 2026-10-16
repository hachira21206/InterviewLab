import os
import uuid
import hashlib
import asyncio
from pathlib import Path
from fastapi import UploadFile

from app.core.config import settings

class StorageService:
    def __init__(self):
        self.project_root = Path(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
        configured_path = Path(settings.STORAGE_ROOT)
        if configured_path.is_absolute():
            self.storage_root = configured_path
        else:
            self.storage_root = (self.project_root / configured_path).resolve()
        os.makedirs(self.storage_root, exist_ok=True)

    async def save_temp_file(self, file: UploadFile, max_size: int | None = None) -> tuple[Path, str, int]:
        """
        Stream file to a temporary file asynchronously, calculating SHA256 and size.
        Raises ValueError if size exceeds max_size.
        """
        effective_max_size = max_size if max_size is not None else settings.MAX_UPLOAD_SIZE_BYTES
        temp_filename = f"tmp_{uuid.uuid4().hex}"
        temp_path = self.storage_root / temp_filename
        
        sha256 = hashlib.sha256()
        size_bytes = 0

        def _write_temp():
            nonlocal size_bytes
            with open(temp_path, "wb") as out_file:
                while chunk := file.file.read(8192):
                    size_bytes += len(chunk)
                    if size_bytes > effective_max_size:
                        raise ValueError(f"File exceeds maximum allowed size of {effective_max_size} bytes")
                    out_file.write(chunk)
                    sha256.update(chunk)
            file.file.seek(0)
            return sha256.hexdigest(), size_bytes

        try:
            hash_str, size_bytes_final = await asyncio.to_thread(_write_temp)
            return temp_path, hash_str, size_bytes_final
        except Exception as e:
            if temp_path.exists():
                os.remove(temp_path)
            raise e

    async def finalize_file(self, temp_path: Path, ext: str) -> str:
        """
        Rename temp file to its final storage key.
        Prevents overwriting.
        """
        storage_key = f"{uuid.uuid4().hex}{ext}"
        final_path = self.storage_root / storage_key
        
        def _rename():
            if final_path.exists():
                raise FileExistsError("File already exists")
            os.replace(temp_path, final_path)
            
        await asyncio.to_thread(_rename)
        return storage_key

    def get_file_path_by_key(self, storage_key: str) -> Path:
        """
        Resolve storage key to a safe absolute path.
        Raises ValueError if path traversal detected.
        Raises FileNotFoundError if file does not exist.
        """
        # Reject obvious dangerous chars early
        if "\\" in storage_key or ".." in storage_key or "/" in storage_key:
            raise ValueError("Invalid storage key")
            
        target_path = (self.storage_root / storage_key).resolve()
        root_path = self.storage_root.resolve()
        
        if not target_path.is_relative_to(root_path):
            raise ValueError("Path traversal detected")
            
        if not target_path.exists():
            raise FileNotFoundError("File not found in storage")
            
        return target_path

    async def delete_file_by_key(self, storage_key: str):
        target = self.storage_root / storage_key
        # Strict containment check
        try:
            if not target.resolve().is_relative_to(self.storage_root.resolve()):
                return
        except ValueError:
            pass
            
        def _delete():
            if target.exists():
                os.remove(target)
        await asyncio.to_thread(_delete)

    async def quarantine_file_by_key(self, storage_key: str) -> Path | None:
        """Atomically move a user file aside until its database deletion commits.

        The caller can restore this path on rollback, avoiding a database row
        that points at a file already permanently deleted.
        """
        if "\\" in storage_key or ".." in storage_key or "/" in storage_key:
            raise ValueError("Invalid storage key")
        source = (self.storage_root / storage_key).resolve()
        root = self.storage_root.resolve()
        if not source.is_relative_to(root):
            raise ValueError("Path traversal detected")
        if not source.exists():
            return None
        quarantined = root / f".deleting_{uuid.uuid4().hex}_{storage_key}"

        def _move():
            os.replace(source, quarantined)

        await asyncio.to_thread(_move)
        return quarantined

    async def restore_quarantined_file(self, quarantined: Path, storage_key: str):
        destination = (self.storage_root / storage_key).resolve()
        root = self.storage_root.resolve()
        if not quarantined.resolve().is_relative_to(root) or not destination.is_relative_to(root):
            raise ValueError("Invalid storage path")

        def _restore():
            if quarantined.exists():
                os.replace(quarantined, destination)

        await asyncio.to_thread(_restore)

    async def delete_quarantined_file(self, quarantined: Path):
        root = self.storage_root.resolve()
        if not quarantined.resolve().is_relative_to(root) or not quarantined.name.startswith(".deleting_"):
            raise ValueError("Invalid quarantine path")

        def _delete():
            if quarantined.exists():
                os.remove(quarantined)

        await asyncio.to_thread(_delete)

    async def delete_temp_file(self, temp_path: Path):
        try:
            if not temp_path.resolve().is_relative_to(self.storage_root.resolve()):
                return
        except Exception:
            return
            
        def _delete():
            if temp_path.exists():
                os.remove(temp_path)
        await asyncio.to_thread(_delete)
