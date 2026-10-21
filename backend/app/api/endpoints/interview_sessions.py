import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.schemas.interview_questions import InterviewSessionResponse, CreateSessionRequest, WeaknessRecommendationResponse
from app.schemas.interview_response import ResponseSubmitRequest, InterviewProgressResponse
from app.services.interview_session import InterviewSessionService
from typing import Optional

router = APIRouter()
session_router = APIRouter()

# Routes mounted at /api/v1/job-applications
@router.post("/{application_id}/interview-sessions", response_model=InterviewSessionResponse)
async def create_interview_session(
    application_id: uuid.UUID,
    request: CreateSessionRequest,
    db: AsyncSession = Depends(get_db)
):
    session = await InterviewSessionService.create_or_retry_session(
        db,
        application_id,
        request.consent_to_external_ai,
        practice_mode=request.practice_mode,
        focus_category=request.focus_category,
    )
    return session

@router.post("/{application_id}/interview-sessions/attempts", response_model=InterviewSessionResponse)
async def create_interview_attempt(
    application_id: uuid.UUID,
    request: CreateSessionRequest,
    db: AsyncSession = Depends(get_db)
):
    session = await InterviewSessionService.create_attempt(
        db,
        application_id,
        request.consent_to_external_ai,
        practice_mode=request.practice_mode,
        focus_category=request.focus_category,
    )
    return session

@router.get("/{application_id}/interview-sessions/current", response_model=InterviewSessionResponse)
async def get_current_session(
    application_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    session = await InterviewSessionService.get_current_session(db, application_id)
    return session

@router.get("/{application_id}/interview-sessions/weakness-recommendation", response_model=WeaknessRecommendationResponse)
async def get_weakness_recommendation(
    application_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    return await InterviewSessionService.get_weakness_recommendation(db, application_id)

from fastapi import Query
from app.schemas.interview_questions import InterviewHistoryListResponse

@router.get("/{application_id}/interview-sessions", response_model=InterviewHistoryListResponse)
async def get_interview_history(
    application_id: uuid.UUID,
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    return await InterviewSessionService.get_history(db, application_id, limit=limit, offset=offset)

@router.get("/{application_id}/interview-sessions/{session_id}", response_model=InterviewSessionResponse)
async def get_session_by_id(
    application_id: uuid.UUID,
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    return await InterviewSessionService.get_session_by_id(db, application_id, session_id)


from app.schemas.interview_progress import InterviewProgressReportResponse
from app.services.interview_progress_service import InterviewProgressService

@router.get("/{application_id}/interview-progress", response_model=InterviewProgressReportResponse)
async def get_interview_progress_report(
    application_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    return await InterviewProgressService.get_progress_report(db, application_id)


# Routes mounted at /api/v1/interview-sessions
@session_router.post("/{session_id}/start", response_model=InterviewProgressResponse)
async def start_interview_session(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    return await InterviewSessionService.start_session(db, session_id)


@session_router.get("/{session_id}/progress", response_model=InterviewProgressResponse)
async def get_interview_progress(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    return await InterviewSessionService.get_progress(db, session_id)


@session_router.put("/{session_id}/questions/{question_id}/response", response_model=InterviewProgressResponse)
async def submit_question_response(
    session_id: uuid.UUID,
    question_id: uuid.UUID,
    request: ResponseSubmitRequest,
    db: AsyncSession = Depends(get_db)
):
    return await InterviewSessionService.submit_question_response(db, session_id, question_id, request)


from app.schemas.interview_response import QuestionHintResponse

@session_router.get("/{session_id}/questions/{question_id}/hint", response_model=QuestionHintResponse)
async def get_question_hint(
    session_id: uuid.UUID,
    question_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    return await InterviewSessionService.get_question_hint(db, session_id, question_id)



from fastapi.responses import Response
from app.schemas.interview_evaluation import CreateEvaluationRequest, InterviewEvaluationResponse
from app.services.interview_evaluation import InterviewEvaluationService
from app.services.report_exporter import EvaluationReportExporter

@session_router.post("/{session_id}/evaluation", response_model=InterviewEvaluationResponse)
async def create_or_retry_evaluation(
    session_id: uuid.UUID,
    request: CreateEvaluationRequest,
    db: AsyncSession = Depends(get_db)
):
    eval_record = await InterviewEvaluationService.create_or_retry_evaluation(
        db, session_id, request.consent_to_external_ai
    )
    return await InterviewEvaluationService.build_response(db, eval_record)


@session_router.get("/{session_id}/evaluation", response_model=InterviewEvaluationResponse)
async def get_evaluation(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    eval_record = await InterviewEvaluationService.get_evaluation(db, session_id)
    return await InterviewEvaluationService.build_response(db, eval_record)


@session_router.get("/{session_id}/evaluation/export-docx")
async def export_evaluation_docx(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    docx_bytes, filename = await EvaluationReportExporter.export_docx(db, session_id)
    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )

