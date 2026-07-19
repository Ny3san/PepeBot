"""Painel de configuração (/setup) — seções e navegação (Components v2).

Estrutura:
  main
  ├── geral (XP de Voz) · mensagens (XP de Chat) · multiplicadores
  ├── config (Settings) → recompensas, canais
  ├── extras (Eventos) · acesso (2FA)
  └── ativar/desativar sistema
  reward:<id>             (rewards_view, fora da árvore de navegação)
"""
from __future__ import annotations

import time
from typing import TYPE_CHECKING

import discord
from discord import ui

from models.guild_config import GuildConfig
from services.log_service import send_log
from utils.format import fmt_mult
from views.base import SectionView, button, channel_select, cid, nav_callback, refresh, toggle_callback
from views.modals import ConfigModal, Field
from views.rewards_view import build_reward_edit, build_rewards
from views.twofa import twofa_gated

if TYPE_CHECKING:
    from bot import VoiceXPBot

_yes_no = lambda v: "Sim" if v else "Não"  # noqa: E731


def _chan_list(ids: list[int]) -> str:
    return " ".join(f"<#{i}>" for i in ids) or "—"


def _msg_status(cfg: GuildConfig) -> str:
    return f"`{cfg.message_xp_amount} XP/msg`" if cfg.message_xp_enabled else "`desativado`"


# ──────────────────────────── Main ────────────────────────────

def build_main(bot: "VoiceXPBot", cfg: GuildConfig) -> SectionView:
    body = (
        f"**Status** `{'Ativo' if cfg.enabled else 'Inativo'}`"
        + (f" · **Double XP** até <t:{int(cfg.double_xp_until)}:f>" if cfg.double_xp_active() else "")
        + f"\n**Voz** `{cfg.xp_per_minute} XP/min` · **Chat** {_msg_status(cfg)}\n"
        f"**Cargos de nível** `{len(cfg.role_rewards)}`"
        f" · **Multiplicadores** `{len(cfg.role_multipliers)}`"
    )
    view = SectionView(bot, cfg.guild_id, title="Voice XP", body=body)
    view.add_text(
        "**XP de Voz / XP de Chat** — como se ganha XP\n"
        "**Settings** — cargos por nível, canais de rank e logs\n"
        "**Multiplicadores** — XP extra por cargo\n"
        "**Eventos** — Double XP e o bônus de call cheia\n"
        "**Permissões** — quem pode configurar"
    )

    view.add_row(
        button("XP de Voz", nav_callback(bot, "geral"), custom_id=cid("nav", "geral")),
        button("XP de Chat", nav_callback(bot, "mensagens"), custom_id=cid("nav", "mensagens")),
        button("Multiplicadores", nav_callback(bot, "multiplicadores"), custom_id=cid("nav", "multiplicadores")),
    )

    async def open_acesso(inner: discord.Interaction) -> None:
        await refresh(bot, inner, "acesso")

    view.add_row(
        button("Settings", nav_callback(bot, "config"), custom_id=cid("nav", "config"), style=discord.ButtonStyle.primary),
        button("Eventos", nav_callback(bot, "extras"), custom_id=cid("nav", "extras")),
        button("Permissões", twofa_gated(bot, "abrir a seção **Acesso**", open_acesso), custom_id=cid("nav", "acesso")),
    )

    async def apply(inner: discord.Interaction) -> None:
        cfg.enabled = not cfg.enabled
        bot.configs.save(cfg)
        if inner.guild:
            bot.tracker.scan_guild(inner.guild)
            await send_log(
                inner.guild, cfg,
                f"Sistema **{'ativado' if cfg.enabled else 'desativado'}** por {inner.user.mention}.",
            )
        await refresh(bot, inner, "main")

    # Ligar/desligar o sistema também exige a confirmação do dono
    label = "**desligar o sistema**" if cfg.enabled else "**ligar o sistema**"
    view.add_row(
        button(
            "Desativar sistema" if cfg.enabled else "Ativar sistema",
            twofa_gated(bot, label, apply),
            custom_id=cid("toggle", "enabled"),
            style=discord.ButtonStyle.danger if cfg.enabled else discord.ButtonStyle.success,
        )
    )
    return view


# ──────────────────────── Hub: Settings ────────────────────────

