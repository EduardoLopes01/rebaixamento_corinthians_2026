"""Diagnóstico das conexões e dos dados: testa cada fonte e gera data/processed/diagnostico.json.

Rodar da raiz do projeto:  python -m src.diagnostico
Depois abra a página de validação (ver README). Tudo fica em cache: rodar de novo não gasta cota.
"""

import json
import sys
from collections import Counter
from datetime import datetime

import pandas as pd

from src.config import DATA_PROCESSED, FUSO, RAIZ, RODADA_CONGELAMENTO, TEMPORADA
from src.ingest import api_football, football_data, historico

JOGOS_ESPERADOS = {2003: 552, 2004: 552, 2005: 462}  # de 2006 em diante: 20 times, 380 jogos
CAMPOS_TABELA = ("pts", "v", "e", "d", "gp", "gc")


def _tentar(func) -> dict:
    """Roda o teste de uma fonte sem deixar a falha de uma derrubar as outras."""
    try:
        return {"status": "ok", **func()}
    except Exception as e:  # noqa: BLE001
        status = "sem_chave" if "chave ausente" in str(e) else "erro"
        return {"status": status, "mensagem": f"{type(e).__name__}: {e}"}


# ---------- football-data.org ----------

def _jogo(p: dict) -> dict:
    return {
        "rodada": p["matchday"],
        "data_utc": p["utcDate"],
        "status": p["status"],
        "mandante": p["homeTeam"]["shortName"],
        "visitante": p["awayTeam"]["shortName"],
        "placar": [p["score"]["fullTime"]["home"], p["score"]["fullTime"]["away"]],
    }


def _reconstruir_tabela(partidas: list[dict]) -> dict:
    tabela = {}
    for p in partidas:
        if p["status"] != "FINISHED":
            continue
        gm, gv = p["score"]["fullTime"]["home"], p["score"]["fullTime"]["away"]
        for time, gp, gc in ((p["homeTeam"]["shortName"], gm, gv), (p["awayTeam"]["shortName"], gv, gm)):
            r = tabela.setdefault(time, dict.fromkeys(CAMPOS_TABELA, 0))
            r["gp"] += gp
            r["gc"] += gc
            if gp > gc:
                r["v"] += 1
                r["pts"] += 3
            elif gp == gc:
                r["e"] += 1
                r["pts"] += 1
            else:
                r["d"] += 1
    return tabela


def diagnostico_football_data() -> dict:
    temporada = football_data.competicao()["currentSeason"]
    partidas = football_data.partidas()
    classificacao = [
        {
            "pos": linha["position"],
            "time": linha["team"]["shortName"],
            "j": linha["playedGames"],
            "pts": linha["points"],
            "v": linha["won"],
            "e": linha["draw"],
            "d": linha["lost"],
            "gp": linha["goalsFor"],
            "gc": linha["goalsAgainst"],
            "sg": linha["goalDifference"],
        }
        for linha in football_data.classificacao()
    ]

    reconstruida = _reconstruir_tabela(partidas)
    diferencas = [
        {"time": linha["time"], "oficial": {k: linha[k] for k in CAMPOS_TABELA}, "reconstruida": reconstruida.get(linha["time"])}
        for linha in classificacao
        if reconstruida.get(linha["time"]) != {k: linha[k] for k in CAMPOS_TABELA}
    ]

    restantes = [p for p in partidas if p["status"] != "FINISHED"]
    corinthians = next(linha for linha in classificacao if "Corinthians" in linha["time"])
    return {
        "temporada": {
            "inicio": temporada["startDate"],
            "fim": temporada["endDate"],
            "rodada_atual": temporada["currentMatchday"],
        },
        "partidas": {
            "total": len(partidas),
            "por_status": dict(Counter(p["status"] for p in partidas)),
            "restantes": len(restantes),
            "ultima_rodada_jogada": max((p["matchday"] for p in partidas if p["status"] == "FINISHED"), default=None),
        },
        "checagem_1_previa": {"confere": not diferencas, "diferencas": diferencas},
        "classificacao": classificacao,
        "atrasados": [_jogo(p) for p in restantes if p["matchday"] <= RODADA_CONGELAMENTO],
        "proxima_rodada": [_jogo(p) for p in restantes if p["matchday"] == RODADA_CONGELAMENTO + 1],
        "corinthians": {
            "linha": corinthians,
            "restantes": [
                _jogo(p) for p in restantes
                if corinthians["time"] in (p["homeTeam"]["shortName"], p["awayTeam"]["shortName"])
            ],
        },
    }


