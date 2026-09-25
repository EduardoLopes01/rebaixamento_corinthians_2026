"""football-data.co.uk: resultados da Série A de 2012 a 2026 (arquivo CSV grátis).

Uso restrito: só resultados, para preencher 2025 e conferir as outras fontes. O arquivo traz odds,
que descartamos na leitura. No site, a fonte é citada pelo nome, sem link (o site tem links de apostas).
"""

import pandas as pd
import requests

from src.config import DATA_RAW
from src.ingest.cache import ErroFonte

URL = "https://www.football-data.co.uk/new/BRA.csv"
ARQUIVO = DATA_RAW / "football_data_uk" / "BRA.csv"
COLUNAS = ["Season", "Date", "Time", "Home", "Away", "HG", "AG"]  # só resultados; odds ficam de fora


def baixar(forcar: bool = False) -> None:
    if ARQUIVO.exists() and not forcar:
        return
    try:
        resp = requests.get(URL, timeout=60, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
    except requests.RequestException as e:
        raise ErroFonte(f"football-data.co.uk: falha no download ({type(e).__name__})") from None
    ARQUIVO.parent.mkdir(parents=True, exist_ok=True)
    ARQUIVO.write_bytes(resp.content)


def carregar() -> pd.DataFrame:
    baixar()
    df = pd.read_csv(ARQUIVO, encoding="utf-8-sig", usecols=COLUNAS)
    df = df.dropna(subset=["HG", "AG"])
    return pd.DataFrame(
        {
            "temporada": df["Season"].astype(int),
            "data": pd.to_datetime(df["Date"], format="%d/%m/%Y"),
            "mandante": df["Home"],
            "visitante": df["Away"],
            "gols_mandante": df["HG"].astype(int),
            "gols_visitante": df["AG"].astype(int),
        }
    )
