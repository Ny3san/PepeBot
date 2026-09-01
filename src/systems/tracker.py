"""Rastreador de sessões de voz.

Correções herdadas da versão anterior (preservadas):
  • Estado de voz como fonte da verdade (member.voice), sem depender de
    caches frágeis para decidir elegibilidade.
  • Tempo em call independente do limite diário de XP.
  • Re-scan automático ao ativar o sistema ou mudar canais permitidos.
  • Cooldown de reconexão empurra o início válido da sessão (anti-farm).
  • Tempo mínimo creditado retroativamente ao ser atingido.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import discord

from services.reward_service import RewardService
from services.xp_service import XpService

if TYPE_CHECKING:
    from database.config_repo import ConfigRepository

log = logging.getLogger(__name__)

SessionKey = tuple[int, int]  # (guild_id, user_id)


@dataclass(slots=True)
class Session:
    guild_id: int
    user_id: int
    channel_id: int
    start_at: float  # início "válido" (já considera o cooldown)
    counted_minutes: int = 0  # minutos já processados nesta sessão


@dataclass(slots=True)
class VoiceTracker:
    configs: ConfigRepository
    xp: XpService
    rewards: RewardService
    sessions: dict[SessionKey, Session] = field(default_factory=dict)
    _last_leave: dict[SessionKey, float] = field(default_factory=dict)

    # ── Ciclo de vida das sessões ───────────────────────────
    def _start(self, guild_id: int, user_id: int, channel_id: int) -> None:
        cfg = self.configs.get(guild_id)
        key = (guild_id, user_id)
        now = time.time()
        left = self._last_leave.get(key, 0.0)
        start_at = left + cfg.reconnect_cooldown_s if now - left < cfg.reconnect_cooldown_s else now
        self.sessions[key] = Session(guild_id, user_id, channel_id, start_at)

    def _end(self, guild_id: int, user_id: int) -> None:
        key = (guild_id, user_id)
        if self.sessions.pop(key, None) is not None:
            self._last_leave[key] = time.time()

    def on_voice_update(self, member: discord.Member, after: discord.VoiceState) -> None:
        """Evento on_voice_state_update."""
        if member.bot:
            return
        cfg = self.configs.get(member.guild.id)
        key = (member.guild.id, member.id)
        in_session = key in self.sessions
        trackable = cfg.enabled and cfg.is_trackable_channel(after.channel.id if after.channel else None)

        if trackable and not in_session:
            self._start(member.guild.id, member.id, after.channel.id)  # type: ignore[union-attr]
        elif not trackable and in_session:
            self._end(member.guild.id, member.id)
        elif trackable and in_session:
            self.sessions[key].channel_id = after.channel.id  # trocou de lobby

    def scan_guild(self, guild: discord.Guild) -> None:
        """Sincroniza sessões com quem já está em call (boot/ativação/config)."""
        cfg = self.configs.get(guild.id)
        seen: set[SessionKey] = set()

        for channel in guild.voice_channels:
            for member in channel.members:
                if member.bot:
                    continue
                key = (guild.id, member.id)
                seen.add(key)
                trackable = cfg.enabled and cfg.is_trackable_channel(channel.id)
                if trackable and key not in self.sessions:
                    self._start(guild.id, member.id, channel.id)
                elif not trackable and key in self.sessions:
                    self._end(guild.id, member.id)

        # Sessões de quem já saiu de call neste servidor
        for key in [k for k in self.sessions if k[0] == guild.id and k not in seen]:
            self._end(*key)

    # ── Tick de XP (a cada 60s) ─────────────────────────────
    @staticmethod
    def _eligible_now(cfg, voice: discord.VoiceState) -> bool:
        if not cfg.allow_deafened and (voice.self_deaf or voice.deaf):
            return False
        if not cfg.allow_muted and (voice.self_mute or voice.mute):
            return False
        return True

    async def tick(self, bot: discord.Client) -> None:
        now = time.time()

        for key, session in list(self.sessions.items()):
            try:
                cfg = self.configs.get(session.guild_id)
                if not cfg.enabled:
                    self.sessions.pop(key, None)
                    continue

                guild = bot.get_guild(session.guild_id)
                member = guild.get_member(session.user_id) if guild else None
                voice = member.voice if member else None

                if voice is None or not cfg.is_trackable_channel(voice.channel.id if voice.channel else None):
                    self._end(session.guild_id, session.user_id)
                    continue

                elapsed = int((now - session.start_at) // 60)
                if elapsed < cfg.min_minutes:
                    continue  # ainda no tempo mínimo
                pending = elapsed - session.counted_minutes
                if pending <= 0:
                    continue

                # Minuto inelegível: não conta tempo nem XP, sessão continua
                if not self._eligible_now(cfg, voice):
                    session.counted_minutes = elapsed
                    continue

                result = self.xp.award_minutes(cfg, member, voice.channel, pending)
                session.counted_minutes = elapsed
                if result is not None:
                    await self.rewards.check_member(member, cfg, result.stats)
            except Exception:
                log.exception("Erro no tick de %s", key)

    def get_session(self, guild_id: int, user_id: int) -> Session | None:
        return self.sessions.get((guild_id, user_id))
