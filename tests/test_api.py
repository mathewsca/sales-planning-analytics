import pandas as pd
import pytest
from fastapi.testclient import TestClient

import api.main as m


@pytest.fixture
def client(monkeypatch):
    fc = pd.DataFrame(
        {
            "unique_id": ["Total", "Total/100/10/1", "Total/100/10/2"],
            "nivel": ["Total", "Representante", "Representante"],
            "ds": pd.to_datetime(["2026-02-01"] * 3),
            "h": [1, 1, 1],
            "p10": [800.0, 80.0, 160.0],
            "p50": [1000.0, 100.0, 200.0],
            "p90": [1250.0, 125.0, 250.0],
            "modelo_versao": ["v1"] * 3,
            "cutoff": pd.to_datetime(["2026-01-01"] * 3),
        }
    )
    m.forecasts.cache_clear()
    monkeypatch.setattr(m, "forecasts", lambda: fc)
    return TestClient(m.app)


def test_health(client):
    r = client.get("/health")
    assert r.json()["status"] == "ok" and r.json()["modelo_versao"] == "v1"


def test_forecast_por_nivel_e_id(client):
    r = client.get("/forecast/Representante", params={"id": "2"})
    assert r.status_code == 200 and r.json()[0]["p50"] == 200.0
    assert client.get("/forecast/Inexistente").status_code == 404


def test_simulacao_probabilidade_50_pct_e_a_mediana(client):
    r = client.post("/quota/simulate", json={"metodo": "probabilidade", "parametro": 0.5})
    body = r.json()
    assert r.status_code == 200
    assert body["meta_total"] == pytest.approx(300.0)
    assert body["prob_media_atingir"] == pytest.approx(0.5, abs=1e-6)


def test_simulacao_previsao_aplica_o_esticamento(client):
    r = client.post("/quota/simulate", json={"metodo": "previsao", "parametro": 0.1})
    assert r.status_code == 200
    assert r.json()["meta_total"] == pytest.approx(330.0)


def test_simulacao_probabilidade_fora_do_intervalo_e_recusada(client):
    r = client.post("/quota/simulate", json={"metodo": "probabilidade", "parametro": 1.0})
    assert r.status_code == 422
