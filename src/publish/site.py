"""Gera site/data/previsao.json: só agregados e previsões, nada de base bruta.

Rodar da raiz (depois de src.simulate.previsao, src.simulate.sensibilidade e src.diagnostico):
    python -m src.publish.site

O que vai para o site:
- a resposta (chance de queda, posição final, pontos que faltam) e a chance de queda dos 20 times;
- a tabela após a 28ª rodada (pontos, vitórias, gols), que o simulador usa como ponto de partida;
- cada jogo restante com vitória/empate/derrota, placar provável e a grade de placares de 0 a 6 gols;
- o confronto direto já disputado entre cada par de times (pontos e saldo), para o desempate no navegador;
- números para a seção "Os dados": cobertura, conferência, backtest e os pontos do 17º colocado desde 2006.
"""

import json
import sys
from datetime import datetime

import pandas as pd

from src.checks.publicacao import UFMG
from src.config import DATA_PROCESSED, FUSO, RAIZ, SITE_DATA, TEMPORADA
from src.features.tabela import classificacao


def _ler(nome: str) -> dict:
    return json.loads((DATA_PROCESSED / nome).read_text(encoding="utf-8"))


def pontos_do_17o(partidas: pd.DataFrame) -> list[dict]:
    """Pontos do 17º colocado (o primeiro da zona de queda) em cada temporada com 20 times, desde 2006."""
    linhas = []
    for ano in range(2006, TEMPORADA):
        tabela = classificacao(partidas[partidas["temporada"] == ano])
        linhas.append({"temporada": ano, "pontos_17o": int(tabela["pts"].iloc[16]),
                       "pontos_16o": int(tabela["pts"].iloc[15])})
    return linhas


def confrontos(encerrados: pd.DataFrame) -> dict[str, list[int]]:
    """Por par de times (em ordem alfabética, "A|B"): [pontos de A, pontos de B, saldo de A] nos jogos já disputados."""
    c: dict[str, list[int]] = {}
    for j in encerrados.itertuples():
        a, b = sorted((j.mandante, j.visitante))
        ga, gb = (j.gols_mandante, j.gols_visitante) if a == j.mandante else (j.gols_visitante, j.gols_mandante)
        ga, gb = int(ga), int(gb)
        r = c.setdefault(f"{a}|{b}", [0, 0, 0])
        r[0] += 3 if ga > gb else 1 if ga == gb else 0
        r[1] += 3 if gb > ga else 1 if ga == gb else 0
        r[2] += ga - gb
    return c


def montar() -> dict:
    previsao = _ler("previsao.json")
    diag = _ler("diagnostico.json")
    bt1 = _ler("backtest_modelo1.json")
    bt2 = _ler("backtest_modelo2.json")
    sens = _ler("sensibilidade.json")
    partidas = pd.read_parquet(DATA_PROCESSED / "partidas.parquet")
    encerrados = partidas[(partidas["temporada"] == TEMPORADA) & partidas["encerrado"]]
    tabela = classificacao(encerrados)
    queda = {t["time"]: t for t in previsao["times"]}

    times = [
        {"time": t, **{k: int(tabela.at[t, k]) for k in ("pos", "pts", "j", "v", "e", "d", "gp", "gc", "sg")},
         "chance_queda": queda[t]["chance_queda"], "pontos_finais_media": queda[t]["pontos_finais_media"]}
        for t in tabela.index
    ]
    p2 = bt2["portao2"]
    modelos = bt2["modelos"]
    resp = previsao["resposta"]
    return {
        "gerado_em": datetime.now(FUSO).isoformat(timespec="seconds"),
        "validade": {"volta_do_campeonato": "2026-10-07", "fuso": "America/Sao_Paulo"},
        "dados": {
            "ate": previsao["dados"]["ate"], "rodada": previsao["dados"]["rodada"],
            "jogos_na_base": previsao["dados"]["jogos_no_treino"], "jogos_restantes": previsao["dados"]["jogos_restantes"],
            "simulacoes": previsao["simulacoes"],
            "jogos_conferidos": diag["conferencia"]["jogos_conferidos"],
            "diferencas_entre_fontes": diag["conferencia"]["diferencas"],
        },
        "modelo": {
            "nome": previsao["modelo"]["nome"],
            "peso_modelo1": p2["peso_modelo1"],
            "decaimento_meia_vida_anos": round(0.6931 / previsao["modelo"]["xi"] / 365.25, 1),
            "mando_gols": round(float(2.718281828 ** previsao["modelo"]["mando"]), 2),
            "backtest": {
                "modelo1_2022_2025": {"jogos": bt1["jogos_avaliados"], "log_loss": bt1["metricas"][str(bt1["xi_escolhido"])]["log_loss"],
                                      "so_mando": bt1["metricas"]["so_mando"]["log_loss"]},
                "prova_2026": {nome: modelos[nome]["2026"]["log_loss"] for nome in ("so_mando", "situacao_parecida", "modelo1", "xg")}
                | {"combinacao": p2["log_loss_2026_combinacao"]},
                "chance_combinacao_melhor": p2["ganho_2026_bootstrap"]["chance_de_ser_melhor"],
                "calibracao": bt2["calibracao"]["escolhido"],
            },
        },
        "ufmg": UFMG,
        "sensibilidade": {k: sens[k] for k in ("variantes", "minimo", "maximo")},
        "corinthians": {
            "time": resp["time"], "chance_queda": resp["chance_queda"], "pos_atual": resp["pos_atual"],
            "pts_atual": resp["pts_atual"], "distribuicao_posicao": resp["distribuicao_posicao"],
            "pontos_finais": resp["pontos_finais"], "pontos_para_menos_de_5pct": {
                k: resp["pontos_para_menos_de_5pct"][k] for k in ("alvo", "pontos_finais", "faltam")},
        },
        "times": times,
        "jogos": [{k: j[k] for k in ("rodada", "data", "mandante", "visitante", "p_mandante", "p_empate", "p_visitante",
                                     "gols_esperados", "placar_mais_provavel", "equilibrado", "grade")}
                  for j in previsao["jogos"]],
        "confrontos": confrontos(encerrados),
        "historia_17o": pontos_do_17o(partidas),
        "cobertura": diag["cobertura"],
        "checagens": {k: v["aprovada"] for k, v in previsao["checagens"].items()},
    }


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    dados = montar()
    SITE_DATA.mkdir(parents=True, exist_ok=True)
    saida = SITE_DATA / "previsao.json"
    saida.write_text(json.dumps(dados, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{saida.relative_to(RAIZ)}: {saida.stat().st_size / 1024:.0f} KB · "
          f"{len(dados['jogos'])} jogos · checagens: {'✅' if all(dados['checagens'].values()) else '❌'}")


if __name__ == "__main__":
    main()
