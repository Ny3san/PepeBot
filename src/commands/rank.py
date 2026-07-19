"""Comando /rank (e -rank): top 10 do ranking de voz (imagem)."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from discord.ext import commands

from systems.ranking import build_rank_file, build_rank_view

if TYPE_CHECKING:
    from bot import VoiceXPBot

log = logging.getLogger(__name__)


class RankCommand(commands.Cog):
    def __init__(self, bot: "VoiceXPBot") -> None:
        self.bot = bot

    @commands.hybrid_command(name="rank", description="Top 10 do ranking de voz")
    @commands.guild_only()
    async def rank(self, ctx: commands.Context) -> None:
        assert ctx.guild is not None
        await ctx.defer()
        try:
            file = await build_rank_file(self.bot, ctx.guild)
        except Exception:
            log.exception("Falha ao gerar a imagem do ranking; usando fallback em texto")
            file = None

        if file is not None:
            await ctx.send(file=file)
        else:
            await ctx.send(view=build_rank_view(self.bot, ctx.guild))


async def setup(bot: "VoiceXPBot") -> None:
    await bot.add_cog(RankCommand(bot))
