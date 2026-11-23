"""Prints dos dashboards do Superset, cada um com o usuário do seu público (mostra o RBAC/RLS).

Uso (Superset de pé em localhost:8088):
    pip install playwright && playwright install chromium
    python scripts/screenshots.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8088"
OUT = Path(__file__).resolve().parents[1] / "docs" / "img"
PWD = os.getenv("DEMO_PASSWORD", "demo1234")
SHOTS = [
    ("01_vendas", "rep_demo", PWD, "vendas"),
    ("02_gestao", "gestor_demo", PWD, "gestao"),
    ("03_diretoria", "diretoria_demo", PWD, "diretoria"),
    ("04_financeiro", "financeiro_demo", PWD, "financeiro"),
    ("05_modelos", "admin", os.getenv("SUPERSET_ADMIN_PASSWORD", "admin"), "modelos"),
]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for name, user, pwd, slug in SHOTS:
            ctx = browser.new_context(
                viewport={"width": 1600, "height": 1000}, device_scale_factor=1, locale="pt-BR"
            )
            page = ctx.new_page()
            page.goto(f"{BASE}/login/")
            page.wait_for_selector("#username", timeout=60_000)
            page.fill("#username", user)
            page.fill("#password", pwd)
            page.keyboard.press("Enter")
            page.wait_for_url(lambda u: "/login" not in u, timeout=60_000)
            page.wait_for_load_state("networkidle")
            page.goto(f"{BASE}/superset/dashboard/{slug}/?standalone=2", wait_until="networkidle")
            page.wait_for_selector(".dashboard-component-chart-holder", timeout=120_000)
            # espera até nenhum gráfico estar carregando (um tempo fixo às vezes fotografava a tela vazia)
            page.wait_for_function(
                "document.querySelectorAll('[data-test=\"loading-indicator\"], .loading').length === 0",
                timeout=120_000,
            )
            page.wait_for_timeout(5_000)  # ECharts/deck.gl terminam a animação
            page.screenshot(path=str(OUT / f"{name}.png"), full_page=True)
            print("ok", name, "como", user)
            ctx.close()
        browser.close()


if __name__ == "__main__":
    main()
