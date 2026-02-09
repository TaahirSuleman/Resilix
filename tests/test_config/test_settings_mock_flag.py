from __future__ import annotations

import resilix.config.settings as settings_module


def _fresh_settings():
    settings_module.get_settings.cache_clear()
    return settings_module.get_settings()


def test_uses_canonical_mock_flag_when_both_are_set(monkeypatch):
    monkeypatch.setenv("USE_MOCK_PROVIDERS", "false")
    monkeypatch.setenv("USE_MOCK_MCP", "true")
    settings = _fresh_settings()
    assert settings.effective_use_mock_providers() is False
    assert settings.is_legacy_mock_flag_used() is False


def test_uses_legacy_flag_when_canonical_absent(monkeypatch):
    monkeypatch.delenv("USE_MOCK_PROVIDERS", raising=False)
    monkeypatch.setenv("USE_MOCK_MCP", "true")
    settings = _fresh_settings()
    assert settings.effective_use_mock_providers() is True
    assert settings.is_legacy_mock_flag_used() is True


def test_uses_default_when_no_flag_set(monkeypatch):
    monkeypatch.delenv("USE_MOCK_PROVIDERS", raising=False)
    monkeypatch.delenv("USE_MOCK_MCP", raising=False)
    settings = _fresh_settings()
    assert settings.effective_use_mock_providers() is settings.use_mock_providers
    assert settings.is_legacy_mock_flag_used() is False


def test_normalizes_gemini_flash_model_alias(monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL_FLASH", "gemini-3-flash")
    settings = _fresh_settings()
    assert settings.resolved_gemini_model_flash() == "gemini-3-flash-preview"


def test_default_thinking_levels_are_low(monkeypatch):
    monkeypatch.delenv("SENTINEL_THINKING_LEVEL", raising=False)
    monkeypatch.delenv("SHERLOCK_THINKING_LEVEL", raising=False)
    monkeypatch.delenv("MECHANIC_THINKING_LEVEL", raising=False)
    settings = _fresh_settings()
    assert settings.sentinel_thinking_level == "low"
    assert settings.sherlock_thinking_level == "low"
    assert settings.mechanic_thinking_level == "low"
