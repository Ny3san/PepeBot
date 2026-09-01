"""VoiceXPBot.on_app_command_error: rede de segurança global para slash commands.

Testado sem instanciar VoiceXPBot de verdade (o __init__ abriria o
clown.db real) — o método não usa `self`, então é chamado direto na
classe com um `self` dummy.
"""

from __future__ import annotations

import logging

import discord
import pytest

from bot import VoiceXPBot


class _FakeHTTPResponse:
    status = 404
    reason = "Not Found"


def _http_exception(code: int) -> discord.HTTPException:
    return discord.HTTPException(_FakeHTTPResponse(), {"code": code, "message": "x"})


class FakeCommand:
    def __init__(self, name: str = "xp") -> None:
        self.qualified_name = name


class FakeResponse:
    def __init__(self, done: bool = False, raise_on_send: bool = False) -> None:
        self._done = done
        self._raise = raise_on_send
        self.sent: list[tuple[str, bool]] = []

    def is_done(self) -> bool:
        return self._done

    async def send_message(self, content: str, ephemeral: bool = False) -> None:
        if self._raise:
            raise _http_exception(50013)  # permissão qualquer, só pra testar o swallow
        self.sent.append((content, ephemeral))


class FakeFollowup:
    def __init__(self) -> None:
        self.sent: list[tuple[str, bool]] = []

    async def send(self, content: str, ephemeral: bool = False) -> None:
        self.sent.append((content, ephemeral))


class FakeInteraction:
    def __init__(self, done: bool = False, raise_on_send: bool = False) -> None:
        self.response = FakeResponse(done, raise_on_send)
        self.followup = FakeFollowup()
        self.command = FakeCommand()


@pytest.mark.asyncio
async def test_erro_generico_nao_respondido_envia_mensagem_efemera():
    interaction = FakeInteraction(done=False)

    await VoiceXPBot.on_app_command_error(None, interaction, ValueError("boom"))

    assert interaction.response.sent == [("Ocorreu um erro ao executar esse comando. Tente novamente.", True)]
    assert interaction.followup.sent == []


@pytest.mark.asyncio
async def test_erro_generico_ja_respondido_usa_followup():
    interaction = FakeInteraction(done=True)

    await VoiceXPBot.on_app_command_error(None, interaction, ValueError("boom"))

    assert interaction.followup.sent == [("Ocorreu um erro ao executar esse comando. Tente novamente.", True)]
    assert interaction.response.sent == []


@pytest.mark.asyncio
async def test_erro_10062_nao_envia_mensagem_so_loga(caplog):
    interaction = FakeInteraction(done=False)

    with caplog.at_level(logging.WARNING, logger="voicexp"):
        await VoiceXPBot.on_app_command_error(None, interaction, _http_exception(10062))

    assert interaction.response.sent == []
    assert interaction.followup.sent == []
    assert any("outra instância" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_falha_ao_enviar_a_mensagem_de_erro_nao_propaga():
    interaction = FakeInteraction(done=False, raise_on_send=True)

    # Não deve levantar, mesmo com o próprio envio da mensagem falhando
    await VoiceXPBot.on_app_command_error(None, interaction, RuntimeError("boom"))
