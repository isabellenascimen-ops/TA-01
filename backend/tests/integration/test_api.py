"""
Testa a API HTTP de verdade (via httpx ASGITransport), não apenas as
funções internas: valida serialização Pydantic, códigos de status,
dependency injection e o commit real feito pelo endpoint.
"""
import pytest
from httpx import ASGITransport, AsyncClient

from app.database import get_session
from app.main import app


@pytest.fixture
def client(session):
    """Substitui a dependency get_session pela sessão transacional de teste."""

    async def _override():
        yield session

    app.dependency_overrides[get_session] = _override
    transport = ASGITransport(app=app)
    yield AsyncClient(transport=transport, base_url="http://test")
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_health_endpoint(client):
    async with client as c:
        response = await c.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "phase": 1}


@pytest.mark.asyncio
async def test_create_agent_starts_with_minimal_identity(client):
    async with client as c:
        response = await c.post("/agent")
    assert response.status_code == 201
    body = response.json()
    # Seção 2 da spec: nasce sem nome e sem autodescrição.
    assert body["name"] is None
    assert body["self_description"] == ""
    assert body["version"] == 1


@pytest.mark.asyncio
async def test_chat_roundtrip_through_http(client):
    async with client as c:
        created = await c.post("/agent")
        agent_id = created.json()["agent_id"]

        response = await c.post(f"/chat/{agent_id}/message", json={"text": "Olá, agente."})

    assert response.status_code == 200
    body = response.json()
    assert body["chosen_action"] == "RESPOND"
    assert body["response_text"]
    assert body["trace_id"]
    assert body["resulting_episode_id"]


@pytest.mark.asyncio
async def test_chat_with_unknown_agent_returns_404(client):
    async with client as c:
        response = await c.post(
            "/chat/00000000-0000-0000-0000-000000000000/message", json={"text": "oi"}
        )
    assert response.status_code == 404
