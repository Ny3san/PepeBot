"""StatsRepository e ConfigRepository sobre Database(path=":memory:")."""

from __future__ import annotations

from datetime import date, timedelta

from database.config_repo import ConfigRepository
from database.connection import Database
from database.stats_repo import StatsRepository
from models.guild_config import GuildConfig


def _today() -> str:
    return date.today().isoformat()


def _yesterday() -> str:
    return (date.today() - timedelta(days=1)).isoformat()


def _two_days_ago() -> str:
    return (date.today() - timedelta(days=2)).isoformat()


# ── StatsRepository ──────────────────────────────────────────
def test_get_cria_linha_com_defaults_zerados(stats_repo: StatsRepository):
    stats = stats_repo.get(guild_id=1, user_id=2)
    assert stats.total_xp == 0
    assert stats.total_seconds == 0
    assert stats.daily_date == _today()


def test_add_xp_acumula_total_period_e_daily(stats_repo: StatsRepository):
    stats_repo.add_xp(guild_id=1, user_id=2, xp=50, seconds=120)
    stats = stats_repo.get(guild_id=1, user_id=2)
    assert stats.total_xp == 50
    assert stats.total_seconds == 120
    assert stats.period_xp == 50
    assert stats.daily_xp == 50


def test_get_reseta_contadores_diarios_na_virada_do_dia(stats_repo: StatsRepository, db: Database):
    stats_repo.add_xp(guild_id=1, user_id=2, xp=50, seconds=60)
    db.conn.execute(
        "UPDATE voice_stats SET daily_date = ? WHERE guild_id = ? AND user_id = ?",
        (_yesterday(), "1", "2"),
    )
    db.conn.commit()

    stats = stats_repo.get(guild_id=1, user_id=2)

    assert stats.daily_xp == 0
    assert stats.daily_seconds == 0
    assert stats.daily_date == _today()
    assert stats.total_xp == 50  # total não é afetado pela virada


def test_register_streak_day_incrementa_em_dias_consecutivos(stats_repo: StatsRepository, db: Database):
    stats = stats_repo.get(guild_id=1, user_id=2)
    db.conn.execute(
        "UPDATE voice_stats SET streak_current = 3, streak_best = 3, streak_last_date = ? "
        "WHERE guild_id = '1' AND user_id = '2'",
        (_yesterday(),),
    )
    db.conn.commit()
    stats = stats_repo.get(guild_id=1, user_id=2)

    updated = stats_repo.register_streak_day(stats)

    assert updated.streak_current == 4
    assert updated.streak_best == 4
    assert updated.streak_last_date == _today()


def test_register_streak_day_ja_contado_hoje_nao_duplica(stats_repo: StatsRepository, db: Database):
    stats = stats_repo.get(guild_id=1, user_id=2)
    db.conn.execute(
        "UPDATE voice_stats SET streak_current = 3, streak_last_date = ? WHERE guild_id = '1' AND user_id = '2'",
        (_today(),),
    )
    db.conn.commit()
    stats = stats_repo.get(guild_id=1, user_id=2)

    updated = stats_repo.register_streak_day(stats)

    assert updated.streak_current == 3  # não incrementou de novo


def test_get_zera_streak_apos_um_dia_inteiro_sem_atividade(stats_repo: StatsRepository, db: Database):
    stats_repo.add_xp(guild_id=1, user_id=2, xp=10, seconds=10)
    db.conn.execute(
        "UPDATE voice_stats SET streak_current = 5, streak_last_date = ? WHERE guild_id = '1' AND user_id = '2'",
        (_two_days_ago(),),
    )
    db.conn.commit()

    stats = stats_repo.get(guild_id=1, user_id=2)

    assert stats.streak_current == 0


def test_adjust_xp_nao_deixa_total_negativo(stats_repo: StatsRepository):
    stats_repo.add_xp(guild_id=1, user_id=2, xp=30, seconds=0)
    stats = stats_repo.adjust_xp(guild_id=1, user_id=2, delta=-100)
    assert stats.total_xp == 0


