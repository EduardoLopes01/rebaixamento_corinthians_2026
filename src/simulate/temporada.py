"""Simulação de Monte Carlo do restante do Brasileirão 2026, a partir da tabela após a 28ª rodada.

Cada jogo restante recebe um placar sorteado da grade de placares do modelo. A classificação final segue o
Art. 15 do Regulamento Específico da Série A 2026:
    1º vitórias · 2º saldo de gols · 3º gols pró · 4º confronto direto (só se o empate for entre 2 clubes:
    pontos nos dois jogos e, se empatar, saldo nesses jogos) · 5º e 6º cartões · 7º sorteio.
Não temos os cartões, então os critérios 5º a 7º viram sorteio (escolha manual, documentada).
Art. 8: os 4 últimos caem (17º a 20º).
"""

import numpy as np
import pandas as pd

N_SIMULACOES = 100_000
ZONA_DE_QUEDA = range(17, 21)


def simular(
    encerrados: pd.DataFrame, restantes: pd.DataFrame, grades: list[np.ndarray], n: int = N_SIMULACOES, semente: int = 2026
) -> dict:
    """Devolve posições finais e pontos de cada time em cada simulação, e os placares sorteados."""
    rng = np.random.default_rng(semente)
    times = sorted(set(encerrados["mandante"]) | set(encerrados["visitante"])
                   | set(restantes["mandante"]) | set(restantes["visitante"]))
    idx = {t: i for i, t in enumerate(times)}
    k = len(times)

    # placares sorteados: gols[s, g] do mandante e do visitante no jogo g da simulação s
    tamanho = grades[0].shape[0]
    gm = np.empty((n, len(grades)), dtype=np.int16)
    gv = np.empty_like(gm)
    for g, grade in enumerate(grades):
        acumulada = np.cumsum(grade.ravel())
        sorteio = np.searchsorted(acumulada, rng.random(n) * acumulada[-1])
        gm[:, g], gv[:, g] = np.divmod(sorteio, tamanho)

    # jogos já disputados: iguais em todas as simulações, somados uma vez só
    base = {c: np.zeros(k, dtype=np.int32) for c in ("pts", "vit", "gp", "gc")}
    for j in encerrados.itertuples():
        m, v, g_m, g_v = idx[j.mandante], idx[j.visitante], int(j.gols_mandante), int(j.gols_visitante)
        base["gp"][m] += g_m; base["gc"][m] += g_v; base["gp"][v] += g_v; base["gc"][v] += g_m
        base["pts"][m] += 3 if g_m > g_v else 1 if g_m == g_v else 0
        base["pts"][v] += 3 if g_v > g_m else 1 if g_m == g_v else 0
        base["vit"][m] += g_m > g_v; base["vit"][v] += g_v > g_m
    pts, vit, gp, gc = (np.tile(base[c], (n, 1)) for c in ("pts", "vit", "gp", "gc"))

    # jogos restantes: um jogo por vez, vetorizado nas n simulações
    for g, j in enumerate(restantes.itertuples()):
        m, v = idx[j.mandante], idx[j.visitante]
        g_m, g_v = gm[:, g].astype(np.int32), gv[:, g].astype(np.int32)
        gp[:, m] += g_m; gc[:, m] += g_v; gp[:, v] += g_v; gc[:, v] += g_m
        pts[:, m] += 3 * (g_m > g_v) + (g_m == g_v)
        pts[:, v] += 3 * (g_v > g_m) + (g_m == g_v)
        vit[:, m] += g_m > g_v; vit[:, v] += g_v > g_m

    sg = gp - gc
    # critérios 1º a 3º numa chave só (inteira), e sorteio como último desempate
    chave = ((pts.astype(np.int64) * 100 + vit) * 1000 + (sg + 500)) * 1000 + gp
    sorteio = rng.random((n, k))
    ordem = np.argsort(-(chave + sorteio), axis=1)  # empate nos critérios 1º a 3º: ordem sorteada

    # 4º critério: confronto direto, só quando exatamente 2 clubes empatam nos critérios 1º a 3º
    confrontos = _confrontos(encerrados, restantes, idx)
    chave_ord = np.take_along_axis(chave, ordem, axis=1)
    empates = np.argwhere(chave_ord[:, :-1] == chave_ord[:, 1:])
    trocas = 0
    for s, p in empates:
        bloco = chave_ord[s] == chave_ord[s, p]
        if bloco.sum() != 2:
            continue  # 3 ou mais empatados: o regulamento pula o confronto direto
        a, b = ordem[s, p], ordem[s, p + 1]
        if _vence_confronto(b, a, s, confrontos, gm, gv):
            ordem[s, p], ordem[s, p + 1] = b, a
            trocas += 1

    posicao = np.empty_like(ordem)
    np.put_along_axis(posicao, ordem, np.arange(1, k + 1), axis=1)
    return {"times": times, "posicao": posicao, "pontos": pts, "gols_mandante": gm, "gols_visitante": gv,
            "trocas_confronto_direto": trocas}


