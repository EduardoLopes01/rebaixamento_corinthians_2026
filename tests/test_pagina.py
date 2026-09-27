"""O conteúdo para buscadores (perguntas frequentes e dados estruturados) bate com a previsão."""

import json
import re

from src.config import RAIZ, SITE_DATA
from src.publish.pagina import SITE, dados_estruturados, pct, perguntas, secao_perguntas, texto

HTML = (RAIZ / "site" / "index.html").read_text(encoding="utf-8")
DADOS = json.loads((SITE_DATA / "previsao.json").read_text(encoding="utf-8"))


def test_um_unico_h1_e_titulo_com_a_chance():
    assert len(re.findall(r"<h1[ >]", HTML)) == 1
    titulo = re.search(r"<title>(.*?)</title>", HTML).group(1)
    assert pct(DADOS["corinthians"]["chance_queda"]) in titulo
    descricao = re.search(r'<meta name="description" content="([^"]*)">', HTML).group(1)
    assert len(titulo) <= 65 and len(descricao) <= 160


def test_perguntas_no_html_estao_em_dia_com_a_previsao():
    # se a previsão mudasse sem rodar src.publish.pagina, o HTML ficaria com números velhos
    assert secao_perguntas(perguntas(DADOS)) in HTML


def test_respostas_trazem_os_numeros_principais():
    respostas = " ".join(texto(r) for _, r in perguntas(DADOS))
    c = DADOS["corinthians"]
    assert pct(c["chance_queda"]) in respostas
    assert f"{c['pontos_para_menos_de_5pct']['pontos_finais']} pontos" in respostas
    adversarios = {j["visitante"] if j["mandante"] == "Corinthians" else j["mandante"]
                   for j in DADOS["jogos"] if "Corinthians" in (j["mandante"], j["visitante"])}
    assert all(a in respostas for a in adversarios)


def test_dados_estruturados_validos():
    bloco = re.search(r'<script type="application/ld\+json">\n(.*?)\n</script>', HTML, re.DOTALL).group(1)
    grafo = json.loads(bloco)["@graph"]
    tipos = {g["@type"] for g in grafo}
    assert tipos == {"WebPage", "Dataset", "FAQPage"}
    faq = next(g for g in grafo if g["@type"] == "FAQPage")
    assert len(faq["mainEntity"]) == len(perguntas(DADOS))
    titulo = re.search(r"<title>(.*?)</title>", HTML).group(1)
    descricao = re.search(r'<meta name="description" content="([^"]*)">', HTML).group(1)
    assert dados_estruturados(DADOS, perguntas(DADOS), titulo, descricao) in HTML


def test_sitemap_e_robots():
    assert f"<loc>{SITE}</loc>" in (RAIZ / "site" / "sitemap.xml").read_text(encoding="utf-8")
    assert f"Sitemap: {SITE}sitemap.xml" in (RAIZ / "site" / "robots.txt").read_text(encoding="utf-8")
