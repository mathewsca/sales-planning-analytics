"""Gerador sintético de vendas de um atacado distribuidor, com mecanismo causal conhecido.

Mecanismo (verdade conhecida, salva em data/ground_truth/ como oráculo):
  pedidos do cliente c no mês m ~ Poisson( taxa_c * habilidade_rep * sazonalidade_m * tendência
                                           * dias_úteis_do_município(m) * choque )
  dia do pedido ~ fator do dia no município (dia da semana, feriado nacional/estadual/MUNICIPAL,
                  véspera = antecipação, ponte = emenda)
  SKU de cada linha ~ popularidade * (1 + uplift) se o SKU está em campanha no mês
                      * (1 - dip) no mês seguinte (antecipação de compras)
  Campanhas preferem SKUs de giro lento (viés de seleção, como no relatório original).
  Metas legadas = (1+g) * max(mesmo mês do ano anterior, média dos últimos 3 meses) -> "catraca".

Privacidade por construção: IDs aleatórios com quantidade de dígitos própria, nomes fictícios,
fornecedores e produtos só por código, municípios públicos (IBGE) de outra região e calendário
posterior aos dados de referência.

Uso: python -m sales_planning_analytics.generator.generate [--scenario base|shock] [--scale 1.0]
"""

from __future__ import annotations

import argparse
import json
import os

import numpy as np
import pandas as pd
import yaml
from faker import Faker

from sales_planning_analytics.public.calendar import day_factor_matrix, load_municipios
from sales_planning_analytics.settings import settings

ID_DIGITS = {
    "filial": 4,
    "coordenador": 5,
    "supervisor": 6,
    "representante": 7,
    "interno": 8,
    "cliente": 10,
    "fornecedor": 4,
    "produto": 9,
    "campanha": 6,
    "pedido": 12,
}


def _ids(rng: np.random.Generator, n: int, kind: str) -> np.ndarray:
    d = ID_DIGITS[kind]
    lo, hi = 10 ** (d - 1), 10**d - 1
    out = np.unique(rng.integers(lo, hi, size=int(n * 1.3) + 10))
    rng.shuffle(out)
    return out[:n]


def _haversine(lat1, lon1, lat2, lon2):
    r = np.pi / 180
    a = (
        np.sin((lat2 - lat1) * r / 2) ** 2
        + np.cos(lat1 * r) * np.cos(lat2 * r) * np.sin((lon2 - lon1) * r / 2) ** 2
    )
    return 6371 * 2 * np.arcsin(np.sqrt(a))


def _people(fake: Faker, n: int) -> list[str]:
    """Nome + inicial do sobrenome: fictício e sem risco de coincidir com pessoas reais."""
    return [f"{fake.first_name()} {fake.last_name()[0]}." for _ in range(n)]


def _client_names(fake: Faker, rng: np.random.Generator, n: int) -> list[str]:
    pre = ["Comercial", "Distribuição", "Mercantil", "Casa", "Empório", "Center", "Atacarejo", "Loja"]
    suf = ["Ltda", "ME", "EIRELI", "& Filhos", "S/A", ""]
    return [
        f"{pre[rng.integers(len(pre))]} {fake.last_name()} {fake.last_name()[:3].upper()} {suf[rng.integers(len(suf))]}".strip()
        for _ in range(n)
    ]


