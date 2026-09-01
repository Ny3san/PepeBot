"""Seção: XP de Chat."""

from __future__ import annotations

from typing import TYPE_CHECKING

import discord

from models.guild_config import GuildConfig
from utils.emoji_utils import get_emoji
from views.base import SectionView, button, channel_select, cid, nav_callback, refresh, toggle_callback
from views.modals import ConfigModal, Field
from views.panel._format import chan_list

if TYPE_CHECKING:
    from bot import VoiceXPBot


def build_messages(bot: VoiceXPBot, cfg: GuildConfig) -> SectionView:
    body = (
        f"**Status** `{'Ativado' if cfg.message_xp_enabled else 'Desativado'}`\n\n"
        f"**XP por mensagem** `{cfg.message_xp_amount}`\n"
        f"**Cooldown** `{cfg.message_cooldown_s}s`\n"
        f"**Canais que dão XP** "
        + (chan_list(cfg.message_allowed_channels) if cfg.message_allowed_channels else "`todos os canais`")
        + "\n\n-# Por padrão, todo canal de texto dá XP. Selecione canais abaixo pra restringir. "
        "Multiplicador de cargo, sequência e Double XP valem no chat também."
    )
    view = SectionView(bot, cfg.guild_id, title="XP de Chat", body=body)
    guild = bot.get_guild(cfg.guild_id)

    select = channel_select(
        guild,
        current=cfg.message_allowed_channels,
        placeholder="Canais permitidos para XP (deixe vazio = todos)",
        channel_types=[discord.ChannelType.text],
        custom_id=cid("msg", "channels"),
        min_values=0,
        max_values=15,
    )

    async def on_channels(interaction: discord.Interaction) -> None:
        cfg.message_allowed_channels = [c.id for c in select.values]
        bot.configs.save(cfg)
        await refresh(bot, interaction, "mensagens")

    select.callback = on_channels
    view.add_row(select)

    async def on_edit_amounts(interaction: discord.Interaction) -> None:
        async def save(inner: discord.Interaction, values: dict) -> None:
            cfg.message_xp_amount = values["message_xp_amount"]
            cfg.message_cooldown_s = values["message_cooldown_s"]
            bot.configs.save(cfg)
            await refresh(bot, inner, "mensagens")

        await interaction.response.send_modal(
            ConfigModal(
                "XP por mensagem e cooldown",
                [
                    Field("message_xp_amount", "XP por mensagem", cfg.message_xp_amount, min_value=1, max_value=1_000),
                    Field(
                        "message_cooldown_s",
                        "Cooldown entre mensagens (segundos)",
                        cfg.message_cooldown_s,
                        min_value=1,
                        max_value=60,
                    ),
                ],
                save,
                custom_id=cid("msg", "edit"),
            )
        )

    view.add_row(
        button("Editar XP e cooldown", on_edit_amounts, custom_id=cid("msg", "amounts")),
        button(
            "Desativar" if cfg.message_xp_enabled else "Ativar",
            toggle_callback(bot, cfg, "message_xp_enabled", "mensagens"),
            custom_id=cid("msg", "toggle"),
            style=discord.ButtonStyle.danger if cfg.message_xp_enabled else discord.ButtonStyle.success,
        ),
    )
    view.add_row(button("Voltar", nav_callback(bot, "main"), custom_id=cid("msg", "back"), emoji=get_emoji("voltar")))
    return view
