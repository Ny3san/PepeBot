"""XpService: multiplicadores e crédito de XP/minutos (services/xp_service.py)."""

from __future__ import annotations

from datetime import date, timedelta

from conftest import FakeGuild, FakeMember, FakeRole, FakeVoiceChannel

from database.connection import Database
from database.stats_repo import StatsRepository
from models.guild_config import GuildConfig, StreakBonus
from services.xp_service import XpService


def _yesterday() -> str:
    return (date.today() - timedelta(days=1)).isoformat()


def make_cfg(**overrides) -> GuildConfig:
    defaults = dict(guild_id=1, xp_per_minute=5, streak_bonuses=[])
    defaults.update(overrides)
    return GuildConfig(**defaults)


# ── role_multiplier ──────────────────────────────────────────
def test_role_multiplier_pega_o_maior_cargo():
    guild = FakeGuild(roles=[FakeRole(1), FakeRole(2), FakeRole(3)])
    member = FakeMember(guild, role_ids=[1, 2])
    cfg = make_cfg(role_multipliers={1: 1.5, 2: 3.0, 3: 5.0})
    assert XpService.role_multiplier(cfg, member) == 3.0


def test_role_multiplier_sem_cargo_e_1():
    guild = FakeGuild()
    member = FakeMember(guild, role_ids=[])
    cfg = make_cfg(role_multipliers={1: 2.0})
    assert XpService.role_multiplier(cfg, member) == 1.0


# ── group_multiplier ─────────────────────────────────────────
def test_group_multiplier_aplica_com_membros_suficientes():
    guild = FakeGuild()
    humans = [FakeMember(guild, id=i) for i in range(6)]
    channel = FakeVoiceChannel(members=humans)
    cfg = make_cfg(group_bonus_enabled=True, group_bonus_min_members=6, group_bonus_multiplier=1.5)
    assert XpService.group_multiplier(cfg, channel) == 1.5


def test_group_multiplier_ignora_bots_na_contagem():
    guild = FakeGuild()
    humans = [FakeMember(guild, id=i) for i in range(5)]
    bots = [FakeMember(guild, id=100 + i, bot=True) for i in range(5)]
    channel = FakeVoiceChannel(members=humans + bots)
    cfg = make_cfg(group_bonus_enabled=True, group_bonus_min_members=6)
    assert XpService.group_multiplier(cfg, channel) == 1.0  # só 5 humanos


def test_group_multiplier_desabilitado_e_1():
    guild = FakeGuild()
    channel = FakeVoiceChannel(members=[FakeMember(guild, id=i) for i in range(10)])
    cfg = make_cfg(group_bonus_enabled=False)
    assert XpService.group_multiplier(cfg, channel) == 1.0


# ── total_multiplier (stacking) ──────────────────────────────
def test_total_multiplier_empilha_role_group_streak_double():
    guild = FakeGuild(roles=[FakeRole(1)])
    member = FakeMember(guild, role_ids=[1])
    channel = FakeVoiceChannel(members=[FakeMember(guild, id=i) for i in range(6)])
    cfg = make_cfg(
        role_multipliers={1: 2.0},
        group_bonus_enabled=True,
        group_bonus_min_members=6,
        group_bonus_multiplier=1.5,
        streak_bonuses=[StreakBonus(7, 1.10)],
        double_xp_until=0.0,
    )
    svc = XpService(stats=None)
    mult = svc.total_multiplier(cfg, member, channel, streak_days=7)
    assert mult == 2.0 * 1.5 * 1.10


# ── award_minutes ────────────────────────────────────────────
def test_award_minutes_credita_xp_e_tempo(stats_repo: StatsRepository):
    guild = FakeGuild()
    member = FakeMember(guild)
    channel = FakeVoiceChannel(members=[member])
    cfg = make_cfg(xp_per_minute=5)
    svc = XpService(stats_repo)

    result = svc.award_minutes(cfg, member, channel, minutes=10)

    assert result is not None
    assert result.xp == 50
    assert result.seconds == 600
    assert result.stats.total_xp == 50
    assert result.stats.total_seconds == 600


def test_award_minutes_respeita_cap_diario_de_minutos(stats_repo: StatsRepository):
    guild = FakeGuild()
    member = FakeMember(guild)
    channel = FakeVoiceChannel(members=[member])
    cfg = make_cfg(xp_per_minute=5, daily_minutes_cap=3)
    svc = XpService(stats_repo)

    result = svc.award_minutes(cfg, member, channel, minutes=10)

    assert result.seconds == 3 * 60  # cortado para o cap
    assert result.xp == 15  # 3 minutos * 5 xp