class Generator:
    def __init__(self, cfg: dict, scenario: str = "base", scale: float = 1.0):
        self.cfg, self.scenario, self.scale = cfg, scenario, scale
        self.rng = np.random.default_rng(cfg["seed"])
        self.fake = Faker("pt_BR")
        Faker.seed(cfg["seed"])
        self.start = pd.Timestamp(cfg["period"]["start"])
        self.end = pd.Timestamp(cfg["period"]["end"])
        self.months = pd.period_range(self.start, self.end, freq="M")

    def n(self, key: str, minimum: int = 1) -> int:
        base = self.cfg["scale"][key]
        if key in ("coordenadores", "fornecedores"):
            return base
        return max(minimum, int(round(base * self.scale)))

    # ------------------------------------------------------------------ geografia
    def geography(self) -> None:
        cfg, rng = self.cfg, self.rng
        mun = load_municipios()
        pot = mun.populacao ** cfg["potencial"]["a"] * mun.pib_per_capita ** cfg["potencial"]["b"]
        mun["potencial_true"] = pot / pot.sum()
        fil = mun.set_index("cod_ibge").loc[cfg["filiais"]]
        dist = np.stack(
            [
                _haversine(mun.latitude.values, mun.longitude.values, la, lo)
                for la, lo in zip(fil.latitude, fil.longitude, strict=True)
            ],
            axis=1,
        )
        mun["filial_idx"] = dist.argmin(axis=1)
        mun["dist_filial_km"] = dist.min(axis=1)
        # cobertura comercial decai com a distância: municípios longe da filial ficam "não explorados"
        p_cov = 1 / (1 + np.exp((mun.dist_filial_km - cfg["cobertura_raio_km"]) / 60))
        mun["atendido"] = rng.random(len(mun)) < p_cov
        self.mun = mun.reset_index(drop=True)
        self.filiais = pd.DataFrame(
            {
                "filial_id": _ids(rng, len(fil), "filial"),
                "cod_ibge": fil.index.values,
                "nome_filial": [f"Filial {m}" for m in fil.municipio],
            }
        )

    # ------------------------------------------------------------------ equipe
    def team(self) -> None:
        cfg, rng, fake = self.cfg, self.rng, self.fake
        n_coord, n_rep = self.n("coordenadores"), self.n("representantes", 20)
        n_sup = max(self.n("supervisores"), len(self.filiais))
        mun = self.mun[self.mun.atendido]
        # filiais -> coordenadores (cidades-polo vizinhas compartilham coordenador)
        fil_coord = np.arange(len(self.filiais)) % n_coord
        coord = pd.DataFrame(
            {"coordenador_id": _ids(rng, n_coord, "coordenador"), "nome": _people(fake, n_coord)}
        )
        # supervisores e representantes alocados por potencial atendido de cada filial
        pot_fil = (
            mun.groupby("filial_idx").potencial_true.sum().reindex(range(len(self.filiais)), fill_value=0)
        )
        sup_fil = rng.choice(len(self.filiais), size=n_sup, p=pot_fil / pot_fil.sum())
        sup_fil[: len(self.filiais)] = np.arange(len(self.filiais))  # toda filial tem ao menos 1 supervisor
        sup = pd.DataFrame(
            {
                "supervisor_id": _ids(rng, n_sup, "supervisor"),
                "nome": _people(fake, n_sup),
                "filial_idx": sup_fil,
            }
        )
        sup["coordenador_id"] = coord.coordenador_id.values[fil_coord[sup.filial_idx]]
        # representantes: por região imediata atendida, proporcional ao potencial
        reg = mun.groupby(["cod_regiao_imediata", "filial_idx"]).potencial_true.sum().reset_index()
        alloc = np.maximum(1, np.round(reg.potencial_true / reg.potencial_true.sum() * n_rep)).astype(int)
        reg = reg.loc[reg.index.repeat(alloc)].reset_index(drop=True)
        n_rep = len(reg)
        rep = pd.DataFrame(
            {
                "representante_id": _ids(rng, n_rep, "representante"),
                "nome": _people(fake, n_rep),
                "cod_regiao_imediata": reg.cod_regiao_imediata.values,
                "filial_idx": reg.filial_idx.values,
            }
        )
        sup_by_fil = sup.groupby("filial_idx").supervisor_id.apply(list)
        rep["supervisor_id"] = [sup_by_fil[f][i % len(sup_by_fil[f])] for i, f in enumerate(rep.filial_idx)]
        rep["habilidade_true"] = np.exp(rng.normal(0, cfg["equipe"]["habilidade_sd_log"], n_rep))
        rep["data_admissao"] = pd.to_datetime("2016-01-01") + pd.to_timedelta(
            rng.integers(0, 2500, n_rep), "D"
        )
        n_int = self.n("vendedores_internos", 3)
        interno = pd.DataFrame(
            {
                "interno_id": _ids(rng, n_int, "interno"),
                "nome": _people(fake, n_int),
                "filial_idx": np.arange(n_int) % len(self.filiais),
            }
        )
        self.coord, self.sup, self.rep, self.interno = coord, sup, rep, interno

    # ------------------------------------------------------------------ clientes e produtos
    def customers(self) -> None:
        _cfg, rng, c = self.cfg, self.rng, self.cfg["clientes"]
        n = self.n("clientes", 300)
        mun = self.mun[self.mun.atendido]
        w = mun.potencial_true**0.9
        mun_idx = rng.choice(mun.index.values, size=n, p=w / w.sum())
        porte = rng.choice(list(c["porte_p"]), size=n, p=list(c["porte_p"].values()))
        cli = pd.DataFrame(
            {
                "cliente_id": _ids(rng, n, "cliente"),
                "razao_social": _client_names(self.fake, rng, n),
                "mun_idx": mun_idx,
                "porte": porte,
                "segmento": [f"Segmento {i:02d}" for i in rng.integers(1, c["segmentos"] + 1, n)],
            }
        )
        cli["cod_ibge"] = self.mun.cod_ibge.values[cli.mun_idx]
        cli["size"] = cli.porte.map(c["porte_mult"]).values
        cli["taxa_true"] = c["pedidos_mes_mediana"] * np.exp(rng.normal(0, c["pedidos_mes_sd_log"], n))
        # representante: um dos representantes da região imediata do cliente
        reg_of_cli = self.mun.cod_regiao_imediata.values[cli.mun_idx]
        reps_by_reg = self.rep.groupby("cod_regiao_imediata").representante_id.apply(list)
        cli["representante_id"] = [
            reps_by_reg[r][rng.integers(len(reps_by_reg[r]))] if r in reps_by_reg.index else -1
            for r in reg_of_cli
        ]
        # regiões sem representante dedicado: atendidas pelo representante da filial mais próxima
        orphan = cli.representante_id == -1
        if orphan.any():
            fil_of = self.mun.filial_idx.values[cli.loc[orphan, "mun_idx"]]
            reps_by_fil = self.rep.groupby("filial_idx").representante_id.apply(list)
            cli.loc[orphan, "representante_id"] = [
                reps_by_fil[f][rng.integers(len(reps_by_fil[f]))] for f in fil_of
            ]
        tele = rng.random(n) < c["share_televenda"]
        fil_of_cli = self.mun.filial_idx.values[cli.mun_idx]
        int_by_fil = self.interno.groupby("filial_idx").interno_id.apply(list)
        cli["interno_id"] = [
            int_by_fil[f][rng.integers(len(int_by_fil[f]))] if (t and f in int_by_fil.index) else pd.NA
            for t, f in zip(tele, fil_of_cli, strict=True)
        ]
        cli["data_cadastro"] = pd.to_datetime("2012-01-01") + pd.to_timedelta(rng.integers(0, 4000, n), "D")
        self.cli = cli

    def products(self) -> None:
        _cfg, rng, p = self.cfg, self.rng, self.cfg["pedido"]
        n, nf = self.n("produtos", 200), self.n("fornecedores")
        forn = pd.DataFrame(
            {
                "fornecedor_id": _ids(rng, nf, "fornecedor"),
                "fornecedor": [f"Fornecedor {i:02d}" for i in range(1, nf + 1)],
            }
        )
        f_idx = rng.integers(0, nf, n)
        lines = np.array(list("ABCDEFGH"))
        prod = pd.DataFrame(
            {
                "produto_id": _ids(rng, n, "produto"),
                "linha": "Linha " + lines[(f_idx + rng.integers(0, 2, n)) % 8],
                "fornecedor_id": forn.fornecedor_id.values[f_idx],
                "preco_unitario": np.round(
                    p["preco_mediana"] * np.exp(rng.normal(0, p["preco_sd_log"], n)), 2
                ).clip(0.2),
            }
        )
        prod["popularidade_true"] = np.exp(rng.normal(0, p["popularidade_sd_log"], n))
        self.forn, self.prod = forn, prod

    # ------------------------------------------------------------------ campanhas
    def campaigns(self) -> None:
        _cfg, rng, k = self.cfg, self.rng, self.cfg["campanhas"]
        rows, links = [], []
        pop = self.prod.popularidade_true.values
        for m in self.months:
            for _ in range(rng.integers(k["por_mes"][0], k["por_mes"][1] + 1)):
                f = rng.choice(self.forn.fornecedor_id.values)
                cand = np.flatnonzero(self.prod.fornecedor_id.values == f)
                size = int(
                    np.clip(
                        k["skus_mediana"] * np.exp(rng.normal(0, 0.6)) * max(self.scale, 0.2), 3, len(cand)
                    )
                )
                w = pop[cand] ** (-k["selecao_giro"])  # prefere giro lento
                skus = rng.choice(cand, size=size, replace=False, p=w / w.sum())
                rows.append(
                    {
                        "periodo": m,
                        "fornecedor_id": f,
                        "tipo": rng.choice(list(k["tipos_p"]), p=list(k["tipos_p"].values())),
                        "uplift_true": float(k["uplift_mediana"] * np.exp(rng.normal(0, k["uplift_sd_log"]))),
                    }
                )
                links.append(skus)
        camp = pd.DataFrame(rows)
        camp["campanha_id"] = _ids(rng, len(camp), "campanha")
        forn_name = self.forn.set_index("fornecedor_id").fornecedor
        camp["descricao"] = [
            f"Campanha {forn_name[f]} {p.strftime('%m/%Y')}"
            for f, p in zip(camp.fornecedor_id, camp.periodo, strict=True)
        ]
        self.camp = camp
        self.camp_skus = links  # índices de produto por campanha

    # ------------------------------------------------------------------ vendas
    def sales(self) -> None:
        cfg, rng = self.cfg, self.rng
        p, cal, k = cfg["pedido"], cfg["calendario"], cfg["campanhas"]
        days = pd.date_range(self.start, self.end, freq="D")
        dfac = day_factor_matrix(days, self.mun, cal)  # dias x municípios
        cli, rep = self.cli, self.rep.set_index("representante_id")
        skill = rep.habilidade_true.reindex(cli.representante_id).values
        uf_cli = self.mun.uf.values[cli.mun_idx]
        base_pop = self.prod.popularidade_true.values
        price = self.prod.preco_unitario.values
        prod_ids = self.prod.produto_id.values
        n_prod = len(prod_ids)
        shock = cfg["shock"]
        truth_camp, out = [], []
        month_of_day = days.to_period("M")
        jit_lo, jit_hi = p["jitter"]

        for _mi, m in enumerate(self.months):
            dmask = month_of_day == m
            dm = dfac[dmask][:, cli.mun_idx.values]  # dias do mês x clientes
            du = (
                dm.sum(axis=0) / 22.0
            )  # dias úteis efetivos do município (feriados municipais reduzem a venda)
            years = (m.start_time - self.start).days / 365.25
            lam = (
                cli.taxa_true.values
                * skill
                * cal["sazonalidade_mes"][m.month - 1]
                * (1 + cal["tendencia_ano"]) ** years
                * du
            )
            if self.scenario == "shock" and m.start_time >= pd.Timestamp(shock["start"]):
                lam = np.where(uf_cli == shock["uf"], lam * shock["mult"], lam)
            n_ord = rng.poisson(lam)
            oc = np.repeat(np.arange(len(cli)), n_ord)  # índice do cliente de cada pedido
            if len(oc) == 0:
                continue
            # dia do pedido ~ fator diário do município do cliente
            cum = np.cumsum(dm[:, oc], axis=0)
            u = rng.random(len(oc)) * cum[-1]
            day_idx = (cum < u).sum(axis=0)
            order_day = days[dmask][np.minimum(day_idx, dmask.sum() - 1)]
            # escolha de SKU: popularidade x campanha (uplift) x antecipação do mês anterior (dip)
            mult = np.ones(n_prod)
            active = self.camp.index[self.camp.periodo == m]
            prev = self.camp.index[self.camp.periodo == m - 1]
            for ci in prev:
                mult[self.camp_skus[ci]] *= 1 - k["dip_frac"] * self.camp.at[ci, "uplift_true"]
            base_w = base_pop * mult  # contrafactual sem as campanhas ativas
            for ci in active:
                mult[self.camp_skus[ci]] *= 1 + self.camp.at[ci, "uplift_true"]
            w = base_pop * mult
            pm = w / w.sum()
            for ci in active:  # verdade: efeito multiplicativo esperado na quantidade dos SKUs da campanha
                s = self.camp_skus[ci]
                p_cf = base_w[s] / (w.sum() - (w[s] - base_w[s]).sum())
                truth_camp.append(
                    {"campanha_idx": ci, "att_ratio_true": float((pm[s] * 1).sum() / p_cf.sum() - 1)}
                )
            size = cli["size"].values[oc]
            n_lines = 1 + rng.poisson(np.maximum(p["linhas_media"] * size**0.3 - 1, 0.1))
            lo = np.repeat(np.arange(len(oc)), n_lines)
            sku = np.searchsorted(np.cumsum(pm), rng.random(len(lo)) * 1.0, side="right").clip(0, n_prod - 1)
            mean_q = p["qtd_media"] * size[lo] ** 0.5
            qty = 1 + rng.negative_binomial(2, 2 / (2 + np.maximum(mean_q - 1, 0.05)))
            jit = rng.uniform(jit_lo, jit_hi, len(lo)) * rng.choice([-1, 1], len(lo))
            val = np.round(qty * price[sku] * (1 + jit), 2)
            ord_ids = (
                _ids(rng, len(oc), "pedido") if len(oc) < 8e5 else rng.integers(10**11, 10**12 - 1, len(oc))
            )
            o_cli = oc[lo]
            tele_ok = cli.interno_id.notna().values[o_cli]
            is_tele_order = rng.random(len(oc)) < cfg["clientes"]["p_pedido_televenda"]
            mdf = pd.DataFrame(
                {
                    "pedido_id": ord_ids[lo],
                    "data_venda": order_day[lo],
                    "cliente_id": cli.cliente_id.values[o_cli],
                    "representante_id": cli.representante_id.values[o_cli],
                    "interno_id": np.where(tele_ok & is_tele_order[lo], cli.interno_id.values[o_cli], pd.NA),
                    "produto_id": prod_ids[sku],
                    "quantidade": qty,
                    "valor_liquido": val,
                }
            )
            # devoluções: linhas negativas alguns dias depois (sorteadas mês a mês: o passado não muda
            # quando o futuro muda, ex.: cenário de choque)
            dev = mdf[rng.random(len(mdf)) < p["share_devolucao"]].copy()
            dev["data_venda"] = (dev.data_venda + pd.to_timedelta(rng.integers(3, 20, len(dev)), "D")).clip(
                upper=self.end
            )
            dev["quantidade"] *= -1
            dev["valor_liquido"] *= -1
            out += [mdf, dev]
        self.vend = pd.concat(out, ignore_index=True).sort_values("data_venda", kind="stable")
        self.vend["interno_id"] = self.vend.interno_id.astype("Int64")
        tc = pd.DataFrame(truth_camp)
        self.camp["att_ratio_true"] = (
            tc.groupby("campanha_idx").att_ratio_true.mean().reindex(self.camp.index).values
        )
        self.camp["dip_true"] = -k["dip_frac"] * self.camp.uplift_true

    # ------------------------------------------------------------------ metas legadas
    def legacy_quotas(self) -> None:
        g = self.cfg["metas_legado"]["crescimento"]
        v = self.vend.merge(self.cli[["cliente_id", "cod_ibge"]], on="cliente_id")
        v["periodo"] = v.data_venda.dt.to_period("M")
        s = (
            v.groupby(["representante_id", "cod_ibge", "periodo"])
            .valor_liquido.sum()
            .unstack("periodo")
            .fillna(0)
        )
        rows = []
        for i, m in enumerate(self.months):
            if i < 3:
                continue
            avg3 = s[self.months[i - 3 : i]].mean(axis=1)
            ly = s[m - 12] if (m - 12) in s.columns else pd.Series(0.0, index=s.index)
            meta = (1 + g) * np.maximum(avg3, ly)
            meta = meta[meta > 0].round(-1)
            rows.append(meta.rename("meta_valor").reset_index().assign(periodo=m))
        self.metas = pd.concat(rows, ignore_index=True)

    def campaign_quotas(self) -> None:
        k = self.cfg["campanhas"]
        v = self.vend[self.vend.valor_liquido > 0].copy()
        v["periodo"] = v.data_venda.dt.to_period("M")
        prod_idx = pd.Series(np.arange(len(self.prod)), index=self.prod.produto_id)
        v["pidx"] = prod_idx.reindex(v.produto_id).values
        rows = []
        for ci, c in self.camp.iterrows():
            hist = v[(v.periodo >= c.periodo - 3) & (v.periodo < c.periodo) & v.pidx.isin(self.camp_skus[ci])]
            if hist.empty:
                continue
            if c.tipo == "F":
                base = hist.groupby("representante_id").valor_liquido.sum() / 3
            elif c.tipo == "Q":
                base = hist.groupby("representante_id").quantidade.sum() / 3
            else:
                base = hist.groupby("representante_id").cliente_id.nunique() / 3
            meta = np.ceil(base * (1 + k["meta_crescimento"]))
            rows.append(
                pd.DataFrame(
                    {
                        "campanha_id": c.campanha_id,
                        "representante_id": meta.index,
                        "meta_rep": meta.values,
                        "meta_interno": np.round(meta.values * k["meta_interno_frac"], 1),
                    }
                )
            )
        self.metas_camp = pd.concat(rows, ignore_index=True)

    # ------------------------------------------------------------------ saída
    def run(self) -> dict[str, pd.DataFrame]:
        self.geography()
        self.team()
        self.customers()
        self.products()
        self.campaigns()
        self.sales()
        self.legacy_quotas()
        self.campaign_quotas()
        return self.tables()

    def tables(self) -> dict[str, pd.DataFrame]:
        fil_id = self.filiais.filial_id.values
        coord_of_sup = self.sup.set_index("supervisor_id").coordenador_id
        camp_prod = pd.DataFrame(
            [
                (self.camp.at[ci, "campanha_id"], self.prod.produto_id.values[s])
                for ci, skus in enumerate(self.camp_skus)
                for s in skus
            ],
            columns=["campanha_id", "produto_id"],
        )
        return {
            "filiais": self.filiais,
            "coordenadores": self.coord,
            "supervisores": self.sup.assign(filial_id=fil_id[self.sup.filial_idx])[
                ["supervisor_id", "nome", "coordenador_id", "filial_id"]
            ],
            "representantes": self.rep.assign(
                filial_id=fil_id[self.rep.filial_idx],
                coordenador_id=coord_of_sup.reindex(self.rep.supervisor_id).values,
            )[["representante_id", "nome", "supervisor_id", "coordenador_id", "filial_id", "data_admissao"]],
            "vendedores_internos": self.interno.assign(filial_id=fil_id[self.interno.filial_idx])[
                ["interno_id", "nome", "filial_id"]
            ],
            "clientes": self.cli[
                [
                    "cliente_id",
                    "razao_social",
                    "cod_ibge",
                    "porte",
                    "segmento",
                    "representante_id",
                    "interno_id",
                    "data_cadastro",
                ]
            ],
            "fornecedores": self.forn,
            "produtos": self.prod[["produto_id", "linha", "fornecedor_id", "preco_unitario"]],
            "campanhas": self.camp.assign(periodo=self.camp.periodo.astype(str))[
                ["campanha_id", "descricao", "fornecedor_id", "tipo", "periodo"]
            ],
            "campanhas_produtos": camp_prod,
            "metas_mensais": self.metas.assign(periodo=self.metas.periodo.astype(str)),
            "metas_campanha": self.metas_camp,
            "vendas_itens": self.vend,
        }

    def truth(self) -> dict[str, pd.DataFrame]:
        return {
            "representantes_true": self.rep[["representante_id", "habilidade_true"]],
            "municipios_true": self.mun[["cod_ibge", "potencial_true", "atendido", "dist_filial_km"]],
            "clientes_true": self.cli[["cliente_id", "taxa_true", "size"]],
            "campanhas_true": self.camp[["campanha_id", "uplift_true", "att_ratio_true", "dip_true"]],
        }


