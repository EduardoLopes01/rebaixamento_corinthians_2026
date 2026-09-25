"""Previsão da pausa: cada jogo restante, 10 mil temporadas simuladas e as checagens 1 a 4.

Usa o Modelo 1 (Dixon-Coles) e, se o Portão 2 passou, combina com o Modelo 2 (XGBoost) no peso do backtest.

Rodar da raiz do projeto, nesta ordem:
    python -m src.ingest.consolidar
    python -m src.models.dixon_coles      (escolhe o decaimento do Modelo 1)
    python -m src.features.variaveis
    python -m src.models.ensemble         (Portão 2: versão do Modelo 2 e peso da combinação)
    python -m src.simulate.previsao

Saída: data/processed/previsao.json (lida pela página de validação).
"""

import json
import sys
from datetime import datetime

import numpy as np
import pandas as pd

from src.checks import checagem1
from src.checks.publicacao import checagem2, checagem3, checagem4
from src.config import DATA_PROCESSED, FUSO, RAIZ, RODADA_CONGELAMENTO, TEMPORADA
from src.features.tabela import classificacao
from src.models.dixon_coles import ModeloDixonColes, Previsao
from src.models.ensemble import ajustar_grade
from src.models.xgb_model import ModeloXGB
from src.simulate.temporada import (
    N_SIMULACOES,
    chance_de_queda,
    distribuicao_posicoes,
    pontos_para_ficar_abaixo,
    simular,
)

TIME = "Corinthians"


GOLS_NA_GRADE_PUBLICADA = 7  # placares de 0 a 6 gols por time: cobrem mais de 99,9% da probabilidade


def _jogo(j, previsao) -> dict:
    grade = previsao.grade[:GOLS_NA_GRADE_PUBLICADA, :GOLS_NA_GRADE_PUBLICADA]
    return {
        "rodada": int(j.rodada),
        "data": None if pd.isna(j.data) else j.data.isoformat(),
        **previsao.resumo(),
        "grade": np.round(grade / grade.sum(), 5).tolist(),  # para o simulador do site
    }


