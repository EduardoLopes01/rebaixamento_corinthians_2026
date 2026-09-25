"""Análise de sensibilidade: quanto a chance de queda muda com outras escolhas razoáveis de modelo.

Rodar da raiz (depois de src.simulate.previsao):  python -m src.simulate.previsao && python -m src.simulate.sensibilidade

Cada variante troca uma escolha e simula 100 mil temporadas. Não é para escolher a "melhor": a previsão
publicada continua a do backtest. Serve para mostrar a faixa de incerteza que vem das escolhas do modelo.
"""

import json
import sys

import pandas as pd

from src.config import DATA_PROCESSED, TEMPORADA
from src.features.variaveis import estatisticas_por_jogo
from src.models.dixon_coles import ModeloDixonColes
from src.models.poisson_xg import ModeloPoissonXG
from src.simulate.temporada import chance_de_queda, simular

TIME = "Corinthians"


def rodar() -> dict:
    partidas = pd.read_parquet(DATA_PROCESSED / "partidas.parquet")
    temporada = partidas[partidas["temporada"] == TEMPORADA]
    encerrados = temporada[temporada["encerrado"]]
    restantes = temporada[~temporada["encerrado"]].sort_values(["data", "mandante"], na_position="last")
    corte = encerrados["data"].max().normalize() + pd.Timedelta(days=1)
    xi = json.loads((DATA_PROCESSED / "backtest_modelo1.json").read_text(encoding="utf-8"))["xi_escolhido"]
    jogos_xg = partidas.merge(estatisticas_por_jogo()[["temporada", "mandante", "visitante", "xg_m", "xg_v"]],
                              on=["temporada", "mandante", "visitante"], how="left")

    def com(modelo) -> float:
        grades = [modelo.prever(j.mandante, j.visitante).grade for j in restantes.itertuples()]
        return chance_de_queda(simular(encerrados, restantes, grades))[TIME]

    dc = ModeloDixonColes(xi).ajustar(partidas, corte)
    principal = json.loads((DATA_PROCESSED / "previsao.json").read_text(encoding="utf-8"))
    variantes = [
        {"nome": "Previsão publicada (combinação dos dois modelos)", "chance": principal["resposta"]["chance_queda"]},
        {"nome": "Só o Modelo 1 (Dixon-Coles)", "chance": com(dc)},
        {"nome": "Mais peso nos jogos recentes (meia-vida de 1 ano)", "chance": com(ModeloDixonColes(2 * xi).ajustar(partidas, corte))},
        {"nome": "Menos peso nos jogos recentes (meia-vida de 4 anos)", "chance": com(ModeloDixonColes(xi / 2).ajustar(partidas, corte))},
        {"nome": "Só os jogos de 2026", "chance": com(ModeloDixonColes(0.0).ajustar(temporada, corte))},
        {"nome": "Força dos times pelo xG, não pelos gols", "chance": com(
            ModeloPoissonXG(xi, alfa=0.0, rho=dc.parametros["rho"]).ajustar(jogos_xg, corte))},
    ]
    for v in variantes:
        v["chance"] = round(float(v["chance"]), 4)
    chances = [v["chance"] for v in variantes]
    return {"time": TIME, "variantes": variantes, "minimo": min(chances), "maximo": max(chances)}


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    r = rodar()
    (DATA_PROCESSED / "sensibilidade.json").write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
    for v in r["variantes"]:
        print(f"  {100 * v['chance']:5.1f}%  {v['nome']}")
    print(f"Faixa: {100 * r['minimo']:.1f}% a {100 * r['maximo']:.1f}%")


if __name__ == "__main__":
    main()
