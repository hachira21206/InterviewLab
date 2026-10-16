from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.db.session import get_db

router = APIRouter()

@router.get("")
async def health_check():
    """
    Health check endpoint to verify the API is running.
    Does not depend on the database.
    """
    return {"status": "ok", "message": "API is healthy"}

@router.get("/db")
async def health_check_db(db: AsyncSession = Depends(get_db)):
    """
    Health check endpoint to verify database connectivity.
    """
    try:
        # Execute a simple query
        await db.execute(text("SELECT 1"))
        return {"status": "ok", "message": "Database is connected"}
    except Exception as e:
        # In a real app, log the error 'e' internally
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection failed",
        )
