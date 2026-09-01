"""Comando /xpadmin (e -xpadmin): correções manuais de XP."""

from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from services.log_service import send_log
from utils.checks import can_manage, no_permission_view
from utils.format import fmt_int

if TYPE_CHECKING:
    from bot import VoiceXPBot


class XpAdmin(commands.Cog):
    def __init__(self, bot: VoiceXPBot) -> None:
        self.bot = bot

    async def cog_check(self, ctx: commands.Context) -> bool:
        if ctx.guild is None or not isinstance(ctx.author, discord.Member):
            return False
        return can_manage(self.bot, self.bot.configs.get(ctx.guild.id), ctx.author)

    async def cog_command_error(self, ctx: commands.Context, error: Exception) -> None:
        if isinstance(error, commands.CheckFailure):
            await ctx.send(view=no_permission_view(ctx.author), ephemeral=True)
        else:
            raise error

    @commands.hybrid_group(name="xpadmin", description="Correções manuais de XP")
    @commands.guild_only()
    async def xpadmin(self, ctx: commands.Context) -> None:
        if ctx.invoked_subcommand is None:
            await ctx.send(
                "Uso: `xpadmin add|remove|reset <membro> [quantidade]` ou `xpadmin resetall`", ephemeral=True
            )

    @xpadmin.command(name="add", description="Adicionar XP a um membro")
    async def add(self, ctx: commands.Context, membro: discord.Member, quantidade: commands.Range[int, 1]) -> None:
        await self._adjust(ctx, membro, quantidade)

    @xpadmin.command(name="remove", description="Remover XP de um membro")
    async def remove(self, ctx: commands.Context, membro: discord.Member, quantidade: commands.Range[int, 1]) -> None:
        await self._adjust(ctx, membro, -quantidade)

    @commands.hybrid_command(name="resetall", description="Zerar o XP de TODOS os membros do servidor")
    @commands.guild_only()
    async def resetall(self, ctx: commands.Context) -> None:
        assert ctx.guild is not None
        cfg = self.bot.configs.get(ctx.guild.id)
        await ctx.defer(ephemeral=True)

        count = self.bot.stats.reset_guild(ctx.guild.id)
        await self._strip_reward_roles(ctx.guild, cfg)
        await send_log(
            ctx.guild,
            cfg,
            f"**XP resetado:** {ctx.author.mention} zerou os dados de **todos** ({count} membros).",
        )
        await ctx.send(f"XP de **todo mundo** zerado ({count} registros).", ephemeral=True)

    @xpadmin.command(name="reset", description="Zerar o XP de um membro")
    async def reset(self, ctx: commands.Context, membro: discord.Member) -> None:
        assert ctx.guild is not None
        cfg = self.bot.configs.get(ctx.guild.id)
        await ctx.defer(ephemeral=True)

        self.bot.stats.reset_user(ctx.guild.id, membro.id)
        await self.bot.rewards.check_member(membro, cfg)
        await send_log(ctx.guild, cfg, f"**XP resetado:** {ctx.author.mention} zerou os dados de {membro.mention}.")
        await ctx.send(
            f"Dados de {membro.mention} foram zerados.", ephemeral=True, allowed_mentions=discord.AllowedMentions.none()
        )

    async def _strip_reward_roles(self, guild: discord.Guild, cfg) -> None:
        """Remove os cargos de nível de todo mundo após um reset geral."""
        for reward in cfg.role_rewards:
            role = guild.get_role(reward.role_id)
            if role is None:
                continue
            for member in list(role.members):
                try:
                    await member.remove_roles(role, reason="Voice XP: reset geral de XP")
                except discord.HTTPException:
                    pass

    async def _adjust(self, ctx: commands.Context, member: discord.Member, delta: int) -> None:
        assert ctx.guild is not None
        stats = self.bot.stats.adjust_xp(ctx.guild.id, member.id, delta)
        cfg = self.bot.configs.get(ctx.guild.id)

        verb = "adicionou" if delta > 0 else "removeu"
        await send_log(
            ctx.guild,
            cfg,
            f"**Ajuste de XP:** {ctx.author.mention} {verb} **{fmt_int(abs(delta))} XP** "
            f"({member.mention} agora tem {fmt_int(stats.total_xp)} XP total).",
        )
        await ctx.send(
            f"Feito. {member.mention} agora tem **{fmt_int(stats.period_xp)} XP** no período "
            f"({fmt_int(stats.total_xp)} total).",
            ephemeral=True,
            allowed_mentions=discord.AllowedMentions.none(),
        )


async def setup(bot: VoiceXPBot) -> None:
    await bot.add_cog(XpAdmin(bot))
