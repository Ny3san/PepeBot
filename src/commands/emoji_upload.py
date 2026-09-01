"""Comando para upload de emojis customizados."""

from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from services.emoji_service import EmojiManager

if TYPE_CHECKING:
    from bot import VoiceXPBot


@discord.app_commands.command(name="emoji_upload", description="Upload all custom emojis to server")
@discord.app_commands.checks.has_permissions(administrator=True)
async def emoji_upload(interaction: discord.Interaction[VoiceXPBot]) -> None:
    """Faz upload de todas as imagens em assets/emojis como emojis do servidor."""
    await interaction.response.defer(thinking=True)

    manager = EmojiManager(interaction.client)
    if not interaction.guild_id:
        await interaction.followup.send("❌ Comando deve ser usado em um servidor", ephemeral=True)
        return

    results = await manager.upload_all(interaction.guild_id)

    if not results:
        await interaction.followup.send("⚠️ Nenhuma imagem encontrada em assets/emojis", ephemeral=True)
        return

    success = sum(1 for v in results.values() if not v.startswith("ERROR"))
    failed = len(results) - success

    msg = f"✅ **{success}** emojis criados"
    if failed > 0:
        msg += f"\n❌ **{failed}** falhas"

    for name, result in results.items():
        status = "✓" if not result.startswith("ERROR") else "✗"
        msg += f"\n{status} {name}: {result[:30]}"

    await interaction.followup.send(msg, ephemeral=True)


async def setup(bot: VoiceXPBot) -> None:
    bot.tree.add_command(emoji_upload)
