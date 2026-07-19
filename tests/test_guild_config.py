"""GuildConfig: defaults, (de)serialização e migração do formato legado."""
from __future__ import annotations

import time

from models.guild_config import GuildConfig, RoleReward, StreakBonus


def test_from_dict_vazio_usa_defaults():
    cfg = GuildConfig.from_dict(123, {})
    assert cfg.guild_id == 123
    assert cfg.enabled is False
    assert cfg.xp_per_minute == 5
    assert cfg.streak_bonuses  # defaults de streak preenchidos


def test_from_dict_formato_atual_aplica_campos():
    raw = {
        "enabled": True,
        "xp_per_minute": 10,
        "role_multipliers": {"111": 1.5},
        "role_rewards": [{"role_id": 999, "required_level": 5}],
        "streak_bonuses": [{"days": 3, "multiplier": 1.1}],
    }
    cfg = GuildConfig.from_dict(1, raw)
    assert cfg.enabled is True
    assert cfg.xp_per_minute == 10
    assert cfg.role_multipliers == {111: 1.5}
    assert cfg.role_rewards == [RoleReward(role_id=999, required_level=5)]
    assert cfg.streak_bonuses == [StreakBonus(3, 1.1)]


def test_to_dict_from_dict_roundtrip_preserva_valores():
    cfg = GuildConfig(guild_id=7, xp_per_minute=42, role_multipliers={5: 2.0})
    cfg.role_rewards.append(RoleReward(role_id=1, required_xp=100, remove_previous=True))
    restored = GuildConfig.from_dict(7, cfg.to_dict())
    assert restored == cfg


def test_from_dict_detecta_e_migra_formato_legado_camelcase():
    raw = {
        "enabled": True,
        "xpPerMinute": 7,
        "allowedChannels": ["1", "2"],
        "roleMultipliers": {"10": "1.5"},
        "roleRewards": [{"roleId": "555", "hours": "12.5"}],
        "top1RoleId": "20",
        "periodStart": 1700000000000,  # ms -> deve virar segundos
        "doubleXpUntil": 1700000000000,
    }
    cfg = GuildConfig.from_dict(9, raw)
    assert cfg.guild_id == 9
    assert cfg.xp_per_minute == 7
    assert cfg.allowed_channels == [1, 2]
    assert cfg.role_multipliers == {10: 1.5}
    assert cfg.role_rewards == [RoleReward(role_id=555, required_hours=12.5)]
    assert cfg.top1_role_id == 20
    assert cfg.period_start == 1700000000.0
    assert cfg.double_xp_until == 1700000000.0


def test_from_dict_legado_sem_timestamp_em_ms_nao_divide():
    # períodos já em segundos (< 1e11) não devem ser divididos por 1000
    raw = {"xpPerMinute": 5, "periodStart": 1700000000}
    cfg = GuildConfig.from_dict(1, raw)
    assert cfg.period_start == 1700000000


def test_double_xp_active():
    cfg = GuildConfig(guild_id=1, double_xp_until=time.time() + 60)
    assert cfg.double_xp_active() is True
    cfg.double_xp_until = time.time() - 60
    assert cfg.double_xp_active() is False
    cfg.double_xp_until = 0.0
    assert cfg.double_xp_active() is False


def test_is_trackable_channel():
    cfg = GuildConfig(guild_id=1, allowed_channels=[1, 2], excluded_channels=[2])
    assert cfg.is_trackable_channel(1) is True
    assert cfg.is_trackable_channel(2) is False  # excluído tem prioridade
    assert cfg.is_trackable_channel(3) is False  # não está na lista
    assert cfg.is_trackable_channel(None) is False


def test_streak_multiplier_pega_o_maior_marco_atingido():
    cfg = GuildConfig(guild_id=1)  # bônus default: 7/1.10, 15/1.25, 30/1.50, 60/2.0
    assert cfg.streak_multiplier(0) == 1.0
    assert cfg.streak_multiplier(6) == 1.0
    assert cfg.streak_multiplier(7) == 1.10
    assert cfg.streak_multiplier(14) == 1.10
    assert cfg.streak_multiplier(15) == 1.25
    assert cfg.streak_multiplier(60) == 2.0
    assert cfg.streak_multiplier(1000) == 2.0


def test_streak_multiplier_desabilitado_sempre_1():
    cfg = GuildConfig(guild_id=1, streak_enabled=False)
    assert cfg.streak_multiplier(365) == 1.0
