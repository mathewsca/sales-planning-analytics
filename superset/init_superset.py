"""Dashboards como código: provisiona o Superset via API REST (idempotente).

Cria: conexão read-only com o warehouse, datasets (com as métricas da camada semântica), gráficos,
cinco dashboards por público, papéis (RBAC por dashboard), usuários de demonstração e regras de
segurança por linha (RLS). Roda no container `superset-init` depois que o Superset está saudável.
"""

from __future__ import annotations

import json
import os
import time
import uuid

import psycopg2
import requests
from dashboards import DASHBOARDS, DATASETS, ROLES, STATUS_LABEL_COLORS

BASE = os.getenv("SUPERSET_URL", "http://superset:8088")
ADMIN_PWD = os.getenv("SUPERSET_ADMIN_PASSWORD", "admin")
BI_URI = os.environ["WAREHOUSE_BI_URI"]
DB_NAME = "Warehouse (BI)"


class API:
    def __init__(self):
        self.s = requests.Session()
        for _ in range(60):
            try:
                r = self.s.post(
                    f"{BASE}/api/v1/security/login",
                    json={"username": "admin", "password": ADMIN_PWD, "provider": "db", "refresh": True},
                    timeout=10,
                )
                if r.ok:
                    break
            except requests.RequestException:
                pass
            time.sleep(5)
        r.raise_for_status()
        self.s.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
        csrf = self.s.get(f"{BASE}/api/v1/security/csrf_token/").json()["result"]
        self.s.headers.update({"X-CSRFToken": csrf, "Referer": BASE})

    def req(self, method: str, path: str, **kw):
        r = self.s.request(method, f"{BASE}{path}", timeout=120, **kw)
        if not r.ok:
            raise RuntimeError(f"{method} {path} -> {r.status_code}: {r.text[:500]}")
        return r.json() if r.text else {}

    def find(self, resource: str, col: str, value: str) -> list[dict]:
        q = json.dumps({"filters": [{"col": col, "opr": "eq", "value": value}], "page_size": 100})
        return self.req("GET", f"/api/v1/{resource}/", params={"q": _rison(q)}).get("result", [])


def _rison(js: str) -> str:
    """Converte o JSON simples usado aqui para rison (formato de query da API do Superset)."""
    obj = json.loads(js)

    def enc(v):
        if isinstance(v, dict):
            return "(" + ",".join(f"{k}:{enc(x)}" for k, x in v.items()) + ")"
        if isinstance(v, list):
            return "!(" + ",".join(enc(x) for x in v) + ")"
        if isinstance(v, bool):
            return "!t" if v else "!f"
        if isinstance(v, int | float):
            return str(v)
        s = str(v)
        return "'" + s.replace("!", "!!").replace("'", "!'") + "'"

    return enc(obj)


# --------------------------------------------------------------------------- banco e datasets
def upsert_database(api: API) -> int:
    found = api.find("database", "database_name", DB_NAME)
    payload = {
        "database_name": DB_NAME,
        "sqlalchemy_uri": BI_URI,
        "expose_in_sqllab": True,
        "allow_dml": False,
    }
    if found:
        api.req("PUT", f"/api/v1/database/{found[0]['id']}", json=payload)
        return found[0]["id"]
    return api.req("POST", "/api/v1/database/", json=payload)["id"]


def recreate_dataset(api: API, db_id: int, spec: dict) -> dict:
    for d in api.find("dataset", "table_name", spec["table"]):
        for c in (
            api.req("GET", f"/api/v1/dataset/{d['id']}/related_objects").get("charts", {}).get("result", [])
        ):
            api.req("DELETE", f"/api/v1/chart/{c['id']}")
        api.req("DELETE", f"/api/v1/dataset/{d['id']}")
    ds_id = api.req(
        "POST",
        "/api/v1/dataset/",
        json={"database": db_id, "schema": spec["schema"], "table_name": spec["table"]},
    )["id"]
    cur = api.req("GET", f"/api/v1/dataset/{ds_id}")["result"]
    cols = {c["column_name"] for c in cur["columns"]}
    metrics = [
        {"metric_name": m, "expression": e, "verbose_name": v, "d3format": f}
        for m, (e, v, f) in spec.get("metrics", {}).items()
    ]
    columns = [
        {k: c[k] for k in ("id", "column_name", "type", "is_dttm", "filterable", "groupby")}
        | {
            "verbose_name": spec.get("labels", {}).get(c["column_name"]),
            "is_dttm": c["column_name"] in spec.get("dttm", []) or c["is_dttm"],
        }
        for c in cur["columns"]
    ]
    body = {"metrics": metrics, "columns": columns}
    if spec.get("dttm"):
        body["main_dttm_col"] = spec["dttm"][0]
    api.req("PUT", f"/api/v1/dataset/{ds_id}?override_columns=true", json=body)
    return {"id": ds_id, "columns": cols}


