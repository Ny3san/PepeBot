"""Ranking automático (imagem), cargo Top 1 e reset periódico."""
from __future__ import annotations

import logging
import time
from io import BytesIO
from typing import TYPE_CHECKING

import discord
from discord import ui

from config.defaults import EMBED_COLOR, RESET_DURATIONS_S, RESET_LABELS
from services.card_service import LeaderboardEntry, render_leaderboard
from services.level_service import curve
from services.log_service import send_log
from utils.format import fmt_hours, fmt_int

if TYPE_CHECKING:
    from bot import VoiceXPBot

log = logging.getLogger(__name__)

# Cache de avatares para a imagem do ranking: user_id → (chave do avatar, png)
_avatar_cache: dict[int, tuple[str, bytes]] = {}


async def _member_avatar(member: discord.Member | None) -> bytes | None:
    if member is None:
        return None
    asset = member.display_avatar.with_size(64)
    cached = _avatar_cache.get(member.id)
    if cached and cached[0] == asset.key:
        return cached[1]
    try:
        data = await asset.read()
    except discord.HTTPException:
        return None
    _avatar_cache[member.id] = (asset.key, data)
    if len(_avatar_cache) > 500:  # evita crescer para sempre
        _avatar_cache.pop(next(iter(_avatar_cache)))
    return data


async def build_rank_file(bot: "VoiceXPBot", guild: discord.Guild) -> discord.File | None:
    """Imagem do top 10 (usada pelo /rank e pela mensagem automática)."""
    top = [s for s in bot.stats.top(guild.id, 10) if s.period_xp > 0]
    if not top:
        return None

    leader_xp = top[0].period_xp
    entries: list[LeaderboardEntry] = []
    for i, s in enumerate(top, start=1):
        member = guild.get_member(s.user_id)
        entries.append(
            LeaderboardEntry(
                rank=i,
                name=member.display_name if member else f"Usuário {str(s.user_id)[-4:]}",
                level_text=f"Nv. {curve.progress(s.total_xp).level}",
                hours_text=fmt_hours(s.period_seconds),
                xp_fraction=s.period_xp / leader_xp,
                avatar_png=await _member_avatar(member),
            )
        )

    png = await render_leaderboard(entries)
    return discord.File(BytesIO(png), filename="rank.png")


def build_rank_view(bot: "VoiceXPBot", guild: discord.Guild) -> ui.LayoutView:
    """Fallback em Components v2 (ranking vazio ou falha na imagem)."""
    cfg = bot.configs.get(guild.id)
    top = [s for s in bot.stats.top(guild.id, 10) if s.period_xp > 0]

    lines = [
        f"**{i}.** <@{s.user_id}> · {fmt_int(s.period_xp)} XP · {fmt_hours(s.period_seconds)}"
        for i, s in enumerate(top, start=1)
    ] or ["Nenhum registro no período."]

    ts = discord.utils.format_dt(discord.utils.utcnow(), style="f")
    body = "\n".join(lines) + f"\n\n-# Reset: {RESET_LABELS[cfg.reset_mode].lower()} · {ts}"
    view = ui.LayoutView()
    view.add_item(ui.Container(ui.TextDisplay(f"### Ranking de voz\n{body}"), accent_colour=EMBED_COLOR))
    return view


async def update_rank_message(bot: "VoiceXPBot", guild: discord.Guild) -> None:
    """Mantém a mensagem de ranking (imagem) editada no canal configurado."""
    cfg = bot.configs.get(guild.id)
    if not cfg.rank_channel_id:
        return
    channel = guild.get_channel(cfg.rank_channel_id)
    if not isinstance(channel, discord.TextChannel):
        return

    file = await build_rank_file(bot, guild)
    if file is not None:
        payload = {"attachments": [file], "embeds": [], "content": None, "view": None}
        send_payload = {"file": file}
    else:
        view = build_rank_view(bot, guild)
        payload = {"attachments": [], "embeds": [], "content": None, "view": view}
        send_payload = {"view": view}

    if cfg.rank_message_id:
        try:
            message = await channel.fetch_message(cfg.rank_message_id)
            await message.edit(**payload)
            return
        except discord.NotFound:
            pass  # mensagem apagada — recria abaixo
        except discord.HTTPException as exc:
            if exc.code != 50005:  # 50005: a mensagem salva é de outro bot — recria abaixo
                log.warning("Falha ao editar ranking em %s: %s", guild.id, exc)
                return
            if file is not None:
                file.reset()  # o upload da edição falhada consumiu o buffer

    try:
        sent = await channel.send(**send_payload)
    except discord.HTTPException:
        return
    cfg.rank_message_id = sent.id
    bot.configs.save(cfg)


async def update_top1(bot: "VoiceXPBot", guild: discord.Guild) -> None:
    """Garante que o cargo Top 1 tenha exatamente um dono."""
    cfg = bot.configs.get(guild.id)
    if not cfg.top1_enabled or not cfg.top1_role_id:
        return
    role = guild.get_role(cfg.top1_role_id)
    if role is None:
        return

    top = bot.stats.top(guild.id, 1)
    leader_id = top[0].user_id if top and top[0].period_xp > 0 else None

    for member in list(role.members):
        if member.id != leader_id:
            try:
                await member.remove_roles(role, reason="Voice XP: perdeu o Top 1")
            except discord.HTTPException:
                pass

    if leader_id is None or any(m.id == leader_id for m in role.members):
        return

    member = guild.get_member(leader_id)
    if member is None:
        return
    try:
        await member.add_roles(role, reason="Voice XP: novo Top 1")
        await send_log(guild, cfg, f"**Novo Top 1** — <@{leader_id}> assumiu a liderança do ranking.")
    except discord.HTTPException:
        pass


async def check_period_reset(bot: "VoiceXPBot", guild: discord.Guild) -> None:
    """Reseta o ranking quando o período (7d/30d) vence."""
    cfg = bot.configs.get(guild.id)
    duration = RESET_DURATIONS_S.get(cfg.reset_mode)
    if duration is None:
        return

    if not cfg.period_start:
        cfg.period_start = time.time()
        bot.configs.save(cfg)
        return
    if time.time() - cfg.period_start < duration:
        return

    top = bot.stats.top(guild.id, 1)
    if top and top[0].period_xp > 0:
        winner = top[0]
        await send_log(
            guild,
            cfg,
            f"**Ranking resetado** vencedor : <@{winner.user_id}> "
            f"com **{fmt_int(winner.period_xp)} XP** ({fmt_hours(winner.period_seconds)}).",
        )

    bot.stats.reset_period(guild.id)
    cfg.period_start = time.time()
    bot.configs.save(cfg)
