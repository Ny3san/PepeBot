"""Repositório das estatísticas de voz.

Regras de datas aplicadas na leitura (lazy):
  • Virada de dia zera os contadores diários.
  • Sequência (streak) é zerada se o membro ficou um dia inteiro sem XP.
"""
from __future__ import annotations

from datetime import date, timedelta

from database.connection import Database
from models.stats import MemberStats


def _today() -> str:
    return date.today().isoformat()


def _yesterday() -> str:
    return (date.today() - timedelta(days=1)).isoformat()


class StatsRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    # ── Leitura ─────────────────────────────────────────────
    def get(self, guild_id: int, user_id: int) -> MemberStats:
        conn = self._db.conn
        key = (str(guild_id), str(user_id))
        conn.execute(
            "INSERT OR IGNORE INTO voice_stats (guild_id, user_id) VALUES (?, ?)", key
        )
        row = conn.execute(
            "SELECT * FROM voice_stats WHERE guild_id = ? AND user_id = ?", key
        ).fetchone()
        stats = MemberStats(
            guild_id=guild_id,
            user_id=user_id,
            **{k: row[k] for k in row.keys() if k not in ("guild_id", "user_id")},
        )

        today = _today()

        if stats.daily_date != today:
            stats.daily_xp = 0
            stats.daily_seconds = 0
            stats.daily_date = today
            conn.execute(
                "UPDATE voice_stats SET daily_xp = 0, daily_seconds = 0, daily_date = ? "
                "WHERE guild_id = ? AND user_id = ?",
                (today, *key),
            )

        # Perdeu a sequência: último XP não foi hoje nem ontem
        if stats.streak_current > 0 and stats.streak_last_date not in (today, _yesterday()):
            stats.streak_current = 0
            conn.execute(
                "UPDATE voice_stats SET streak_current = 0 WHERE guild_id = ? AND user_id = ?",
                key,
            )

        # Commit incondicional: o INSERT OR IGNORE acima abre uma transação
        # mesmo em leituras; deixá-la pendurada segura o lock do WAL.
        conn.commit()
        return stats

    def top(self, guild_id: int, limit: int = 10) -> list[MemberStats]:
        rows = self._db.conn.execute(
            "SELECT * FROM voice_stats WHERE guild_id = ? ORDER BY period_xp DESC LIMIT ?",
            (str(guild_id), limit),
        ).fetchall()
        return [
            MemberStats(
                guild_id=guild_id,
                user_id=int(r["user_id"]),
                **{k: r[k] for k in r.keys() if k not in ("guild_id", "user_id")},
            )
            for r in rows
        ]

    def rank_of(self, guild_id: int, user_id: int) -> int:
        row = self._db.conn.execute(
            "SELECT COUNT(*) + 1 AS rank FROM voice_stats "
            "WHERE guild_id = ? AND period_xp > "
            "(SELECT period_xp FROM voice_stats WHERE guild_id = ? AND user_id = ?)",
            (str(guild_id), str(guild_id), str(user_id)),
        ).fetchone()
        return int(row["rank"]) if row else 1

    # ── Escrita ─────────────────────────────────────────────
    def add_xp(self, guild_id: int, user_id: int, xp: int, seconds: int) -> None:
        self.get(guild_id, user_id)  # garante a linha e o rollover diário
        self._db.conn.execute(
            "UPDATE voice_stats SET "
            "total_xp = total_xp + :xp, total_seconds = total_seconds + :sec, "
            "period_xp = period_xp + :xp, period_seconds = period_seconds + :sec, "
            "daily_xp = daily_xp + :xp, daily_seconds = daily_seconds + :sec "
            "WHERE guild_id = :g AND user_id = :u",
            {"xp": xp, "sec": seconds, "g": str(guild_id), "u": str(user_id)},
        )
        self._db.conn.commit()

    def register_streak_day(self, stats: MemberStats) -> MemberStats:
        """Registra atividade de hoje na sequência (chamar quando ganhar XP)."""
        today = _today()
        if stats.streak_last_date == today:
            return stats  # já contou hoje

        stats.streak_current = (
            stats.streak_current + 1 if stats.streak_last_date == _yesterday() else 1
        )
        stats.streak_best = max(stats.streak_best, stats.streak_current)
        stats.streak_last_date = today
        self._db.conn.execute(
            "UPDATE voice_stats SET streak_current = ?, streak_best = ?, streak_last_date = ? "
            "WHERE guild_id = ? AND user_id = ?",
            (stats.streak_current, stats.streak_best, today, str(stats.guild_id), str(stats.user_id)),
        )
        self._db.conn.commit()
        return stats

    def reset_period(self, guild_id: int) -> None:
        self._db.conn.execute(
            "UPDATE voice_stats SET period_xp = 0, period_seconds = 0 WHERE guild_id = ?",
            (str(guild_id),),
        )
        self._db.conn.commit()

    def adjust_xp(self, guild_id: int, user_id: int, delta: int) -> MemberStats:
        """Ajuste manual de XP (não altera as horas)."""
        self.get(guild_id, user_id)
        self._db.conn.execute(
            "UPDATE voice_stats SET "
            "total_xp = MAX(0, total_xp + :d), period_xp = MAX(0, period_xp + :d) "
            "WHERE guild_id = :g AND user_id = :u",
            {"d": delta, "g": str(guild_id), "u": str(user_id)},
        )
        self._db.conn.commit()
        return self.get(guild_id, user_id)

    def reset_guild(self, guild_id: int) -> int:
        """Zera XP, horas e sequência de TODOS os membros do servidor."""
        cur = self._db.conn.execute(
            "UPDATE voice_stats SET total_xp = 0, total_seconds = 0, period_xp = 0, "
            "period_seconds = 0, daily_xp = 0, daily_seconds = 0, "
            "streak_current = 0, streak_best = 0, streak_last_date = '' "
            "WHERE guild_id = ?",
            (str(guild_id),),
        )
        self._db.conn.commit()
        return cur.rowcount

    def reset_user(self, guild_id: int, user_id: int) -> None:
        self.get(guild_id, user_id)
        self._db.conn.execute(
            "UPDATE voice_stats SET total_xp = 0, total_seconds = 0, period_xp = 0, "
            "period_seconds = 0, daily_xp = 0, daily_seconds = 0, "
            "streak_current = 0, streak_best = 0, streak_last_date = '' "
            "WHERE guild_id = ? AND user_id = ?",
            (str(guild_id), str(user_id)),
        )
        self._db.conn.commit()
