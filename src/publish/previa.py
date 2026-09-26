"""Gera a imagem de prévia do site (site/img/previa.png, 1200 x 627) para LinkedIn, WhatsApp e afins.

Os números vêm de site/data/previsao.json, sem digitação manual. A página da imagem é montada aqui, com a
fonte e o escudo do site embutidos, e fotografada pelo Microsoft Edge sem janela (headless), chamado com
argumentos fixos, sem shell. Sem a foto da torcida: a licença dela (CC BY-SA) pede crédito, e a prévia não
tem onde mostrá-lo.

Rodar da raiz (Windows, com o Edge instalado, depois de src.publish.site):
    python -m src.publish.previa
"""

import base64
import json
import subprocess  # nosec B404
import sys
import tempfile
from pathlib import Path
from string import Template

import pandas as pd

from src.config import DATA_PROCESSED, RAIZ, SITE_DATA

EDGE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
SAIDA = RAIZ / "site" / "img" / "previa.png"
LARGURA, ALTURA = 1200, 627
LIMITE_BYTES = 300_000  # o WhatsApp deixa de mostrar prévias maiores que isso
FONTES = RAIZ / "site" / "vendor" / "@fontsource" / "barlow-condensed"
TIME = "Corinthians"

PAGINA = Template("""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<style>
@font-face { font-family: "Barlow Condensed"; font-weight: 800; src: url(data:font/woff2;base64,$fonte800) format("woff2"); }
@font-face { font-family: "Barlow Condensed"; font-weight: 600; src: url(data:font/woff2;base64,$fonte600) format("woff2"); }
* { box-sizing: border-box; margin: 0; }
html, body { width: ${largura}px; height: ${altura}px; overflow: hidden; }
body { position: relative; background: #0a0a0a; color: #f5f5f5; font: 16px/1.3 "Segoe UI", system-ui, sans-serif; }
.listras { position: absolute; inset: -20% -10%; opacity: .035;
           background: repeating-linear-gradient(90deg, #fff 0 22px, transparent 22px 60px); transform: skewX(-12deg); }
.titulo { font-family: "Barlow Condensed", sans-serif; }
.topo { position: absolute; left: 64px; right: 64px; top: 44px; display: flex; align-items: center; justify-content: space-between; }
.marca { display: flex; align-items: center; gap: 14px; font-weight: 800; font-size: 40px; letter-spacing: .01em; }
.marca img { height: 52px; }
.selo { color: #a8a8a8; font-size: 18px; text-align: right; line-height: 1.3; }
.texto { position: absolute; left: 64px; top: 138px; width: 600px; }
.sobre { display: flex; align-items: center; gap: 12px; color: #a8a8a8; font-weight: 600; font-size: 22px;
         letter-spacing: .14em; text-transform: uppercase; }
.sobre::before { content: ""; width: 34px; height: 3px; background: #ed1c2e; }
.numero { font-weight: 800; font-size: 214px; line-height: .86; letter-spacing: -.01em; margin: 10px 0 18px -6px; }
.frase { font-size: 29px; line-height: 1.3; }
.frase b { color: #ed1c2e; }
.base { color: #a8a8a8; font-size: 19px; margin-top: 12px; }
.pontos { position: absolute; left: 736px; top: 138px; }
.legenda { position: absolute; left: 736px; top: 556px; width: 400px; color: #a8a8a8; font-size: 17px; }
.legenda i { display: inline-block; width: 12px; height: 12px; border-radius: 50%; background: #ed1c2e; margin: 0 6px 0 0; }
.rodape { position: absolute; left: 64px; top: 556px; font-weight: 600; font-size: 26px; letter-spacing: .02em; }
.rodape small { display: block; font-family: "Segoe UI", system-ui, sans-serif; font-weight: 400; font-size: 16px;
                color: #7a7a7a; letter-spacing: 0; margin-top: 2px; }
</style></head>
<body>
<div class="listras"></div>
<div class="topo">
  <div class="marca titulo"><img src="data:image/svg+xml;base64,$escudo" alt="">VAI CAIR?</div>
  <div class="selo">Brasileirão 2026<br>previsão da pausa, com dados até a ${rodada}ª rodada</div>
</div>
<div class="texto">
  <p class="sobre titulo">Chance do Corinthians ser rebaixado</p>
  <p class="numero titulo">$chance</p>
  <p class="frase">O Corinthians cai em <b>1 em cada $um_em</b> das $simulacoes mil temporadas simuladas.</p>
  <p class="base">Base: $jogos jogos do Brasileirão analisados, de $inicio a $fim.</p>
</div>
$pontos
<p class="legenda"><i></i>rebaixado · cada ponto = $por_ponto temporadas</p>
<p class="rodape titulo">rebaixamentocorinthians.com.br<small>Site independente, de estudo. Não é recomendação de aposta.</small></p>
</body></html>
""")


