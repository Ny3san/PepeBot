"""Seção: Canais (logs e ranking)."""
from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord import ui

from models.guild_config import GuildConfig
from views.base import SectionView, button, channel_select, cid, nav_callback, refresh

if TYPE_CHECKING:
    from bot import VoiceXPBot


def build_channels(bot: "VoiceXPBot", cfg: GuildConfig) -> SectionView:
    body = (
        f"**Canal de logs** {f'<#{cfg.log_channel_id}>' if cfg.log_channel_id else '—'}\n"
        f"**Canal de ranking** {f'<#{cfg.rank_channel_id}>' if cfg.rank_channel_id else '—'}"
    )
    view = SectionView(bot, cfg.guild_id, title="Canais", body=body)
    guild = bot.get_guild(cfg.guild_id)

    def text_channel(key: str, placeholder: str) -> ui.ChannelSelect:
        select = channel_select(
            guild, current=getattr(cfg, key), placeholder=placeholder,
            channel_types=[discord.ChannelType.text], custom_id=cid("chan", key),
            min_values=0, max_values=1,
        )

        async def cb(interaction: discord.Interaction) -> None:
            setattr(cfg, key, select.values[0].id if select.values else None)
            if key == "rank_channel_id":
                cfg.rank_message_id = None
            bot.configs.save(cfg)
            await refresh(bot, interaction, "canais")

        select.callback = cb
        return select

    view.add_row(text_channel("log_channel_id", "Canal de logs"))
    view.add_row(text_channel("rank_channel_id", "Canal de ranking (atualização automática)"))

    view.add_row(button("Voltar", nav_callback(bot, "config"), custom_id=cid("chan", "back")))
    return view
