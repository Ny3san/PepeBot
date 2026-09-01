"""Seção: Multiplicadores por cargo."""

from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord import ui

from models.guild_config import GuildConfig
from utils.emoji_utils import get_emoji
from utils.format import fmt_mult
from views.base import SectionView, button, cid, nav_callback, refresh
from views.modals import ConfigModal, Field

if TYPE_CHECKING:
    from bot import VoiceXPBot


def build_multiplicadores(bot: VoiceXPBot, cfg: GuildConfig) -> SectionView:
    guild = bot.get_guild(cfg.guild_id)

    def _role_position(role_id: int) -> int:
        role = guild.get_role(role_id) if guild else None
        return role.position if role else -1

    mults = sorted(cfg.role_multipliers.items(), key=lambda kv: -_role_position(kv[0]))
    lines = [f"<@&{role_id}> · {fmt_mult(value)}" for role_id, value in mults] or ["—"]

    body = (
        "\n".join(lines) + "\n\n-# Ordenados do cargo mais alto pro mais baixo. Se a pessoa tem vários cargos, "
        "só o maior multiplicador conta. E isso afeta só o XP, nunca o tempo de call."
    )
    view = SectionView(bot, cfg.guild_id, title="Multiplicadores por Cargo", body=body)

    add_select = ui.RoleSelect(placeholder="Adicionar ou editar cargo", custom_id=cid("mult", "add"))

    async def on_add(interaction: discord.Interaction) -> None:
        role = add_select.values[0]

        async def save(inner: discord.Interaction, values: dict) -> None:
            cfg.role_multipliers[role.id] = values["value"]
            bot.configs.save(cfg)
            await refresh(bot, inner, "multiplicadores")

        await interaction.response.send_modal(
            ConfigModal(
                f"Multiplicador: {role.name[:32]}",
                [
                    Field(
                        "value",
                        "Multiplicador (ex: 1.25, 2, 4)",
                        cfg.role_multipliers.get(role.id, 2),
                        kind="float",
                        min_value=1,
                        max_value=100,
                    )
                ],
                save,
                custom_id=cid("mult", "modal", str(role.id)),
            )
        )

    add_select.callback = on_add
    view.add_row(add_select)

    remove = ui.Select(placeholder="Remover multiplicador", custom_id=cid("mult", "remove"))
    if mults:
        for role_id, value in mults[:25]:
            role = guild.get_role(role_id) if guild else None
            remove.add_option(
                label=(role.name if role else f"Cargo {role_id}")[:100],
                description=fmt_mult(value),
                value=str(role_id),
            )
    else:
        remove.add_option(label="—", value="none")
        remove.disabled = True

    async def on_remove(interaction: discord.Interaction) -> None:
        cfg.role_multipliers.pop(int(remove.values[0]), None)
        bot.configs.save(cfg)
        await refresh(bot, interaction, "multiplicadores")

    remove.callback = on_remove
    view.add_row(remove)

    view.add_row(button("Voltar", nav_callback(bot, "main"), custom_id=cid("mult", "back"), emoji=get_emoji("voltar")))
    return view
