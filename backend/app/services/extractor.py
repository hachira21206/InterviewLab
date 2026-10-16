import re
import asyncio
from pathlib import Path
from pypdf import PdfReader
from pypdf.errors import FileNotDecryptedError
import docx
import logging

logger = logging.getLogger(__name__)

MAX_TEXT_LENGTH = 100000
MAX_PDF_PAGES = 50

class ExtractionError(Exception):
    pass

class BaseExtractor:
    @classmethod
    def _normalize_text(cls, text: str) -> str:
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    @classmethod
    def _validate_length(cls, text: str) -> str:
        if len(text) > MAX_TEXT_LENGTH:
            raise ExtractionError("Nội dung vượt quá giới hạn 100.000 ký tự.")
        return text

class PDFExtractor(BaseExtractor):
    @classmethod
    def extract_sync(cls, file_path: Path) -> str:
        try:
            reader = PdfReader(str(file_path))
            
            if reader.is_encrypted:
                try:
                    reader.decrypt("")
                except Exception:
                    pass
                if reader.is_encrypted:
                    raise ExtractionError("Không thể đọc PDF bị khóa mật khẩu.")

            if len(reader.pages) > MAX_PDF_PAGES:
                raise ExtractionError(f"PDF vượt quá giới hạn {MAX_PDF_PAGES} trang.")

            extracted_text = []
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    extracted_text.append(text)
            
            raw_text = "\n\n".join(extracted_text)
            clean_text = cls._normalize_text(raw_text)
            
            if not clean_text:
                raise ExtractionError("Không tìm thấy nội dung văn bản trong PDF. CV dạng scan hiện chưa được hỗ trợ.")
                
            return cls._validate_length(clean_text)
            
        except FileNotDecryptedError:
            raise ExtractionError("Không thể đọc PDF bị khóa mật khẩu.")
        except ExtractionError:
            raise
        except Exception as e:
            logger.exception("Lỗi parser khi đọc PDF")
            raise ExtractionError("Không thể trích xuất nội dung PDF.")

class DOCXExtractor(BaseExtractor):
    @classmethod
    def extract_sync(cls, file_path: Path) -> str:
        try:
            doc = docx.Document(str(file_path))
            extracted_text = []
            
            for element in doc.element.body:
                if element.tag.endswith('p'):
                    p = docx.text.paragraph.Paragraph(element, doc)
                    if p.text.strip():
                        extracted_text.append(p.text)
                elif element.tag.endswith('tbl'):
                    t = docx.table.Table(element, doc)
                    for row in t.rows:
                        row_data = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                        if row_data:
                            extracted_text.append(" | ".join(row_data))
                            
            raw_text = "\n".join(extracted_text)
            clean_text = cls._normalize_text(raw_text)
            
            if not clean_text:
                raise ExtractionError("Không tìm thấy nội dung văn bản trong DOCX.")
                
            return cls._validate_length(clean_text)
            
        except ExtractionError:
            raise
        except Exception as e:
            logger.exception("Lỗi parser khi đọc DOCX")
            raise ExtractionError("Không thể trích xuất nội dung DOCX.")

class CVTextExtractor:
    @staticmethod
    async def extract_text(file_path: Path, media_type: str) -> str:
        if media_type == "application/pdf":
            return await asyncio.to_thread(PDFExtractor.extract_sync, file_path)
        elif media_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            return await asyncio.to_thread(DOCXExtractor.extract_sync, file_path)
        else:
            raise ExtractionError("Định dạng file không được hỗ trợ để trích xuất.")
