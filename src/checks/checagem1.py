"""Checagem 1: a tabela reconstruída pelos resultados é igual à oficial?

Compara, para os 20 times: pontos, jogos, vitórias, empates, derrotas, gols pró, gols contra e saldo.
- Oficial: classificação do football-data.org (tabela da CBF replicada pela API).
- Reconstruída A: resultados do football-data.org.
- Reconstruída B: resultados do football-data.co.uk (fonte independente).

Rodar da raiz:  python -m src.checks.checagem1
"""

import json
import sys

import pandas as pd

from src.config import DATA_PROCESSED, TEMPORADA
from src.features.tabela import COLUNAS, classificacao
from src.ingest import football_data
from src.ingest.consolidar import _uk
from src.ingest.times import padronizar

MAPA_OFICIAL = {"pts": "points", "j": "playedGames", "v": "won", "e": "draw", "d": "lost",
                "gp": "goalsFor", "gc": "goalsAgainst", "sg": "goalDifference"}


def tabela_oficial() -> pd.DataFrame:
    linhas = football_data.classificacao()
    df = pd.DataFrame({"time": [l["team"]["shortName"] for l in linhas], "pos": [l["position"] for l in linhas],
                       **{k: [l[v] for l in linhas] for k, v in MAPA_OFICIAL.items()}})
    df["time"] = padronizar(df["time"], "football_data_org")
    return df.set_index("time")


def _diferencas(oficial: pd.DataFrame, reconstruida: pd.DataFrame) -> list[dict]:
    r = reconstruida.reindex(oficial.index)
    difs = []
    for time in oficial.index:
        campos = [c for c in COLUNAS if pd.isna(r.at[time, c]) or int(r.at[time, c]) != int(oficial.at[time, c])]
        if campos:
            difs.append({"time": time, "campos": campos})
    return difs


def rodar() -> dict:
    oficial = tabela_oficial()
    partidas = pd.read_parquet(DATA_PROCESSED / "partidas.parquet")
    a = classificacao(partidas[partidas["temporada"] == TEMPORADA])
    uk = _uk()
    b = classificacao(uk[uk["temporada"] == TEMPORADA])
    resultado = {
        "times": len(oficial),
        "football_data_org": {"diferencas": _diferencas(oficial, a)},
        "football_data_uk": {"diferencas": _diferencas(oficial, b)},
        "ordem_confere": list(a.index) == list(oficial.sort_values("pos").index),
    }
    resultado["aprovada"] = (
        len(oficial) == 20
        and not resultado["football_data_org"]["diferencas"]
        and not resultado["football_data_uk"]["diferencas"]
    )
    return resultado


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    r = rodar()
    (DATA_PROCESSED / "checagem1.json").write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{'✅' if r['aprovada'] else '❌'} Checagem 1: tabela reconstruída igual à oficial nos {r['times']} times")
    for fonte in ("football_data_org", "football_data_uk"):
        print(f"   {fonte}: {r[fonte]['diferencas'] or 'sem diferenças'}")
    print(f"   ordem da tabela confere: {r['ordem_confere']}")


if __name__ == "__main__":
    main()
