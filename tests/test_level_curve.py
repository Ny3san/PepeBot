"""Curva de níveis (services/level_service.py)."""
from __future__ import annotations

from services.level_service import LevelCurve


def test_xp_for_level_segue_formula_quadratica():
    curve = LevelCurve(base=100, linear=55, quad=15)
    assert curve.xp_for_level(0) == 100
    assert curve.xp_for_level(1) == 100 + 55 + 15
    assert curve.xp_for_level(2) == 100 + 55 * 2 + 15 * 4


def test_progress_xp_zero_fica_no_nivel_zero():
    curve = LevelCurve()
    progress = curve.progress(0)
    assert progress.level == 0
    assert progress.current == 0
    assert progress.needed == curve.xp_for_level(0)


def test_progress_avanca_nivel_ao_completar_custo():
    curve = LevelCurve(base=100, linear=0, quad=0)  # cada nível custa exatamente 100
    progress = curve.progress(250)
    assert progress.level == 2
    assert progress.current == 50
    assert progress.needed == 100


def test_progress_fraction_e_percent():
    curve = LevelCurve(base=100, linear=0, quad=0)
    progress = curve.progress(25)
    assert progress.fraction == 0.25
    assert progress.percent == 25


def test_total_xp_for_level_e_inverso_de_progress():
    curve = LevelCurve()
    for target_level in (0, 1, 5, 10, 20):
        total = curve.total_xp_for_level(target_level)
        assert curve.progress(total).level == target_level
        assert curve.progress(total).current == 0
