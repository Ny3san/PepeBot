"""can_manage: permissões do painel/comandos administrativos (utils/checks.py)."""

from __future__ import annotations

import logging

from conftest import FakeBot, FakeGuild, FakeMember, FakeRole

from models.guild_config import GuildConfig
from utils.checks import can_manage


def test_dono_do_servidor_pode_gerenciar():
    guild = FakeGuild(owner_id=999)
    owner = FakeMember(guild, id=999)
    bot = FakeBot()
    cfg = GuildConfig(guild_id=1)

    assert can_manage(bot, cfg, owner) is True


def test_sem_cargo_configurado_apenas_dono_pode():
    guild = FakeGuild(owner_id=999)
    other = FakeMember(guild, id=1)
    bot = FakeBot()
    cfg = GuildConfig(guild_id=1, manager_role_id=None)

    assert can_manage(bot, cfg, other) is False


def test_membro_com_cargo_gerente_pode_gerenciar():
    guild = FakeGuild(owner_id=999, roles=[FakeRole(42)])
    member = FakeMember(guild, id=1, role_ids=[42])
    bot = FakeBot()
    cfg = GuildConfig(guild_id=1, manager_role_id=42)

    assert can_manage(bot, cfg, member) is True


def test_bypass_permite_acesso_mesmo_sem_cargo_ou_ser_dono():
    guild = FakeGuild(owner_id=999)
    bypassed = FakeMember(guild, id=777)
    bot = FakeBot(bypass_user_ids=frozenset({777}))
    cfg = GuildConfig(guild_id=1)

    assert can_manage(bot, cfg, bypassed) is True


def test_bypass_exercido_e_logado(caplog):
    guild = FakeGuild(owner_id=999)
    bypassed = FakeMember(guild, id=777)
    bot = FakeBot(bypass_user_ids=frozenset({777}))
    cfg = GuildConfig(guild_id=1)

    with caplog.at_level(logging.WARNING, logger="utils.checks"):
        can_manage(bot, cfg, bypassed)

    assert any("BYPASS_USER_IDS" in record.message for record in caplog.records)


def test_uso_normal_por_dono_nao_gera_log_de_bypass(caplog):
    guild = FakeGuild(owner_id=999)
    owner = FakeMember(guild, id=999)
    bot = FakeBot()  # sem nenhum bypass configurado
    cfg = GuildConfig(guild_id=1)

    with caplog.at_level(logging.WARNING, logger="utils.checks"):
        can_manage(bot, cfg, owner)

    assert not any("BYPASS_USER_IDS" in record.message for record in caplog.records)
