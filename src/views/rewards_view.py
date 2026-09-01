"""Seções do painel: Recompensas e edição individual de recompensa."""

from __future__ import annotations

import asyncio
import logging
import re
from typing import TYPE_CHECKING

import discord
from discord import ui

from config.defaults import RESET_LABELS
from models.guild_config import GuildConfig, RoleReward
from utils.emoji_utils import get_emoji
from views.base import SectionView, button, channel_select, cid, nav_callback, refresh
from views.modals import ConfigModal, Field

if TYPE_CHECKING:
    from bot import VoiceXPBot

log = logging.getLogger(__name__)

# Extrai o nível do nome do cargo: "Lvl - 50", "「Level 50」", "nível 50 ⭐"...
# Usado apenas para PRÉ-PREENCHER o modal — o admin sempre confirma o valor.
_LEVEL_ROLE_RE = re.compile(r"(?i)(?:lvl|level|n[ií]vel)\s*[-–—:.]*\s*(\d+)")


def _schedule_reward_sync(bot: VoiceXPBot, guild: discord.Guild, cfg: GuildConfig) -> None:
    """Sincroniza os cargos de recompensa de até 500 membros em background.

    Cada membro pode disparar 1-2 chamadas HTTP (add/remove cargo); rodar
    isso sequencialmente dentro do callback da interação seguraria a
    resposta do modal por muito tempo em servidores grandes.
    """

    async def _run() -> None:
        try:
            for stats in bot.stats.top(cfg.guild_id, 500):
                member = guild.get_member(stats.user_id)
                if member and not member.bot:
                    await bot.rewards.check_member(member, cfg, stats)
        except Exception:
            log.exception("Falha ao sincronizar recompensas em background (guild %s)", cfg.guild_id)

    asyncio.create_task(_run())


def _role_name(bot: VoiceXPBot, guild_id: int, role_id: int) -> str:
    guild = bot.get_guild(guild_id)
    role = guild.get_role(role_id) if guild else None
    return role.name if role else f"Cargo {role_id}"


def _reward_label(r: RoleReward) -> str:
    parts = []
    if r.required_xp:
        parts.append(f"{r.required_xp} XP")
    if r.required_level:
        parts.append(f"nível {r.required_level}")
    if r.required_hours:
        parts.append(f"{r.required_hours:g}h")
    return " · ".join(parts) or "sem requisitos"


def _find_reward(cfg: GuildConfig, role_id: int) -> RoleReward | None:
    return next((r for r in cfg.role_rewards if r.role_id == role_id), None)


async def _sort_level_roles(guild: discord.Guild, cfg: GuildConfig) -> None:
    """Ordena os cargos de recompensa na hierarquia do Discord.

    Requisito maior fica MAIS ALTO na lista (ex.: 50 acima de 40, 10 embaixo).
    Só troca as posições que os próprios cargos de nível já ocupam — o resto
    da hierarquia do servidor não é tocado.

    Busca os cargos direto da API: logo após criar um cargo, o cache do bot
    ainda pode não tê-lo (foi o que deixava o recém-criado fora da ordem).
    """
    try:
        fresh = {role.id: role for role in await guild.fetch_roles()}
    except discord.HTTPException:
        return

    pairs = [
        (reward.sort_key(), role) for reward in cfg.role_rewards if (role := fresh.get(reward.role_id)) is not None
    ]
    if len(pairs) < 2:
        return

    pairs.sort(key=lambda p: p[0])  # menor exigência primeiro
    slots = sorted(role.position for _, role in pairs)  # posições ocupadas, de baixo p/ cima
    positions = {role: slot for (_, role), slot in zip(pairs, slots, strict=True)}
    if all(role.position == slot for role, slot in positions.items()):
        return  # já está em ordem
    try:
        await guild.edit_role_positions(positions=positions, reason="Voice XP: ordenar cargos de nível")
    except discord.HTTPException:
        pass  # sem permissão/cargo acima do bot — a recompensa continua valendo


# ──────────────────────── Seção: Recompensas ────────────────────────


