"""XP por mensagens no chat (estilo Loritta).

Por padrão todos os canais de texto contam; a whitelist no /setup restringe.
Cooldown por membro evita farm de spam.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

if TYPE_CHECKING:
    from bot import VoiceXPBot

log = logging.getLogger(__name__)


class MessageXpEvent(commands.Cog):
    """Ganho de XP ao enviar mensagens no chat."""

    def __init__(self, bot: VoiceXPBot) -> None:
        self.bot = bot
        self._cooldowns: dict[tuple[int, int], float] = {}  # (guild, user) → último crédito

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or message.guild is None:
            return
        if not isinstance(message.author, discord.Member):
            return

        cfg = self.bot.configs.get(message.guild.id)
        if not cfg.enabled or not cfg.message_xp_enabled:
            return

        # Comandos e mensagens muito curtas não contam
        content = message.content.strip()
        if len(content) < 2 or content.startswith(self.bot.command_prefix):
            return

        # Whitelist de canais (vazia = todos). Threads herdam do canal pai.
        if cfg.message_allowed_channels:
            channel_ids = {message.channel.id, getattr(message.channel, "parent_id", None)}
            if channel_ids.isdisjoint(cfg.message_allowed_channels):
                return

        key = (message.guild.id, message.author.id)
        now = time.time()
        if now - self._cooldowns.get(key, 0) < cfg.message_cooldown_s:
            return

        try:
            result = self.bot.xp.award_message_xp(cfg, message.author)
        except Exception:
            log.exception("Erro ao creditar XP de mensagem")
            return

        if result is None:
            return
        self._cooldowns[key] = now
        if len(self._cooldowns) > 5000:  # evita crescer para sempre
            cutoff = now - 3600
            self._cooldowns = {k: t for k, t in self._cooldowns.items() if t > cutoff}

        # Recompensas automáticas valem também para XP de chat
        try:
            await self.bot.rewards.check_member(message.author, cfg, result.stats)
        except Exception:
            log.exception("Erro ao checar recompensas após XP de mensagem")


async def setup(bot: VoiceXPBot) -> None:
    await bot.add_cog(MessageXpEvent(bot))
