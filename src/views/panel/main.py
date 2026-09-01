"""Seção: Main (menu principal) e hub de Settings."""

from __future__ import annotations

from typing import TYPE_CHECKING

import discord

from models.guild_config import GuildConfig
from services.log_service import send_log
from utils.emoji_utils import get_emoji
from views.base import SectionView, button, cid, nav_callback, refresh
from views.twofa import twofa_gated

if TYPE_CHECKING:
    from bot import VoiceXPBot


def _msg_status(cfg: GuildConfig) -> str:
    return f"`{cfg.message_xp_amount} XP/msg`" if cfg.message_xp_enabled else "`desativado`"


def build_main(bot: VoiceXPBot, cfg: GuildConfig) -> SectionView:
    body = (
        f"**Status** `{'Ativo' if cfg.enabled else 'Inativo'}`"
        + (f" · **Double XP** até <t:{int(cfg.double_xp_until)}:f>" if cfg.double_xp_active() else "")
        + f"\n**Voz** `{cfg.xp_per_minute} XP/min` · **Chat** {_msg_status(cfg)}\n"
        f"**Cargos de nível** `{len(cfg.role_rewards)}`"
        f" · **Multiplicadores** `{len(cfg.role_multipliers)}`"
    )
    view = SectionView(bot, cfg.guild_id, title="Voice XP", body=body)
    view.add_text(
        "**XP de Voz / XP de Chat:** como se ganha XP\n"
        "**Settings:** cargos por nível, canais de rank e logs\n"
        "**Multiplicadores:** XP extra por cargo\n"
        "**Eventos:** Double XP e o bônus de call cheia\n"
        "**Permissões:** quem pode configurar"
    )

    view.add_row(
        button("XP de Voz", nav_callback(bot, "geral"), custom_id=cid("nav", "geral"), emoji=get_emoji("xp_call")),
        button("XP de Chat", nav_callback(bot, "mensagens"), custom_id=cid("nav", "mensagens"), emoji=get_emoji("xp_chat")),
        button("Multiplicadores", nav_callback(bot, "multiplicadores"), custom_id=cid("nav", "multiplicadores"), emoji=get_emoji("multiplicador")),
    )

    async def open_acesso(inner: discord.Interaction) -> None:
        await refresh(bot, inner, "acesso")

    view.add_row(
        button(
            "Settings", nav_callback(bot, "config"), custom_id=cid("nav", "config"), style=discord.ButtonStyle.primary, emoji=get_emoji("settings")
        ),
        button("Eventos", nav_callback(bot, "extras"), custom_id=cid("nav", "extras"), emoji=get_emoji("eventos")),
        button("Permissões", twofa_gated(bot, "abrir a seção **Acesso**", open_acesso), custom_id=cid("nav", "acesso"), emoji=get_emoji("permissoes")),
    )

    async def apply(inner: discord.Interaction) -> None:
        cfg.enabled = not cfg.enabled
        bot.configs.save(cfg)
        if inner.guild:
            bot.tracker.scan_guild(inner.guild)
            await send_log(
                inner.guild,
                cfg,
                f"Sistema **{'ativado' if cfg.enabled else 'desativado'}** por {inner.user.mention}.",
            )
        await refresh(bot, inner, "main")

    # Ligar/desligar o sistema também exige a confirmação do dono
    label = "**desligar o sistema**" if cfg.enabled else "**ligar o sistema**"
    view.add_row(
        button(
            "Desativar sistema" if cfg.enabled else "Ativar sistema",
            twofa_gated(bot, label, apply),
            custom_id=cid("toggle", "enabled"),
            style=discord.ButtonStyle.danger if cfg.enabled else discord.ButtonStyle.success,
            emoji=get_emoji("sistema_toggle"),
        )
    )
    return view


def build_config_hub(bot: VoiceXPBot, cfg: GuildConfig) -> SectionView:
    body = f"**Cargos:** `{len(cfg.role_rewards)}` cargo(s) de nível\n**Canais:** logs e ranking"
    view = SectionView(bot, cfg.guild_id, title="Settings", body=body)

    view.add_row(
        button("Cargos", nav_callback(bot, "recompensas"), custom_id=cid("nav", "recompensas"), emoji=get_emoji("cargo")),
        button("Canais", nav_callback(bot, "canais"), custom_id=cid("nav", "canais"), emoji=get_emoji("canais")),
        button("Voltar", nav_callback(bot, "main"), custom_id=cid("cfg", "back"), emoji=get_emoji("voltar")),
    )
    return view
