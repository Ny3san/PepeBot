"""Sistema de níveis baseado no XP total.

A curva é isolada nesta classe para poder ser trocada no futuro sem
tocar no resto do código (basta alterar `xp_for_level` mantendo a
assinatura).
"""
from __future__ import annotations

from dataclasses import dataclass

from config.defaults import LEVEL_XP_BASE, LEVEL_XP_LINEAR, LEVEL_XP_QUAD


@dataclass(frozen=True, slots=True)
class LevelProgress:
    level: int        # nível atual
    current: int      # XP acumulado dentro do nível atual
    needed: int       # XP necessário para o próximo nível
    total_xp: int     # XP total do membro

    @property
    def fraction(self) -> float:
        return self.current / self.needed if self.needed else 1.0

    @property
    def percent(self) -> int:
        return round(self.fraction * 100)


class LevelCurve:
    """Curva quadrática: custo do nível N -> N+1 = base + linear·N + quad·N²."""

    def __init__(
        self,
        base: int = LEVEL_XP_BASE,
        linear: int = LEVEL_XP_LINEAR,
        quad: int = LEVEL_XP_QUAD,
    ) -> None:
        self.base = base
        self.linear = linear
        self.quad = quad

    def xp_for_level(self, level: int) -> int:
        """XP necessário para subir DO nível `level` para o próximo."""
        return self.base + self.linear * level + self.quad * level * level

    def progress(self, total_xp: int) -> LevelProgress:
        """Nível atual e progresso dentro dele a partir do XP total."""
        level = 0
        remaining = max(0, total_xp)
        while remaining >= (cost := self.xp_for_level(level)):
            remaining -= cost
            level += 1
        return LevelProgress(
            level=level,
            current=remaining,
            needed=self.xp_for_level(level),
            total_xp=total_xp,
        )

    def total_xp_for_level(self, target_level: int) -> int:
        """XP total necessário para atingir um nível específico (do nível 0)."""
        total = 0
        for level in range(target_level):
            total += self.xp_for_level(level)
        return total


# Instância padrão compartilhada
curve = LevelCurve()
