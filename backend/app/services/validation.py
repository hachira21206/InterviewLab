import os
import re
import zipfile
from pathlib import Path, PurePosixPath

class FileValidationError(Exception):
    pass

class FileValidator:
    ALLOWED_EXTENSIONS = {'.pdf', '.docx'}
    MAX_UNCOMPRESSED_SIZE = 50 * 1024 * 1024  # 50MB zip bomb limit
    MAX_ZIP_ENTRIES = 1000
    MAX_FILENAME_LENGTH = 255
    
    # MIME mapping
    MIME_MAPPING = {
        '.pdf': 'application/pdf',
        '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    }

    @classmethod
    def validate_filename(cls, filename: str) -> str:
        """Validates length, control chars, path traversals. Returns the valid extension."""
        if not filename:
            raise FileValidationError("Filename is empty")
            
        if len(filename) > cls.MAX_FILENAME_LENGTH:
            raise FileValidationError(f"Filename exceeds {cls.MAX_FILENAME_LENGTH} characters")
            
        # Reject control characters (0x00-0x1F and 0x7F)
        if re.search(r'[\x00-\x1f\x7f]', filename):
            raise FileValidationError("Filename contains control characters")
            
        # Reject path separators
        if '/' in filename or '\\' in filename:
            raise FileValidationError("Filename cannot contain path separators")
            
        # Though path separators are checked, double check for standard traversal strings just in case
        if '..' in filename:
            raise FileValidationError("Filename cannot contain path traversal patterns")
            
        ext = os.path.splitext(filename)[1].lower()
        if ext not in cls.ALLOWED_EXTENSIONS:
            raise FileValidationError(f"Unsupported file extension. Allowed: {', '.join(cls.ALLOWED_EXTENSIONS)}")
            
        return ext

    @classmethod
    def validate_mime_type(cls, ext: str, content_type: str | None) -> None:
        """Validates that the provided extension matches the expected MIME type."""
        expected = cls.MIME_MAPPING.get(ext)
        if content_type != expected:
            raise FileValidationError(f"MIME type mismatch. Expected {expected} for extension {ext}")

    @classmethod
    def validate_file_content(cls, file_path: Path, ext: str) -> str:
        """
        Validates magic bytes / zip structure.
        Returns the determined media_type.
        """
        if ext == '.pdf':
            return cls._validate_pdf(file_path)
        elif ext == '.docx':
            return cls._validate_docx(file_path)
        else:
            raise FileValidationError("Unknown extension for validation")

    @classmethod
    def _validate_pdf(cls, file_path: Path) -> str:
        with open(file_path, 'rb') as f:
            header = f.read(1024)
            # The PDF signature must be exactly at the beginning (no garbage before it)
            if not header.startswith(b'%PDF-'):
                raise FileValidationError("Invalid PDF signature or garbage before signature")
        return cls.MIME_MAPPING['.pdf']

    @classmethod
    def _validate_docx(cls, file_path: Path) -> str:
        if not zipfile.is_zipfile(file_path):
            raise FileValidationError("DOCX file is not a valid ZIP archive")
        
        try:
            with zipfile.ZipFile(file_path) as zf:
                infos = zf.infolist()
                
                if len(infos) > cls.MAX_ZIP_ENTRIES:
                    raise FileValidationError("Too many files in ZIP archive (possible zip bomb)")
                
                total_uncompressed = 0
                has_content_types = False
                has_document = False
                
                for info in infos:
                    # Prevent zip-slip or traversal in zip
                    # Reject backslashes completely to prevent Windows path traversal masking
                    if "\\" in info.filename:
                        raise FileValidationError("Dangerous path found in ZIP archive")
                        
                    posix_path = PurePosixPath(info.filename)
                    from pathlib import PureWindowsPath
                    if posix_path.is_absolute() or PureWindowsPath(info.filename).is_absolute() or '..' in posix_path.parts:
                        raise FileValidationError("Dangerous path found in ZIP archive")
                        
                    total_uncompressed += info.file_size
                    if total_uncompressed > cls.MAX_UNCOMPRESSED_SIZE:
                        raise FileValidationError("Uncompressed size too large (possible zip bomb)")
                        
                    if info.filename == '[Content_Types].xml':
                        has_content_types = True
                    elif info.filename == 'word/document.xml':
                        has_document = True

                if not (has_content_types and has_document):
                    raise FileValidationError("Missing required DOCX internal files")
                    
        except zipfile.BadZipFile:
            raise FileValidationError("Corrupted DOCX archive")
            
        return cls.MIME_MAPPING['.docx']
