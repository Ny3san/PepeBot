"""Navegação do painel /setup (views/panel.py): rede de segurança antes de
modularizar panel.py em subpacote, para garantir que a navegação entre
seções continua igual depois da divisão.
"""
from __future__ import annotations

import pytest
from conftest import FakeBot

from models.guild_config import GuildConfig, RoleReward
from views.base import SectionView
from views.panel import _SECTIONS, render


def _title(view: SectionView) -> str:
    """Extrai o "### Título" do primeiro TextDisplay do Container."""
    return view.container.children[0].content.splitlines()[0].removeprefix("### ")


EXPECTED_TITLES = {
    "main": "Voice XP",
    "config": "Settings",
    "geral": "XP de Voz",
    "mensagens": "XP de Chat",
    "canais": "Canais",
    "recompensas": "Cargos de Nível",
    "multiplicadores": "Multiplicadores por Cargo",
    "extras": "Eventos",
    "acesso": "Acesso",
}


@pytest.mark.parametrize("section", sorted(_SECTIONS))
def test_render_constroi_cada_secao_conhecida(section: str):
    bot = FakeBot(cfg=GuildConfig(guild_id=1))
    view = render(bot, 1, section)
    assert isinstance(view, SectionView)
    assert _title(view) == EXPECTED_TITLES[section]


def test_render_secao_desconhecida_cai_para_main():
    bot = FakeBot(cfg=GuildConfig(guild_id=1))
    view = render(bot, 1, "isso-nao-existe")
    assert _title(view) == "Voice XP"


def test_render_reward_edit_de_recompensa_existente():
    cfg = GuildConfig(guild_id=1, role_rewards=[RoleReward(role_id=42, required_xp=100)])
    bot = FakeBot(cfg=cfg)

    view = render(bot, 1, "reward:42")

    assert _title(view) == "Editar Recompensa"


def test_render_reward_edit_de_recompensa_inexistente_cai_para_lista():
    bot = FakeBot(cfg=GuildConfig(guild_id=1))
    view = render(bot, 1, "reward:999")
    assert _title(view) == "Cargos de Nível"


def test_todas_as_secoes_tem_pelo_menos_um_botao_voltar_ou_navegacao():
    """Regressão mínima de UI: nenhuma seção (exceto main) deve ser um
    beco sem saída — sempre precisa dar pra voltar."""
    bot = FakeBot(cfg=GuildConfig(guild_id=1))
    for section in _SECTIONS:
        if section == "main":
            continue
        view = render(bot, 1, section)
        custom_ids = [
            item.custom_id
            for row in view.container.children
            if hasattr(row, "children")
            for item in row.children
            if hasattr(item, "custom_id")
        ]
        assert any("back" in (cid or "") for cid in custom_ids), f"seção {section} sem botão de voltar"