def test_award_minutes_cap_de_minutos_zerado_nao_credita_nada(stats_repo: StatsRepository):
    guild = FakeGuild()
    member = FakeMember(guild)
    channel = FakeVoiceChannel(members=[member])
    cfg = make_cfg(xp_per_minute=5, daily_minutes_cap=5)
    svc = XpService(stats_repo)

    svc.award_minutes(cfg, member, channel, minutes=5)  # bate o cap
    result = svc.award_minutes(cfg, member, channel, minutes=5)  # nada sobra

    assert result is None


def test_award_minutes_cap_de_xp_corta_xp_mas_nao_o_tempo(stats_repo: StatsRepository):
    guild = FakeGuild()
    member = FakeMember(guild)
    channel = FakeVoiceChannel(members=[member])
    cfg = make_cfg(xp_per_minute=100, daily_xp_cap=50)
    svc = XpService(stats_repo)

    result = svc.award_minutes(cfg, member, channel, minutes=10)

    assert result.xp == 50  # cortado pelo cap de XP
    assert result.seconds == 600  # tempo não é afetado pelo cap de XP


def test_award_minutes_multiplicador_nao_afeta_tempo_creditado(stats_repo: StatsRepository):
    guild = FakeGuild(roles=[FakeRole(1)])
    member = FakeMember(guild, role_ids=[1])
    channel = FakeVoiceChannel(members=[member])
    cfg = make_cfg(xp_per_minute=5, role_multipliers={1: 2.0})
    svc = XpService(stats_repo)

    result = svc.award_minutes(cfg, member, channel, minutes=10)

    assert result.xp == 100  # 5 * 2.0 * 10
    assert result.seconds == 600  # tempo é sempre 1:1


# ── award_message_xp ─────────────────────────────────────────
def test_award_message_xp_credita_sem_bonus_de_grupo(stats_repo: StatsRepository):
    guild = FakeGuild()
    member = FakeMember(guild)
    cfg = make_cfg(message_xp_amount=10)
    svc = XpService(stats_repo)

    result = svc.award_message_xp(cfg, member)

    assert result is not None
    assert result.xp == 10
    assert result.seconds == 0


def test_award_message_xp_respeita_cap_diario(stats_repo: StatsRepository):
    guild = FakeGuild()
    member = FakeMember(guild)
    cfg = make_cfg(message_xp_amount=10, daily_xp_cap=15)
    svc = XpService(stats_repo)

    svc.award_message_xp(cfg, member)  # +10, total 10
    result = svc.award_message_xp(cfg, member)  # só sobra 5

    assert result.xp == 5


def test_award_message_xp_sem_xp_retorna_none(stats_repo: StatsRepository):
    guild = FakeGuild()
    member = FakeMember(guild)
    cfg = make_cfg(message_xp_amount=10, daily_xp_cap=10)
    svc = XpService(stats_repo)

    svc.award_message_xp(cfg, member)  # bate o cap
    result = svc.award_message_xp(cfg, member)

    assert result is None


# ── Bônus de streak vale no dia do marco (não no dia seguinte) ──
def test_award_minutes_aplica_bonus_de_streak_no_proprio_dia_do_marco(stats_repo: StatsRepository, db: Database):
    guild = FakeGuild()
    member = FakeMember(guild)
    channel = FakeVoiceChannel(members=[member])
    cfg = make_cfg(xp_per_minute=10, streak_bonuses=[StreakBonus(7, 2.0)])
    svc = XpService(stats_repo)

    # Membro já tem streak de 6 dias, ativo ontem: hoje é o 7º dia (marco).
    stats_repo.add_xp(guild_id=1, user_id=member.id, xp=0, seconds=0)
    db.conn.execute(
        "UPDATE voice_stats SET streak_current = 6, streak_last_date = ? WHERE guild_id = '1' AND user_id = ?",
        (_yesterday(), str(member.id)),
    )
    db.conn.commit()

    result = svc.award_minutes(cfg, member, channel, minutes=1)

    assert result.xp == 20  # 10 xp/min * 2.0 (bônus já vale hoje, no marco)
    assert result.stats.streak_current == 7  # streak também foi persistido


def test_award_message_xp_aplica_bonus_de_streak_no_proprio_dia_do_marco(stats_repo: StatsRepository, db: Database):
    guild = FakeGuild()
    member = FakeMember(guild)
    cfg = make_cfg(message_xp_amount=10, streak_bonuses=[StreakBonus(7, 2.0)])
    svc = XpService(stats_repo)

    stats_repo.add_xp(guild_id=1, user_id=member.id, xp=0, seconds=0)
    db.conn.execute(
        "UPDATE voice_stats SET streak_current = 6, streak_last_date = ? WHERE guild_id = '1' AND user_id = ?",
        (_yesterday(), str(member.id)),
    )
    db.conn.commit()

    result = svc.award_message_xp(cfg, member)

    assert result.xp == 20  # 10 * 2.0
    assert result.stats.streak_current == 7
