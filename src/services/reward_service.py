"""Recompensas automáticas de cargo.

Cada recompensa pode exigir XP total, nível e/ou horas totais — todos os
requisitos configurados precisam ser atendidos. Suporta remoção dos cargos
anteriores e mensagem personalizada em um canal específico.
"""

from __future__ import annotations

import logging

import discord

from database.stats_repo import StatsRepository
from models.guild_config import GuildConfig, RoleReward
from models.stats import MemberStats
from services.level_service import curve
from services.log_service import send_log
from utils.format import fmt_hours, fmt_int

log = logging.getLogger(__name__)


def meets_requirements(reward: RoleReward, stats: MemberStats, level: int) -> bool:
    if reward.required_xp > 0 and stats.total_xp < reward.required_xp:
        return False
    if reward.required_level > 0 and level < reward.required_level:
        return False
    if reward.required_hours > 0 and stats.total_hours < reward.required_hours:
        return False
    return True


def highest_earned(cfg: GuildConfig, stats: MemberStats) -> RoleReward | None:
    """Maior recompensa que o membro já atingiu (para exibição no cartão)."""
    level = curve.progress(stats.total_xp).level
    earned = [r for r in cfg.role_rewards if meets_requirements(r, stats, level)]
    return max(earned, key=RoleReward.sort_key) if earned else None


def next_reward(cfg: GuildConfig, stats: MemberStats) -> RoleReward | None:
    """Próxima recompensa que o membro ainda não atingiu (menor exigência)."""
    level = curve.progress(stats.total_xp).level
    pending = [r for r in cfg.role_rewards if not meets_requirements(r, stats, level)]
    return min(pending, key=RoleReward.sort_key) if pending else None


class RewardService:
    def __init__(self, stats: StatsRepository) -> None:
        self._stats = stats

    async def check_member(self, member: discord.Member, cfg: GuildConfig, stats: MemberStats | None = None) -> None:
        """Sincroniza o cargo de recompensa do membro com o XP dele.

        O membro fica com EXATAMENTE UM cargo: o de maior exigência que o XP
        alcança. Os demais cargos de recompensa são removidos. Idempotente —
        sem mudanças, nenhuma chamada à API nem anúncio é feito.
        """
        if not cfg.role_rewards:
            return

        stats = stats or self._stats.get(cfg.guild_id, member.id)
        level = curve.progress(stats.total_xp).level

        earned = [r for r in cfg.role_rewards if meets_requirements(r, stats, level)]
        best = max(earned, key=RoleReward.sort_key) if earned else None

        # Remove qualquer cargo de recompensa que não seja o mais alto
        for reward in cfg.role_rewards:
            if best is not None and reward.role_id == best.role_id:
                continue
            role = member.guild.get_role(reward.role_id)
            if role is not None and member.get_role(reward.role_id) is not None:
                try:
                    await member.remove_roles(role, reason="Voice XP: substituído pelo cargo mais alto")
                except discord.HTTPException:
                    pass

        if best is None or member.get_role(best.role_id) is not None:
            return
        role = member.guild.get_role(best.role_id)
        if role is None:
            return

        try:
            await member.add_roles(role, reason="Voice XP: recompensa automática")
        except discord.HTTPException as exc:
            log.warning("Sem permissão para dar %s em %s: %s", role.name, member.guild.id, exc)
            return

        await self._announce(member, cfg, best, role, stats, level)

    async def _announce(
        self,
        member: discord.Member,
        cfg: GuildConfig,
        reward: RoleReward,
        role: discord.Role,
        stats: MemberStats,
        level: int,
    ) -> None:
        default = f"**Cargo concedido:** {member.mention} recebeu {role.mention}."
        text = reward.message.strip() or default
        text = (
            text.replace("{user}", member.mention)
            .replace("{role}", role.mention)
            .replace("{level}", str(level))
            .replace("{hours}", fmt_hours(stats.total_seconds))
            .replace("{xp}", fmt_int(stats.total_xp))
        )

        channel = member.guild.get_channel(reward.channel_id) if reward.channel_id else None
        if isinstance(channel, discord.abc.Messageable):
            try:
                await channel.send(text, allowed_mentions=discord.AllowedMentions(users=[member], roles=False))
                return
            except discord.HTTPException:
                pass
        await send_log(member.guild, cfg, text)
