"""Migração idempotente do schema (database/connection.py)."""
from __future__ import annotations

from pathlib import Path

from database.connection import Database


def _columns(db: Database, table: str) -> set[str]:
    return {row["name"] for row in db.conn.execute(f"PRAGMA table_info({table})")}


def test_migracao_adiciona_colunas_de_streak_em_tabela_nova():
    db = Database(path=":memory:")
    try:
        columns = _columns(db, "voice_stats")
        assert {"streak_current", "streak_best", "streak_last_date"} <= columns
    finally:
        db.close()


def test_migracao_e_idempotente_em_banco_ja_migrado(tmp_path: Path):
    db_path = tmp_path / "clown-test.db"

    first = Database(path=db_path)
    first.close()

    # Reabrir o mesmo arquivo não deve falhar (colunas já existem)
    second = Database(path=db_path)
    try:
        columns = _columns(second, "voice_stats")
        assert {"streak_current", "streak_best", "streak_last_date"} <= columns
    finally:
        second.close()
