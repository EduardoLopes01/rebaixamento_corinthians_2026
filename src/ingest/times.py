"""Tabela de-para dos nomes dos times entre as fontes (arquivo de_para_times.csv, ao lado)."""

from functools import cache
from pathlib import Path

import pandas as pd

ARQUIVO = Path(__file__).with_name("de_para_times.csv")
FONTES = ("historico", "football_data_uk", "football_data_org", "api_football")


@cache
def _mapa(fonte: str) -> dict[str, str]:
    if fonte not in FONTES:
        raise ValueError(f"fonte desconhecida: {fonte}")
    df = pd.read_csv(ARQUIVO, encoding="utf-8", dtype=str).dropna(subset=[fonte])
    return dict(zip(df[fonte], df["nome"], strict=True))


def padronizar(nomes: pd.Series, fonte: str) -> pd.Series:
    """Troca o nome da fonte pelo nome padrão. Falha se aparecer um time fora da tabela."""
    mapa = _mapa(fonte)
    faltando = sorted(set(nomes) - set(mapa))
    if faltando:
        raise KeyError(f"{fonte}: times sem de-para em {ARQUIVO.name}: {faltando}")
    return nomes.map(mapa)
