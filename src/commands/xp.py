"""Comando /xp (e -xp): cartão de perfil gerado com Pillow."""
from __future__ import annotations

import logging
from io import BytesIO
from typing import TYPE_CHECKING

import discord
from discord import app_commands, ui
from discord.ext import commands

from config.defaults import EMBED_COLOR
from services.card_service import CardData, render_card
from services.level_service import curve
from utils.format import fmt_hours, fmt_int, progress_bar

if TYPE_CHECKING:
    from bot import VoiceXPBot

log = logging.getLogger(__name__)


class XpCommand(commands.Cog):
    def __init__(self, bot: "VoiceXPBot") -> None:
        self.bot = bot

    @commands.hybrid_command(name="xp", description="Seu perfil de XP de voz")
    @app_commands.describe(membro="Ver o perfil de outro membro")
    @commands.guild_only()
    async def xp(self, ctx: commands.Context, membro: discord.Member | None = None) -> None:
        member = membro or ctx.author
        assert isinstance(member, discord.Member) and ctx.guild is not None
        await ctx.defer()

        stats = self.bot.stats.get(ctx.guild.id, member.id)
        progress = curve.progress(stats.total_xp)
        rank = f"#{self.bot.stats.rank_of(ctx.guild.id, member.id)}" if stats.period_xp > 0 else "—"

        try:
            avatar = await member.display_avatar.with_size(256).read()
        except discord.HTTPException:
            avatar = None

        data = CardData(
            name=member.display_name,
            level=progress.level,
            level_current=progress.current,
            level_needed=progress.needed,
            level_percent=progress.percent,
            hours_text=fmt_hours(stats.total_seconds),
            rank=rank,
            avatar_png=avatar,
        )

        try:
            png = await render_card(data)
            await ctx.send(file=discord.File(BytesIO(png), filename="xp.png"))
        except Exception:
            log.exception("Falha ao gerar o cartão; usando fallback em texto")
            await ctx.send(view=self._fallback_view(member, data))

    @staticmethod
    def _fallback_view(member: discord.Member, data: CardData) -> ui.LayoutView:
        body = (
            f"### {member.display_name}\n"
            f"**Nível {data.level}**\n"
            f"{progress_bar(data.level_current / max(1, data.level_needed))} {data.level_percent}%\n"
            f"{fmt_int(data.level_current)} / {fmt_int(data.level_needed)} XP\n\n"
            f"**Horas** {data.hours_text} · **Posição** {data.rank}"
        )
        view = ui.LayoutView()
        view.add_item(ui.Container(ui.TextDisplay(body), accent_colour=EMBED_COLOR))
        return view


async def setup(bot: "VoiceXPBot") -> None:
    await bot.add_cog(XpCommand(bot))
