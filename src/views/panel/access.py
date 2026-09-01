"""Seção: Acesso (cargo autorizado a gerenciar o bot, protegido por 2FA)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord import ui

from models.guild_config import GuildConfig
from services.log_service import send_log
from utils.emoji_utils import get_emoji
from views.base import SectionView, button, cid, nav_callback, refresh
from views.twofa import twofa_gated

if TYPE_CHECKING:
    from bot import VoiceXPBot


def build_acesso(bot: VoiceXPBot, cfg: GuildConfig) -> SectionView:
    body = (
        "**Cargo autorizado** "
        + (f"<@&{cfg.manager_role_id}>" if cfg.manager_role_id else "—")
        + "\n\n-# Só o dono do servidor e quem tiver o cargo definido aqui pode usar /setup "
        "e /xpadmin (adicionar, remover ou resetar XP). Sem cargo definido, só o dono mesmo. "
        "E toda mudança feita aqui precisa ser confirmada pelo dono na DM."
    )
    view = SectionView(bot, cfg.guild_id, title="Acesso", body=body)

    role_select = ui.RoleSelect(
        placeholder="Cargo autorizado a gerenciar o Voice XP",
        min_values=0,
        max_values=1,
        custom_id=cid("perm", "role"),
    )

    async def on_role(interaction: discord.Interaction) -> None:
        # Captura a escolha agora; o 2FA pode adiar a aplicação para depois
        chosen = role_select.values[0].id if role_select.values else None

        async def apply(inner: discord.Interaction) -> None:
            cfg.manager_role_id = chosen
            bot.configs.save(cfg)
            if inner.guild:
                await send_log(
                    inner.guild,
                    cfg,
                    f"**Permissões alteradas:** {inner.user.mention} definiu o cargo autorizado: "
                    + (f"<@&{chosen}>." if chosen else "nenhum."),
                )
            await refresh(bot, inner, "acesso")

        await twofa_gated(bot, "alterar as **permissões**", apply)(interaction)

    role_select.callback = on_role
    view.add_row(role_select)

    async def on_clear(interaction: discord.Interaction) -> None:
        async def apply(inner: discord.Interaction) -> None:
            cfg.manager_role_id = None
            bot.configs.save(cfg)
            if inner.guild:
                await send_log(
                    inner.guild,
                    cfg,
                    f"**Permissões alteradas:** {inner.user.mention} removeu o cargo autorizado.",
                )
            await refresh(bot, inner, "acesso")

        await twofa_gated(bot, "alterar as **permissões**", apply)(interaction)

    view.add_row(
        button("Limpar cargo", on_clear, custom_id=cid("perm", "clear"), disabled=cfg.manager_role_id is None),
        button("Voltar", nav_callback(bot, "main"), custom_id=cid("perm", "back"), emoji=get_emoji("voltar")),
    )
    return view
