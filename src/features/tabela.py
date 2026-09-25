"""Classificação a partir dos resultados, com os pontos do regulamento (3 por vitória, 1 por empate)."""

import pandas as pd

COLUNAS = ["pts", "j", "v", "e", "d", "gp", "gc", "sg"]


def classificacao(partidas: pd.DataFrame) -> pd.DataFrame:
    """Tabela dos jogos encerrados, ordenada por pontos, vitórias, saldo e gols pró (Art. 15, 1º a 3º).

    O confronto direto e os cartões (4º a 6º) só entram na simulação do fim do campeonato.
    """
    jogos = partidas[partidas["encerrado"]]
    lados = []
    for time, gp, gc in (
        ("mandante", "gols_mandante", "gols_visitante"),
        ("visitante", "gols_visitante", "gols_mandante"),
    ):
        lado = pd.DataFrame({"time": jogos[time], "gp": jogos[gp].astype(int), "gc": jogos[gc].astype(int)})
        lados.append(lado)
    t = pd.concat(lados)
    t["v"] = (t["gp"] > t["gc"]).astype(int)
    t["e"] = (t["gp"] == t["gc"]).astype(int)
    t["d"] = (t["gp"] < t["gc"]).astype(int)
    t = t.groupby("time").agg(j=("gp", "size"), v=("v", "sum"), e=("e", "sum"), d=("d", "sum"),
                              gp=("gp", "sum"), gc=("gc", "sum"))
    t["pts"] = 3 * t["v"] + t["e"]
    t["sg"] = t["gp"] - t["gc"]
    t = t.sort_values(["pts", "v", "sg", "gp"], ascending=False)
    t.insert(0, "pos", range(1, len(t) + 1))
    return t[["pos", *COLUNAS]]
