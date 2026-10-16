import pytest
from httpx import AsyncClient
from app.core.config import settings

pytestmark = pytest.mark.asyncio

async def test_health_check(client: AsyncClient):
    response = await client.get(f"{settings.API_V1_STR}/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "message": "API is healthy"}

async def test_health_check_db_success(client: AsyncClient):
    from app.main import app
    from app.db.session import get_db
    
    async def override_get_db():
        class MockSession:
            async def execute(self, query):
                pass
        yield MockSession()

    app.dependency_overrides[get_db] = override_get_db
    
    try:
        response = await client.get(f"{settings.API_V1_STR}/health/db")
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "message": "Database is connected"}
    finally:
        app.dependency_overrides.clear()

async def test_health_check_db_failure(client: AsyncClient):
    from app.main import app
    from app.db.session import get_db
    
    async def override_get_db():
        class MockSession:
            async def execute(self, query):
                raise Exception("DB Connection Error")
        yield MockSession()

    app.dependency_overrides[get_db] = override_get_db
    
    try:
        response = await client.get(f"{settings.API_V1_STR}/health/db")
        assert response.status_code == 503
        assert response.json() == {"detail": "Database connection failed"}
    finally:
        app.dependency_overrides.clear()
