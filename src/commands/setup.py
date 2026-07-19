"""Comando /setup: abre o painel de configuração (efêmero)."""
from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from config.defaults import COMPONENT_PREFIX
from utils.checks import can_manage, no_permission_view
from views.base import mark_live_panel, refresh
from views.panel import render
from views.twofa import require_twofa

if TYPE_CHECKING:
    from bot import VoiceXPBot

log = logging.getLogger(__name__)


class SetupCommand(commands.Cog):
    def __init__(self, bot: "VoiceXPBot") -> None:
        self.bot = bot

    @app_commands.command(name="setup", description="Painel de configuração do Voice XP")
    @app_commands.guild_only()
    async def setup_cmd(self, interaction: discord.Interaction) -> None:
        assert interaction.guild_id is not None
        cfg = self.bot.configs.get(interaction.guild_id)
        if not isinstance(interaction.user, discord.Member) or not can_manage(self.bot, cfg, interaction.user):
            await interaction.response.send_message(view=no_permission_view(interaction.user), ephemeral=True)
            return

        view = render(self.bot, interaction.guild_id, "main")
        try:
            await interaction.response.send_message(view=view, ephemeral=True)
            message = await interaction.original_response()
            mark_live_panel(self.bot, message.id)
        except discord.HTTPException as exc:
            if exc.code in (10062, 40060):  # outra instância do bot respondeu antes
                log.warning("Interação do /setup já respondida por outra instância do bot.")
                return
            raise

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction) -> None:
        """Ressuscita painéis abertos antes de um restart do bot.

        As views do painel vivem em memória; após reiniciar, os botões de um
        /setup antigo caem aqui sem ninguém para responder. Detectamos pelo
        custom_id (vx:*) e re-renderizamos o painel na mesma mensagem.
        """
        if interaction.type is not discord.InteractionType.component:
            return
        custom_id = (interaction.data or {}).get("custom_id", "")
        if not custom_id.startswith(f"{COMPONENT_PREFIX}:") or interaction.guild_id is None:
            return

        # Painel com view ativa: ela mesma responde, nunca duplicamos
        message_id = interaction.message.id if interaction.message else 0
        if self.bot.live_panels.get(message_id, 0) > time.time():
            return

        # Margem extra para uma view ativa fora do registro responder primeiro
        await asyncio.sleep(0.4)
        if interaction.response.is_done():
            return

        cfg = self.bot.configs.get(interaction.guild_id)
        if not isinstance(interaction.user, discord.Member) or not can_manage(self.bot, cfg, interaction.user):
            await interaction.response.send_message(view=no_permission_view(interaction.user), ephemeral=True)
            return

        # vx:nav:<seção> reabre direto na seção; o resto volta ao menu
        parts = custom_id.split(":")
        section = parts[2] if len(parts) >= 3 and parts[1] == "nav" else "main"

        # Acesso continua protegido mesmo em painéis ressuscitados
        if section == "acesso":
            async def reopen(inner: discord.Interaction) -> None:
                await refresh(self.bot, inner, section)

            if not await require_twofa(
                self.bot, interaction, action_label="abrir a seção **Acesso**", action=reopen
            ):
                return

        view = render(self.bot, interaction.guild_id, section)
        try:
            await interaction.response.edit_message(content=None, embed=None, view=view)
            mark_live_panel(self.bot, message_id)
        except discord.HTTPException as exc:
            # Nunca mandamos um segundo painel — só avisamos para reabrir
            log.warning("Falha ao ressuscitar painel em %s: %s", interaction.guild_id, exc)
            if not interaction.response.is_done():
                try:
                    await interaction.response.send_message(
                        "Este painel expirou. Use /setup para abrir um novo.", ephemeral=True
                    )
                except discord.HTTPException:
                    pass


async def setup(bot: "VoiceXPBot") -> None:
    await bot.add_cog(SetupCommand(bot))
