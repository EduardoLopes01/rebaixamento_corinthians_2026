"""Somas de probabilidade: cada jogo fecha 100% e as chances de queda somam 4 (4 vagas)."""

import numpy as np
import pandas as pd

from src.checks.publicacao import checagem2, checagem3
from src.models.dixon_coles import Previsao
from src.simulate.temporada import chance_de_queda, simular


def test_previsao_de_jogo_fecha_100():
    rng = np.random.default_rng(0)
    grade = rng.random((11, 11))
    p = Previsao("A", "B", grade / grade.sum())
    assert abs(p.p_mandante + p.p_empate + p.p_visitante - 1) < 1e-12
    assert checagem3([p.resumo()])["aprovada"]


def test_checagem3_reprova_jogo_fora_de_100():
    jogo = {"mandante": "A", "visitante": "B", "p_mandante": 0.5, "p_empate": 0.3, "p_visitante": 0.3}
    assert not checagem3([jogo])["aprovada"]


def test_chances_de_queda_somam_4_numa_liga_de_20():
    times = [f"T{i:02d}" for i in range(20)]
    restantes = pd.DataFrame(
        [{"mandante": a, "visitante": b} for a in times for b in times if a != b][:60]
    )
    encerrados = pd.DataFrame(columns=["mandante", "visitante", "gols_mandante", "gols_visitante"])
    rng = np.random.default_rng(1)
    grades = []
    for _ in range(len(restantes)):
        g = rng.random((6, 6))
        grades.append(g / g.sum())
    chances = chance_de_queda(simular(encerrados, restantes, grades, n=2000))
    assert checagem2(chances)["aprovada"]


def test_grade_ajustada_tem_as_chances_da_combinacao():
    from src.models.ensemble import ajustar_grade

    rng = np.random.default_rng(3)
    grade = rng.random((11, 11))
    grade /= grade.sum()
    alvo = np.array([0.40, 0.33, 0.27])
    p = Previsao("A", "B", ajustar_grade(grade, alvo))
    assert np.allclose([p.p_mandante, p.p_empate, p.p_visitante], alvo)
    assert abs(p.grade.sum() - 1) < 1e-12
