"""Tasks periódicas do bot (extensão).

  • xp_tick    — credita XP das sessões ativas a cada 60s.
  • rank_tick  — ranking, Top 1 e reset de período a cada 5 min.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from discord.ext import commands, tasks

from config.defaults import RANKING_INTERVAL_MINUTES, XP_TICK_SECONDS
from systems import ranking

if TYPE_CHECKING:
    from bot import VoiceXPBot

log = logging.getLogger(__name__)


class Scheduler(commands.Cog):
    def __init__(self, bot: "VoiceXPBot") -> None:
        self.bot = bot
        self.xp_tick.start()
        self.rank_tick.start()

    async def cog_unload(self) -> None:
        self.xp_tick.cancel()
        self.rank_tick.cancel()

    @tasks.loop(seconds=XP_TICK_SECONDS)
    async def xp_tick(self) -> None:
        await self.bot.tracker.tick(self.bot)

    @tasks.loop(minutes=RANKING_INTERVAL_MINUTES)
    async def rank_tick(self) -> None:
        for guild in self.bot.guilds:
            try:
                if not self.bot.configs.get(guild.id).enabled:
                    continue
                await ranking.check_period_reset(self.bot, guild)
                await ranking.update_top1(self.bot, guild)
                await ranking.update_rank_message(self.bot, guild)
            except Exception:
                log.exception("Erro no loop de ranking (%s)", guild.id)

    @xp_tick.before_loop
    @rank_tick.before_loop
    async def _wait_ready(self) -> None:
        await self.bot.wait_until_ready()


async def setup(bot: "VoiceXPBot") -> None:
    await bot.add_cog(Scheduler(bot))
