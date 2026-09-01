"""Carregamento de configurações via .env (config/settings.py)."""

from __future__ import annotations

import pytest

from config.settings import _parse_bypass_ids, load_settings


def test_parse_bypass_ids_vazio():
    assert _parse_bypass_ids("") == frozenset()


def test_parse_bypass_ids_varios_ids_com_espacos():
    assert _parse_bypass_ids("123, 456,789") == frozenset({123, 456, 789})


def test_parse_bypass_ids_ignora_valores_nao_numericos():
    assert _parse_bypass_ids("123,abc,,999") == frozenset({123, 999})


def test_load_settings_le_bypass_user_ids_do_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("BOT_TOKEN", "fake-token")
    monkeypatch.setenv("BYPASS_USER_IDS", "111,222")
    monkeypatch.delenv("CLOWN_TOKEN", raising=False)

    settings = load_settings()

    assert settings.bypass_user_ids == frozenset({111, 222})


def test_load_settings_sem_bypass_user_ids_fica_vazio(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("BOT_TOKEN", "fake-token")
    monkeypatch.delenv("BYPASS_USER_IDS", raising=False)

    settings = load_settings()

    assert settings.bypass_user_ids == frozenset()
