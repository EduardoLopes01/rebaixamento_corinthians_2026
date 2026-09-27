"""Escreve no site/index.html o conteúdo para buscadores: perguntas frequentes e dados estruturados.

O topo e os gráficos do site são montados por JavaScript. O Google executa JavaScript, com atraso; Bing,
LinkedIn e robôs de IA, em geral, não. Por isso as respostas principais também vão escritas no HTML, numa
seção visível de perguntas frequentes, com os números lidos de site/data/previsao.json (sem digitação
manual). Junto vão os dados estruturados (schema.org, JSON-LD) e o site/sitemap.xml.

Rodar da raiz, depois de src.publish.site:
    python -m src.publish.pagina
"""

import json
import re
import sys
from datetime import datetime
from html import escape

from src.config import FUSO, RAIZ, SITE_DATA

SITE = "https://rebaixamentocorinthians.com.br/"
REPOSITORIO = "https://github.com/EduardoLopes01/rebaixamento_corinthians_2026"
AUTOR = "Eduardo Lopes"
PRIMEIRA_TEMPORADA = 2003  # início da base histórica (Brasileirão Dataset)
DATA_DO_REGISTRO = "2026-09-26"  # snapshot em predictions/ e Release no GitHub
TIME = "Corinthians"
INDEX = RAIZ / "site" / "index.html"
SITEMAP = RAIZ / "site" / "sitemap.xml"


def num(x: float, casas: int = 0) -> str:
    return f"{x:,.{casas}f}".replace(",", "_").replace(".", ",").replace("_", ".")


def pct(x: float, casas: int = 1) -> str:
    return f"{num(100 * x, casas)}%"


def dia(iso: str) -> str:
    return f"{iso[8:10]}/{iso[5:7]}"


def perguntas(d: dict) -> list[tuple[str, str]]:
    """Pares (pergunta, resposta em HTML simples), com o que as pessoas buscam sobre o assunto."""
    c, dados = d["corinthians"], d["dados"]
    meta = c["pontos_para_menos_de_5pct"]
    jogos = [j for j in d["jogos"] if TIME in (j["mandante"], j["visitante"])]
    esperados = sum(3 * (j["p_mandante"] if j["mandante"] == TIME else j["p_visitante"]) + j["p_empate"] for j in jogos)
    p17 = [h["pontos_17o"] for h in d["historia_17o"]]
    ameacados = sorted((t for t in d["times"] if t["chance_queda"] >= 0.10), key=lambda t: -t["chance_queda"])
    sims = f"{num(dados['simulacoes'] / 1000)} mil"

    linhas_jogos = []
    for j in jogos:
        casa = j["mandante"] == TIME
        adv = j["visitante"] if casa else j["mandante"]
        vence, perde = (j["p_mandante"], j["p_visitante"]) if casa else (j["p_visitante"], j["p_mandante"])
        linhas_jogos.append(f"<li>{dia(j['data'])}, {j['rodada']}ª rodada: {escape(adv)} "
                            f"({'em casa' if casa else 'fora'}). Vence {pct(vence, 0)}, empata {pct(j['p_empate'], 0)}, "
                            f"perde {pct(perde, 0)}.</li>")
    linhas_briga = [f"<li>{t['pos']}º {escape(t['time'])}, {t['pts']} pontos: {pct(t['chance_queda'])}</li>" for t in ameacados]

    return [
        ("O Corinthians vai cair em 2026?",
         (f"<p>Pela previsão feita na pausa da Data Fifa, com dados até a {dados['rodada']}ª rodada ({dia(dados['ate'])}/2026), "
          f"o Corinthians cai em <b>{pct(c['chance_queda'])}</b> das {sims} temporadas simuladas: "
          f"1 em cada {round(1 / c['chance_queda'])}. Nas outras, escapa. Na pausa, o time estava em "
          f"{c['pos_atual']}º lugar, com {c['pts_atual']} pontos. Quatro times caem.</p>")),
        ("Quantos pontos o Corinthians precisa para não cair?",
         (f"<p>Para a chance de queda ficar abaixo de 5%, o Corinthians precisa chegar a <b>{meta['pontos_finais']} pontos</b>: "
          f"faltam {meta['faltam']}, dos {3 * len(jogos)} em disputa. Somando os {len(jogos)} jogos, o modelo espera cerca de "
          f"{num(esperados, 1)} pontos. Desde 2006, o 17º colocado, o primeiro da zona de rebaixamento, fez entre "
          f"{min(p17)} e {max(p17)} pontos.</p>")),
        (f"Quais são os {len(jogos)} jogos que faltam para o Corinthians?",
         f"<p>Chance de cada resultado, do ponto de vista do Corinthians:</p><ul>{''.join(linhas_jogos)}</ul>"),
        ("Quem mais está na briga contra o rebaixamento?",
         f"<p>Chance de queda dos times com 10% ou mais, com a posição e os pontos na pausa:</p><ul>{''.join(linhas_briga)}</ul>"),
        ("Como a chance de rebaixamento é calculada?",
         (f"<p>O modelo aprendeu com {num(dados['jogos_na_base'])} jogos do Brasileirão, de {PRIMEIRA_TEMPORADA} a "
          f"{dados['ate'][:4]}. Ele estima a chance de vitória, empate e derrota de cada um dos {dados['jogos_restantes']} jogos "
          f"restantes, combinando dois modelos: {round(100 * d['modelo']['peso_modelo1'])}% Dixon-Coles, que olha a força de "
          f"ataque e defesa e o mando de campo, e {round(100 * (1 - d['modelo']['peso_modelo1']))}% XGBoost, que olha o momento "
          f"do time. Depois, o computador joga o resto do campeonato {sims} vezes, com os critérios de desempate do "
          f"regulamento, e conta em quantas o time termina entre o 17º e o 20º lugar.</p>")),
        ("Por que o número é diferente do da UFMG?",
         (f"<p>Na mesma pausa, a UFMG calculou {pct(d['ufmg']['chance_queda_corinthians'])} "
          f"({dia(d['ufmg']['data'])}/{d['ufmg']['data'][:4]}). Os métodos são parecidos, mas os modelos e os dados de entrada "
          f"não são iguais. Trocando escolhas do nosso modelo, o número fica entre {pct(d['sensibilidade']['minimo'], 0)} e "
          f"{pct(d['sensibilidade']['maximo'], 0)}.</p>")),
        ("A previsão é atualizada?",
         (f"<p>Não. Ela foi registrada uma única vez no GitHub, em {dia(DATA_DO_REGISTRO)}/{DATA_DO_REGISTRO[:4]}, antes da volta "
          f"do campeonato, e não muda. No fim do campeonato sai a comparação com o que aconteceu. "
          f'<a href="{REPOSITORIO}" rel="noopener">Ver o registro no GitHub</a>.</p>')),
    ]