def _confrontos(encerrados, restantes, idx) -> dict:
    """Para cada par de times: jogos já disputados (placar fixo) e jogos restantes (coluna na simulação)."""
    c: dict[frozenset, dict] = {}
    for j in encerrados.itertuples():
        par = c.setdefault(frozenset((idx[j.mandante], idx[j.visitante])), {"fixos": [], "simulados": []})
        par["fixos"].append((idx[j.mandante], int(j.gols_mandante), int(j.gols_visitante)))
    for g, j in enumerate(restantes.itertuples()):
        par = c.setdefault(frozenset((idx[j.mandante], idx[j.visitante])), {"fixos": [], "simulados": []})
        par["simulados"].append((idx[j.mandante], g))
    return c


def _vence_confronto(x: int, y: int, s: int, confrontos: dict, gm, gv) -> bool:
    """x fica à frente de y no confronto direto? (pontos nos dois jogos; depois, saldo nesses jogos)"""
    pts = {x: 0, y: 0}
    saldo = {x: 0, y: 0}
    par = confrontos.get(frozenset((x, y)), {"fixos": [], "simulados": []})
    jogos = list(par["fixos"]) + [(m, int(gm[s, g]), int(gv[s, g])) for m, g in par["simulados"]]
    for mandante, g_m, g_v in jogos:
        visitante = y if mandante == x else x
        saldo[mandante] += g_m - g_v
        saldo[visitante] += g_v - g_m
        pts[mandante] += 3 if g_m > g_v else (1 if g_m == g_v else 0)
        pts[visitante] += 3 if g_v > g_m else (1 if g_m == g_v else 0)
    return (pts[x], saldo[x]) > (pts[y], saldo[y])


def chance_de_queda(resultado: dict) -> dict[str, float]:
    pos = resultado["posicao"]
    queda = (pos >= ZONA_DE_QUEDA.start).mean(axis=0)
    return {t: float(q) for t, q in zip(resultado["times"], queda, strict=True)}


def distribuicao_posicoes(resultado: dict, time: str) -> list[float]:
    i = resultado["times"].index(time)
    k = len(resultado["times"])
    return (np.bincount(resultado["posicao"][:, i], minlength=k + 1)[1:] / len(resultado["posicao"])).tolist()


def pontos_para_ficar_abaixo(resultado: dict, time: str, alvo: float = 0.05, minimo_casos: int = 50) -> dict:
    """Menor total de pontos a partir do qual a chance de queda, entre as simulações que terminam com esse total,
    fica abaixo do alvo (e continua abaixo para totais maiores)."""
    i = resultado["times"].index(time)
    pontos = resultado["pontos"][:, i]
    caiu = resultado["posicao"][:, i] >= ZONA_DE_QUEDA.start
    curva = []
    for p in range(int(pontos.min()), int(pontos.max()) + 1):
        casos = pontos == p
        if casos.sum() >= minimo_casos:
            curva.append({"pontos": p, "simulacoes": int(casos.sum()), "chance_queda": round(float(caiu[casos].mean()), 4)})
    necessario = None
    for c in reversed(curva):
        if c["chance_queda"] >= alvo:
            break
        necessario = c["pontos"]
    return {"alvo": alvo, "pontos_finais": necessario, "curva": curva}
