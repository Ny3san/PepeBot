"""Constantes globais do bot."""

# IDs de bypass (admin global: pula cargo, cargo autorizado e 2FA)
BYPASS_USER_IDS = {1048415732368674906}

# Identidade visual (minimalista, sem emojis)
EMBED_COLOR = 0x2B2D31

# Prefixo de todos os customIds de componentes
COMPONENT_PREFIX = "vx"

# Intervalos das tasks
XP_TICK_SECONDS = 60
RANKING_INTERVAL_MINUTES = 5

# Curva de níveis: custo do nível N -> N+1 = BASE + LINEAR*N + QUAD*N²
# (modular: altere aqui para mudar a progressão inteira)
LEVEL_XP_BASE = 100
LEVEL_XP_LINEAR = 55
LEVEL_XP_QUAD = 15

# Durações do reset de ranking
RESET_DURATIONS_S = {
    "7d": 7 * 24 * 3600,
    "30d": 30 * 24 * 3600,
}
RESET_LABELS = {"never": "Nunca", "7d": "7 dias", "30d": "30 dias"}
