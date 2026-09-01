"""Carregamento de variáveis de ambiente (.env)."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True, slots=True)
class Settings:
    token: str
    dev_guild_id: int | None
    bypass_user_ids: frozenset[int] = frozenset()


def _parse_bypass_ids(raw: str) -> frozenset[int]:
    return frozenset(int(v) for v in raw.split(",") if v.strip().isdigit())


def load_settings() -> Settings:
    token = os.getenv("BOT_TOKEN") or os.getenv("CLOWN_TOKEN")
    if not token:
        raise RuntimeError("Defina BOT_TOKEN (ou CLOWN_TOKEN) no arquivo .env")

    raw_guild = os.getenv("DEV_GUILD_ID") or os.getenv("CLOWN_GUILD_ID") or ""
    dev_guild_id = int(raw_guild) if raw_guild.strip().isdigit() else None

    bypass_user_ids = _parse_bypass_ids(os.getenv("BYPASS_USER_IDS", ""))

    return Settings(token=token, dev_guild_id=dev_guild_id, bypass_user_ids=bypass_user_ids)
