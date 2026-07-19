"""Modelo da configuração por servidor.

Serializado como JSON na tabela guild_config. O parser aceita também o
formato legado (camelCase, IDs como string, timestamps em ms) gerado pela
versão JavaScript do bot, migrando-o de forma transparente.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass(slots=True)
class RoleReward:
    """Recompensa automática de cargo.

    Requisitos com valor 0/None são ignorados; os configurados precisam
    TODOS ser atendidos para o cargo ser concedido.
    """

    role_id: int
    required_xp: int = 0
    required_level: int = 0
    required_hours: float = 0.0
    remove_previous: bool = False   # remove os cargos de recompensa anteriores
    message: str = ""               # mensagem personalizada ({user} {role} {level} {hours} {xp})
    channel_id: int | None = None   # canal da mensagem (fallback: canal de logs)

    def sort_key(self) -> tuple[float, int, int]:
        """Ordena recompensas da menor para a maior exigência."""
        return (self.required_hours, self.required_xp, self.required_level)


@dataclass(slots=True)
class StreakBonus:
    days: int
    multiplier: float


def _default_streak_bonuses() -> list[StreakBonus]:
    return [
        StreakBonus(7, 1.10),
        StreakBonus(15, 1.25),
        StreakBonus(30, 1.50),
        StreakBonus(60, 2.0),
    ]


@dataclass(slots=True)
class GuildConfig:
    guild_id: int
    enabled: bool = False

    # Canais
    allowed_channels: list[int] = field(default_factory=list)
    excluded_channels: list[int] = field(default_factory=list)

    # XP
    xp_per_minute: int = 5
    role_multipliers: dict[int, float] = field(default_factory=dict)
    min_minutes: int = 3
    allow_muted: bool = True
    allow_deafened: bool = False

    # Limites diários e anti-abuso
    daily_xp_cap: int = 0
    daily_minutes_cap: int = 0
    reconnect_cooldown_s: int = 30

    # Recompensas
    role_rewards: list[RoleReward] = field(default_factory=list)
    top1_role_id: int | None = None
    top1_enabled: bool = True
    reset_mode: str = "never"  # never | 7d | 30d
    period_start: float = 0.0  # epoch (s)

    # Canais utilitários
    log_channel_id: int | None = None
    rank_channel_id: int | None = None
    rank_message_id: int | None = None

    # Extras
    group_bonus_enabled: bool = True
    group_bonus_min_members: int = 6
    group_bonus_multiplier: float = 1.5
    double_xp_until: float = 0.0  # epoch (s). 0 = inativo
    double_xp_multiplier: float = 2.0

    # Sequência (streak)
    streak_enabled: bool = True
    streak_bonuses: list[StreakBonus] = field(default_factory=_default_streak_bonuses)

    # Mensagens (XP por chat) — por padrão todos os canais de texto contam
    message_xp_enabled: bool = True
    message_xp_amount: int = 10
    message_cooldown_s: int = 5
    message_allowed_channels: list[int] = field(default_factory=list)

    # Permissões do painel
    manager_role_id: int | None = None

    # ── Helpers ─────────────────────────────────────────────
    def double_xp_active(self) -> bool:
        return self.double_xp_until > time.time()

    def is_trackable_channel(self, channel_id: int | None) -> bool:
        if channel_id is None or channel_id in self.excluded_channels:
            return False
        return channel_id in self.allowed_channels

    def streak_multiplier(self, streak_days: int) -> float:
        """Maior bônus cuja exigência de dias foi atingida (1.0 se nenhum)."""
        if not self.streak_enabled:
            return 1.0
        best = 1.0
        for bonus in self.streak_bonuses:
            if streak_days >= bonus.days:
                best = max(best, bonus.multiplier)
        return best

    # ── Serialização ────────────────────────────────────────
    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("guild_id")
        return data

    @classmethod
    def from_dict(cls, guild_id: int, raw: dict[str, Any]) -> "GuildConfig":
        if any(key in raw for key in ("xpPerMinute", "allowedChannels", "roleRewards")):
            raw = _migrate_legacy(raw)

        cfg = cls(guild_id=guild_id)
        for key, value in raw.items():
            if not hasattr(cfg, key) or key == "guild_id":
                continue
            if key == "role_rewards":
                value = [RoleReward(**r) for r in value]
            elif key == "streak_bonuses":
                value = [StreakBonus(**b) for b in value]
            elif key == "role_multipliers":
                value = {int(k): float(v) for k, v in value.items()}
            setattr(cfg, key, value)
        return cfg


def _ms_to_s(value: float) -> float:
    """Timestamps legados vinham em milissegundos."""
    return value / 1000 if value > 1e11 else value


def _migrate_legacy(raw: dict[str, Any]) -> dict[str, Any]:
    """Converte a config camelCase da versão JavaScript para o formato atual."""
    def ints(values: list | None) -> list[int]:
        return [int(v) for v in (values or [])]

    def opt_int(value: Any) -> int | None:
        return int(value) if value else None

    return {
        "enabled": raw.get("enabled", False),
        "allowed_channels": ints(raw.get("allowedChannels")),
        "excluded_channels": ints(raw.get("excludedChannels")),
        "xp_per_minute": raw.get("xpPerMinute", 5),
        "role_multipliers": {int(k): float(v) for k, v in (raw.get("roleMultipliers") or {}).items()},
        "min_minutes": raw.get("minMinutes", 3),
        "allow_muted": raw.get("allowMuted", True),
        "allow_deafened": raw.get("allowDeafened", False),
        "daily_xp_cap": raw.get("dailyXpCap", 0),
        "daily_minutes_cap": raw.get("dailyMinutesCap", 0),
        "reconnect_cooldown_s": raw.get("reconnectCooldownSec", 30),
        "role_rewards": [
            {"role_id": int(r["roleId"]), "required_hours": float(r.get("hours", 0))}
            for r in (raw.get("roleRewards") or [])
        ],
        "top1_role_id": opt_int(raw.get("top1RoleId")),
        "top1_enabled": raw.get("top1Enabled", True),
        "reset_mode": raw.get("resetMode", "never"),
        "period_start": _ms_to_s(raw.get("periodStart", 0)),
        "log_channel_id": opt_int(raw.get("logChannelId")),
        "rank_channel_id": opt_int(raw.get("rankChannelId")),
        "rank_message_id": opt_int(raw.get("rankMessageId")),
        "group_bonus_enabled": raw.get("groupBonusEnabled", True),
        "group_bonus_min_members": raw.get("groupBonusMinMembers", 6),
        "group_bonus_multiplier": raw.get("groupBonusMultiplier", 1.5),
        "double_xp_until": _ms_to_s(raw.get("doubleXpUntil", 0)),
        "double_xp_multiplier": raw.get("doubleXpMultiplier", 2.0),
        "message_xp_enabled": raw.get("messageXpEnabled", True),
        "message_xp_amount": raw.get("messageXpAmount", 10),
        "message_cooldown_s": raw.get("messageCooldownSec", 5),
        "message_allowed_channels": ints(raw.get("messageAllowedChannels")),
    }
