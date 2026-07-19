"""Formatação compartilhada entre as seções do painel."""
from __future__ import annotations


def yes_no(v: bool) -> str:
    return "Sim" if v else "Não"


def chan_list(ids: list[int]) -> str:
    return " ".join(f"<#{i}>" for i in ids) or "—"
