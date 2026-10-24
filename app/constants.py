"""Shared constants used by models, seeds and forms."""

PAYMENT_METHODS: tuple[str, ...] = (
    "Cash",
    "Card",
    "Transfer",
    "Other",
)

# Categories created on first run. Existing names are left untouched.
DEFAULT_CATEGORIES: tuple[dict[str, str], ...] = (
    {"name": "Comida y bebidas", "color": "#f97316"},
    {"name": "Supermercado", "color": "#84cc16"},
    {"name": "Transporte", "color": "#3b82f6"},
    {"name": "Vivienda", "color": "#8b5cf6"},
    {"name": "Servicios", "color": "#06b6d4"},
    {"name": "Salud", "color": "#10b981"},
    {"name": "Entretenimiento", "color": "#ec4899"},
    {"name": "Compras", "color": "#eab308"},
    {"name": "Otros", "color": "#64748b"},
)
