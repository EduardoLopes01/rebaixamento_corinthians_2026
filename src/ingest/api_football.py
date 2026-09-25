"""API-Football (api-sports.io): estatísticas por jogo do Brasileirão (liga 71).

Limites por plano (lidos da própria API em /status, que não gasta cota):
- Grátis: 100 chamadas por dia, 10 por minuto, só as temporadas 2022 a 2024.
- Pro: 7.500 chamadas por dia, 300 por minuto, todas as temporadas.
Guardamos um contador diário local e paramos antes de chegar ao limite do dia.

Coleta em lote (retoma de onde parou; o que já está em cache não gasta cota):
    python -m src.ingest.api_football 2024
"""

import json
import sys
from datetime import UTC, datetime

import pandas as pd

from src.config import API_FOOTBALL_KEY, DATA_RAW
from src.ingest.cache import ErroFonte, get_json
from src.ingest.times import padronizar

BASE = "https://v3.football.api-sports.io"
LIGA = 71  # Brasileirão Série A
PASTA = DATA_RAW / "api_football"
CONTADOR = PASTA / "_uso_diario.json"
RESERVA = 5
INTERVALO_S = {"Free": 6.5, "Pro": 0.25}  # 10 e 300 chamadas/min, com folga
_plano: dict = {}
ENCERRADA = ("FT", "AET", "PEN")


def _erro(dados: dict) -> str | None:
    erros = dados.get("errors")  # a API responde HTTP 200 mesmo com erro de chave ou de plano
    if not erros:
        return None
    itens = erros.items() if isinstance(erros, dict) else enumerate(erros)
    return "API-Football: " + "; ".join(f"{k}: {v}" for k, v in itens)


def _registrar_chamada() -> None:
    hoje = datetime.now(UTC).date().isoformat()  # a cota zera à meia-noite UTC
    uso = json.loads(CONTADOR.read_text()) if CONTADOR.exists() else {}
    if uso.get(hoje, 0) >= _limites()["limite_dia"] - RESERVA:
        raise ErroFonte(f"API-Football: cota diária quase no fim ({uso[hoje]} chamadas hoje)")
    uso[hoje] = uso.get(hoje, 0) + 1
    CONTADOR.parent.mkdir(parents=True, exist_ok=True)
    CONTADOR.write_text(json.dumps(uso))


def _get(
    caminho: str,
    nome_cache: str | None,
    params: dict | None = None,
    forcar: bool = False,
    conta_na_cota: bool = True,
) -> dict:
    if not API_FOOTBALL_KEY:
        raise ErroFonte("API-Football: chave ausente no .env (API_FOOTBALL_KEY)")
    cache = PASTA / nome_cache if nome_cache else None
    if conta_na_cota and (forcar or cache is None or not cache.exists()):
        _registrar_chamada()
    return get_json(
        f"{BASE}{caminho}",
        headers={"x-apisports-key": API_FOOTBALL_KEY},
        fonte="api-football",
        cache=cache,
        params=params,
        intervalo_s=_limites()["intervalo_s"] if conta_na_cota else 0.0,  # /status não conta nem espera
        forcar=forcar,
        erro_na_resposta=_erro,
    )


def _limites() -> dict:
    """Plano da conta, consultado uma vez por execução. Plano desconhecido usa o ritmo do grátis."""
    if not _plano:
        s = status()
        _plano.update(limite_dia=s["limite_dia"], intervalo_s=INTERVALO_S.get(s["plano"], INTERVALO_S["Free"]))
    return _plano


def status() -> dict:
    """Plano e uso do dia. Não conta na cota e não vai para o cache (a resposta traz dados da conta)."""
    r = _get("/status", None, conta_na_cota=False)["response"]
    return {
        "plano": r["subscription"]["plan"],
        "ativo": r["subscription"]["active"],
        "chamadas_hoje": r["requests"]["current"],
        "limite_dia": r["requests"]["limit_day"],
    }


def temporadas_da_liga(forcar: bool = False) -> list[dict]:
    """Temporadas do Brasileirão com a cobertura de cada uma (estatísticas, escalações etc.)."""
    return _get("/leagues", f"liga_{LIGA}.json", {"id": LIGA}, forcar)["response"][0]["seasons"]


def partidas(temporada: int, forcar: bool = False) -> list[dict]:
    return _get("/fixtures", f"partidas_{temporada}.json", {"league": LIGA, "season": temporada}, forcar)[
        "response"
    ]


def estatisticas_da_partida(id_partida: int, forcar: bool = False) -> list[dict]:
    return _get(
        "/fixtures/statistics", f"estatisticas/{id_partida}.json", {"fixture": id_partida}, forcar
    )["response"]


# ---------- coleta em lote e tabela de estatísticas ----------

ESTATISTICAS = {  # nome na API -> nosso nome
    "Total Shots": "finalizacoes",
    "Shots on Goal": "no_alvo",
    "Shots insidebox": "dentro_area",
    "expected_goals": "xg",
}


def _cache_estatisticas(id_partida: int):
    return PASTA / "estatisticas" / f"{id_partida}.json"


def coletar_estatisticas(temporada: int) -> dict:
    """Baixa as estatísticas dos jogos encerrados da temporada, dos mais recentes para os mais antigos,
    até a cota do dia acabar. Rodar de novo no dia seguinte continua de onde parou."""
    encerradas = [p for p in partidas(temporada) if p["fixture"]["status"]["short"] in ENCERRADA]
    encerradas.sort(key=lambda p: p["fixture"]["timestamp"], reverse=True)
    baixadas = 0
    for p in encerradas:
        if _cache_estatisticas(p["fixture"]["id"]).exists():
            continue
        try:
            estatisticas_da_partida(p["fixture"]["id"])
        except ErroFonte as e:
            if "cota diária" in str(e):
                break
            raise
        baixadas += 1
    no_cache = sum(_cache_estatisticas(p["fixture"]["id"]).exists() for p in encerradas)
    return {"temporada": temporada, "encerradas": len(encerradas), "baixadas_agora": baixadas, "no_cache": no_cache}


def tabela_estatisticas(temporada: int) -> pd.DataFrame:
    """Uma linha por jogo com as estatísticas dos dois lados, só com o que já está em cache (não gasta cota)."""
    linhas = []
    for p in partidas(temporada):
        arquivo = _cache_estatisticas(p["fixture"]["id"])
        if not arquivo.exists():
            continue
        lados = json.loads(arquivo.read_text(encoding="utf-8"))["response"]
        if len(lados) != 2:
            continue
        linha = {
            "temporada": temporada,
            "data": pd.Timestamp(p["fixture"]["date"]).tz_convert("America/Sao_Paulo").tz_localize(None),
            "mandante": p["teams"]["home"]["name"],
            "visitante": p["teams"]["away"]["name"],
        }
        por_time = {d["team"]["id"]: d for d in lados}
        for lado, time in (("mandante", "home"), ("visitante", "away")):
            valores = {s["type"]: s["value"] for s in por_time[p["teams"][time]["id"]]["statistics"]}
            for nome_api, nome in ESTATISTICAS.items():
                v = valores.get(nome_api)
                linha[f"{nome}_{lado}"] = float(v) if v not in (None, "") else None
        linhas.append(linha)
    df = pd.DataFrame(linhas)
    if not df.empty:
        df["mandante"] = padronizar(df["mandante"], "api_football")
        df["visitante"] = padronizar(df["visitante"], "api_football")
    return df


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    for ano in [int(a) for a in sys.argv[1:]] or [2024]:
        print(coletar_estatisticas(ano))
    print(status())