def rodar() -> dict:
    partidas = pd.read_parquet(DATA_PROCESSED / "partidas.parquet")
    temporada = partidas[partidas["temporada"] == TEMPORADA]
    encerrados = temporada[temporada["encerrado"]]
    restantes = temporada[~temporada["encerrado"]].sort_values(["data", "mandante"], na_position="last")
    if encerrados["rodada"].max() != RODADA_CONGELAMENTO:
        raise RuntimeError("há jogo depois da 28ª rodada nos dados: a previsão precisa dos dados congelados")

    data_dados = encerrados["data"].max()
    data_corte = data_dados.normalize() + pd.Timedelta(days=1)
    backtest = json.loads((DATA_PROCESSED / "backtest_modelo1.json").read_text(encoding="utf-8"))
    modelo = ModeloDixonColes(backtest["xi_escolhido"]).ajustar(partidas, data_corte)

    previsoes = [modelo.prever(j.mandante, j.visitante) for j in restantes.itertuples()]

    portao2 = json.loads((DATA_PROCESSED / "backtest_modelo2.json").read_text(encoding="utf-8"))["portao2"]
    nome_modelo = "Modelo 1 (Dixon-Coles)"
    if portao2["passa"]:
        w = portao2["peso_modelo1"]
        variaveis = pd.read_parquet(DATA_PROCESSED / "variaveis.parquet")
        m2 = ModeloXGB(portao2["versao_modelo2"]).ajustar(variaveis, data_corte)
        linhas = restantes[["mandante", "visitante"]].merge(
            variaveis[(variaveis["temporada"] == TEMPORADA) & ~variaveis["encerrado"]],
            on=["mandante", "visitante"], how="left", validate="one_to_one")
        p2 = m2.prever(linhas)
        previsoes = [
            Previsao(p.mandante, p.visitante,
                     ajustar_grade(p.grade, w * np.array([p.p_mandante, p.p_empate, p.p_visitante]) + (1 - w) * q))
            for p, q in zip(previsoes, p2, strict=True)
        ]
        nome_modelo = (f"Combinação: {round(100 * w)}% Modelo 1 (Dixon-Coles) + "
                       f"{round(100 * (1 - w))}% Modelo 2 (XGBoost, versão {portao2['versao_modelo2']})")
    jogos = [_jogo(j, p) for j, p in zip(restantes.itertuples(), previsoes, strict=True)]

    sim = simular(encerrados, restantes, [p.grade for p in previsoes])
    chances = chance_de_queda(sim)
    tabela = classificacao(encerrados)
    i = sim["times"].index(TIME)
    pontos_finais = sim["pontos"]

    times = [
        {
            "time": t,
            "pos_atual": int(tabela.at[t, "pos"]),
            "pts_atual": int(tabela.at[t, "pts"]),
            "jogos_restantes": int(((restantes["mandante"] == t) | (restantes["visitante"] == t)).sum()),
            "chance_queda": round(chances[t], 4),
            "pontos_finais_media": round(float(pontos_finais[:, k].mean()), 1),
            "posicao_media": round(float(sim["posicao"][:, k].mean()), 1),
        }
        for k, t in enumerate(sim["times"])
    ]
    times.sort(key=lambda x: x["pos_atual"])

    do_time = [j for j in jogos if TIME in (j["mandante"], j["visitante"])]
    necessario = pontos_para_ficar_abaixo(sim, TIME)
    pts_atual = int(tabela.at[TIME, "pts"])

    checagens = {
        "1_tabela_igual_oficial": checagem1.rodar(),
        "2_soma_quedas_igual_4": checagem2(chances),
        "3_soma_jogo_igual_100": checagem3(jogos),
        "4_diferenca_ufmg": checagem4(chances[TIME]),
    }
    return {
        "gerado_em": datetime.now(FUSO).isoformat(timespec="seconds"),
        "modelo": {"nome": nome_modelo, "xi": modelo.xi, **modelo.parametros,
                   "backtest": {k: backtest[k] for k in ("temporadas", "jogos_avaliados", "metricas")},
                   "portao2": portao2},
        "dados": {"ate": data_dados.date().isoformat(), "rodada": RODADA_CONGELAMENTO,
                  "jogos_2026": len(encerrados), "jogos_restantes": len(restantes),
                  "jogos_no_treino": int(((partidas["data"] < data_corte) & partidas["encerrado"]).sum())},
        "simulacoes": N_SIMULACOES,
        "resposta": {
            "time": TIME,
            "chance_queda": round(chances[TIME], 4),
            "pos_atual": int(tabela.at[TIME, "pos"]),
            "pts_atual": pts_atual,
            "distribuicao_posicao": [round(x, 4) for x in distribuicao_posicoes(sim, TIME)],
            "pontos_finais": {
                "media": round(float(pontos_finais[:, i].mean()), 1),
                "p10": int(np.percentile(pontos_finais[:, i], 10)),
                "p90": int(np.percentile(pontos_finais[:, i], 90)),
            },
            "pontos_para_menos_de_5pct": {
                **necessario,
                "faltam": None if necessario["pontos_finais"] is None else necessario["pontos_finais"] - pts_atual,
            },
            "proximo_jogo": do_time[0],
            "jogos_restantes": do_time,
        },
        "times": times,
        "jogos": jogos,
        "checagens": checagens,
        "trocas_confronto_direto": sim["trocas_confronto_direto"],
    }


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    r = rodar()
    saida = DATA_PROCESSED / "previsao.json"
    saida.write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")

    resp = r["resposta"]
    print(r["modelo"]["nome"])
    print(f"Chance de queda do {resp['time']}: {100 * resp['chance_queda']:.1f}%  (UFMG: 21,4%)")
    n = resp["pontos_para_menos_de_5pct"]
    print(f"Pontos finais para ficar abaixo de 5%: {n['pontos_finais']} (faltam {n['faltam']} em "
          f"{len(resp['jogos_restantes'])} jogos)")
    pj = resp["proximo_jogo"]
    print(f"Próximo jogo: {pj['mandante']} x {pj['visitante']}: {100 * pj['p_mandante']:.0f}% / "
          f"{100 * pj['p_empate']:.0f}% / {100 * pj['p_visitante']:.0f}%, placar mais provável "
          f"{pj['placar_mais_provavel'][0]}x{pj['placar_mais_provavel'][1]}")
    print("\nChance de queda (maiores):")
    for t in sorted(r["times"], key=lambda x: -x["chance_queda"])[:8]:
        print(f"  {t['time']:<14} {t['pos_atual']:>2}º {t['pts_atual']:>3} pts → {100 * t['chance_queda']:5.1f}%")
    print("\nChecagens:")
    for nome, c in r["checagens"].items():
        print(f"  {'✅' if c['aprovada'] else '❌'} {nome}")
    print(f"\nDetalhes em {saida.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
