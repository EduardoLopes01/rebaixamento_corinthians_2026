"""football-data.org: jogos, resultados e tabela do Brasileirão 2026 (competição BSA).

Plano grátis: 10 chamadas por minuto e só a temporada atual.
"""

from src.config import DATA_RAW, FOOTBALL_DATA_KEY, TEMPORADA
from src.ingest.cache import ErroFonte, get_json

BASE = "https://api.football-data.org/v4"
COMPETICAO = "BSA"
PASTA = DATA_RAW / "football_data"
INTERVALO_S = 6.5  # 10 chamadas/min, com folga


def _get(caminho: str, nome_cache: str, params: dict | None = None, forcar: bool = False) -> dict:
    if not FOOTBALL_DATA_KEY:
        raise ErroFonte("football-data.org: chave ausente no .env (FOOTBALL_DATA_API_KEY)")
    return get_json(
        f"{BASE}{caminho}",
        headers={"X-Auth-Token": FOOTBALL_DATA_KEY},
        fonte="football-data",
        cache=PASTA / nome_cache,
        params=params,
        intervalo_s=INTERVALO_S,
        forcar=forcar,
    )


def competicao(forcar: bool = False) -> dict:
    return _get(f"/competitions/{COMPETICAO}", "competicao.json", forcar=forcar)


def partidas(temporada: int = TEMPORADA, forcar: bool = False) -> list[dict]:
    dados = _get(
        f"/competitions/{COMPETICAO}/matches",
        f"partidas_{temporada}.json",
        {"season": temporada},
        forcar,
    )
    return dados["matches"]


def classificacao(temporada: int = TEMPORADA, forcar: bool = False) -> list[dict]:
    """Tabela oficial geral (tipo TOTAL)."""
    dados = _get(
        f"/competitions/{COMPETICAO}/standings",
        f"classificacao_{temporada}.json",
        {"season": temporada},
        forcar,
    )
    return next(s["table"] for s in dados["standings"] if s["type"] == "TOTAL")
