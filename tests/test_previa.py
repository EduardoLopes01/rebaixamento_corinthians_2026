"""A prévia para redes sociais bate com a previsão e cabe nos limites do LinkedIn e do WhatsApp."""

import json
import re

from src.config import RAIZ, SITE_DATA
from src.publish.previa import ALTURA, LARGURA, LIMITE_BYTES, SAIDA, num, tamanho_png

SITE = "https://rebaixamentocorinthians.com.br/"
INDEX = (RAIZ / "site" / "index.html").read_text(encoding="utf-8")


def meta(propriedade: str) -> str:
    achado = re.search(rf'<meta (?:property|name)="{re.escape(propriedade)}" content="([^"]*)">', INDEX)
    assert achado, f"falta a tag {propriedade} em site/index.html"
    return achado.group(1)


def test_imagem_no_tamanho_e_leve():
    assert tamanho_png(SAIDA) == (LARGURA, ALTURA) == (1200, 627)
    assert SAIDA.stat().st_size <= LIMITE_BYTES


def test_tags_apontam_para_o_site_e_a_imagem():
    assert meta("og:url") == SITE
    assert meta("og:image") == SITE + "img/previa.png"
    assert (meta("og:image:width"), meta("og:image:height")) == (str(LARGURA), str(ALTURA))
    assert meta("twitter:card") == "summary_large_image"


def test_titulo_da_previa_usa_a_chance_da_previsao():
    dados = json.loads((SITE_DATA / "previsao.json").read_text(encoding="utf-8"))
    chance = f"{num(100 * dados['corinthians']['chance_queda'], 1)}%"
    assert chance in meta("og:title")
    assert chance in meta("og:image:alt")
    assert f"{num(dados['dados']['jogos_na_base'])} jogos" in meta("og:description")


def test_pagina_404_existe():
    assert "Página não encontrada" in (RAIZ / "site" / "404.html").read_text(encoding="utf-8")
