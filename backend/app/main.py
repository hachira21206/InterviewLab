import logging
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager

from app.core.config import settings
from app.core.logging import setup_logging
from app.api import health
from app.db.session import engine

# Initialize structured logging with sensitive data redaction
setup_logging(debug=settings.DEBUG)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    # Dispose the database engine cleanly on shutdown
    logger.info("Shutting down application: disposing database engine...")
    await engine.dispose()
    logger.info("Database engine disposed.")

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json" if settings.DEBUG else None,
    docs_url=f"{settings.API_V1_STR}/docs" if settings.DEBUG else None,
    redoc_url=f"{settings.API_V1_STR}/redoc" if settings.DEBUG else None,
    lifespan=lifespan
)

# Set up CORS with explicit origins, methods and headers
allowed_origins = [str(o) for o in settings.FRONTEND_ORIGINS] if settings.FRONTEND_ORIGINS else []
if allowed_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "Accept", "Origin", "X-Requested-With"],
    )

# Global unhandled exception handler to prevent leaking raw tracebacks
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    # Never attach the raw exception here: arbitrary third-party exceptions can
    # embed prompts, credentials, local paths, or user content in their text.
    logger.error(
        "Unhandled server error on %s %s: %s",
        request.method,
        request.url.path,
        type(exc).__name__,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Lỗi hệ thống nội bộ. Vui lòng thử lại sau."},
    )

# Include routers
app.include_router(health.router, prefix=f"{settings.API_V1_STR}/health", tags=["health"])
from app.api import cv_documents
from app.api.endpoints import job_applications, application_analyses, interview_sessions
app.include_router(cv_documents.router, prefix=f"{settings.API_V1_STR}/cv-documents", tags=["cv_documents"])
app.include_router(job_applications.router, prefix=f"{settings.API_V1_STR}/job-applications", tags=["job_applications"])
app.include_router(application_analyses.router, prefix=f"{settings.API_V1_STR}/job-applications", tags=["application_analyses"])
app.include_router(interview_sessions.router, prefix=f"{settings.API_V1_STR}/job-applications", tags=["interview_sessions"])
app.include_router(interview_sessions.session_router, prefix=f"{settings.API_V1_STR}/interview-sessions", tags=["interview_sessions_flow"])

@app.get("/")
async def root():
    return {"message": "Welcome to Backend Intern Interview Platform API"}