# ---------- API-Football ----------

def _testar_temporada(ano: int) -> dict:
    partidas = api_football.partidas(ano)
    encerradas = [p for p in partidas if p["fixture"]["status"]["short"] in ("FT", "AET", "PEN")]
    resultado = {"partidas": len(partidas), "encerradas": len(encerradas)}
    if not encerradas:
        return resultado

    ultima = max(encerradas, key=lambda p: p["fixture"]["timestamp"])
    stats = api_football.estatisticas_da_partida(ultima["fixture"]["id"])
    tipos = {s["type"]: s["value"] for s in stats[0]["statistics"]} if stats else {}
    resultado.update(
        {
            "jogo_testado": f'{ultima["teams"]["home"]["name"]} x {ultima["teams"]["away"]["name"]} '
            f'({ultima["fixture"]["date"][:10]})',
            "estatisticas": tipos,
            "tem_xg": tipos.get("expected_goals") not in (None, ""),
            "tem_no_alvo": tipos.get("Shots on Goal") is not None,
            "tem_dentro_da_area": tipos.get("Shots insidebox") is not None,
        }
    )
    return resultado


def diagnostico_api_football() -> dict:
    api_football.status()  # falha logo se a chave for inválida
    temporadas = [
        {
            "ano": s["year"],
            "atual": s["current"],
            "estatisticas_por_jogo": s["coverage"]["fixtures"]["statistics_fixtures"],
            "escalacoes": s["coverage"]["fixtures"]["lineups"],
        }
        for s in api_football.temporadas_da_liga()
    ]
    testes = {str(ano): _tentar(lambda ano=ano: _testar_temporada(ano)) for ano in (TEMPORADA, TEMPORADA - 1, TEMPORADA - 2)}
    return {"conta": api_football.status(), "temporadas": temporadas, "testes": testes}


# ---------- Dataset histórico ----------

def diagnostico_historico() -> dict:
    partidas = historico.carregar("partidas")
    stats = historico.carregar("estatisticas")
    # a base usa 0 no lugar de "sem dado": jogo sem nenhuma finalização registrada = sem dado
    com_finalizacoes = set(stats.loc[stats["chutes"].fillna(0) > 0, "partida_id"])
    com_no_alvo = set(stats.loc[stats["chutes_no_alvo"].fillna(0) > 0, "partida_id"])

    por_temporada = [
        {
            "temporada": int(ano),
            "jogos": len(grupo),
            "esperado": JOGOS_ESPERADOS.get(int(ano), 380),
            "pct_com_finalizacoes": round(100 * float(grupo["ID"].isin(com_finalizacoes).mean()), 1),
            "pct_com_no_alvo": round(100 * float(grupo["ID"].isin(com_no_alvo).mean()), 1),
        }
        for ano, grupo in partidas.groupby("temporada")
    ]
    return {
        "periodo": f'{partidas["data"].min():%d/%m/%Y} a {partidas["data"].max():%d/%m/%Y}',
        "linhas": {nome: len(historico.carregar(nome)) for nome in historico.ARQUIVOS},
        "colunas": {
            "partidas": [c for c in partidas.columns if c != "temporada"],
            "estatisticas": list(stats.columns),
        },
        "times_distintos": int(pd.concat([partidas["mandante"], partidas["visitante"]]).nunique()),
        "por_temporada": por_temporada,
        "temporadas_com_buraco": [t["temporada"] for t in por_temporada if t["jogos"] != t["esperado"]],
    }


# ---------- Mapa de cobertura: que dado temos em cada temporada, e de qual fonte ----------

