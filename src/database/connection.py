"""Conexão SQLite única do bot (WAL, migrações automáticas).

As operações são síncronas porém sub-milissegundo; para o volume de um bot
de voz (1 escrita por membro ativo por minuto) isso não bloqueia o event
loop de forma perceptível e evita a complexidade de um pool assíncrono.
"""
from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

log = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS guild_config (
    guild_id TEXT PRIMARY KEY,
    config   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS voice_stats (
    guild_id       TEXT NOT NULL,
    user_id        TEXT NOT NULL,
    total_xp       INTEGER NOT NULL DEFAULT 0,
    total_seconds  INTEGER NOT NULL DEFAULT 0,
    period_xp      INTEGER NOT NULL DEFAULT 0,
    period_seconds INTEGER NOT NULL DEFAULT 0,
    daily_xp       INTEGER NOT NULL DEFAULT 0,
    daily_seconds  INTEGER NOT NULL DEFAULT 0,
    daily_date     TEXT    NOT NULL DEFAULT '',
    PRIMARY KEY (guild_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_stats_period ON voice_stats (guild_id, period_xp DESC);
CREATE INDEX IF NOT EXISTS idx_stats_total  ON voice_stats (guild_id, total_xp DESC);
"""

# Colunas adicionadas após a versão inicial (migração idempotente)
_MIGRATIONS = [
    "ALTER TABLE voice_stats ADD COLUMN streak_current INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE voice_stats ADD COLUMN streak_best INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE voice_stats ADD COLUMN streak_last_date TEXT NOT NULL DEFAULT ''",
]


class Database:
    """Encapsula a conexão sqlite3 compartilhada pelos repositórios."""

    def __init__(self, path: Path | None = None, **kwargs) -> None:
        if path is None:
            # Suporta CLOWN_DB_PATH como env var para hosts (padrão: raiz do projeto)
            import os
            db_env = os.getenv("CLOWN_DB_PATH")
            if db_env:
                path = Path(db_env)
            else:
                # src/database/connection.py → raiz do projeto (clown/)
                path = Path(__file__).resolve().parents[2] / "clown.db"

        self.conn = sqlite3.connect(str(path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode = WAL")
        self.conn.execute("PRAGMA synchronous = NORMAL")
        self.conn.executescript(_SCHEMA)
        self._migrate()
        log.info("Banco de dados pronto em %s", path)

    def _migrate(self) -> None:
        for ddl in _MIGRATIONS:
            try:
                self.conn.execute(ddl)
            except sqlite3.OperationalError:
                pass  # coluna já existe
        self.conn.commit()

    def close(self) -> None:
        self.conn.commit()
        self.conn.close()
