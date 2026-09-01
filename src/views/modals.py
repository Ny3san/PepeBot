"""Modais genéricos do painel (entrada numérica e de texto validada)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

import discord
from discord import ui


@dataclass(frozen=True, slots=True)
class Field:
    key: str
    label: str
    default: Any
    kind: str = "int"  # int | float | str
    min_value: float = 0
    max_value: float = 1_000_000
    required: bool = True
    paragraph: bool = False


OnSave = Callable[[discord.Interaction, dict[str, Any]], Awaitable[None]]


class ConfigModal(ui.Modal):
    """Modal montado dinamicamente a partir de uma lista de Fields."""

    def __init__(self, title: str, fields: list[Field], on_save: OnSave, custom_id: str) -> None:
        super().__init__(title=title, custom_id=custom_id, timeout=600)
        self._fields = fields
        self._on_save = on_save
        self._inputs: dict[str, ui.TextInput] = {}
        for f in fields:
            item = ui.TextInput(
                label=f.label,
                default=str(f.default),
                required=f.required,
                style=discord.TextStyle.paragraph if f.paragraph else discord.TextStyle.short,
                max_length=1000 if f.paragraph else 32,
            )
            self._inputs[f.key] = item
            self.add_item(item)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        values: dict[str, Any] = {}
        for f in self._fields:
            raw = self._inputs[f.key].value.strip()
            if f.kind == "str":
                values[f.key] = raw
                continue
            try:
                number = float(raw.replace(",", ".")) if f.kind == "float" else int(raw)
            except ValueError:
                await interaction.response.send_message(
                    f"Valor inválido em **{f.label}**. Use apenas números.", ephemeral=True
                )
                return
            values[f.key] = min(f.max_value, max(f.min_value, number))
            if f.kind == "int":
                values[f.key] = int(values[f.key])
        await self._on_save(interaction, values)
