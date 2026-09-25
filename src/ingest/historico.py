"""Dataset histórico do Brasileirão 2003–2024 (github.com/adaoduque/Brasileirao_Dataset).

Sem licença declarada: uso só para treino interno. Nunca republicar os arquivos.
"""

import pandas as pd
import requests

from src.config import DATA_RAW

BASE = "https://raw.githubusercontent.com/adaoduque/Brasileirao_Dataset/master"
PASTA = DATA_RAW / "historico"
ARQUIVOS = {
    "partidas": "campeonato-brasileiro-full.csv",
    "estatisticas": "campeonato-brasileiro-estatisticas-full.csv",
    "gols": "campeonato-brasileiro-gols.csv",
    "cartoes": "campeonato-brasileiro-cartoes.csv",
}


def baixar(forcar: bool = False) -> None:
    PASTA.mkdir(parents=True, exist_ok=True)
    for nome in [*ARQUIVOS.values(), "Legenda.txt"]:
        destino = PASTA / nome
        if destino.exists() and not forcar:
            continue
        resp = requests.get(f"{BASE}/{nome}", timeout=60)
        resp.raise_for_status()
        destino.write_bytes(resp.content)


def carregar(tabela: str = "partidas") -> pd.DataFrame:
    baixar()
    df = pd.read_csv(PASTA / ARQUIVOS[tabela], na_values=["None", ""])
    if tabela == "partidas":
        df["data"] = pd.to_datetime(df["data"], format="%d/%m/%Y")
        df["temporada"] = df["data"].dt.year
        # a temporada 2020 (pandemia) terminou em fevereiro de 2021
        df.loc[(df["data"].dt.year == 2021) & (df["data"].dt.month <= 2), "temporada"] = 2020
    return df
