from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional

import structlog

from resilix.config import get_settings

logger = structlog.get_logger(__name__)


def _jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        dumped = value.model_dump()
        return _jsonable(dumped)  # Recursively convert nested values
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _jsonable(val) for key, val in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if hasattr(value, "value"):
        try:
            return value.value
        except Exception:  # pragma: no cover
            pass
    return value


class SessionStore:
    async def init(self) -> None:  # pragma: no cover - interface
        return None

    async def save(self, session_id: str, state: Dict[str, Any]) -> None:  # pragma: no cover
        raise NotImplementedError

    async def get(self, session_id: str) -> Optional[Dict[str, Any]]:  # pragma: no cover
        raise NotImplementedError

    async def list_items(self) -> list[tuple[str, Dict[str, Any]]]:  # pragma: no cover
        raise NotImplementedError


@dataclass
class MemorySessionStore(SessionStore):
    _sessions: Dict[str, Dict[str, Any]]

    def __init__(self) -> None:
        self._sessions = {}

    async def save(self, session_id: str, state: Dict[str, Any]) -> None:
        self._sessions[session_id] = json.loads(json.dumps(_jsonable(state)))

    async def get(self, session_id: str) -> Optional[Dict[str, Any]]:
        return self._sessions.get(session_id)

    async def list_items(self) -> list[tuple[str, Dict[str, Any]]]:
        return list(self._sessions.items())


class PostgresSessionStore(SessionStore):
    def __init__(self, database_url: str) -> None:
        from sqlalchemy import Column, DateTime, MetaData, String, Table
        from sqlalchemy.dialects.postgresql import JSONB
        from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
        from sqlalchemy.sql import func

        self._engine = create_async_engine(database_url, echo=False, future=True)
        self._sessionmaker = async_sessionmaker(self._engine, expire_on_commit=False)
        self._metadata = MetaData()
        self._table = Table(
            "resilix_sessions",
            self._metadata,
            Column("session_id", String, primary_key=True),
            Column("state", JSONB, nullable=False),
            Column("updated_at", DateTime(timezone=True), server_default=func.now(), onupdate=func.now()),
        )

    async def init(self) -> None:
        async with self._engine.begin() as conn:
            await conn.run_sync(self._metadata.create_all)

    async def save(self, session_id: str, state: Dict[str, Any]) -> None:
        from sqlalchemy.dialects.postgresql import insert

        payload = json.loads(json.dumps(_jsonable(state)))
        async with self._sessionmaker() as session:
            stmt = insert(self._table).values(session_id=session_id, state=payload)
            stmt = stmt.on_conflict_do_update(
                index_elements=[self._table.c.session_id],
                set_={"state": payload},
            )
            await session.execute(stmt)
            await session.commit()

    async def get(self, session_id: str) -> Optional[Dict[str, Any]]:
        from sqlalchemy import select

        async with self._sessionmaker() as session:
            result = await session.execute(select(self._table.c.state).where(self._table.c.session_id == session_id))
            row = result.first()
            if not row:
                return None
            return row[0]

    async def list_items(self) -> list[tuple[str, Dict[str, Any]]]:
        from sqlalchemy import select

        async with self._sessionmaker() as session:
            result = await session.execute(select(self._table.c.session_id, self._table.c.state))
            rows = result.fetchall()
            return [(row[0], row[1]) for row in rows]


def _normalize_db_url(url: str) -> str:
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


_session_store: Optional[SessionStore] = None


def get_session_store() -> SessionStore:
    global _session_store
    if _session_store is not None:
        return _session_store

    settings = get_settings()
    if settings.database_url:
        database_url = _normalize_db_url(settings.database_url)
        _session_store = PostgresSessionStore(database_url)
    else:
        logger.warning("DATABASE_URL not set; using in-memory session store")
        _session_store = MemorySessionStore()
    return _session_store


async def ensure_session_store_initialized() -> SessionStore:
    """Initialize session store and gracefully fall back if DB is unavailable."""
    global _session_store
    store = get_session_store()
    try:
        await store.init()
        return store
    except Exception as exc:
        if isinstance(store, PostgresSessionStore):
            logger.warning(
                "Postgres session store init failed; falling back to in-memory store",
                error=str(exc),
            )
            _session_store = MemorySessionStore()
            await _session_store.init()
            return _session_store
        raise