NOMES_FONTE = {"historico": "Dataset histórico", "football_data_uk": "football-data.co.uk",
               "football_data_org": "football-data.org", "api_football": "API-Football"}


def _celula(fonte: str | None, jogos: int, total: int) -> dict:
    return {"fonte": NOMES_FONTE.get(fonte), "jogos": int(jogos), "total": int(total),
            "pct": round(100 * jogos / total, 1) if total else 0.0}


def cobertura() -> dict:
    """Para cada temporada: % de jogos com resultado, finalizações, no alvo, dentro da área e xG.
    Quando mais de uma fonte tem o dado, fica a de maior cobertura. Só lê o que já está em cache."""
    partidas = pd.read_parquet(DATA_PROCESSED / "partidas.parquet")
    encerrados = partidas[partidas["encerrado"]]

    hist = historico.carregar("partidas")
    stats = historico.carregar("estatisticas").merge(hist[["ID", "temporada"]], left_on="partida_id", right_on="ID")
    por_jogo = stats.groupby(["temporada", "partida_id"])[["chutes", "chutes_no_alvo"]].max()

    api = {}
    for ano in range(2010, TEMPORADA + 1):
        if (api_football.PASTA / f"partidas_{ano}.json").exists():
            api[ano] = api_football.tabela_estatisticas(ano)

    anos = []
    for ano in sorted(encerrados["temporada"].unique()):
        ano = int(ano)
        jogos_ano = encerrados[encerrados["temporada"] == ano]
        total = len(jogos_ano)
        linha = {"temporada": ano, "resultados": _celula(jogos_ano["fonte"].mode()[0], total, total)}
        for chave, col_hist, col_api in (("finalizacoes", "chutes", "finalizacoes_mandante"),
                                         ("no_alvo", "chutes_no_alvo", "no_alvo_mandante"),
                                         ("dentro_area", None, "dentro_area_mandante"),
                                         ("xg", None, "xg_mandante")):
            opcoes = [_celula(None, 0, total)]
            if col_hist and ano in por_jogo.index.get_level_values(0):
                opcoes.append(_celula("historico", int((por_jogo.loc[ano, col_hist].fillna(0) > 0).sum()), total))
            if ano in api and not api[ano].empty:
                opcoes.append(_celula("api_football", int(api[ano][col_api].notna().sum()), total))
            linha[chave] = max(opcoes, key=lambda c: c["jogos"])
        anos.append(linha)
    return {
        "linhas": {"resultados": "Resultados", "finalizacoes": "Finalizações", "no_alvo": "No alvo",
                   "dentro_area": "Na área", "xg": "xG"},
        "anos": anos,
    }


def _resumo_conferencia() -> dict:
    """Quantos jogos foram conferidos entre duas fontes e quantas diferenças apareceram."""
    c = json.loads((DATA_PROCESSED / "conferencia_fontes.json").read_text(encoding="utf-8"))
    jogos = sum(t["em_comum"] for comp in c.values() for t in comp["por_temporada"])
    diferencas = sum(v for comp in c.values() for t in comp["por_temporada"] for k, v in t.items()
                     if k not in ("temporada", "em_comum"))
    return {"jogos_conferidos": jogos, "diferencas": diferencas, "confere": all(comp["confere"] for comp in c.values())}


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    resultado = {
        "gerado_em": datetime.now(FUSO).isoformat(timespec="seconds"),
        "rodada_congelamento": RODADA_CONGELAMENTO,
        "fontes": {
            "football_data": _tentar(diagnostico_football_data),
            "api_football": _tentar(diagnostico_api_football),
            "historico": _tentar(diagnostico_historico),
        },
        "cobertura": _tentar(cobertura),
        "conferencia": _tentar(_resumo_conferencia),
    }
    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    saida = DATA_PROCESSED / "diagnostico.json"
    saida.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")

    icones = {"ok": "✅", "sem_chave": "⏳", "erro": "❌"}
    for nome, r in resultado["fontes"].items():
        print(f"{icones[r['status']]} {nome}: {r.get('mensagem', 'ok')}")
    print(f"\nDetalhes em {saida.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
