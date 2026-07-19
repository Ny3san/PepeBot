"""Confirmação de ações protegidas do painel pela DM do dono.

`require_twofa` é chamado antes de uma ação protegida: o dono passa direto;
para qualquer outra pessoa, o bot envia na DM do dono um pedido com botões
**Confirmar ação** / **Recusar**. Ao confirmar, a ação pendente é executada
no painel na hora. Cada pedido vale para UMA ação e expira em 3 minutos —
a DM se atualiza sozinha em todos os casos (confirmado/recusado/expirado).
Bypass: IDs em BYPASS_USER_IDS passam direto, sem 2FA.
"""
from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Awaitable, Callable

import discord
from discord import ui

from config.defaults import EMBED_COLOR
from services.twofa_service import REQUEST_TTL_S

if TYPE_CHECKING:
    from bot import VoiceXPBot

log = logging.getLogger(__name__)

Action = Callable[[discord.Interaction], Awaitable[None]]


def twofa_gated(bot: "VoiceXPBot", action_label: str, apply: Action) -> Callable[[discord.Interaction], Awaitable[None]]:
    """Colapsa o par repetido `require_twofa(...) -> apply(...)` num único
    callback de botão/select: quem pode age direto, o resto vai pra DM."""
    async def cb(interaction: discord.Interaction) -> None:
        if not await require_twofa(bot, interaction, action_label=action_label, action=apply):
            return
        await apply(interaction)
    return cb


def _confirm_button(callback: Callable[[discord.Interaction], Awaitable[None]]) -> ui.Button:
    btn = ui.Button(label="Confirmar ação", style=discord.ButtonStyle.success)
    btn.callback = callback
    return btn


def _deny_button(callback: Callable[[discord.Interaction], Awaitable[None]]) -> ui.Button:
    btn = ui.Button(label="Recusar", style=discord.ButtonStyle.danger)
    btn.callback = callback
    return btn


class _ApprovalView(ui.LayoutView):
    """Botões na DM do dono. Consome o pedido no primeiro clique (uso único)."""

    def __init__(self, bot: "VoiceXPBot", key: tuple[int, int], base: str, expires_at: float) -> None:
        super().__init__(timeout=REQUEST_TTL_S)
        self.bot = bot
        self.key = key
        self.base = base                      # linha "@fulano quer ... em ..."
        self.message: discord.Message | None = None

        self._text = ui.TextDisplay(self._body(f"**Expira** <t:{int(expires_at)}:R>"))
        self._row = ui.ActionRow(
            _confirm_button(self._on_confirm),
            _deny_button(self._on_deny),
        )
        self.container = ui.Container(self._text, self._row, accent_colour=EMBED_COLOR)
        self.add_item(self.container)

    def _body(self, tail: str) -> str:
        return f"### Confirmação de ação\n{self.base}\n\n{tail}"

    async def _finish(self, result: str, interaction: discord.Interaction | None = None) -> None:
        """Estado final da DM: some com os botões e registra o desfecho."""
        self.stop()
        self._text.content = self._body(result)
        self.container.remove_item(self._row)
        try:
            if interaction is not None:
                await interaction.response.edit_message(view=self)
            elif self.message is not None:
                await self.message.edit(view=self)
        except discord.HTTPException:
            pass

    async def _notify_requester(self, panel_interaction: discord.Interaction, text: str) -> None:
        try:
            await panel_interaction.followup.send(text, ephemeral=True)
        except discord.HTTPException:
            pass

    async def _on_confirm(self, interaction: discord.Interaction) -> None:
        payload = self.bot.twofa.pop(*self.key)
        if payload is None:
            await self._finish("**Pedido expirado.**", interaction)
            return

        await self._finish(f"**Ação confirmada** <t:{int(time.time())}:R>.", interaction)
        panel_interaction, action = payload
        try:
            await action(panel_interaction)
        except discord.HTTPException:
            log.warning("Não consegui aplicar a ação confirmada em %s", self.key[0])
        await self._notify_requester(panel_interaction, "O dono confirmou — ação aplicada.")

    async def _on_deny(self, interaction: discord.Interaction) -> None:
        payload = self.bot.twofa.pop(*self.key)
        await self._finish("**Ação recusada.**", interaction)
        if payload is not None:
            panel_interaction, _ = payload
            await self._notify_requester(panel_interaction, "O dono recusou a ação.")

    async def on_timeout(self) -> None:
        payload = self.bot.twofa.pop(*self.key)
        await self._finish("**Pedido expirado sem resposta.**")
        if payload is not None:
            panel_interaction, _ = payload
            await self._notify_requester(panel_interaction, "O dono não respondeu a tempo. Tente novamente.")


async def require_twofa(
    bot: "VoiceXPBot",
    interaction: discord.Interaction,
    *,
    action_label: str,
    action: Action,
) -> bool:
    """True somente para o dono (o chamador segue normalmente).

    Para os demais: envia o pedido com botões na DM do dono e retorna False.
    Se o dono clicar em Confirmar, `action` é executada por conta própria.
    """
    guild = interaction.guild
    assert guild is not None

    if interaction.user.id in bot.settings.bypass_user_ids:
        log.warning(
            "BYPASS_USER_IDS: %s (%s) usou o bypass de 2FA em %s (%s) — ação: %s",
            interaction.user, interaction.user.id, guild.name, guild.id, action_label,
        )
        return True
    if interaction.user.id == guild.owner_id:
        return True

    # Segura a interação do painel: quem edita a mensagem depois é a `action`
    await interaction.response.defer()

    if bot.twofa.active(guild.id, interaction.user.id):
        await interaction.followup.send(
            "Você já tem um pedido aguardando a confirmação do dono.", ephemeral=True
        )
        return False

    base = f"{interaction.user.mention} quer {action_label} em **{guild.name}**."
    expires_at = time.time() + REQUEST_TTL_S
    view = _ApprovalView(bot, (guild.id, interaction.user.id), base, expires_at)

    try:
        owner = guild.owner or await bot.fetch_user(guild.owner_id)  # type: ignore[arg-type]
        view.message = await owner.send(view=view)
    except discord.HTTPException as exc:
        log.warning("Não consegui enviar a DM de confirmação ao dono de %s: %s", guild.id, exc)
        await interaction.followup.send(
            "Não consegui enviar o pedido na DM do dono do servidor (DM fechada).", ephemeral=True
        )
        return False

    bot.twofa.put(guild.id, interaction.user.id, (interaction, action))
    await interaction.followup.send(
        "Pedido enviado ao dono do servidor — aguardando a confirmação.", ephemeral=True
    )
    return False
