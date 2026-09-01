"""Formatação de números, tempo e barras de progresso."""

from __future__ import annotations


def fmt_int(n: int | float) -> str:
    """1234567 -> '1.234.567' (padrão pt-BR)."""
    return f"{int(n):,}".replace(",", ".")


def fmt_hours(seconds: int | float) -> str:
    """3720 -> '1h 02m'."""
    h, rem = divmod(int(seconds), 3600)
    return f"{h}h {rem // 60:02d}m"


def fmt_mult(value: float) -> str:
    """1.5 -> '1.5x' / 2.0 -> '2x'."""
    text = f"{value:.2f}".rstrip("0").rstrip(".")
    return f"{text}x"


def progress_bar(fraction: float, length: int = 16) -> str:
    """Barra de progresso textual: '████████░░░░░░░░'."""
    fraction = max(0.0, min(1.0, fraction))
    filled = round(fraction * length)
    return "█" * filled + "░" * (length - filled)
