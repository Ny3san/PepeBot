"""Gerenciador de emojis customizados: upload e mapeamento."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import discord

if TYPE_CHECKING:
    from bot import VoiceXPBot

ASSETS_DIR = Path(__file__).parent.parent.parent / "assets" / "emojis"
EMOJI_MAP_FILE = Path(__file__).parent.parent.parent / ".emoji_map.json"


class EmojiManager:
    def __init__(self, bot: VoiceXPBot):
        self.bot = bot
        self.emojis: dict[str, discord.Emoji] = {}
        self._load_map()

    def _load_map(self) -> None:
        """Carrega mapeamento de emojis do arquivo."""
        if EMOJI_MAP_FILE.exists():
            with open(EMOJI_MAP_FILE) as f:
                data = json.load(f)
                self.emojis = {name: discord.PartialEmoji.from_str(emoji_str)
                               for name, emoji_str in data.items()}

    def _save_map(self) -> None:
        """Salva mapeamento de emojis."""
        with open(EMOJI_MAP_FILE, "w") as f:
            json.dump({name: str(emoji) for name, emoji in self.emojis.items()}, f, indent=2)

    async def upload_all(self, guild_id: int, skip_existing: bool = True) -> dict[str, str]:
        """Upload de imagens como emojis (só faltantes se skip_existing=True)."""
        guild = self.bot.get_guild(guild_id)
        if not guild:
            raise ValueError(f"Guild {guild_id} não encontrada")

        results = {}
        if not ASSETS_DIR.exists():
            return results

        # Carrega emojis já existentes do servidor
        existing_names = {e.name for e in guild.emojis} if skip_existing else set()

        for img_file in sorted(ASSETS_DIR.glob("*.png")):
            emoji_name = img_file.stem.replace("-", "_").replace(" ", "_")[:32]

            # Se já existe no servidor, pula
            if emoji_name in existing_names:
                results[emoji_name] = f"⏭️ Já existe"
                print(f"⏭️ {emoji_name} já existe no servidor")
                continue

            try:
                with open(img_file, "rb") as f:
                    emoji = await guild.create_custom_emoji(name=emoji_name, image=f.read())
                    self.emojis[emoji_name] = emoji
                    results[emoji_name] = str(emoji)
                    print(f"✓ {emoji_name} criado: {emoji}")
            except discord.errors.HTTPException as e:
                print(f"✗ Falha ao criar {emoji_name}: {e}")
                results[emoji_name] = f"ERROR: {e}"

        self._save_map()
        return results

    def get(self, name: str) -> discord.PartialEmoji | None:
        """Retorna emoji por nome."""
        return self.emojis.get(name)

    def get_or_placeholder(self, name: str) -> str:
        """Retorna emoji ou placeholder se não encontrado."""
        emoji = self.get(name)
        return str(emoji) if emoji else f":{name}:"
