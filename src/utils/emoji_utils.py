"""Utilities para usar emojis customizados nos buttons."""

import json
from pathlib import Path

EMOJI_MAP_FILE = Path(__file__).parent.parent.parent / ".emoji_map.json"


def load_emoji_map() -> dict[str, str]:
    """Carrega mapeamento de emojis customizados."""
    if not EMOJI_MAP_FILE.exists():
        return {}
    with open(EMOJI_MAP_FILE) as f:
        return json.load(f)


# Cache em memória
_emoji_cache = load_emoji_map()


def get_emoji(name: str) -> str | None:
    """Retorna emoji customizado por nome, ou None se não encontrado."""
    return _emoji_cache.get(name)


def emoji_or_text(name: str, fallback: str = "") -> str:
    """Retorna emoji ou texto fallback."""
    return get_emoji(name) or fallback or name