def secao_perguntas(pares: list[tuple[str, str]]) -> str:
    blocos = "\n".join(
        f"    <details{' open' if i == 0 else ''}>\n      <summary><h3>{escape(p)}</h3></summary>\n      {r}\n    </details>"
        for i, (p, r) in enumerate(pares)
    )
    return f'  <section class="card revela" id="perguntas">\n    <h2>Perguntas frequentes</h2>\n{blocos}\n  </section>'


def texto(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()


def dados_estruturados(d: dict, pares: list[tuple[str, str]], titulo: str, descricao: str) -> str:
    autor = {"@type": "Person", "name": AUTOR}
    grafo = [
        {"@type": "WebPage", "@id": SITE, "url": SITE, "name": titulo, "description": descricao, "inLanguage": "pt-BR",
         "datePublished": DATA_DO_REGISTRO, "author": autor,
         "about": {"@type": "SportsTeam", "name": "Sport Club Corinthians Paulista", "sport": "Futebol"}},
        {"@type": "Dataset", "name": "Previsão de rebaixamento do Brasileirão Série A 2026, feita na pausa da Data Fifa",
         "description": (f"Chance de vitória, empate e derrota de cada um dos {d['dados']['jogos_restantes']} jogos restantes e "
                         f"chance de queda dos 20 times, em {num(d['dados']['simulacoes'])} temporadas simuladas, com dados "
                         f"até a {d['dados']['rodada']}ª rodada."),
         "url": SITE, "sameAs": REPOSITORIO, "creator": autor, "datePublished": DATA_DO_REGISTRO, "inLanguage": "pt-BR",
         "isAccessibleForFree": True, "temporalCoverage": f"{d['dados']['ate']}/2026-12-02",
         "keywords": ["Corinthians", "rebaixamento", "Brasileirão 2026", "probabilidade", "simulação Monte Carlo"],
         "distribution": {"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": SITE + "data/previsao.json"}},
        {"@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": p, "acceptedAnswer": {"@type": "Answer", "text": texto(r)}} for p, r in pares]},
    ]
    corpo = json.dumps({"@context": "https://schema.org", "@graph": grafo}, ensure_ascii=False, indent=1).replace("</", "<\\/")
    return f'<script type="application/ld+json">\n{corpo}\n</script>'


def trocar(html: str, marcador: str, conteudo: str) -> str:
    """Troca o que está entre <!-- marcador:inicio --> e <!-- marcador:fim --> (roda quantas vezes quiser)."""
    padrao = re.compile(rf"(<!-- {marcador}:inicio -->).*?\n([ \t]*)(<!-- {marcador}:fim -->)", re.DOTALL)
    if not padrao.search(html):
        raise RuntimeError(f"marcador {marcador} não encontrado em {INDEX.name}")
    return padrao.sub(lambda m: f"{m.group(1)}\n{conteudo}\n{m.group(2)}{m.group(3)}", html)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    d = json.loads((SITE_DATA / "previsao.json").read_text(encoding="utf-8"))
    html = INDEX.read_text(encoding="utf-8")
    titulo = re.search(r"<title>(.*?)</title>", html).group(1)
    descricao = re.search(r'<meta name="description" content="([^"]*)">', html).group(1)
    pares = perguntas(d)
    html = trocar(html, "seo:perguntas", secao_perguntas(pares))
    html = trocar(html, "seo:dados-estruturados", dados_estruturados(d, pares, titulo, descricao))
    INDEX.write_bytes(html.encode("utf-8"))
    SITEMAP.write_bytes(
        ('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
         f"  <url><loc>{SITE}</loc><lastmod>{datetime.now(FUSO).date().isoformat()}</lastmod></url>\n</urlset>\n").encode())
    print(f"{INDEX.relative_to(RAIZ).as_posix()}: {len(pares)} perguntas frequentes e dados estruturados; "
          f"{SITEMAP.relative_to(RAIZ).as_posix()} atualizado")


if __name__ == "__main__":
    main()
