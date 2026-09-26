"""O simulador do site (JavaScript) dá o mesmo resultado que a simulação em Python quando nada é fixado."""

import json
import shutil
import subprocess

import pytest

from src.config import DATA_PROCESSED, RAIZ, SITE_DATA

TOLERANCIA = 0.01  # 1 ponto percentual: as duas simulações (100 mil temporadas cada) são sorteios independentes

SCRIPT = """
import { readFileSync } from "node:fs";
import { simular, simularEmPartes } from "./site/js/simulador.js";
const dados = JSON.parse(readFileSync("site/data/previsao.json", "utf-8"));
const cor = dados.jogos.map((j, g) => [j, g]).filter(([j]) => [j.mandante, j.visitante].includes("Corinthians"));
const vitorias = Object.fromEntries(cor.map(([j, g]) => [g, j.mandante === "Corinthians" ? 0 : 2]));
const inicio = performance.now();
const livre = simularEmPartes(dados, {});  // o mesmo cálculo do site, em 8 partes de 12.500
const ms = performance.now() - inicio;
const tudoVitoria = simular(dados, vitorias, 5000);
console.log(JSON.stringify({ times: livre.times, chance: livre.chanceQueda, ms,
  corTudoVitoria: tudoVitoria.chanceQueda[tudoVitoria.times.indexOf("Corinthians")] }));
"""


@pytest.fixture(scope="module")
def resultado_js():
    if not shutil.which("node") or not (SITE_DATA / "previsao.json").exists():
        pytest.skip("precisa do Node e de site/data/previsao.json (python -m src.publish.site)")
    if not (DATA_PROCESSED / "previsao.json").exists():
        pytest.skip("precisa de data/processed/previsao.json, que fica fora do Git (python -m src.pipeline)")
    saida = subprocess.run(["node", "--input-type=module", "-e", SCRIPT], cwd=RAIZ, capture_output=True,
                           text=True, encoding="utf-8", check=True)
    return json.loads(saida.stdout)


def test_js_igual_ao_python(resultado_js):
    python = {t["time"]: t["chance_queda"] for t in json.loads((DATA_PROCESSED / "previsao.json").read_text(encoding="utf-8"))["times"]}
    diferencas = {t: round(c - python[t], 4) for t, c in zip(resultado_js["times"], resultado_js["chance"], strict=True)}
    assert all(abs(d) <= TOLERANCIA for d in diferencas.values()), diferencas


def test_js_soma_4_vagas(resultado_js):
    assert abs(sum(resultado_js["chance"]) - 4) < 1e-9


def test_js_corinthians_vencendo_tudo_nao_cai(resultado_js):
    assert resultado_js["corTudoVitoria"] == 0


def test_js_rapido(resultado_js):
    assert resultado_js["ms"] < 6000  # 100 mil temporadas em sequência; no site as partes rodam em paralelo, em Workers