def test_reset_user_zera_apenas_o_membro_alvo(stats_repo: StatsRepository):
    stats_repo.add_xp(guild_id=1, user_id=2, xp=100, seconds=100)
    stats_repo.add_xp(guild_id=1, user_id=3, xp=100, seconds=100)

    stats_repo.reset_user(guild_id=1, user_id=2)

    assert stats_repo.get(guild_id=1, user_id=2).total_xp == 0
    assert stats_repo.get(guild_id=1, user_id=3).total_xp == 100


def test_reset_guild_zera_todos_os_membros(stats_repo: StatsRepository):
    stats_repo.add_xp(guild_id=1, user_id=2, xp=100, seconds=100)
    stats_repo.add_xp(guild_id=1, user_id=3, xp=100, seconds=100)

    affected = stats_repo.reset_guild(guild_id=1)

    assert affected == 2
    assert stats_repo.get(guild_id=1, user_id=2).total_xp == 0
    assert stats_repo.get(guild_id=1, user_id=3).total_xp == 0


def test_top_ordena_por_period_xp_desc(stats_repo: StatsRepository):
    stats_repo.add_xp(guild_id=1, user_id=1, xp=10, seconds=0)
    stats_repo.add_xp(guild_id=1, user_id=2, xp=30, seconds=0)
    stats_repo.add_xp(guild_id=1, user_id=3, xp=20, seconds=0)

    top = stats_repo.top(guild_id=1, limit=10)

    assert [s.user_id for s in top] == [2, 3, 1]


def test_rank_of_calcula_posicao(stats_repo: StatsRepository):
    stats_repo.add_xp(guild_id=1, user_id=1, xp=10, seconds=0)
    stats_repo.add_xp(guild_id=1, user_id=2, xp=30, seconds=0)
    stats_repo.add_xp(guild_id=1, user_id=3, xp=20, seconds=0)

    assert stats_repo.rank_of(1, 2) == 1
    assert stats_repo.rank_of(1, 3) == 2
    assert stats_repo.rank_of(1, 1) == 3


# ── ConfigRepository ──────────────────────────────────────────
def test_get_sem_registro_retorna_defaults(config_repo: ConfigRepository):
    cfg = config_repo.get(guild_id=99)
    assert cfg.guild_id == 99
    assert cfg.enabled is False


def test_save_get_faz_roundtrip(config_repo: ConfigRepository):
    cfg = GuildConfig(guild_id=5, enabled=True, xp_per_minute=20)
    config_repo.save(cfg)

    # nova instância do repo (sem cache) força releitura do banco
    fresh_repo = ConfigRepository(config_repo._db)
    fetched = fresh_repo.get(guild_id=5)

    assert fetched.enabled is True
    assert fetched.xp_per_minute == 20


def test_get_usa_cache_em_memoria(config_repo: ConfigRepository, db: Database):
    cfg = GuildConfig(guild_id=5, xp_per_minute=20)
    config_repo.save(cfg)

    db.conn.execute("DELETE FROM guild_config WHERE guild_id = '5'")
    db.conn.commit()

    # ainda vem do cache, não do banco (que já não tem mais a linha)
    assert config_repo.get(guild_id=5).xp_per_minute == 20


def test_get_com_json_corrompido_cai_para_defaults_em_vez_de_derrubar_o_guild(
    config_repo: ConfigRepository, db: Database
):
    db.conn.execute("INSERT INTO guild_config (guild_id, config) VALUES (?, ?)", ("42", "{isso não é json"))
    db.conn.commit()

    cfg = config_repo.get(guild_id=42)

    assert cfg.guild_id == 42
    assert cfg.enabled is False  # defaults, sem propagar a exceção


def test_get_com_config_estruturalmente_invalida_cai_para_defaults(config_repo: ConfigRepository, db: Database):
    # JSON válido, mas com um formato que quebra a reconstrução do dataclass
    db.conn.execute(
        "INSERT INTO guild_config (guild_id, config) VALUES (?, ?)",
        ("42", '{"role_rewards": "isso deveria ser uma lista"}'),
    )
    db.conn.commit()

    cfg = config_repo.get(guild_id=42)

    assert cfg.guild_id == 42
    assert cfg.role_rewards == []
