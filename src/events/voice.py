"""Eventos de voz e sincronização inicial (extensão)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

if TYPE_CHECKING:
    from bot import VoiceXPBot

log = logging.getLogger(__name__)


class VoiceEvents(commands.Cog):
    def __init__(self, bot: VoiceXPBot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        log.info("Online como %s", self.bot.user)
        # Retoma sessões de quem já estava em call quando o bot ligou
        for guild in self.bot.guilds:
            self.bot.tracker.scan_guild(guild)

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild) -> None:
        self.bot.tracker.scan_guild(guild)

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ) -> None:
        self.bot.tracker.on_voice_update(member, after)


async def setup(bot: VoiceXPBot) -> None:
    await bot.add_cog(VoiceEvents(bot))
