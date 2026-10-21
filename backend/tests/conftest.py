import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

from app.db.session import SessionLocal
from app.core.config import settings
import pytest_asyncio

@pytest.fixture(autouse=True)
def block_external_ai_network_calls(monkeypatch):
    """Ensure no test can ever make a real external network call to AI providers."""
    original_send = AsyncClient.send

    async def guarded_send(self, request, *args, **kwargs):
        host = request.url.host
        # Allow ASGI test transport (host == "test") and local services
        if host not in ("test", "localhost", "127.0.0.1", "example.test"):
            raise RuntimeError(f"Real external network call to {host} is blocked during automated tests!")
        return await original_send(self, request, *args, **kwargs)

    monkeypatch.setattr(AsyncClient, "send", guarded_send)

@pytest_asyncio.fixture
async def async_session():
    async with SessionLocal() as session:
        yield session