def num(x: float, casas: int = 0) -> str:
    return f"{x:,.{casas}f}".replace(",", "_").replace(".", ",").replace("_", ".")


def ordem_dos_pontos(total: int, semente: int = 2026) -> list[int]:
    """Posição em que cada ponto fica vermelho: o mesmo embaralhamento do site (js/app.js, classe Pontos)."""
    s = semente
    def aleatorio() -> float:
        nonlocal s
        s = (s * 1664525 + 1013904223) % 2**32
        return s / 2**32
    ordem = list(range(total))
    for i in range(total - 1, 0, -1):
        j = int(aleatorio() * (i + 1))
        ordem[i], ordem[j] = ordem[j], ordem[i]
    posto = [0] * total
    for k, p in enumerate(ordem):
        posto[p] = k
    return posto


def grade_de_pontos(chance: float, lado: int = 10, celula: int = 40) -> str:
    """100 pontos (10 x 10): na prévia, cada um vale 1.000 temporadas, para ficarem visíveis no celular."""
    total = lado * lado
    vermelhos = round(chance * total)
    posto = ordem_dos_pontos(total)
    circulos = []
    for i in range(total):
        x, y = (i % lado + 0.5) * celula, (i // lado + 0.5) * celula
        cor = "#ed1c2e" if posto[i] < vermelhos else "#5c5c5c"
        circulos.append(f'<circle cx="{x:g}" cy="{y:g}" r="{celula * 0.34:g}" fill="{cor}"/>')
    return f'<svg class="pontos" width="{lado * celula}" height="{lado * celula}">{"".join(circulos)}</svg>'


def b64(caminho: Path) -> str:
    return base64.b64encode(caminho.read_bytes()).decode()


def montar_pagina(dados: dict, inicio: int) -> str:
    c = dados["corinthians"]
    return PAGINA.substitute(
        largura=LARGURA, altura=ALTURA,
        fonte800=b64(FONTES / "barlow-condensed-latin-800-normal.woff2"),
        fonte600=b64(FONTES / "barlow-condensed-latin-600-normal.woff2"),
        escudo=b64(RAIZ / "site" / "img" / "escudo-corinthians.svg"),
        rodada=dados["dados"]["rodada"],
        chance=f"{num(100 * c['chance_queda'], 1)}%",
        um_em=round(1 / c["chance_queda"]),
        simulacoes=num(dados["dados"]["simulacoes"] / 1000),
        jogos=num(dados["dados"]["jogos_na_base"]),
        inicio=inicio, fim=dados["dados"]["ate"][:4],
        pontos=grade_de_pontos(c["chance_queda"]),
        por_ponto=num(dados["dados"]["simulacoes"] / 100),
    )


def tamanho_png(caminho: Path) -> tuple[int, int]:
    cabecalho = caminho.read_bytes()[:24]
    if cabecalho[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"{caminho} não é PNG")
    return int.from_bytes(cabecalho[16:20], "big"), int.from_bytes(cabecalho[20:24], "big")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    dados = json.loads((SITE_DATA / "previsao.json").read_text(encoding="utf-8"))
    inicio = int(pd.read_parquet(DATA_PROCESSED / "partidas.parquet", columns=["temporada"])["temporada"].min())
    if not EDGE.exists():
        raise RuntimeError(f"Microsoft Edge não encontrado em {EDGE}")
    with tempfile.TemporaryDirectory() as pasta:
        pagina = Path(pasta) / "previa.html"
        pagina.write_text(montar_pagina(dados, inicio), encoding="utf-8")
        foto = Path(pasta) / "previa.png"
        comando = [str(EDGE), "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
                   f"--user-data-dir={Path(pasta) / 'perfil'}", "--force-device-scale-factor=1",
                   f"--window-size={LARGURA},{ALTURA}", "--virtual-time-budget=5000",
                   f"--screenshot={foto}", pagina.as_uri()]
        subprocess.run(comando, check=True, timeout=120, capture_output=True)  # nosec B603
        if tamanho_png(foto) != (LARGURA, ALTURA):
            raise RuntimeError(f"a foto saiu com {tamanho_png(foto)}, e não {LARGURA} x {ALTURA}")
        SAIDA.write_bytes(foto.read_bytes())
    tamanho = SAIDA.stat().st_size
    if tamanho > LIMITE_BYTES:
        raise RuntimeError(f"{SAIDA.name} tem {tamanho} bytes; o limite para prévias do WhatsApp é {LIMITE_BYTES}")
    print(f"{SAIDA.relative_to(RAIZ)}: {LARGURA} x {ALTURA}, {tamanho / 1000:.0f} KB")


if __name__ == "__main__":
    main()
