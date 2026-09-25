"""Sem vazamento: o Modelo 1 só aprende com jogos anteriores à data de corte."""

import numpy as np
import pandas as pd

from src.models.dixon_coles import ModeloDixonColes


def test_modelo_ignora_jogos_na_data_de_corte_e_depois():
    rng = np.random.default_rng(0)
    times = ["A", "B", "C", "D"]
    linhas = []
    for dia in range(60):
        m, v = rng.choice(times, 2, replace=False)
        linhas.append((pd.Timestamp("2026-01-01") + pd.Timedelta(days=dia), m, v, *rng.integers(0, 4, 2)))
    # jogos no dia do corte e depois, com um time que só aparece aí
    linhas += [(pd.Timestamp("2026-03-02"), "FUTURO", "A", 9, 0), (pd.Timestamp("2026-03-10"), "B", "FUTURO", 0, 9)]
    partidas = pd.DataFrame(linhas, columns=["data", "mandante", "visitante", "gols_mandante", "gols_visitante"])
    partidas["encerrado"] = True

    modelo = ModeloDixonColes(xi=0.001).ajustar(partidas, pd.Timestamp("2026-03-02"))
    assert "FUTURO" not in modelo.times

    # e a previsão não muda se os jogos futuros mudarem de placar
    alterada = partidas.copy()
    alterada.loc[alterada["data"] >= "2026-03-02", ["gols_mandante", "gols_visitante"]] = [0, 5]
    p1 = modelo.prever("A", "B").grade
    p2 = ModeloDixonColes(xi=0.001).ajustar(alterada, pd.Timestamp("2026-03-02")).prever("A", "B").grade
    assert np.allclose(p1, p2)


def test_variaveis_do_modelo2_nao_olham_o_futuro():
    from src.features.variaveis import montar

    rng = np.random.default_rng(1)
    times = ["A", "B", "C", "D", "E", "F"]
    linhas = []
    for dia in range(80):
        m, v = rng.choice(times, 2, replace=False)
        linhas.append((2026, pd.Timestamp("2026-01-01") + pd.Timedelta(days=dia), m, v, *rng.integers(0, 4, 2)))
    partidas = pd.DataFrame(linhas, columns=["temporada", "data", "mandante", "visitante", "gols_mandante", "gols_visitante"])
    partidas = partidas.drop_duplicates(["temporada", "mandante", "visitante"]).reset_index(drop=True)
    partidas["encerrado"] = True
    partidas["rodada"] = 1
    stats = partidas[["temporada", "mandante", "visitante"]].assign(
        xg_m=rng.random(len(partidas)), xg_v=rng.random(len(partidas)), no_alvo_m=3.0, no_alvo_v=2.0, area_m=5.0, area_v=4.0)

    corte = pd.Timestamp("2026-02-15")
    original = montar(partidas, stats)
    alterada = partidas.copy()
    futuro = alterada["data"] >= corte
    alterada.loc[futuro, ["gols_mandante", "gols_visitante"]] = [9, 0]
    stats_alt = stats.copy()
    stats_alt.loc[futuro.to_numpy(), ["xg_m", "xg_v"]] = 99.0
    nova = montar(alterada, stats_alt)

    colunas = [c for c in original.columns if c.endswith(("_m", "_v", "_diff")) and not c.startswith("gols")]
    ate_o_corte = original["data"] <= corte  # o jogo do dia do corte usa só o que veio antes dele
    pd.testing.assert_frame_equal(original.loc[ate_o_corte, colunas], nova.loc[ate_o_corte, colunas])
