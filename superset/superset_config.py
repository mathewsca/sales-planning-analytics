"""Configuração do Apache Superset (montada em /app/superset_home_config via docker compose)."""

import os

SECRET_KEY = os.environ["SUPERSET_SECRET_KEY"]
SQLALCHEMY_DATABASE_URI = os.environ["SUPERSET_DB_URI"]

APP_NAME = "Vendas e Metas"
BABEL_DEFAULT_LOCALE = "pt_BR"
LANGUAGES = {"pt_BR": {"flag": "br", "name": "Português"}, "en": {"flag": "us", "name": "English"}}
ROW_LIMIT = 50000

# números e datas no padrão brasileiro (1.234,56 · Fev 2026 · Seg)
D3_FORMAT = {"decimal": ",", "thousands": ".", "grouping": [3], "currency": ["R$ ", ""]}
D3_TIME_FORMAT = {
    "dateTime": "%A, %e de %B de %Y. %X",
    "date": "%d/%m/%Y",
    "time": "%H:%M:%S",
    "periods": ["AM", "PM"],
    "days": ["Domingo", "Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado"],
    "shortDays": ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"],
    "months": [
        "Janeiro",
        "Fevereiro",
        "Março",
        "Abril",
        "Maio",
        "Junho",
        "Julho",
        "Agosto",
        "Setembro",
        "Outubro",
        "Novembro",
        "Dezembro",
    ],
    "shortMonths": ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"],
}
SUPERSET_WEBSERVER_TIMEOUT = 120
MAPBOX_API_KEY = os.getenv("MAPBOX_API_KEY", "")

FEATURE_FLAGS = {
    "DASHBOARD_RBAC": True,  # cada dashboard é visível só para os papéis do seu público
    "DASHBOARD_NATIVE_FILTERS": True,
}

# --- padrão visual: marinho + âmbar --------------------------------------------------------
# Todas as cores passaram no validador de daltonismo (protanopia e deuteranopia, OKLab) e de
# contraste. Regras: séries sempre na ordem fixa abaixo; verde/âmbar/vermelho de status são
# reservados para "no ritmo / atenção / em risco" e sempre vêm com texto.
MARINHO, AZUL, AMBAR = "#0d366b", "#2a78d6", "#eda100"
STATUS = {"bom": "#0ca30c", "atencao": "#fab219", "risco": "#d03b3b"}

EXTRA_CATEGORICAL_COLOR_SCHEMES = [
    {
        "id": "marca_marinho",
        "description": "Séries dos gráficos: azul da marca, âmbar e demais cores validadas, em ordem fixa",
        "label": "Marca (marinho + âmbar)",
        "isDefault": True,
        "colors": [AZUL, AMBAR, "#1baf7a", "#eb6834", "#6250d6", "#e87ba4", "#008300", "#e34948"],
    }
]
EXTRA_SEQUENTIAL_COLOR_SCHEMES = [
    {
        "id": "marca_azul",
        "description": "Rampa sequencial de um tom (magnitude), do azul claro ao marinho da marca",
        "label": "Marca azul",
        "isDefault": True,
        "colors": ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", MARINHO],
    }
]


def _icone(tinta: str) -> str:
    """Ícone do app (sem nome de empresa): três barras crescentes, a última em âmbar, + o nome."""
    from urllib.parse import quote

    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="190" height="32" viewBox="0 0 190 32">'
        f'<rect x="2" y="17" width="5.5" height="10" rx="1.5" fill="{tinta}"/>'
        f'<rect x="10.25" y="11" width="5.5" height="16" rx="1.5" fill="{tinta}"/>'
        f'<rect x="18.5" y="5" width="5.5" height="22" rx="1.5" fill="{AMBAR}"/>'
        f'<text x="34" y="22" font-family="Inter, Segoe UI, Arial, sans-serif" font-size="16" '
        f'font-weight="600" fill="{tinta}">{APP_NAME}</text></svg>'
    )
    return "data:image/svg+xml;charset=utf-8," + quote(svg)


APP_ICON = _icone(MARINHO)

# Tema do Superset 6 (tokens do Ant Design): cor primária, links, status e ícone
THEME_DEFAULT = {
    "token": {
        "brandAppName": APP_NAME,
        "brandLogoAlt": APP_NAME,
        "brandLogoUrl": APP_ICON,
        "brandLogoHref": "/",
        "brandLogoHeight": "28px",
        "brandLogoMargin": "16px 0",
        "colorPrimary": MARINHO,
        "colorLink": "#256abf",
        "colorInfo": AZUL,
        "colorSuccess": STATUS["bom"],
        "colorWarning": STATUS["atencao"],
        "colorError": STATUS["risco"],
        "fontFamily": "Inter, Helvetica, Arial, sans-serif",
    },
    "algorithm": "default",
}
# modo escuro: o marinho some sobre fundo escuro, então botões e links usam passos mais claros da
# mesma rampa azul, e o ícone usa tinta clara
THEME_DARK = {
    "token": {
        **THEME_DEFAULT["token"],
        "brandLogoUrl": _icone("#f0efec"),
        "colorPrimary": "#3987e5",
        "colorLink": "#6da7ec",
        "colorInfo": "#6da7ec",
    },
    "algorithm": "dark",
}

# API de segurança (papéis/usuários) usada pelo init_superset.py para provisionar RBAC e RLS como código
FAB_ADD_SECURITY_API = True

# mapa de fundo sem chave do Mapbox (OpenStreetMap)
DECKGL_BASE_MAP = [
    ["tile://https://tile.openstreetmap.org/{z}/{x}/{y}.png", "OpenStreetMap"],
    ["mapbox://styles/mapbox/light-v9", "Mapbox claro (requer MAPBOX_API_KEY)"],
]

CACHE_CONFIG = {"CACHE_TYPE": "SimpleCache", "CACHE_DEFAULT_TIMEOUT": 600}
DATA_CACHE_CONFIG = CACHE_CONFIG
