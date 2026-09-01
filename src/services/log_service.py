"""Envio de logs para o canal configurado do servidor."""

from __future__ import annotations

import logging

import discord
from discord import ui

from config.defaults import EMBED_COLOR
from models.guild_config import GuildConfig

log = logging.getLogger(__name__)


async def send_log(guild: discord.Guild, cfg: GuildConfig, description: str) -> None:
    if not cfg.log_channel_id:
        return
    channel = guild.get_channel(cfg.log_channel_id)
    if not isinstance(channel, discord.abc.Messageable):
        return
    try:
        ts = discord.utils.format_dt(discord.utils.utcnow(), style="f")
        view = ui.LayoutView()
        view.add_item(ui.Container(ui.TextDisplay(f"{description}\n-# {ts}"), accent_colour=EMBED_COLOR))
        await channel.send(view=view)
    except discord.HTTPException as exc:
        log.warning("Falha ao enviar log em %s: %s", guild.id, exc)
