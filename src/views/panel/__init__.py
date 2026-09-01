"""Painel de configuração (/setup) — seções e navegação (Components v2).

Dividido em subpacote por seção (era um único arquivo de 483 linhas / 9
seções): main.py (menu + hub de Settings), voice.py, messages.py,
channels.py, multipliers.py, events.py, access.py, e dispatcher.py
(_SECTIONS + render()). Estrutura:

  main
  ├── geral (XP de Voz) · mensagens (XP de Chat) · multiplicadores
  ├── config (Settings) → recompensas, canais
  ├── extras (Eventos) · acesso (2FA)
  └── ativar/desativar sistema
  reward:<id>             (rewards_view, fora da árvore de navegação)
"""

from __future__ import annotations

from views.panel.dispatcher import _SECTIONS, render

__all__ = ["render", "_SECTIONS"]
