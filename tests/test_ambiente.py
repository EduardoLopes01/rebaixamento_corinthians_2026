"""Confere se o ambiente está pronto: pacotes carregam e segredos ficam fora do Git."""

import importlib
import subprocess

import pytest

from src.config import RAIZ

PACOTES = [
    "pandas", "numpy", "scipy", "scipy.interpolate", "penaltyblog", "xgboost",
    "sklearn", "requests", "dotenv", "pyarrow", "matplotlib", "PIL",
]


@pytest.mark.parametrize("nome", PACOTES)
def test_pacote_carrega(nome):
    importlib.import_module(nome)


def test_numpy_random_funciona():
    # o Smart App Control do Windows já bloqueou este módulo nesta máquina
    import numpy as np

    assert 0 <= np.random.default_rng(0).integers(0, 10) < 10


def test_dixon_coles_disponivel():
    import penaltyblog as pb

    assert hasattr(pb.models, "DixonColesGoalModel")


@pytest.mark.parametrize("caminho", [".env", "data/raw/qualquer.json"])
def test_segredos_e_dados_brutos_fora_do_git(caminho):
    resultado = subprocess.run(["git", "check-ignore", "-q", caminho], cwd=RAIZ, check=False)
    ignorado = resultado.returncode == 0
    assert ignorado, f"{caminho} deveria estar no .gitignore"
