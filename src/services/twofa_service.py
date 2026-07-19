"""Confirmação em duas etapas (2FA) das ações protegidas do painel.

Quando alguém que não é o dono tenta uma ação protegida (Permissões,
ligar/desligar o sistema), o bot manda um pedido na DM do dono com botões
de Confirmar/Recusar. Cada pedido vale para UMA ação e expira em 3 minutos
sem resposta.

Este serviço só guarda os pedidos pendentes (em memória); a parte visual
(DM, botões) vive em views/twofa.py.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

REQUEST_TTL_S = 180     # pedido sem resposta expira em 3 minutos

Key = tuple[int, int]   # (guild_id, user_id)


@dataclass(slots=True)
class PendingRequest:
    payload: Any        # (interação do painel, ação a executar)
    expires_at: float


class TwoFactorService:
    def __init__(self) -> None:
        self._pending: dict[Key, PendingRequest] = {}

    def active(self, guild_id: int, user_id: int) -> bool:
        """True se a pessoa já tem um pedido aguardando o dono."""
        pending = self._pending.get((guild_id, user_id))
        if pending is None:
            return False
        if pending.expires_at < time.time():
            del self._pending[(guild_id, user_id)]
            return False
        return True

    def put(self, guild_id: int, user_id: int, payload: Any) -> float:
        """Registra o pedido; retorna quando ele expira."""
        expires_at = time.time() + REQUEST_TTL_S
        self._pending[(guild_id, user_id)] = PendingRequest(payload, expires_at)
        return expires_at

    def pop(self, guild_id: int, user_id: int) -> Any | None:
        """Consome o pedido (uso único). None se não existe ou expirou."""
        pending = self._pending.pop((guild_id, user_id), None)
        if pending is None or pending.expires_at < time.time():
            return None
        return pending.payload
