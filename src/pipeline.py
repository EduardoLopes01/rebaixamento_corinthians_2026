"""Roda o pipeline inteiro, na ordem, dos dados em cache até o JSON do site.

Rodar da raiz:  python -m src.pipeline

Não baixa nada novo: as fontes ficam congeladas no cache de data/raw (dados até a 28ª rodada).
Leva uns 2 minutos, quase todo no backtest.
"""

import sys
import time

from src import diagnostico
from src.features import variaveis
from src.ingest import consolidar
from src.models import dixon_coles, ensemble
from src.publish import previa, site
from src.simulate import previsao, sensibilidade

ETAPAS = [
    ("Junta as fontes e confere uma contra a outra", consolidar.main),
    ("Modelo 1: backtest escolhe o decaimento temporal", dixon_coles.main),
    ("Variáveis do Modelo 2, sem vazamento", variaveis.main),
    ("Modelo 2 e Portão 2: versão e peso da combinação", ensemble.main),
    ("Previsão: 100 mil temporadas e checagens 1 a 4", previsao.main),
    ("Sensibilidade: outras escolhas de modelo", sensibilidade.main),
    ("Diagnóstico e cobertura dos dados", diagnostico.main),
    ("JSON do site (só agregados)", site.main),
    ("Imagem de prévia para redes sociais (precisa do Edge)", previa.main),
]


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    inicio = time.monotonic()
    for i, (nome, etapa) in enumerate(ETAPAS, 1):
        print(f"\n=== {i}/{len(ETAPAS)} · {nome} ===")
        etapa()
    print(f"\nPronto em {time.monotonic() - inicio:.0f} s.")


if __name__ == "__main__":
    main()