# --------------------------------------------------------------------------- gráficos e dashboards
def create_chart(api: API, dash_id: int, ds: dict, chart: dict) -> int:
    params = {"datasource": f"{ds['id']}__table", "viz_type": chart["viz"], **chart["params"]}
    params.setdefault("color_scheme", "marca_marinho")
    body = {
        "slice_name": chart["name"],
        "viz_type": chart["viz"],
        "datasource_id": ds["id"],
        "datasource_type": "table",
        "params": json.dumps(params),
        "dashboards": [dash_id],
        "description": chart.get("desc", ""),
    }
    return api.req("POST", "/api/v1/chart/", json=body)["id"]


def layout(title: str, rows: list[list[dict]], chart_ids: dict) -> dict:
    pos = {
        "DASHBOARD_VERSION_KEY": "v2",
        "ROOT_ID": {"type": "ROOT", "id": "ROOT_ID", "children": ["GRID_ID"]},
        "GRID_ID": {"type": "GRID", "id": "GRID_ID", "children": [], "parents": ["ROOT_ID"]},
        "HEADER_ID": {"id": "HEADER_ID", "type": "HEADER", "meta": {"text": title}},
    }
    for i, row in enumerate(rows):
        rid = f"ROW-{i}"
        pos["GRID_ID"]["children"].append(rid)
        pos[rid] = {
            "type": "ROW",
            "id": rid,
            "children": [],
            "parents": ["ROOT_ID", "GRID_ID"],
            "meta": {"background": "BACKGROUND_TRANSPARENT"},
        }
        for j, item in enumerate(row):
            cid = f"CHART-{i}-{j}"
            pos[rid]["children"].append(cid)
            pos[cid] = {
                "type": "CHART",
                "id": cid,
                "children": [],
                "parents": ["ROOT_ID", "GRID_ID", rid],
                "meta": {
                    "width": item["w"],
                    "height": item.get("h", 50),
                    "chartId": chart_ids[item["chart"]],
                    "sliceName": item["chart"],
                    "uuid": str(uuid.uuid4()),
                },
            }
    return pos


def native_filters(filters: list[dict], datasets: dict, chart_ds: dict, chart_ids: dict) -> list[dict]:
    out = []
    for f in filters:
        ds = datasets[f["dataset"]]
        excluded = [
            chart_ids[name]
            for name, dsname in chart_ds.items()
            if f["column"] not in datasets[dsname]["columns"]
        ]
        out.append(
            {
                "id": f"NATIVE_FILTER-{uuid.uuid4().hex[:10]}",
                "name": f["name"],
                "filterType": "filter_select",
                "targets": [{"datasetId": ds["id"], "column": {"name": f["column"]}}],
                "controlValues": {
                    "multiSelect": True,
                    "enableEmptyFilter": False,
                    "searchAllOptions": False,
                    "inverseSelection": False,
                },
                "defaultDataMask": {"filterState": {}, "extraFormData": {}},
                "cascadeParentIds": [],
                "scope": {"rootPath": ["ROOT_ID"], "excluded": excluded},
                "type": "NATIVE_FILTER",
                "description": "",
                "chartsInScope": [cid for name, cid in chart_ids.items() if cid not in excluded],
            }
        )
    return out


def build_dashboard(api: API, d: dict, datasets: dict, role_ids: dict) -> int:
    for old in api.find("dashboard", "slug", d["slug"]):
        api.req("DELETE", f"/api/v1/dashboard/{old['id']}")
    dash_id = api.req(
        "POST",
        "/api/v1/dashboard/",
        json={"dashboard_title": d["title"], "slug": d["slug"], "published": True},
    )["id"]
    chart_ids, chart_ds = {}, {}
    for c in d["charts"]:
        chart_ids[c["name"]] = create_chart(api, dash_id, datasets[c["dataset"]], c)
        chart_ds[c["name"]] = c["dataset"]
    meta = {
        "color_scheme": "marca_marinho",
        "native_filter_configuration": native_filters(d.get("filters", []), datasets, chart_ds, chart_ids),
        "cross_filters_enabled": True,
        "refresh_frequency": 0,
        "timed_refresh_immune_slices": [],
        "expanded_slices": {},
        "label_colors": STATUS_LABEL_COLORS,
        "shared_label_colors": [],
    }
    api.req(
        "PUT",
        f"/api/v1/dashboard/{dash_id}",
        json={
            "position_json": json.dumps(layout(d["title"], d["rows"], chart_ids)),
            "json_metadata": json.dumps(meta),
            "roles": [role_ids[r] for r in d["roles"]],
            "css": "",
        },
    )
    return dash_id


