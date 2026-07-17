import asyncio
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import get_settings
from app.database import SessionLocal
from app.main import app
from app.models import Base
from app.processing import process_pending


@pytest.fixture
async def client(tmp_path: Path, monkeypatch):
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'test.db'}"
    test_engine = create_async_engine(db_url, connect_args={"check_same_thread": False})
    test_sessions = async_sessionmaker(test_engine, expire_on_commit=False)
    monkeypatch.setattr("app.main.engine", test_engine)
    monkeypatch.setattr("app.database.SessionLocal", test_sessions)
    monkeypatch.setattr("app.processing.SessionLocal", test_sessions)
    get_settings.cache_clear()
    settings = get_settings()
    monkeypatch.setattr(settings, "scheduler_enabled", False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        yield http
    await test_engine.dispose()
    get_settings.cache_clear()


@pytest.mark.anyio
async def test_send_deduplicates_normalized_prompt(client):
    first = await client.post("/send", json={"prompt": "  hello   world\n"})
    duplicate = await client.post("/send", json={"prompt": "hello world"})
    assert first.status_code == 201
    assert duplicate.status_code == 201
    assert first.json() == {"id": duplicate.json()["id"], "exists": False}
    assert duplicate.json()["exists"] is True


@pytest.mark.anyio
async def test_query_and_processing(client):
    await client.post("/send", json={"prompt": "pending"})
    before = await client.get("/query")
    assert before.json()[0]["processed"] is False
    processed, failed = await process_pending()
    assert (processed, failed) == (1, 0)
    after = await client.get("/today")
    assert after.json()[0]["processed"] is True
    assert after.json()[0]["processed_at"] is not None


@pytest.mark.anyio
async def test_empty_prompt_is_rejected(client):
    response = await client.post("/send", json={"prompt": " \n "})
    assert response.status_code == 422
