"""Verificações de permissão do painel e comandos administrativos."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from discord import ui

from config.defaults import EMBED_COLOR
from models.guild_config import GuildConfig

if TYPE_CHECKING:
    from bot import VoiceXPBot

log = logging.getLogger(__name__)


def no_permission_view(user: discord.abc.User) -> ui.LayoutView:
    """Mensagem padrão de acesso negado (visual minimalista do bot)."""
    view = ui.LayoutView()
    view.add_item(
        ui.Container(
            ui.TextDisplay(
                f"### Acesso negado\n{user.mention} você não tem permissão para usar isso."
            ),
            accent_colour=EMBED_COLOR,
        )
    )
    return view


def can_manage(bot: "VoiceXPBot", cfg: GuildConfig, member: discord.Member) -> bool:
    """True se o membro pode gerenciar o bot (/setup e /xpadmin).

    SOMENTE o dono do servidor e quem tem o cargo definido em Permissões
    podem usar. Sem cargo configurado, apenas o dono tem acesso.
    Bypass: IDs em settings.bypass_user_ids (env BYPASS_USER_IDS) passam
    direto (admin global) — cada uso é logado.
    """
    if member.id in bot.settings.bypass_user_ids:
        log.warning(
            "BYPASS_USER_IDS: %s (%s) usou o bypass administrativo em %s (%s)",
            member, member.id, member.guild.name, member.guild.id,
        )
        return True
    if member.id == member.guild.owner_id:
        return True
    if cfg.manager_role_id is not None:
        return member.get_role(cfg.manager_role_id) is not None
    return False
