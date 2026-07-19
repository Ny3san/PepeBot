"""Infraestrutura compartilhada das views do painel (Components v2)."""
from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Awaitable, Callable

import discord
from discord import ui

from config.defaults import COMPONENT_PREFIX, EMBED_COLOR
from utils.checks import can_manage, no_permission_view

if TYPE_CHECKING:
    from bot import VoiceXPBot
    from models.guild_config import GuildConfig

log = logging.getLogger(__name__)

Callback = Callable[[discord.Interaction], Awaitable[None]]

PANEL_TIMEOUT_S = 900  # vida da view do painel


def mark_live_panel(bot: "VoiceXPBot", message_id: int) -> None:
    """Registra que esta mensagem tem uma view ativa (evita painel duplicado).

    O ressuscitador do setup consulta este registro: se a view ainda está
    viva, ela mesma responde e o ressuscitador não interfere.
    """
    now = time.time()
    bot.live_panels[message_id] = now + PANEL_TIMEOUT_S - 5
    if len(bot.live_panels) > 500:  # limpa expirados de vez em quando
        bot.live_panels = {k: t for k, t in bot.live_panels.items() if t > now}


def cid(*parts: str) -> str:
    """customId padronizado: vx:parte:parte."""
    return ":".join((COMPONENT_PREFIX, *parts))


def button(
    label: str,
    callback: Callback,
    *,
    custom_id: str,
    style: discord.ButtonStyle = discord.ButtonStyle.secondary,
    disabled: bool = False,
) -> ui.Button:
    btn = ui.Button(label=label, style=style, custom_id=custom_id, disabled=disabled)
    btn.callback = callback
    return btn


def channel_select(
    guild: discord.Guild | None,
    *,
    current: list[int] | int | None,
    placeholder: str,
    channel_types: list[discord.ChannelType],
    custom_id: str,
    min_values: int = 0,
    max_values: int = 1,
) -> ui.ChannelSelect:
    """ChannelSelect com default_values já filtrados.

    Canais deletados não podem ir em default_values (a API rejeita a view),
    então descartamos qualquer id que o guild não reconheça mais. `current`
    aceita uma lista (multi-select) ou um único id/None (single-select).
    Não liga `.callback` — cada seção define seu próprio save+refresh, já
    que a lógica pós-seleção difere entre elas.
    """
    if isinstance(current, list):
        valid = [i for i in current if guild and guild.get_channel(i)][:max_values]
    elif current and guild and guild.get_channel(current):
        valid = [current]
    else:
        valid = []
    return ui.ChannelSelect(
        placeholder=placeholder,
        channel_types=channel_types,
        min_values=min_values,
        max_values=max_values,
        custom_id=custom_id,
        default_values=[
            discord.SelectDefaultValue(id=i, type=discord.SelectDefaultValueType.channel) for i in valid
        ],
    )


def nav_callback(bot: "VoiceXPBot", section: str) -> Callback:
    """Callback padrão de navegação: refresh(bot, interaction, section).

    Cobre tanto os botões "ir para X" quanto todo botão "Voltar" — são a
    mesma operação (refresh para uma seção fixa).
    """
    async def cb(interaction: discord.Interaction) -> None:
        await refresh(bot, interaction, section)
    return cb


def toggle_callback(bot: "VoiceXPBot", cfg: "GuildConfig", key: str, section: str) -> Callback:
    """Callback padrão: inverte cfg.<key> (bool), salva e faz refresh(section)."""
    async def cb(interaction: discord.Interaction) -> None:
        setattr(cfg, key, not getattr(cfg, key))
        bot.configs.save(cfg)
        await refresh(bot, interaction, section)
    return cb


class SectionView(ui.LayoutView):
    """View base de uma seção do painel: um Container colorido com um
    título+corpo em Markdown, seguido das ActionRows adicionadas via
    add_row(). Só quem pode gerenciar o bot interage.
    """

    def __init__(self, bot: "VoiceXPBot", guild_id: int, *, title: str, body: str) -> None:
        super().__init__(timeout=PANEL_TIMEOUT_S)
        self.bot = bot
        self.guild_id = guild_id
        self.container = ui.Container(ui.TextDisplay(f"### {title}\n{body}"), accent_colour=EMBED_COLOR)
        self.add_item(self.container)

    def add_text(self, content: str) -> "SectionView":
        """Bloco de texto extra separado do anterior por uma divisória."""
        self.container.add_item(ui.Separator())
        self.container.add_item(ui.TextDisplay(content))
        return self

    def add_row(self, *items: ui.Item) -> "SectionView":
        """Agrupa botões/select numa linha visual (ActionRow) dentro do Container."""
        if not any(isinstance(c, ui.ActionRow) for c in self.container.children):
            self.container.add_item(ui.Separator())  # divisória entre texto e botões
        self.container.add_item(ui.ActionRow(*items))
        return self

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        cfg = self.bot.configs.get(self.guild_id)
        if isinstance(interaction.user, discord.Member) and can_manage(cfg, interaction.user):
            return True
        await interaction.response.send_message(view=no_permission_view(interaction.user), ephemeral=True)
        return False

    async def on_error(
        self, interaction: discord.Interaction, error: Exception, item: ui.Item
    ) -> None:
        # 10062/40060: outra instância do bot (mesmo token) respondeu antes.
        # Não há o que fazer aqui além de avisar de forma limpa no log.
        if isinstance(error, discord.HTTPException) and error.code in (10062, 40060):
            log.warning(
                "Interação já respondida por outra instância do bot (%s) — "
                "verifique se o bot não está rodando na host e local ao mesmo tempo.",
                getattr(item, "custom_id", item),
            )
            return
        log.exception("Erro no painel (%s)", getattr(item, "custom_id", item))
        if not interaction.response.is_done():
            try:
                await interaction.response.send_message("Ocorreu um erro. Tente novamente.", ephemeral=True)
            except discord.HTTPException:
                pass


async def refresh(bot: "VoiceXPBot", interaction: discord.Interaction, section: str) -> None:
    """Re-renderiza o painel na mesma mensagem (componentes e modals)."""
    from views.panel import render  # import local para evitar ciclo

    view = render(bot, interaction.guild_id, section)  # type: ignore[arg-type]
    if not interaction.response.is_done():
        await interaction.response.edit_message(content=None, embed=None, view=view)
    else:
        await interaction.edit_original_response(content=None, embed=None, view=view)
    if interaction.message is not None:
        mark_live_panel(bot, interaction.message.id)
