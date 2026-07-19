"""Dispatcher do painel: mapa seção -> builder e render()."""
from __future__ import annotations

from typing import TYPE_CHECKING

from views.base import SectionView
from views.panel.access import build_acesso
from views.panel.channels import build_channels
from views.panel.events import build_extras
from views.panel.main import build_config_hub, build_main
from views.panel.messages import build_messages
from views.panel.multipliers import build_multiplicadores
from views.panel.voice import build_geral
from views.rewards_view import build_reward_edit, build_rewards

if TYPE_CHECKING:
    from bot import VoiceXPBot

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
