"""Junta as fontes numa base única de partidas, com nomes padronizados, e confere as fontes entre si.

Rodar da raiz do projeto:  python -m src.ingest.consolidar

Quem entra em cada período:
- 2003–2024: dataset histórico (tem as estatísticas por jogo de 2017–2023)
- 2025: football-data.co.uk (o histórico acaba em 2024)
- 2026: football-data.org (fonte oficial da temporada, com os jogos restantes)
O football-data.co.uk também serve para conferir 2012–2024 e 2026, jogo a jogo.

Saídas (fora do Git, porque contêm a base bruta):
- data/processed/partidas.parquet
- data/processed/conferencia_fontes.json
"""

import json
import sys

import pandas as pd

from src.config import DATA_PROCESSED, FUSO, RAIZ, TEMPORADA
from src.ingest import football_data, football_data_uk, historico
from src.ingest.times import padronizar

CHAVE = ["temporada", "mandante", "visitante"]  # cada time recebe cada adversário uma vez por temporada
PLACAR = ["gols_mandante", "gols_visitante"]


def _historico() -> pd.DataFrame:
    df = historico.carregar("partidas")
    return pd.DataFrame(
        {
            "temporada": df["temporada"],
            "data": df["data"],
            "rodada": df["rodata"],
            "mandante": padronizar(df["mandante"], "historico"),
            "visitante": padronizar(df["visitante"], "historico"),
            "gols_mandante": df["mandante_Placar"],
            "gols_visitante": df["visitante_Placar"],
            "encerrado": True,
            "fonte": "historico",
        }
    )


def _uk() -> pd.DataFrame:
    df = football_data_uk.carregar()
    df["mandante"] = padronizar(df["mandante"], "football_data_uk")
    df["visitante"] = padronizar(df["visitante"], "football_data_uk")
    return df.assign(rodada=pd.NA, encerrado=True, fonte="football_data_uk")


def _org() -> pd.DataFrame:
    linhas = []
    for p in football_data.partidas():
        encerrado = p["status"] == "FINISHED"
        sem_data = p["status"] == "POSTPONED"  # adiado: a data da API é a original, não vale mais
        data = pd.Timestamp(p["utcDate"]).tz_convert(FUSO).tz_localize(None)
        linhas.append(
            {
                "temporada": TEMPORADA,
                "data": pd.NaT if sem_data else data,
                "rodada": p["matchday"],
                "mandante": p["homeTeam"]["shortName"],
                "visitante": p["awayTeam"]["shortName"],
                "gols_mandante": p["score"]["fullTime"]["home"] if encerrado else None,
                "gols_visitante": p["score"]["fullTime"]["away"] if encerrado else None,
                "encerrado": encerrado,
                "fonte": "football_data_org",
            }
        )
    df = pd.DataFrame(linhas)
    df["mandante"] = padronizar(df["mandante"], "football_data_org")
    df["visitante"] = padronizar(df["visitante"], "football_data_org")
    return df


def comparar(a: pd.DataFrame, b: pd.DataFrame, nome_a: str, nome_b: str) -> dict:
    """Confere duas fontes jogo a jogo, por temporada: jogos que só uma tem e placares diferentes."""
    m = a[CHAVE + PLACAR].merge(b[CHAVE + PLACAR], on=CHAVE, how="outer", suffixes=("_a", "_b"), indicator=True)
    so_a = m[m["_merge"] == "left_only"]
    so_b = m[m["_merge"] == "right_only"]
    ambos = m[m["_merge"] == "both"]
    placar_diferente = ambos[
        (ambos["gols_mandante_a"] != ambos["gols_mandante_b"]) | (ambos["gols_visitante_a"] != ambos["gols_visitante_b"])
    ]

    def jogos(df: pd.DataFrame, colunas: list[str]) -> list[dict]:
        return json.loads(df[colunas].to_json(orient="records", force_ascii=False))

    por_temporada = [
        {
            "temporada": int(t),
            "em_comum": int((ambos["temporada"] == t).sum()),
            f"so_{nome_a}": int((so_a["temporada"] == t).sum()),
            f"so_{nome_b}": int((so_b["temporada"] == t).sum()),
            "placar_diferente": int((placar_diferente["temporada"] == t).sum()),
        }
        for t in sorted(m["temporada"].unique())
    ]
    return {
        "fontes": [nome_a, nome_b],
        "confere": so_a.empty and so_b.empty and placar_diferente.empty,
        "por_temporada": por_temporada,
        "divergencias": {
            "placar_diferente": jogos(
                placar_diferente,
                CHAVE + ["gols_mandante_a", "gols_visitante_a", "gols_mandante_b", "gols_visitante_b"],
            ),
            f"so_{nome_a}": jogos(so_a, CHAVE),
            f"so_{nome_b}": jogos(so_b, CHAVE),
        },
    }


def consolidar() -> tuple[pd.DataFrame, dict]:
    hist, uk, org = _historico(), _uk(), _org()
    org_encerrados = org[org["encerrado"]]

    conferencia = {
        "historico_x_uk_2012_2024": comparar(
            hist[hist["temporada"] >= 2012], uk[uk["temporada"] <= 2024], "historico", "football_data_uk"
        ),
        "org_x_uk_2026": comparar(
            org_encerrados, uk[uk["temporada"] == TEMPORADA], "football_data_org", "football_data_uk"
        ),
    }

    partidas = pd.concat(
        [hist, uk[uk["temporada"] == 2025], org], ignore_index=True
    ).sort_values(["temporada", "data", "mandante"], na_position="last", ignore_index=True)
    partidas["rodada"] = partidas["rodada"].astype("Int64")
    partidas[PLACAR] = partidas[PLACAR].astype("Int64")
    return partidas, conferencia


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    partidas, conferencia = consolidar()
    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    partidas.to_parquet(DATA_PROCESSED / "partidas.parquet", index=False)
    (DATA_PROCESSED / "conferencia_fontes.json").write_text(
        json.dumps(conferencia, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    por_temporada = partidas.groupby("temporada").agg(jogos=("encerrado", "size"), encerrados=("encerrado", "sum"))
    print(f"Partidas: {len(partidas)} ({partidas['temporada'].min()}–{partidas['temporada'].max()})")
    print(por_temporada.tail(4).to_string())
    for nome, c in conferencia.items():
        print(f"{'✅' if c['confere'] else '⚠️'} {nome}: " + ", ".join(
            f"{k}={sum(t[k] for t in c['por_temporada'])}" for k in c["por_temporada"][0] if k != "temporada"
        ))
    print(f"\nDetalhes em {(DATA_PROCESSED / 'conferencia_fontes.json').relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
