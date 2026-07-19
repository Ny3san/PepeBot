"""Seção: XP de Voz."""
from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord import ui

from models.guild_config import GuildConfig
from views.panel._format import chan_list, yes_no
from views.base import SectionView, button, channel_select, cid, nav_callback, refresh, toggle_callback
from views.modals import ConfigModal, Field

if TYPE_CHECKING:
    from bot import VoiceXPBot


def build_geral(bot: "VoiceXPBot", cfg: GuildConfig) -> SectionView:
    body = (
        f"**Canais permitidos**\n{chan_list(cfg.allowed_channels)}\n"
        f"**Canais excluídos**\n{chan_list(cfg.excluded_channels)}\n\n"
        f"**XP por minuto** `{cfg.xp_per_minute}` · **Tempo mínimo** `{cfg.min_minutes} min`\n"
        f"**XP mutado** `{yes_no(cfg.allow_muted)}` · **XP ensurdecido** `{yes_no(cfg.allow_deafened)}`"
    )
    view = SectionView(bot, cfg.guild_id, title="XP de Voz", body=body)
    guild = bot.get_guild(cfg.guild_id)

    def voice_channels(key: str, placeholder: str) -> ui.ChannelSelect:
        select = channel_select(
            guild, current=getattr(cfg, key), placeholder=placeholder,
            channel_types=[discord.ChannelType.voice], custom_id=cid("geral", key),
            min_values=0, max_values=15,
        )

        async def cb(interaction: discord.Interaction) -> None:
            setattr(cfg, key, [c.id for c in select.values])
            bot.configs.save(cfg)
            if interaction.guild:
                bot.tracker.scan_guild(interaction.guild)  # sincroniza quem já está em call
            await refresh(bot, interaction, "geral")

        select.callback = cb
        return select

    view.add_row(voice_channels("allowed_channels", "Canais permitidos"))
    view.add_row(voice_channels("excluded_channels", "Canais excluídos"))

    async def on_edit(interaction: discord.Interaction) -> None:
        async def save(inner: discord.Interaction, values: dict) -> None:
            cfg.xp_per_minute = values["xp_per_minute"]
            cfg.min_minutes = values["min_minutes"]
            bot.configs.save(cfg)
            await refresh(bot, inner, "geral")

        await interaction.response.send_modal(
            ConfigModal(
                "XP e tempo mínimo",
                [
                    Field("xp_per_minute", "XP base por minuto", cfg.xp_per_minute, min_value=1, max_value=10_000),
                    Field("min_minutes", "Tempo mínimo para contar (minutos)", cfg.min_minutes, max_value=120),
                ],
                save,
                custom_id=cid("geral", "xpmin"),
            )
        )

    view.add_row(
        button("Editar XP e tempo mínimo", on_edit, custom_id=cid("geral", "edit")),
        button(f"Mutado: {yes_no(cfg.allow_muted)}", toggle_callback(bot, cfg, "allow_muted", "geral"), custom_id=cid("geral", "muted")),
        button(f"Ensurdecido: {yes_no(cfg.allow_deafened)}", toggle_callback(bot, cfg, "allow_deafened", "geral"), custom_id=cid("geral", "deaf")),
    )
    view.add_row(button("Voltar", nav_callback(bot, "main"), custom_id=cid("geral", "back")))
    return view