def build_config_hub(bot: "VoiceXPBot", cfg: GuildConfig) -> SectionView:
    body = (
        f"**Cargos** — `{len(cfg.role_rewards)}` cargo(s) de nível\n"
        f"**Canais** — logs e ranking"
    )
    view = SectionView(bot, cfg.guild_id, title="Settings", body=body)

    view.add_row(
        button("Cargos", nav_callback(bot, "recompensas"), custom_id=cid("nav", "recompensas")),
        button("Canais", nav_callback(bot, "canais"), custom_id=cid("nav", "canais")),
        button("Voltar", nav_callback(bot, "main"), custom_id=cid("cfg", "back")),
    )
    return view


# ──────────────────────────── Voz ────────────────────────────

def build_geral(bot: "VoiceXPBot", cfg: GuildConfig) -> SectionView:
    body = (
        f"**Canais permitidos**\n{_chan_list(cfg.allowed_channels)}\n"
        f"**Canais excluídos**\n{_chan_list(cfg.excluded_channels)}\n\n"
        f"**XP por minuto** `{cfg.xp_per_minute}` · **Tempo mínimo** `{cfg.min_minutes} min`\n"
        f"**XP mutado** `{_yes_no(cfg.allow_muted)}` · **XP ensurdecido** `{_yes_no(cfg.allow_deafened)}`"
    )
    view = SectionView(bot, cfg.guild_id, title="XP de Voz", body=body)
    guild = bot.get_guild(cfg.guild_id)

    def voice_channels(key: str, placeholder: str) -> ui.ChannelSelect:
        select = channel_select(
            guild, current=getattr(cfg, key), placeholder=placeholder,
            channel_types=[discord.ChannelType.voice], custom_id=cid("geral", key),
            min_values=0, max_values=15,
        )

        async def cb(interaction: discord.Interaction) -> None:
            setattr(cfg, key, [c.id for c in select.values])
            bot.configs.save(cfg)
            if interaction.guild:
                bot.tracker.scan_guild(interaction.guild)  # sincroniza quem já está em call
            await refresh(bot, interaction, "geral")

        select.callback = cb
        return select

    view.add_row(voice_channels("allowed_channels", "Canais permitidos"))
    view.add_row(voice_channels("excluded_channels", "Canais excluídos"))

    async def on_edit(interaction: discord.Interaction) -> None:
        async def save(inner: discord.Interaction, values: dict) -> None:
            cfg.xp_per_minute = values["xp_per_minute"]
            cfg.min_minutes = values["min_minutes"]
            bot.configs.save(cfg)
            await refresh(bot, inner, "geral")

        await interaction.response.send_modal(
            ConfigModal(
                "XP e tempo mínimo",
                [
                    Field("xp_per_minute", "XP base por minuto", cfg.xp_per_minute, min_value=1, max_value=10_000),
                    Field("min_minutes", "Tempo mínimo para contar (minutos)", cfg.min_minutes, max_value=120),
                ],
                save,
                custom_id=cid("geral", "xpmin"),
            )
        )

    view.add_row(
        button("Editar XP e tempo mínimo", on_edit, custom_id=cid("geral", "edit")),
        button(f"Mutado: {_yes_no(cfg.allow_muted)}", toggle_callback(bot, cfg, "allow_muted", "geral"), custom_id=cid("geral", "muted")),
        button(f"Ensurdecido: {_yes_no(cfg.allow_deafened)}", toggle_callback(bot, cfg, "allow_deafened", "geral"), custom_id=cid("geral", "deaf")),
    )
    view.add_row(button("Voltar", nav_callback(bot, "main"), custom_id=cid("geral", "back")))
    return view


# ──────────────────────── Multiplicadores ────────────────────────

