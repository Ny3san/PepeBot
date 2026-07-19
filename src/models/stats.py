"""Modelo das estatísticas de um membro."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class MemberStats:
    guild_id: int
    user_id: int
    total_xp: int = 0
    total_seconds: int = 0
    period_xp: int = 0       # zera no reset do ranking
    period_seconds: int = 0
    daily_xp: int = 0
    daily_seconds: int = 0
    daily_date: str = ""
    streak_current: int = 0
    streak_best: int = 0
    streak_last_date: str = ""

    @property
    def total_hours(self) -> float:
        return self.total_seconds / 3600
