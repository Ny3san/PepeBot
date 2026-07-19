"""Repositório da configuração por servidor (com cache em memória)."""
from __future__ import annotations

import json

from database.connection import Database
from models.guild_config import GuildConfig


class ConfigRepository:
    def __init__(self, db: Database) -> None:
        self._db = db
        self._cache: dict[int, GuildConfig] = {}

    def get(self, guild_id: int) -> GuildConfig:
        """Config do servidor (defaults mesclados; migra formato legado)."""
        if guild_id in self._cache:
            return self._cache[guild_id]

        row = self._db.conn.execute(
            "SELECT config FROM guild_config WHERE guild_id = ?", (str(guild_id),)
        ).fetchone()
        cfg = GuildConfig.from_dict(guild_id, json.loads(row["config"]) if row else {})
        self._cache[guild_id] = cfg
        return cfg

    def save(self, cfg: GuildConfig) -> None:
        self._cache[cfg.guild_id] = cfg
        self._db.conn.execute(
            "INSERT INTO guild_config (guild_id, config) VALUES (?, ?) "
            "ON CONFLICT(guild_id) DO UPDATE SET config = excluded.config",
            (str(cfg.guild_id), json.dumps(cfg.to_dict())),
        )
        self._db.conn.commit()
