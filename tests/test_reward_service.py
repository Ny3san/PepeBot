"""RewardService: elegibilidade e sincronização de cargo (services/reward_service.py)."""
from __future__ import annotations

import pytest
from conftest import FakeGuild, FakeMember, FakeRole

from database.stats_repo import StatsRepository
from models.guild_config import GuildConfig, RoleReward
from models.stats import MemberStats
from services.reward_service import RewardService, highest_earned, meets_requirements, next_reward


def make_stats(**overrides) -> MemberStats:
    defaults = dict(guild_id=1, user_id=1, total_xp=0, total_seconds=0)
    defaults.update(overrides)
    return MemberStats(**defaults)


# ── meets_requirements ───────────────────────────────────────
def test_meets_requirements_todos_os_campos_configurados_precisam_bater():
    reward = RoleReward(role_id=1, required_xp=100, required_level=5, required_hours=2.0)
    stats = make_stats(total_xp=150, total_seconds=3 * 3600)
    assert meets_requirements(reward, stats, level=5) is True
    assert meets_requirements(reward, stats, level=4) is False  # nível não bate


def test_meets_requirements_campos_zerados_sao_ignorados():
    reward = RoleReward(role_id=1, required_xp=0, required_level=0, required_hours=0.0)
    stats = make_stats(total_xp=0)
    assert meets_requirements(reward, stats, level=0) is True


# ── highest_earned / next_reward ─────────────────────────────
def test_highest_earned_escolhe_a_maior_exigencia_atingida():
    rewards = [
        RoleReward(role_id=1, required_xp=100),
        RoleReward(role_id=2, required_xp=500),
        RoleReward(role_id=3, required_xp=10_000),  # não atingida
    ]
    cfg = GuildConfig(guild_id=1, role_rewards=rewards)
    stats = make_stats(total_xp=600)
    assert highest_earned(cfg, stats).role_id == 2


def test_next_reward_escolhe_a_menor_exigencia_pendente():
    rewards = [
        RoleReward(role_id=1, required_xp=100),
        RoleReward(role_id=2, required_xp=500),
        RoleReward(role_id=3, required_xp=10_000),
    ]
    cfg = GuildConfig(guild_id=1, role_rewards=rewards)
    stats = make_stats(total_xp=600)
    assert next_reward(cfg, stats).role_id == 3


# ── RewardService.check_member ───────────────────────────────
@pytest.mark.asyncio
async def test_check_member_concede_cargo_quando_elegivel(stats_repo: StatsRepository):
    guild = FakeGuild(roles=[FakeRole(10)])
    member = FakeMember(guild)
    cfg = GuildConfig(guild_id=1, role_rewards=[RoleReward(role_id=10, required_xp=50)])
    stats = make_stats(guild_id=1, user_id=member.id, total_xp=100)

    svc = RewardService(stats_repo)
    await svc.check_member(member, cfg, stats)

    assert member.added_roles == [10]


@pytest.mark.asyncio
async def test_check_member_sem_cargos_configurados_nao_faz_nada(stats_repo: StatsRepository):
    guild = FakeGuild()
    member = FakeMember(guild)
    cfg = GuildConfig(guild_id=1, role_rewards=[])
    svc = RewardService(stats_repo)

    await svc.check_member(member, cfg, make_stats())

    assert member.added_roles == []
    assert member.removed_roles == []


@pytest.mark.asyncio
async def test_check_member_mantem_so_o_cargo_mais_alto(stats_repo: StatsRepository):
    guild = FakeGuild(roles=[FakeRole(1), FakeRole(2)])
    member = FakeMember(guild, role_ids=[1])  # já tem o cargo de menor exigência
    cfg = GuildConfig(
        guild_id=1,
        role_rewards=[
            RoleReward(role_id=1, required_xp=50),
            RoleReward(role_id=2, required_xp=100),
        ],
    )
    stats = make_stats(guild_id=1, user_id=member.id, total_xp=200)  # agora atinge os dois

    svc = RewardService(stats_repo)
    await svc.check_member(member, cfg, stats)

    assert member.added_roles == [2]
    assert member.removed_roles == [1]


@pytest.mark.asyncio
async def test_check_member_idempotente_sem_mudancas(stats_repo: StatsRepository):
    guild = FakeGuild(roles=[FakeRole(1)])
    member = FakeMember(guild, role_ids=[1])  # já tem o cargo correto
    cfg = GuildConfig(guild_id=1, role_rewards=[RoleReward(role_id=1, required_xp=50)])
    stats = make_stats(guild_id=1, user_id=member.id, total_xp=100)

    svc = RewardService(stats_repo)
    await svc.check_member(member, cfg, stats)

    assert member.added_roles == []
    assert member.removed_roles == []
