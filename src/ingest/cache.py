"""Chamadas HTTP com cache em data/raw e intervalo mínimo entre chamadas de cada fonte.

Uma resposta salva em cache nunca é baixada de novo, a não ser com forcar=True:
os dados da previsão ficam congelados no primeiro download.
"""

import json
import time
from collections.abc import Callable
from pathlib import Path

import requests

_ultima_chamada: dict[str, float] = {}


class ErroFonte(RuntimeError):
    """Falha ao consultar uma fonte. A mensagem nunca inclui chaves."""


def get_json(
    url: str,
    *,
    headers: dict,
    fonte: str,
    cache: Path | None,
    params: dict | None = None,
    intervalo_s: float = 0.0,
    forcar: bool = False,
    erro_na_resposta: Callable[[dict], str | None] | None = None,
) -> dict:
    if cache is not None and cache.exists() and not forcar:
        return json.loads(cache.read_text(encoding="utf-8"))

    espera = _ultima_chamada.get(fonte, 0.0) + intervalo_s - time.monotonic()
    if espera > 0:
        time.sleep(espera)
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=30)
    except requests.RequestException as e:
        raise ErroFonte(f"{fonte}: falha de rede ({type(e).__name__})") from None
    finally:
        _ultima_chamada[fonte] = time.monotonic()

    if resp.status_code != 200:
        raise ErroFonte(f"{fonte}: HTTP {resp.status_code} - {resp.text[:200]}")
    dados = resp.json()
    if erro_na_resposta and (msg := erro_na_resposta(dados)):
        raise ErroFonte(msg)  # respostas com erro não vão para o cache

    if cache is not None:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")
    return dados
