"""Regras de negócio do ganho de XP.

Centraliza o cálculo de multiplicadores e a aplicação dos limites diários,
para que o tracker fique responsável apenas por "quando" creditar e este
serviço por "quanto".
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import discord

from database.stats_repo import StatsRepository
from models.guild_config import GuildConfig
from models.stats import MemberStats

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class AwardResult:
    xp: int
    seconds: int
    stats: MemberStats


class XpService:
    def __init__(self, stats: StatsRepository) -> None:
        self._stats = stats

    # ── Multiplicadores ─────────────────────────────────────
    @staticmethod
    def role_multiplier(cfg: GuildConfig, member: discord.Member) -> float:
        """Maior multiplicador entre os cargos do membro (1.0 se nenhum)."""
        best = 1.0
        for role_id, value in cfg.role_multipliers.items():
            if member.get_role(role_id) is not None:
                best = max(best, value)
        return best

    @staticmethod
    def group_multiplier(cfg: GuildConfig, channel: discord.abc.Connectable) -> float:
        if not cfg.group_bonus_enabled:
            return 1.0
        humans = sum(1 for m in getattr(channel, "members", []) if not m.bot)
        return cfg.group_bonus_multiplier if humans >= cfg.group_bonus_min_members else 1.0

    def total_multiplier(
        self,
        cfg: GuildConfig,
        member: discord.Member,
        channel: discord.abc.Connectable,
        streak_days: int,
    ) -> float:
        """Multiplicador final aplicado ao XP (nunca ao tempo em call)."""
        mult = self.role_multiplier(cfg, member)
        mult *= self.group_multiplier(cfg, channel)
        mult *= cfg.streak_multiplier(streak_days)
        if cfg.double_xp_active():
            mult *= cfg.double_xp_multiplier
        return mult

    # ── Crédito de minutos ──────────────────────────────────
    def award_minutes(
        self,
        cfg: GuildConfig,
        member: discord.Member,
        channel: discord.abc.Connectable,
        minutes: int,
    ) -> AwardResult | None:
        """Credita `minutes` minutos elegíveis a um membro.

        Regras:
          • Limite diário de TEMPO corta os minutos (tempo e XP param).
          • Limite diário de XP corta apenas o XP (tempo continua).
          • Multiplicadores afetam somente o XP, nunca o tempo.
        Retorna None se nada foi creditado.
        """
        stats = self._stats.get(cfg.guild_id, member.id)

        if cfg.daily_minutes_cap > 0:
            remaining = cfg.daily_minutes_cap - stats.daily_seconds // 60
            minutes = min(minutes, max(0, remaining))
        if minutes <= 0:
            return None

        mult = self.total_multiplier(cfg, member, channel, stats.streak_current)
        xp = round(cfg.xp_per_minute * mult * minutes)
        if cfg.daily_xp_cap > 0:
            xp = min(xp, max(0, cfg.daily_xp_cap - stats.daily_xp))

        self._stats.add_xp(cfg.guild_id, member.id, xp, minutes * 60)
        # Recarrega para o check de recompensas ver o XP já creditado
        stats = self._stats.get(cfg.guild_id, member.id)
        if xp > 0:
            stats = self._stats.register_streak_day(stats)

        return AwardResult(xp=xp, seconds=minutes * 60, stats=stats)

    # ── Crédito de mensagens ────────────────────────────────
    def award_message_xp(self, cfg: GuildConfig, member: discord.Member) -> AwardResult | None:
        """Credita XP por mensagem com os mesmos multiplicadores que voz.

        Sem bônus de grupo (não há "call cheia" no chat); role, streak e
        double XP se aplicam. Respeita o limite diário de XP.
        Retorna None se nada foi creditado.
        """
        stats = self._stats.get(cfg.guild_id, member.id)

        mult = self.role_multiplier(cfg, member)
        mult *= cfg.streak_multiplier(stats.streak_current)
        if cfg.double_xp_active():
            mult *= cfg.double_xp_multiplier

        xp = round(cfg.message_xp_amount * mult)
        if cfg.daily_xp_cap > 0:
            xp = min(xp, max(0, cfg.daily_xp_cap - stats.daily_xp))
        if xp <= 0:
            return None

        self._stats.add_xp(cfg.guild_id, member.id, xp, 0)
        # Recarrega para o check de recompensas ver o XP já creditado
        stats = self._stats.get(cfg.guild_id, member.id)
        stats = self._stats.register_streak_day(stats)

        return AwardResult(xp=xp, seconds=0, stats=stats)
