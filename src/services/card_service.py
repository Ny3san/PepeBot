"""Geração das imagens do bot (Pillow): cartão de perfil e leaderboard.

Estilo "profile banner": topo com gradiente colorido (indigo → roxo → rosa),
painel escuro embaixo e avatar sobreposto com anel — inspirado nos cartões
da Loritta / perfis do Discord. Desenhado em 2x e reduzido com LANCZOS.
O desenho roda em thread (asyncio.to_thread) para não bloquear o event loop.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

# ── Paleta (preto e cinza) ──────────────────────────────────
PANEL = (17, 18, 20)             # painel quase preto
TEXT = (255, 255, 255, 255)
MUTED = (150, 155, 163, 255)
FAINT = (105, 110, 118, 255)
BAR_BG = (46, 48, 53, 255)
GRAD = [(72, 74, 82), (48, 50, 56), (30, 31, 35)]        # banner: cinza → preto
BAR_GRAD = [(245, 245, 248), (200, 203, 209), (150, 155, 163)]  # barra: branco → cinza
GOLD = (241, 196, 83, 255)
SILVER = (200, 204, 210, 255)
BRONZE = (205, 127, 80, 255)

S = 2  # fator de supersampling

_FONT_BOLD = [
    "C:/Windows/Fonts/seguisb.ttf",
    "C:/Windows/Fonts/segoeuib.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]
_FONT_REGULAR = [
    "C:/Windows/Fonts/segoeui.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


def _font(size: int, bold: bool = False):
    for path in _FONT_BOLD if bold else _FONT_REGULAR:
        if Path(path).exists():
            return ImageFont.truetype(path, size * S)
    return ImageFont.load_default(size * S)


def _px(v: float) -> int:
    return int(v * S)


def _lerp(c1: tuple, c2: tuple, t: float) -> tuple:
    return tuple(int(a + (b - a) * t) for a, b in zip(c1, c2))


def _grad_color(t: float, stops: list[tuple] = GRAD) -> tuple:
    """Cor do gradiente triplo em t ∈ [0, 1]."""
    if t < 0.5:
        return _lerp(stops[0], stops[1], t * 2)
    return _lerp(stops[1], stops[2], (t - 0.5) * 2)


def _diag_gradient(w: int, h: int) -> Image.Image:
    """Gradiente diagonal suave (renderizado pequeno e ampliado)."""
    sw, sh = 96, 40
    base = Image.new("RGB", (sw, sh))
    pixels = base.load()
    for y in range(sh):
        for x in range(sw):
            t = (x / (sw - 1) * 0.75) + (y / (sh - 1) * 0.25)
            pixels[x, y] = _grad_color(t)
    return base.resize((w, h), Image.BILINEAR)


def _decor_circles(img: Image.Image, region_h: int) -> None:
    """Círculos translúcidos decorativos na área do banner."""
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    W = img.width
    circles = [  # (cx, cy, raio, alpha) em frações da largura/altura do banner
        (0.28, -0.55, 1.15, 10),
        (0.62, 1.35, 0.95, 8),
        (0.88, -0.25, 0.75, 11),
        (0.45, 0.45, 0.30, 7),
    ]
    for fx, fy, fr, alpha in circles:
        cx, cy, r = W * fx, region_h * fy, region_h * fr
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(255, 255, 255, alpha))
    img.alpha_composite(overlay)


def _circle_avatar(avatar_png: bytes | None, size: int) -> Image.Image:
    d = _px(size)
    if avatar_png:
        raw = Image.open(BytesIO(avatar_png)).convert("RGB")
        raw = ImageOps.fit(raw, (d, d))
    else:
        raw = Image.new("RGB", (d, d), BAR_BG[:3])
    mask = Image.new("L", (d * 2, d * 2), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, d * 2, d * 2), fill=255)
    mask = mask.resize((d, d), Image.LANCZOS)
    raw.putalpha(mask)
    return raw


def _gradient_bar(target: Image.Image, x0: int, y0: int, x1: int, y1: int) -> None:
    """Barra horizontal com gradiente claro (branco → cinza) e cantos redondos."""
    w, h = x1 - x0, y1 - y0
    if w <= 0:
        return
    grad = Image.new("RGB", (w, h))
    gd = ImageDraw.Draw(grad)
    for x in range(w):
        gd.line([(x, 0), (x, h)], fill=_grad_color(x / max(1, w - 1), BAR_GRAD))
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, w - 1, h - 1), radius=h // 2, fill=255)
    target.paste(grad, (x0, y0), mask)


def _truncate(draw: ImageDraw.ImageDraw, text: str, font, max_w: int) -> str:
    if draw.textlength(text, font=font) <= max_w:
        return text
    while text and draw.textlength(text + "…", font=font) > max_w:
        text = text[:-1]
    return text + "…"


def _banner_base(w: int, h: int, banner_h: int) -> Image.Image:
    """Base do cartão: banner gradiente + painel escuro embaixo."""
    base = Image.new("RGBA", (w, h))
    base.paste(_diag_gradient(w, h), (0, 0))
    _decor_circles(base, banner_h)
    ImageDraw.Draw(base).rectangle((0, banner_h, w, h), fill=PANEL)
    return base


def _finish(base: Image.Image, radius: int) -> bytes:
    """Aplica os cantos arredondados e finaliza em 1x."""
    mask = Image.new("L", base.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, base.width - 1, base.height - 1), radius=radius, fill=255
    )
    out = Image.new("RGBA", base.size, (0, 0, 0, 0))
    out.paste(base, (0, 0), mask)
    out = out.resize((out.width // S, out.height // S), Image.LANCZOS)
    buf = BytesIO()
    out.save(buf, "PNG")
    return buf.getvalue()


# ════════════════════════ Cartão de perfil ════════════════════════

@dataclass(frozen=True, slots=True)
class CardData:
    """Tudo que o cartão /xp exibe."""

    name: str
    level: int
    level_current: int
    level_needed: int
    level_percent: int
    hours_text: str
    rank: str
    avatar_png: bytes | None


def _draw_card(data: CardData) -> bytes:
    W, H, BANNER = _px(1000), _px(340), _px(128)
    img = _banner_base(W, H, BANNER)
    draw = ImageDraw.Draw(img)

    # ── Avatar sobreposto ao banner, com anel na cor do painel ──
    av_size = 150
    ax, acy = _px(56), BANNER  # centro vertical na linha do banner
    ring = _px(7)
    draw.ellipse(
        (ax - ring, acy - _px(av_size // 2) - ring,
         ax + _px(av_size) + ring, acy + _px(av_size // 2) + ring),
        fill=PANEL,
    )
    avatar = _circle_avatar(data.avatar_png, av_size)
    img.paste(avatar, (ax, acy - _px(av_size // 2)), avatar)

    left, right = _px(250), _px(952)

    # ── Nome (sobre o painel, abaixo do banner) ─────────────
    name_font = _font(40, bold=True)
    name = _truncate(draw, data.name, name_font, right - left)
    draw.text((left, _px(142)), name, font=name_font, fill=TEXT)

    # ── Barra de nível: XP acima, porcentagem no final ──────
    bar_y, bar_h = _px(226), _px(18)
    pct_font = _font(20, bold=True)
    pct_text = f"{data.level_percent}%"
    pct_w = draw.textlength(pct_text, font=pct_font)
    bar_right = right - int(pct_w) - _px(16)

    xp_font = _font(17)
    xp_text = f"{data.level_current:,} / {data.level_needed:,} XP".replace(",", ".")
    xp_w = draw.textlength(xp_text, font=xp_font)
    draw.text((bar_right - xp_w, bar_y - _px(30)), xp_text, font=xp_font, fill=MUTED)

    draw.rounded_rectangle((left, bar_y, bar_right, bar_y + bar_h), radius=bar_h // 2, fill=BAR_BG)
    fill_w = max(bar_h, int((bar_right - left) * data.level_percent / 100))
    _gradient_bar(img, left, bar_y, left + fill_w, bar_y + bar_h)
    draw.text((bar_right + _px(14), bar_y + bar_h // 2 - _px(13)), pct_text, font=pct_font, fill=TEXT)

    # ── Estatísticas ────────────────────────────────────────
    stats = [
        ("NÍVEL", str(data.level), 0.34),
        ("HORAS", data.hours_text, 0.36),
        ("POSIÇÃO", data.rank, 0.30),
    ]
    label_font, value_font = _font(13, bold=True), _font(25, bold=True)
    x, total_w = left, right - left
    for label, value, frac in stats:
        col_w = int(total_w * frac)
        draw.text((x, _px(268)), label, font=label_font, fill=FAINT)
        value = _truncate(draw, value, value_font, col_w - _px(12))
        draw.text((x, _px(288)), value, font=value_font, fill=TEXT)
        x += col_w

    return _finish(img, _px(28))


async def render_card(data: CardData) -> bytes:
    return await asyncio.to_thread(_draw_card, data)


# ════════════════════════ Leaderboard ════════════════════════

@dataclass(frozen=True, slots=True)
class LeaderboardEntry:
    rank: int
    name: str
    level_text: str      # "Nv. 42"
    hours_text: str      # "10h 05m"
    xp_fraction: float   # xp relativo ao 1º lugar (0..1)
    avatar_png: bytes | None


RANK_COLORS = {1: GOLD, 2: SILVER, 3: BRONZE}


def _draw_leaderboard(entries: list[LeaderboardEntry]) -> bytes:
    row_h, pad_top, pad_bottom = 46, 10, 12
    W = _px(620)
    H = _px(pad_top + row_h * len(entries) + pad_bottom)
    img = Image.new("RGBA", (W, H))
    ImageDraw.Draw(img).rectangle((0, 0, W, H), fill=PANEL)
    draw = ImageDraw.Draw(img)

    rank_font = _font(16, bold=True)
    name_font = _font(15, bold=True)
    level_font = _font(14, bold=True)
    hours_font = _font(12)

    for i, entry in enumerate(entries):
        cy = _px(pad_top + i * row_h + row_h // 2)

        # posição (top 3 colorido)
        rank_text = str(entry.rank)
        color = RANK_COLORS.get(entry.rank, FAINT)
        rank_w = draw.textlength(rank_text, font=rank_font)
        draw.text((_px(44) - rank_w, cy - _px(11)), rank_text, font=rank_font, fill=color)

        # avatar
        avatar = _circle_avatar(entry.avatar_png, 30)
        img.paste(avatar, (_px(58), cy - _px(15)), avatar)

        # horas e nível à direita
        hours_w = draw.textlength(entry.hours_text, font=hours_font)
        draw.text((W - _px(26) - hours_w, cy - _px(7)), entry.hours_text, font=hours_font, fill=MUTED)
        lvl_w = draw.textlength(entry.level_text, font=level_font)
        lvl_x = W - _px(26) - hours_w - _px(14) - lvl_w
        draw.text((lvl_x, cy - _px(9)), entry.level_text, font=level_font, fill=TEXT)

        # nome + barra sutil de XP relativo ao líder
        name_x = _px(100)
        name = _truncate(draw, entry.name, name_font, lvl_x - name_x - _px(16))
        draw.text((name_x, cy - _px(16)), name, font=name_font, fill=TEXT)

        bar_y = cy + _px(7)
        bar_max = lvl_x - name_x - _px(16)
        bar_w = max(_px(4), int(bar_max * entry.xp_fraction))
        draw.rounded_rectangle((name_x, bar_y, name_x + bar_max, bar_y + _px(3)), radius=_px(1), fill=BAR_BG)
        _gradient_bar(img, name_x, bar_y, name_x + bar_w, bar_y + _px(3))

    return _finish(img, _px(18))


async def render_leaderboard(entries: list[LeaderboardEntry]) -> bytes:
    return await asyncio.to_thread(_draw_leaderboard, entries)