# --------------------------------------------------------------------------- segurança
def upsert_role(api: API, name: str) -> int:
    found = [
        r
        for r in api.req("GET", "/api/v1/security/roles/", params={"q": "(page_size:100)"})["result"]
        if r["name"] == name
    ]
    return found[0]["id"] if found else api.req("POST", "/api/v1/security/roles/", json={"name": name})["id"]


def permission_index(api: API) -> list[dict]:
    out, page = [], 0
    while True:
        res = api.req(
            "GET", "/api/v1/security/permissions-resources/", params={"q": f"(page:{page},page_size:100)"}
        )["result"]
        out += res
        if len(res) < 100:
            return out
        page += 1


def grant_datasets(api: API, role_id: int, dataset_ids: list[int], perms: list[dict]) -> None:
    wanted = [
        p["id"]
        for p in perms
        if p["permission"]["name"] == "datasource_access"
        and any(p["view_menu"]["name"].endswith(f"(id:{i})") for i in dataset_ids)
    ]
    api.req(
        "POST", f"/api/v1/security/roles/{role_id}/permissions", json={"permission_view_menu_ids": wanted}
    )


def upsert_user(api: API, username: str, first: str, roles: list[int], password: str) -> None:
    users = api.req("GET", "/api/v1/security/users/", params={"q": "(page_size:100)"})["result"]
    found = [u for u in users if u["username"] == username]
    body = {
        "first_name": first,
        "last_name": "Demo",
        "username": username,
        "email": f"{username}@example.com",
        "active": True,
        "roles": roles,
    }
    if found:
        api.req("PUT", f"/api/v1/security/users/{found[0]['id']}", json=body | {"password": password})
    else:
        api.req("POST", "/api/v1/security/users/", json=body | {"password": password})


def upsert_rls(api: API, name: str, tables: list[int], roles: list[int], clause: str) -> None:
    for r in api.find("rowlevelsecurity", "name", name):
        api.req("DELETE", f"/api/v1/rowlevelsecurity/{r['id']}")
    api.req(
        "POST",
        "/api/v1/rowlevelsecurity/",
        json={
            "name": name,
            "filter_type": "Regular",
            "tables": tables,
            "roles": roles,
            "clause": clause,
            "group_key": "",
            "description": "RLS de demonstração",
        },
    )


def demo_people() -> dict:
    """Escolhe um representante 'em atenção' e o supervisor dele para os usuários de demonstração."""
    with psycopg2.connect(BI_URI.replace("postgresql+psycopg2", "postgresql")) as conn, conn.cursor() as cur:
        cur.execute(
            "select cod_representante, cod_supervisor from marts.rpt_vendas_mes_corrente "
            "where prob_atingir_meta is not null order by abs(prob_atingir_meta - 0.5) limit 1"
        )
        rep, sup = cur.fetchone()
    return {"rep": int(rep), "sup": int(sup)}


def main() -> None:
    api = API()
    db_id = upsert_database(api)
    datasets = {name: recreate_dataset(api, db_id, spec) for name, spec in DATASETS.items()}
    role_ids = {r: upsert_role(api, r) for r in ROLES}
    perms = permission_index(api)
    for role, ds_names in ROLES.items():
        grant_datasets(api, role_ids[role], [datasets[n]["id"] for n in ds_names], perms)
    for d in DASHBOARDS:
        build_dashboard(api, d, datasets, role_ids)
        print(f"[superset] dashboard '{d['title']}' ok")

    people = demo_people()
    gamma = upsert_role(api, "Gamma")
    rep_role = upsert_role(api, "Vendas · RCA demo")
    sup_role = upsert_role(api, "Gestão · Supervisor demo")
    rep_tables = [datasets[n]["id"] for n in DATASETS if "cod_representante" in datasets[n]["columns"]]
    sup_tables = [datasets[n]["id"] for n in DATASETS if "cod_supervisor" in datasets[n]["columns"]]
    upsert_rls(api, "rls_rep_demo", rep_tables, [rep_role], f"cod_representante = {people['rep']}")
    upsert_rls(api, "rls_sup_demo", sup_tables, [sup_role], f"cod_supervisor = {people['sup']}")
    pwd = os.getenv("DEMO_PASSWORD", "demo1234")
    upsert_user(api, "rep_demo", "Representante", [gamma, role_ids["Vendas"], rep_role], pwd)
    upsert_user(api, "gestor_demo", "Supervisor", [gamma, role_ids["Gestao"], sup_role], pwd)
    upsert_user(api, "diretoria_demo", "Diretoria", [gamma, role_ids["Diretoria"]], pwd)
    upsert_user(api, "financeiro_demo", "Financeiro", [gamma, role_ids["Financeiro"]], pwd)
    print(
        f"[superset] papéis, RLS (rep {people['rep']}, supervisor {people['sup']}) e usuários de demonstração ok"
    )


if __name__ == "__main__":
    main()
