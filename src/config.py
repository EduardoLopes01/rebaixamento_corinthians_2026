"""Caminhos, constantes e chaves do projeto. As chaves vêm só do .env."""

import os
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent.parent
DATA_RAW = RAIZ / "data" / "raw"
DATA_PROCESSED = RAIZ / "data" / "processed"
PREDICTIONS = RAIZ / "predictions"
SITE_DATA = RAIZ / "site" / "data"

load_dotenv(RAIZ / ".env")

FOOTBALL_DATA_KEY = os.getenv("FOOTBALL_DATA_API_KEY", "").strip()
API_FOOTBALL_KEY = os.getenv("API_FOOTBALL_KEY", "").strip()

TEMPORADA = 2026
RODADA_CONGELAMENTO = 28
FUSO = ZoneInfo("America/Sao_Paulo")