def build_multiplicadores(bot: "VoiceXPBot", cfg: GuildConfig) -> SectionView:
    guild = bot.get_guild(cfg.guild_id)

    def _role_position(role_id: int) -> int:
        role = guild.get_role(role_id) if guild else None
        return role.position if role else -1

    mults = sorted(cfg.role_multipliers.items(), key=lambda kv: -_role_position(kv[0]))
    lines = [f"<@&{role_id}> · {fmt_mult(value)}" for role_id, value in mults] or ["—"]

    body = (
        "\n".join(lines)
        + "\n\n-# Ordenados pela hierarquia do cargo (do mais alto ao mais baixo). Com vários "
        "cargos, vale apenas o MAIOR multiplicador. Afeta somente o XP, nunca o tempo."
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
                f"Multiplicador — {role.name[:32]}",
                [Field("value", "Multiplicador (ex: 1.25, 2, 4)", cfg.role_multipliers.get(role.id, 2),
                       kind="float", min_value=1, max_value=100)],
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

    view.add_row(button("Voltar", nav_callback(bot, "main"), custom_id=cid("mult", "back")))
    return view


# ─────────────────────────── Eventos ───────────────────────────

def build_extras(bot: "VoiceXPBot", cfg: GuildConfig) -> SectionView:
    double = cfg.double_xp_active()
    body = (
        f"**Bônus de call cheia** `{_yes_no(cfg.group_bonus_enabled)}` · "
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
                    Field("min_members", "Mínimo de pessoas na call", cfg.group_bonus_min_members, min_value=2, max_value=99),
                    Field("multiplier", "Multiplicador (ex: 1.5)", cfg.group_bonus_multiplier, kind="float", min_value=1, max_value=10),
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
                    inner.guild, cfg,
                    f"**Double XP ativado** — {fmt_mult(values['multiplier'])} até "
                    f"<t:{int(cfg.double_xp_until)}:f> (por {inner.user.mention}).",
                )
            await refresh(bot, inner, "extras")

        remaining = max(0, (cfg.double_xp_until - time.time()) / 3600)
        await interaction.response.send_modal(
            ConfigModal(
                "Double XP",
                [
                    Field("hours", "Duração em horas (0 = encerrar)", round(remaining) or 24, kind="float", max_value=720),
                    Field("multiplier", "Multiplicador (ex: 2)", cfg.double_xp_multiplier, kind="float", min_value=1, max_value=10),
                ],
                save,
                custom_id=cid("extras", "doublemodal"),
            )
        )

    view.add_row(
        button(f"Bônus: {_yes_no(cfg.group_bonus_enabled)}", toggle_callback(bot, cfg, "group_bonus_enabled", "extras"), custom_id=cid("extras", "group")),
        button("Configurar bônus", on_group_config, custom_id=cid("extras", "groupcfg")),
        button("Editar Double XP" if double else "Iniciar Double XP", on_double, custom_id=cid("extras", "double")),
    )
    view.add_row(button("Voltar", nav_callback(bot, "main"), custom_id=cid("extras", "back")))
    return view


# ─────────────────────────── Acesso ───────────────────────────

def build_acesso(bot: "VoiceXPBot", cfg: GuildConfig) -> SectionView:
    body = (
        f"**Cargo autorizado** "
        + (f"<@&{cfg.manager_role_id}>" if cfg.manager_role_id else "—")
        + "\n\n-# SOMENTE o dono do servidor e quem tem o cargo definido aqui usam o /setup "
        "e o /xpadmin (adicionar, remover e resetar XP). Sem cargo definido, apenas o dono. "
        "Cada ação aqui precisa ser confirmada pelo dono na DM."
    )
    view = SectionView(bot, cfg.guild_id, title="Acesso", body=body)

    role_select = ui.RoleSelect(
        placeholder="Cargo autorizado a gerenciar o Voice XP",
        min_values=0, max_values=1,
        custom_id=cid("perm", "role"),
    )

    async def on_role(interaction: discord.Interaction) -> None:
        # Captura a escolha agora; o 2FA pode adiar a aplicação para depois
        chosen = role_select.values[0].id if role_select.values else None

        async def apply(inner: discord.Interaction) -> None:
            cfg.manager_role_id = chosen
            bot.configs.save(cfg)
            if inner.guild:
                await send_log(
                    inner.guild, cfg,
                    f"**Permissões alteradas** — {inner.user.mention} definiu o cargo autorizado: "
                    + (f"<@&{chosen}>." if chosen else "nenhum."),
                )
            await refresh(bot, inner, "acesso")

        await twofa_gated(bot, "alterar as **permissões**", apply)(interaction)

    role_select.callback = on_role
    view.add_row(role_select)

    async def on_clear(interaction: discord.Interaction) -> None:
        async def apply(inner: discord.Interaction) -> None:
            cfg.manager_role_id = None
            bot.configs.save(cfg)
            if inner.guild:
                await send_log(
                    inner.guild, cfg,
                    f"**Permissões alteradas** — {inner.user.mention} removeu o cargo autorizado.",
                )
            await refresh(bot, inner, "acesso")

        await twofa_gated(bot, "alterar as **permissões**", apply)(interaction)

    view.add_row(
        button("Limpar cargo", on_clear, custom_id=cid("perm", "clear"), disabled=cfg.manager_role_id is None),
        button("Voltar", nav_callback(bot, "main"), custom_id=cid("perm", "back")),
    )
    return view


# ─────────────────────────── Chat ───────────────────────────

def build_messages(bot: "VoiceXPBot", cfg: GuildConfig) -> SectionView:
    body = (
        f"**Status** `{'Ativado' if cfg.message_xp_enabled else 'Desativado'}`\n\n"
        f"**XP por mensagem** `{cfg.message_xp_amount}`\n"
        f"**Cooldown** `{cfg.message_cooldown_s}s`\n"
        f"**Canais que dão XP** "
        + (_chan_list(cfg.message_allowed_channels) if cfg.message_allowed_channels else "`todos os canais`")
        + "\n\n-# Por padrão todo canal de texto dá XP; selecione canais para restringir. "
        "Multiplicadores de cargo, sequência e Double XP também valem no chat."
    )
    view = SectionView(bot, cfg.guild_id, title="XP de Chat", body=body)
    guild = bot.get_guild(cfg.guild_id)

    select = channel_select(
        guild, current=cfg.message_allowed_channels, placeholder="Canais permitidos para XP (deixe vazio = todos)",
        channel_types=[discord.ChannelType.text], custom_id=cid("msg", "channels"),
        min_values=0, max_values=15,
    )

    async def on_channels(interaction: discord.Interaction) -> None:
        cfg.message_allowed_channels = [c.id for c in select.values]
        bot.configs.save(cfg)
        await refresh(bot, interaction, "mensagens")

    select.callback = on_channels
    view.add_row(select)

    async def on_edit_amounts(interaction: discord.Interaction) -> None:
        async def save(inner: discord.Interaction, values: dict) -> None:
            cfg.message_xp_amount = values["message_xp_amount"]
            cfg.message_cooldown_s = values["message_cooldown_s"]
            bot.configs.save(cfg)
            await refresh(bot, inner, "mensagens")

        await interaction.response.send_modal(
            ConfigModal(
                "XP por mensagem e cooldown",
                [
                    Field("message_xp_amount", "XP por mensagem", cfg.message_xp_amount, min_value=1, max_value=1_000),
                    Field("message_cooldown_s", "Cooldown entre mensagens (segundos)", cfg.message_cooldown_s, min_value=1, max_value=60),
                ],
                save,
                custom_id=cid("msg", "edit"),
            )
        )

    view.add_row(
        button("Editar XP e cooldown", on_edit_amounts, custom_id=cid("msg", "amounts")),
        button(
            "Desativar" if cfg.message_xp_enabled else "Ativar",
            toggle_callback(bot, cfg, "message_xp_enabled", "mensagens"),
            custom_id=cid("msg", "toggle"),
            style=discord.ButtonStyle.danger if cfg.message_xp_enabled else discord.ButtonStyle.success,
        ),
    )
    view.add_row(button("Voltar", nav_callback(bot, "main"), custom_id=cid("msg", "back")))
    return view


# ─────────────────────────── Canais ───────────────────────────

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


# ─────────────────────────── Dispatcher ───────────────────────────

_SECTIONS = {
    "main": build_main,
    "config": build_config_hub,
    "geral": build_geral,
    "mensagens": build_messages,
    "canais": build_channels,
    "recompensas": build_rewards,
    "multiplicadores": build_multiplicadores,
    "extras": build_extras,
    "acesso": build_acesso,
}


def render(bot: "VoiceXPBot", guild_id: int, section: str = "main") -> SectionView:
    """Constrói a view (Components v2) de qualquer seção do painel."""
    cfg = bot.configs.get(guild_id)
    if section.startswith("reward:"):
        return build_reward_edit(bot, cfg, int(section.split(":", 1)[1]))
    return _SECTIONS.get(section, build_main)(bot, cfg)
