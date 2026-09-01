"""Seção: Eventos (bônus de call cheia e Double XP)."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

import discord

from models.guild_config import GuildConfig
from services.log_service import send_log
from utils.emoji_utils import get_emoji
from utils.format import fmt_mult
from views.base import SectionView, button, cid, nav_callback, refresh, toggle_callback
from views.modals import ConfigModal, Field
from views.panel._format import yes_no

if TYPE_CHECKING:
    from bot import VoiceXPBot


def build_extras(bot: VoiceXPBot, cfg: GuildConfig) -> SectionView:
    double = cfg.double_xp_active()
    body = (
        f"**Bônus de call cheia** `{yes_no(cfg.group_bonus_enabled)}` · "
        f"{cfg.group_bonus_min_members}+ pessoas · {fmt_mult(cfg.group_bonus_multiplier)}\n"
        f"**Double XP** "
        + (f"`{fmt_mult(cfg.double_xp_multiplier)}` até <t:{int(cfg.double_xp_until)}:f>" if double else "`inativo`")
    )
    view = SectionView(bot, cfg.guild_id, title="Eventos", body=body)

    async def on_group_config(interaction: discord.Interaction) -> None:
        async def save(inner: discord.Interaction, values: dict) -> None:
            cfg.group_bonus_min_members = values["min_members"]
            cfg.group_bonus_multiplier = values["multiplier"]
            bot.configs.save(cfg)
            await refresh(bot, inner, "extras")

        await interaction.response.send_modal(
            ConfigModal(
                "Bônus de call cheia",
                [
                    Field(
                        "min_members",
                        "Mínimo de pessoas na call",
                        cfg.group_bonus_min_members,
                        min_value=2,
                        max_value=99,
                    ),
                    Field(
                        "multiplier",
                        "Multiplicador (ex: 1.5)",
                        cfg.group_bonus_multiplier,
                        kind="float",
                        min_value=1,
                        max_value=10,
                    ),
                ],
                save,
                custom_id=cid("extras", "groupmodal"),
            )
        )

    async def on_double(interaction: discord.Interaction) -> None:
        async def save(inner: discord.Interaction, values: dict) -> None:
            cfg.double_xp_until = time.time() + values["hours"] * 3600 if values["hours"] > 0 else 0
            cfg.double_xp_multiplier = values["multiplier"]
            bot.configs.save(cfg)
            if values["hours"] > 0 and inner.guild:
                await send_log(
                    inner.guild,
                    cfg,
                    f"**Double XP ativado:** {fmt_mult(values['multiplier'])} até "
                    f"<t:{int(cfg.double_xp_until)}:f> (por {inner.user.mention}).",
                )
            await refresh(bot, inner, "extras")

        remaining = max(0, (cfg.double_xp_until - time.time()) / 3600)
        await interaction.response.send_modal(
            ConfigModal(
                "Double XP",
                [
                    Field(
                        "hours", "Duração em horas (0 = encerrar)", round(remaining) or 24, kind="float", max_value=720
                    ),
                    Field(
                        "multiplier",
                        "Multiplicador (ex: 2)",
                        cfg.double_xp_multiplier,
                        kind="float",
                        min_value=1,
                        max_value=10,
                    ),
                ],
                save,
                custom_id=cid("extras", "doublemodal"),
            )
        )

    view.add_row(
        button(
            f"Bônus: {yes_no(cfg.group_bonus_enabled)}",
            toggle_callback(bot, cfg, "group_bonus_enabled", "extras"),
            custom_id=cid("extras", "group"),
        ),
        button("Configurar bônus", on_group_config, custom_id=cid("extras", "groupcfg")),
        button("Editar Double XP" if double else "Iniciar Double XP", on_double, custom_id=cid("extras", "double"), emoji=get_emoji("edit_create_role")),
    )
    view.add_row(button("Voltar", nav_callback(bot, "main"), custom_id=cid("extras", "back"), emoji=get_emoji("voltar")))
    return view
