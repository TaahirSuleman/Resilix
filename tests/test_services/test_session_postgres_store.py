from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import pytest

from resilix.services.session import PostgresSessionStore


@dataclass
class _ResultFirst:
    payload: dict

    def first(self):
        return (self.payload,)


@dataclass
class _ResultFetchAll:
    payload: list[tuple[str, dict]]

    def fetchall(self):
        return self.payload


class _FakeSession:
    def __init__(self, execute_result):
        self.execute_result = execute_result
        self.executed_stmt = None
        self.committed = False

    async def execute(self, stmt):
        self.executed_stmt = stmt
        return self.execute_result

    async def commit(self):
        self.committed = True


class _FakeSessionContextManager:
    def __init__(self, session: _FakeSession):
        self._session = session

    async def __aenter__(self) -> _FakeSession:
        return self._session

    async def __aexit__(self, exc_type, exc, tb):
        return False


@pytest.mark.asyncio
async def test_postgres_save_executes_and_commits(monkeypatch: pytest.MonkeyPatch):
    store = PostgresSessionStore("postgresql+asyncpg://user:pass@localhost:5432/resilix")

    fake_session = _FakeSession(execute_result=None)
    monkeypatch.setattr(store, "_sessionmaker", lambda: _FakeSessionContextManager(fake_session))

    await store.save(
        "INC-POSTGRES-001",
        {
            "created_at": datetime(2026, 2, 5, tzinfo=timezone.utc),
            "state": "ok",
        },
    )

    assert fake_session.executed_stmt is not None
    assert fake_session.committed is True


@pytest.mark.asyncio
async def test_postgres_get_returns_state(monkeypatch: pytest.MonkeyPatch):
    store = PostgresSessionStore("postgresql+asyncpg://user:pass@localhost:5432/resilix")

    expected = {"incident_id": "INC-POSTGRES-002", "status": "resolved"}
    fake_session = _FakeSession(execute_result=_ResultFirst(payload=expected))
    monkeypatch.setattr(store, "_sessionmaker", lambda: _FakeSessionContextManager(fake_session))

    result = await store.get("INC-POSTGRES-002")

    assert result == expected
    assert fake_session.executed_stmt is not None


@pytest.mark.asyncio
async def test_postgres_list_items_returns_rows(monkeypatch: pytest.MonkeyPatch):
    store = PostgresSessionStore("postgresql+asyncpg://user:pass@localhost:5432/resilix")

    rows = [
        ("INC-POSTGRES-010", {"status": "processing"}),
        ("INC-POSTGRES-011", {"status": "resolved"}),
    ]
    fake_session = _FakeSession(execute_result=_ResultFetchAll(payload=rows))
    monkeypatch.setattr(store, "_sessionmaker", lambda: _FakeSessionContextManager(fake_session))

    result = await store.list_items()

    assert result == rows
    assert fake_session.executed_stmt is not None
