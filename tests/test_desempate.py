"""Desempate do Art. 15 na simulação: confronto direto só entre 2 clubes; com 3 ou mais, sorteio."""

import numpy as np
import pandas as pd

from src.simulate.temporada import simular


def _jogos(lista, encerrado=True):
    return pd.DataFrame(
        [{"mandante": m, "visitante": v, "gols_mandante": gm, "gols_visitante": gv, "encerrado": encerrado}
         for m, v, gm, gv in lista]
    )


def _placar_certo(gm: int, gv: int, tamanho: int = 5) -> np.ndarray:
    grade = np.zeros((tamanho, tamanho))
    grade[gm, gv] = 1.0
    return grade


def _posicoes(resultado, time):
    return resultado["posicao"][:, resultado["times"].index(time)]


def test_confronto_direto_decide_empate_entre_dois():
    # A e B terminam iguais em pontos, vitórias, saldo e gols pró; A venceu o confronto direto
    encerrados = _jogos([("A", "B", 1, 0), ("C", "A", 1, 0), ("B", "D", 1, 0)])
    restantes = _jogos([("C", "D", None, None)], encerrado=False)
    r = simular(encerrados, restantes, [_placar_certo(0, 0)], n=500)
    assert (_posicoes(r, "C") == 1).all()
    assert (_posicoes(r, "A") == 2).all()
    assert (_posicoes(r, "B") == 3).all()
    assert (_posicoes(r, "D") == 4).all()


def test_criterios_vem_antes_do_confronto_direto():
    # B perdeu para A, mas tem mais gols pró (3º critério), então fica à frente
    encerrados = _jogos([("A", "B", 1, 0), ("C", "A", 1, 0), ("B", "D", 3, 2)])
    restantes = _jogos([("C", "D", None, None)], encerrado=False)
    r = simular(encerrados, restantes, [_placar_certo(0, 0)], n=200)
    assert (_posicoes(r, "B") < _posicoes(r, "A")).all()


def test_tres_empatados_vira_sorteio():
    # A, B e C venceram um ao outro por 1 x 0: empate triplo, sem confronto direto (§ 2º)
    encerrados = _jogos([("A", "B", 1, 0), ("B", "C", 1, 0), ("C", "A", 1, 0)])
    restantes = _jogos([("D", "E", None, None)], encerrado=False)
    r = simular(encerrados, restantes, [_placar_certo(0, 0)], n=6000)
    for time in ("A", "B", "C"):
        assert abs((_posicoes(r, time) == 1).mean() - 1 / 3) < 0.03