def truncate_at(tables: dict[str, pd.DataFrame], snapshot: str | None) -> dict[str, pd.DataFrame]:
    """O mundo simulado é gerado inteiro (determinístico); a EXTRAÇÃO só enxerga até "hoje".

    Assim, ciclos com datas de referência diferentes veem exatamente o mesmo passado, como num ERP real.
    """
    if not snapshot:
        return tables
    snap = pd.Timestamp(snapshot)
    per = snap.strftime("%Y-%m")
    t = dict(tables)
    t["vendas_itens"] = t["vendas_itens"][t["vendas_itens"].data_venda <= snap]
    t["metas_mensais"] = t["metas_mensais"][t["metas_mensais"].periodo <= per]
    t["campanhas"] = t["campanhas"][t["campanhas"].periodo <= per]
    ok = set(t["campanhas"].campanha_id)
    t["campanhas_produtos"] = t["campanhas_produtos"][t["campanhas_produtos"].campanha_id.isin(ok)]
    t["metas_campanha"] = t["metas_campanha"][t["metas_campanha"].campanha_id.isin(ok)]
    return t


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", default=os.getenv("SCENARIO", "base"), choices=["base", "shock"])
    ap.add_argument("--scale", type=float, default=float(os.getenv("GEN_SCALE", "1.0")))
    a = ap.parse_args()
    cfg = yaml.safe_load(settings.generator_config.read_text(encoding="utf-8"))
    g = Generator(cfg, a.scenario, a.scale)
    tables = truncate_at(g.run(), os.getenv("SNAPSHOT_DATE"))
    land, truth = settings.landing_dir, settings.truth_dir
    land.mkdir(parents=True, exist_ok=True)
    truth.mkdir(parents=True, exist_ok=True)
    for name, df in tables.items():
        df.to_parquet(land / f"{name}.parquet", index=False)
    for name, df in g.truth().items():
        df.to_parquet(truth / f"{name}.parquet", index=False)
    print(json.dumps({k: len(v) for k, v in tables.items()}, indent=1))


if __name__ == "__main__":
    main()
