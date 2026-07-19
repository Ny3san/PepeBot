"""Voice XP — ponto de entrada.

Bot de XP por tempo em call: tracking de voz, níveis, sequência,
recompensas automáticas, ranking e painel de configuração.
"""
from __future__ import annotations

import logging

import discord
from discord.ext import commands

from config.settings import Settings, load_settings
from database import ConfigRepository, Database, StatsRepository
from services.reward_service import RewardService
from services.twofa_service import TwoFactorService
from services.xp_service import XpService
from systems.tracker import VoiceTracker

log = logging.getLogger("voicexp")

EXTENSIONS = [
    "events.voice",
    "events.messages",
    "systems.scheduler",
    "commands.xp",
    "commands.rank",
    "commands.xpadmin",
    "commands.setup",
]


class VoiceXPBot(commands.Bot):
    def __init__(self, settings: Settings) -> None:
        intents = discord.Intents.default()
        intents.members = True          # cargos e cache de membros
        intents.message_content = True  # comandos por prefixo "-"

        super().__init__(
            command_prefix="-",
            intents=intents,
            help_command=None,
            allowed_mentions=discord.AllowedMentions(everyone=False, roles=False),
        )

        self.settings = settings
        self.db = Database()
        self.configs = ConfigRepository(self.db)
        self.stats = StatsRepository(self.db)
        self.xp = XpService(self.stats)
        self.rewards = RewardService(self.stats)
        self.tracker = VoiceTracker(self.configs, self.xp, self.rewards)
        self.twofa = TwoFactorService()
        self.live_panels: dict[int, float] = {}  # message_id → expiração da view ativa

    async def setup_hook(self) -> None:
        for ext in EXTENSIONS:
            await self.load_extension(ext)
        log.info("%d extensões carregadas", len(EXTENSIONS))

        if self.settings.dev_guild_id:
            guild = discord.Object(id=self.settings.dev_guild_id)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            log.info("Slash commands sincronizados no servidor %s", self.settings.dev_guild_id)
        else:
            await self.tree.sync()
            log.info("Slash commands sincronizados globalmente")

    async def on_command_error(self, ctx: commands.Context, error: Exception) -> None:
        # Texto começando com "-" que não é comando (ex.: "-xp[") não é erro
        if isinstance(error, commands.CommandNotFound):
            return
        await super().on_command_error(ctx, error)

    async def close(self) -> None:
        await super().close()
        self.db.close()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    logging.getLogger("discord").setLevel(logging.WARNING)
    # O bot só monitora estado de voz (nunca conecta em call): PyNaCl/davey
    # não são necessários e os avisos deles apenas poluem o log da host.
    logging.getLogger("discord.client").addFilter(
        lambda record: "voice will NOT be supported" not in record.getMessage()
    )

    settings = load_settings()
    bot = VoiceXPBot(settings)
    bot.run(settings.token, log_handler=None)


if __name__ == "__main__":
    main()