def build_rewards(bot: VoiceXPBot, cfg: GuildConfig) -> SectionView:
    rewards = sorted(cfg.role_rewards, key=RoleReward.sort_key)
    lines = [f"<@&{r.role_id}> · {_reward_label(r)}" for r in rewards] or ["—"]

    body = (
        "\n".join(lines) + "\n\n"
        f"**Reset do ranking** `{RESET_LABELS[cfg.reset_mode]}`\n\n"
        '-# Em "Criar cargo de nível", você digita o nome e o nível e o bot cuida do resto: cria o '
        "cargo, vincula e já organiza a hierarquia (nível maior fica mais acima). Se o cargo já "
        'existe, use o menu "Adicionar cargo de recompensa".'
    )
    view = SectionView(bot, cfg.guild_id, title="Cargos de Nível", body=body)

    add_select = ui.RoleSelect(placeholder="Adicionar cargo de recompensa", custom_id=cid("rw", "add"))

    async def on_add(interaction: discord.Interaction) -> None:
        role = add_select.values[0]
        await interaction.response.send_modal(_requirements_modal(bot, cfg.guild_id, role.id, is_new=True))

    add_select.callback = on_add
    view.add_row(add_select)

    manage = ui.Select(placeholder="Editar recompensa", custom_id=cid("rw", "manage"))
    if rewards:
        for r in rewards[:25]:
            manage.add_option(
                label=_role_name(bot, cfg.guild_id, r.role_id)[:100],
                description=_reward_label(r)[:100],
                value=str(r.role_id),
            )
    else:
        manage.add_option(label="—", value="none")
        manage.disabled = True

    async def on_manage(interaction: discord.Interaction) -> None:
        await refresh(bot, interaction, f"reward:{manage.values[0]}")

    manage.callback = on_manage
    view.add_row(manage)

    async def on_reset_cycle(interaction: discord.Interaction) -> None:
        order = ["never", "7d", "30d"]
        cfg.reset_mode = order[(order.index(cfg.reset_mode) + 1) % len(order)]
        import time

        cfg.period_start = time.time()
        bot.configs.save(cfg)
        await refresh(bot, interaction, "recompensas")

    async def on_create_level_role(interaction: discord.Interaction) -> None:
        """Cria um cargo pelo nome digitado e o vincula a um nível."""

        async def save(inner: discord.Interaction, values: dict) -> None:
            name = values["name"].strip()[:100]
            level = values["level"]
            if not name:
                await inner.response.send_message("Digite o nome do cargo.", ephemeral=True)
                return
            if inner.guild is None:
                return

            await inner.response.defer()
            try:
                role = await inner.guild.create_role(name=name, reason=f"Voice XP: cargo de nível {level}")
            except discord.HTTPException:
                await inner.followup.send(
                    "Não consegui criar o cargo. Confira se tenho a permissão **Gerenciar Cargos**.",
                    ephemeral=True,
                )
                return

            cfg.role_rewards.append(RoleReward(role_id=role.id, required_level=level))
            bot.configs.save(cfg)
            await _sort_level_roles(inner.guild, cfg)  # nível maior fica acima na hierarquia
            await refresh(bot, inner, "recompensas")

            # Entrega a quem já atingiu o nível, em background (não segura a interação)
            _schedule_reward_sync(bot, inner.guild, cfg)

        await interaction.response.send_modal(
            ConfigModal(
                "Criar cargo de nível",
                [
                    Field("name", "Nome do cargo (ex: Veterano)", "", kind="str"),
                    Field("level", "Nível para ganhar o cargo (ex: 50)", 10, min_value=1, max_value=1000),
                ],
                save,
                custom_id=cid("rw", "newlvlrole"),
            )
        )

    view.add_row(
        button(
            "Criar cargo de nível",
            on_create_level_role,
            custom_id=cid("rw", "newlvl"),
            style=discord.ButtonStyle.primary,
        ),
        button(f"Reset: {RESET_LABELS[cfg.reset_mode]}", on_reset_cycle, custom_id=cid("rw", "reset")),
        button("Voltar", nav_callback(bot, "config"), custom_id=cid("rw", "back"), emoji=get_emoji("voltar")),
    )
    return view


# ──────────────────── Seção: edição de recompensa ────────────────────


