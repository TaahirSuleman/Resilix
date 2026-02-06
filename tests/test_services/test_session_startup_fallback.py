from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_ensure_session_store_initialized_falls_back_to_memory(monkeypatch: pytest.MonkeyPatch):
    import resilix.config.settings as settings_module
    import resilix.services.session as session_module

    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/resilix")
    settings_module.get_settings.cache_clear()
    session_module._session_store = None

    async def _raise_conn_refused(self):  # type: ignore[no-untyped-def]
        raise ConnectionRefusedError("connection refused")

    monkeypatch.setattr(session_module.PostgresSessionStore, "init", _raise_conn_refused)

    store = await session_module.ensure_session_store_initialized()
    assert isinstance(store, session_module.MemorySessionStore)
    assert isinstance(session_module.get_session_store(), session_module.MemorySessionStore)

    settings_module.get_settings.cache_clear()
    session_module._session_store = None
