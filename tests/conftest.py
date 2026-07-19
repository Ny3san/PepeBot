"""Fixtures compartilhadas: banco em memória e dublês leves de discord.py.

Não instanciamos discord.Member/Guild reais (exigem estado de conexão);
os dublês aqui implementam só a superfície usada pelos services testados.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from database.config_repo import ConfigRepository
from database.connection import Database
from database.stats_repo import StatsRepository


class FakeRole:
    def __init__(self, role_id: int) -> None:
        self.id = role_id
        self.name = f"role-{role_id}"
        self.mention = f"<@&{role_id}>"


class FakeGuild:
    def __init__(self, roles: list[FakeRole] | None = None) -> None:
        self.id = 1
        self._roles = {r.id: r for r in (roles or [])}

    def get_role(self, role_id: int) -> FakeRole | None:
        return self._roles.get(role_id)

    def get_channel(self, channel_id: int | None):
        return None  # nenhum teste depende de canal de log real


class FakeMember:
    """Duble de discord.Member: só a superfície usada pelos services."""

    def __init__(self, guild: FakeGuild, id: int = 42, role_ids: list[int] | None = None, bot: bool = False) -> None:
        self.guild = guild
        self.id = id
        self.bot = bot
        self.mention = f"<@{id}>"
        self._role_ids: set[int] = set(role_ids or [])
        self.added_roles: list[int] = []
        self.removed_roles: list[int] = []

    def get_role(self, role_id: int) -> FakeRole | None:
        if role_id not in self._role_ids:
            return None
        return self.guild.get_role(role_id)

    async def add_roles(self, role: FakeRole, reason: str | None = None) -> None:
        self._role_ids.add(role.id)
        self.added_roles.append(role.id)

    async def remove_roles(self, role: FakeRole, reason: str | None = None) -> None:
        self._role_ids.discard(role.id)
        self.removed_roles.append(role.id)


class FakeVoiceChannel:
    def __init__(self, members: list[FakeMember] | None = None) -> None:
        self.members = members or []


@pytest.fixture
def db() -> Database:
    database = Database(path=":memory:")
    yield database
    database.close()


@pytest.fixture
def stats_repo(db: Database) -> StatsRepository:
    return StatsRepository(db)


@pytest.fixture
def config_repo(db: Database) -> ConfigRepository:
    return ConfigRepository(db)