def build_reward_edit(bot: VoiceXPBot, cfg: GuildConfig, role_id: int) -> SectionView:
    reward = _find_reward(cfg, role_id)
    if reward is None:  # foi removida enquanto o painel estava aberto
        return build_rewards(bot, cfg)

    body = (
        f"**Cargo** <@&{reward.role_id}>\n"
        f"**Requisitos** {_reward_label(reward)}\n"
        f"**Canal da mensagem** {f'<#{reward.channel_id}>' if reward.channel_id else 'canal de logs'}\n"
        f"**Mensagem** {reward.message or '_padrão_'}\n\n"
        "-# Placeholders da mensagem: {user} {role} {level} {hours} {xp}"
    )
    view = SectionView(bot, cfg.guild_id, title="Editar Recompensa", body=body)
    guild = bot.get_guild(cfg.guild_id)

    chan_select = channel_select(
        guild,
        current=reward.channel_id,
        placeholder="Canal da mensagem personalizada",
        channel_types=[discord.ChannelType.text],
        custom_id=cid("rwe", "channel"),
        min_values=0,
        max_values=1,
    )

    async def on_channel(interaction: discord.Interaction) -> None:
        reward.channel_id = chan_select.values[0].id if chan_select.values else None
        bot.configs.save(cfg)
        await refresh(bot, interaction, f"reward:{role_id}")

    chan_select.callback = on_channel
    view.add_row(chan_select)

    async def on_requirements(interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(_requirements_modal(bot, cfg.guild_id, role_id, is_new=False))

    async def on_message(interaction: discord.Interaction) -> None:
        async def save(inner: discord.Interaction, values: dict) -> None:
            reward.message = values["message"]
            bot.configs.save(cfg)
            await refresh(bot, inner, f"reward:{role_id}")

        modal = ConfigModal(
            "Mensagem personalizada",
            [
                Field(
                    "message",
                    "Mensagem ({user} {role} {level}...)",
                    reward.message,
                    kind="str",
                    required=False,
                    paragraph=True,
                )
            ],
            save,
            custom_id=cid("rwe", "msg", str(role_id)),
        )
        await interaction.response.send_modal(modal)

    async def on_delete(interaction: discord.Interaction) -> None:
        cfg.role_rewards = [r for r in cfg.role_rewards if r.role_id != role_id]
        bot.configs.save(cfg)
        await refresh(bot, interaction, "recompensas")

    view.add_row(
        button("Requisitos", on_requirements, custom_id=cid("rwe", "req")),
        button("Mensagem", on_message, custom_id=cid("rwe", "text")),
        button("Excluir", on_delete, custom_id=cid("rwe", "del"), style=discord.ButtonStyle.danger),
    )
    view.add_row(button("Voltar", nav_callback(bot, "recompensas"), custom_id=cid("rwe", "back")))
    return view


def _requirements_modal(bot: VoiceXPBot, guild_id: int, role_id: int, *, is_new: bool) -> ConfigModal:
    cfg = bot.configs.get(guild_id)
    reward = _find_reward(cfg, role_id)
    if reward is None:
        # Cargo novo: se o nome indicar um nível ("Lvl - 50"), pré-preenche
        guild = bot.get_guild(guild_id)
        role = guild.get_role(role_id) if guild else None
        match = _LEVEL_ROLE_RE.search(role.name) if role else None
        level_guess = min(1000, int(match.group(1))) if match else 0
        reward = RoleReward(role_id=role_id, required_level=level_guess)

    async def save(interaction: discord.Interaction, values: dict) -> None:
        if all(v <= 0 for v in values.values()):
            await interaction.response.send_message(
                "Configure pelo menos um requisito (XP, nível ou horas).", ephemeral=True
            )
            return
        reward.required_xp = values["required_xp"]
        reward.required_level = values["required_level"]
        reward.required_hours = values["required_hours"]
        if _find_reward(cfg, role_id) is None:
            cfg.role_rewards.append(reward)
        bot.configs.save(cfg)
        if interaction.guild:
            await _sort_level_roles(interaction.guild, cfg)  # mantém a hierarquia por nível
        await refresh(bot, interaction, f"reward:{role_id}")

        # Entrega a quem já cumpre o requisito, em background (não segura a interação)
        if interaction.guild:
            _schedule_reward_sync(bot, interaction.guild, cfg)

    return ConfigModal(
        "Requisitos da recompensa (0 = ignorar)",
        [
            Field("required_level", "Nível necessário", reward.required_level, max_value=1000),
            Field("required_xp", "XP total necessário (opcional)", reward.required_xp, max_value=10**9),
            Field(
                "required_hours",
                "Horas totais necessárias (opcional)",
                reward.required_hours,
                kind="float",
                max_value=100_000,
            ),
        ],
        save,
        custom_id=cid("rwe", "reqm", str(role_id), "new" if is_new else "edit"),
    )
