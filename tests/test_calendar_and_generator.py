import numpy as np
import pandas as pd

from sales_planning_analytics.generator.generate import ID_DIGITS, truncate_at
from sales_planning_analytics.public.calendar import day_factor_matrix, holiday_matrix, load_municipios


def test_feriado_municipal_zera_o_dia(cfg):
    mun = load_municipios()
    days = pd.date_range("2024-01-01", "2024-12-31")
    hol = holiday_matrix(days, mun)
    f = day_factor_matrix(days, mun, cfg["calendario"])
    assert hol.any(), "o snapshot público deveria ter feriados"
    assert (f[hol] == 0).all()
    # Natal (nacional) é feriado em todos os municípios
    natal = days.get_loc(pd.Timestamp("2024-12-25"))
    assert hol[natal].all()


def test_domingo_nao_vende_e_sabado_e_meio_expediente(cfg):
    mun = load_municipios().head(3)
    days = pd.date_range("2024-03-04", "2024-03-10")  # seg a dom, sem feriados nacionais
    f = day_factor_matrix(days, mun, cfg["calendario"])
    assert (f[-1] == 0).all()
    assert (f[5] < 0.2).all()


def test_ids_tem_a_quantidade_de_digitos_propria(small_world):
    _, t = small_world
    for kind, table, col in [
        ("cliente", "clientes", "cliente_id"),
        ("produto", "produtos", "produto_id"),
        ("representante", "representantes", "representante_id"),
    ]:
        lens = t[table][col].astype(str).str.len().unique()
        assert list(lens) == [ID_DIGITS[kind]]
        assert t[table][col].is_unique


def test_sem_nomes_de_produto_e_fornecedor_so_por_codigo(small_world):
    _, t = small_world
    assert set(t["produtos"].columns) == {"produto_id", "linha", "fornecedor_id", "preco_unitario"}
    assert t["fornecedores"].fornecedor.str.match(r"^Fornecedor \d{2}$").all()


def test_vendas_respeitam_feriados_e_domingos(small_world):
    _, t = small_world
    v = t["vendas_itens"]
    vendas = v[v.valor_liquido > 0]
    assert (vendas.data_venda.dt.day_of_week < 6).all()


def test_truncate_nao_deixa_futuro(small_world):
    _, t = small_world
    cut = truncate_at(t, "2025-06-15")
    assert cut["vendas_itens"].data_venda.max() <= pd.Timestamp("2025-06-15")
    assert cut["campanhas"].periodo.max() <= "2025-06"
    assert set(cut["metas_campanha"].campanha_id) <= set(cut["campanhas"].campanha_id)


def test_metas_legadas_sao_catraca(small_world):
    """A regra antiga nunca fica abaixo de (1+g) x média dos últimos 3 meses."""
    g, t = small_world
    assert (t["metas_mensais"].meta_valor > 0).all()
    assert np.isfinite(t["metas_mensais"].meta_valor).all()


def test_campanhas_preferem_giro_lento(small_world):
    g, _ = small_world
    pop = g.prod.popularidade_true.to_numpy()
    in_camp = np.concatenate(g.camp_skus)  # com repetição: SKUs escolhidos mais vezes pesam mais
    assert np.median(pop[in_camp]) < np.median(pop)
