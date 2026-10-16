import uuid
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.schemas.application_analysis import AnalysisCreateRequest, ApplicationAnalysisResponse
from app.services.application_analysis import ApplicationAnalysisService
from app.core.exceptions import ProviderConfigurationError

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/{application_id}/analysis", response_model=ApplicationAnalysisResponse)
async def analyze_application(
    application_id: uuid.UUID,
    req: AnalysisCreateRequest,
    db: AsyncSession = Depends(get_db)
):
    if not req.consent_to_external_ai:
        raise HTTPException(status_code=422, detail="Bạn phải đồng ý với điều khoản gửi dữ liệu.")
        
    try:
        analysis = await ApplicationAnalysisService.create_or_retry_analysis(db, application_id, req)
        return analysis
    except ProviderConfigurationError as e:
        logger.error(f"Provider configuration error: {e}")
        raise HTTPException(status_code=503, detail="Dịch vụ AI chưa được cấu hình. Vui lòng thử lại sau.")
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        logger.error(f"Analysis creation failed", exc_info=True)
        raise HTTPException(status_code=500, detail="Lỗi máy chủ nội bộ.")

@router.get("/{application_id}/analysis", response_model=ApplicationAnalysisResponse)
async def get_analysis(
    application_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    analysis = await ApplicationAnalysisService.get_by_application_id(db, application_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Không tìm thấy kết quả phân tích.")
    return analysis
