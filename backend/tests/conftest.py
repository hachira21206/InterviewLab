import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

from app.db.session import SessionLocal
import pytest_asyncio

@pytest_asyncio.fixture
async def async_session():
    async with SessionLocal() as session:
        yield session
