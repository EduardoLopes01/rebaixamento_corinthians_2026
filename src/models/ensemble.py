"""Backtest walk-forward do Modelo 2 e da combinação com o Modelo 1, e decisão do Portão 2.

Rodar da raiz (depois de src.features.variaveis):  python -m src.models.ensemble

Como funciona:
- Jogos avaliados: 2025 inteiro e 2026 até a 28ª rodada. Cada jogo é previsto só com o que veio antes:
  o Modelo 1 é reajustado toda semana; o Modelo 2, todo mês (as variáveis dele se atualizam a cada jogo).
- 2025 escolhe a versão do Modelo 2 e o peso da combinação. 2026 fica guardado para a prova final:
  o Portão 2 passa se a combinação tiver log-loss menor que o do Modelo 1 em 2026.
- Referências mínimas: "só mando" (frequência de vitória/empate/derrota) e "situação parecida"
  (frequência dos resultados de jogos com diferença de Elo parecida).
"""

import json
import sys

import numpy as np
import pandas as pd

from src.config import DATA_PROCESSED
from src.models.dixon_coles import ANOS_DE_TREINO, ModeloDixonColes
from src.models.xgb_model import VERSOES, ModeloXGB, resultado

TEMPORADA_PESO = 2025
TEMPORADA_PROVA = 2026
PESOS = np.round(np.arange(0, 1.0001, 0.05), 2)  # peso do Modelo 1 na combinação
FAIXAS_ELO = 10


def metricas(p: np.ndarray, y: np.ndarray) -> dict:
    p = np.clip(p, 1e-12, 1)
    um = np.eye(3)[y]
    return {"log_loss": round(float(-np.mean(np.log(p[np.arange(len(y)), y]))), 4),
            "brier": round(float(np.mean(((p - um) ** 2).sum(axis=1))), 4), "jogos": len(y)}


def calibracao(p: np.ndarray, y: np.ndarray, faixas: int = 10) -> list[dict]:
    prev, real = p.ravel(), np.eye(3)[y].ravel()
    idx = np.minimum((prev * faixas).astype(int), faixas - 1)
    return [{"faixa": f"{k * 10}–{(k + 1) * 10}%", "casos": int((idx == k).sum()),
             "previsto": round(float(prev[idx == k].mean()), 3), "real": round(float(real[idx == k].mean()), 3)}
            for k in range(faixas) if (idx == k).any()]


def _baselines(v: pd.DataFrame, corte: pd.Timestamp, jogos: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    treino = v[v["encerrado"] & (v["data"] < corte) & (v["data"] >= corte - pd.DateOffset(years=ANOS_DE_TREINO))]
    y = resultado(treino["gols_mandante"], treino["gols_visitante"])
    so_mando = np.tile(np.bincount(y, minlength=3) / len(y), (len(jogos), 1))
    limites = np.quantile(treino["elo_diff"], np.linspace(0, 1, FAIXAS_ELO + 1)[1:-1])
    faixa_treino = np.searchsorted(limites, treino["elo_diff"])
    freq = np.array([(np.bincount(y[faixa_treino == k], minlength=3) + 1) / ((faixa_treino == k).sum() + 3)
                     for k in range(FAIXAS_ELO)])
    parecida = freq[np.searchsorted(limites, jogos["elo_diff"])]
    return so_mando, parecida


def backtest(partidas: pd.DataFrame, v: pd.DataFrame, xi: float) -> dict:
    alvo = v[v["encerrado"] & v["temporada"].isin([TEMPORADA_PESO, TEMPORADA_PROVA])].copy()
    alvo["semana"] = alvo["data"].dt.to_period("W-MON").dt.start_time
    alvo["mes"] = alvo["data"].dt.to_period("M").dt.start_time
    probs = {nome: np.full((len(alvo), 3), np.nan) for nome in ["modelo1", "so_mando", "situacao_parecida", *VERSOES]}
    pos = {i: k for k, i in enumerate(alvo.index)}

    for semana, jogos in alvo.groupby("semana"):  # Modelo 1 e referências: toda semana
        m1 = ModeloDixonColes(xi).ajustar(partidas, semana)
        so_mando, parecida = _baselines(v, semana, jogos)
        for k, j in enumerate(jogos.itertuples()):
            if j.mandante in m1.times and j.visitante in m1.times:
                p = m1.prever(j.mandante, j.visitante)
                probs["modelo1"][pos[j.Index]] = [p.p_mandante, p.p_empate, p.p_visitante]
            probs["so_mando"][pos[j.Index]] = so_mando[k]
            probs["situacao_parecida"][pos[j.Index]] = parecida[k]

    n_treino = {}
    for mes, jogos in alvo.groupby("mes"):  # Modelo 2: todo mês
        for versao in VERSOES:
            m2 = ModeloXGB(versao).ajustar(v, mes)
            n_treino.setdefault(versao, []).append(m2.n_treino)
            idx = [pos[i] for i in jogos.index]
            probs[versao][idx] = m2.prever(jogos)

    ok = ~np.isnan(probs["modelo1"]).any(axis=1)
    y = resultado(alvo["gols_mandante"], alvo["gols_visitante"])[ok]
    temporada = alvo["temporada"].to_numpy()[ok]
    probs = {k: p[ok] for k, p in probs.items()}
    peso_, prova = temporada == TEMPORADA_PESO, temporada == TEMPORADA_PROVA

    resultado_por_modelo = {
        nome: {str(TEMPORADA_PESO): metricas(p[peso_], y[peso_]), str(TEMPORADA_PROVA): metricas(p[prova], y[prova]),
               "total": metricas(p, y)}
        for nome, p in probs.items()
    }

    # escolha em 2025: versão do Modelo 2 e peso da combinação
    combinacoes = {}
    for versao in VERSOES:
        curva = {float(w): metricas(w * probs["modelo1"][peso_] + (1 - w) * probs[versao][peso_], y[peso_])["log_loss"]
                 for w in PESOS}
        w = min(curva, key=curva.get)
        p_comb = w * probs["modelo1"] + (1 - w) * probs[versao]
        combinacoes[versao] = {
            "peso_modelo1": w, "curva_2025": curva,
            str(TEMPORADA_PESO): metricas(p_comb[peso_], y[peso_]),
            str(TEMPORADA_PROVA): metricas(p_comb[prova], y[prova]),
            "total": metricas(p_comb, y),
        }
    versao = min(VERSOES, key=lambda k: resultado_por_modelo[k][str(TEMPORADA_PESO)]["log_loss"])
    escolha = combinacoes[versao]
    ll_comb = escolha[str(TEMPORADA_PROVA)]["log_loss"]
    ll_m1 = resultado_por_modelo["modelo1"][str(TEMPORADA_PROVA)]["log_loss"]
    passa = escolha["peso_modelo1"] < 1 and ll_comb < ll_m1
    p_final = escolha["peso_modelo1"] * probs["modelo1"] + (1 - escolha["peso_modelo1"]) * probs[versao]
    ganho = _bootstrap(p_final[prova], probs["modelo1"][prova], y[prova])

    return {
        "jogos_avaliados": int(ok.sum()),
        "jogos_fora_sem_historico": int((~ok).sum()),
        "treino_modelo2_media": {k: int(np.mean(n)) for k, n in n_treino.items()},
        "modelos": resultado_por_modelo,
        "combinacoes": combinacoes,
        "portao2": {
            "versao_modelo2": versao,
            "peso_modelo1": escolha["peso_modelo1"],
            "log_loss_2026_combinacao": ll_comb,
            "log_loss_2026_modelo1": ll_m1,
            "passa": bool(passa),
            "ganho_2026_bootstrap": ganho,
            "decisao": ("combinação do Modelo 1 com o Modelo 2" if passa else "só o Modelo 1"),
        },
        "calibracao": {"modelo1": calibracao(probs["modelo1"], y),
                       "escolhido": calibracao(p_final if passa else probs["modelo1"], y)},
    }


def _bootstrap(p_a: np.ndarray, p_b: np.ndarray, y: np.ndarray, n: int = 5000) -> dict:
    """Quanto o log-loss de A fica abaixo do de B, sorteando os jogos com reposição (incerteza do ganho)."""
    rng = np.random.default_rng(2026)
    perda_a = -np.log(np.clip(p_a[np.arange(len(y)), y], 1e-12, 1))
    perda_b = -np.log(np.clip(p_b[np.arange(len(y)), y], 1e-12, 1))
    amostras = rng.integers(0, len(y), (n, len(y)))
    ganhos = perda_b[amostras].mean(axis=1) - perda_a[amostras].mean(axis=1)
    return {"ganho_medio": round(float(ganhos.mean()), 4),
            "intervalo_90": [round(float(np.percentile(ganhos, 5)), 4), round(float(np.percentile(ganhos, 95)), 4)],
            "chance_de_ser_melhor": round(float((ganhos > 0).mean()), 3)}


def ajustar_grade(grade: np.ndarray, alvo: np.ndarray) -> np.ndarray:
    """Reescala a grade de placares do Modelo 1 para ter as chances de vitória/empate/derrota da combinação,
    mantendo o formato dos placares dentro de cada resultado (os gols ainda servem ao desempate)."""
    mascaras = [np.tril(np.ones_like(grade), -1), np.eye(len(grade)), np.triu(np.ones_like(grade), 1)]
    nova = sum(grade * m * (alvo[k] / (grade * m).sum()) for k, m in enumerate(mascaras))
    return nova / nova.sum()


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    partidas = pd.read_parquet(DATA_PROCESSED / "partidas.parquet")
    v = pd.read_parquet(DATA_PROCESSED / "variaveis.parquet")
    xi = json.loads((DATA_PROCESSED / "backtest_modelo1.json").read_text(encoding="utf-8"))["xi_escolhido"]
    r = backtest(partidas, v, xi)
    (DATA_PROCESSED / "backtest_modelo2.json").write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Jogos avaliados: {r['jogos_avaliados']} (fora: {r['jogos_fora_sem_historico']})")
    print(f"{'modelo':>18} | {'2025':>7} | {'2026':>7} | {'total':>7}   (log-loss; menor é melhor)")
    for nome, m in r["modelos"].items():
        print(f"{nome:>18} | {m['2025']['log_loss']:.4f} | {m['2026']['log_loss']:.4f} | {m['total']['log_loss']:.4f}")
    for versao, c in r["combinacoes"].items():
        print(f"{'M1+' + versao:>18} | {c['2025']['log_loss']:.4f} | {c['2026']['log_loss']:.4f} | "
              f"{c['total']['log_loss']:.4f}   peso do Modelo 1 = {c['peso_modelo1']:.2f}")
    p = r["portao2"]
    print(f"\nPortão 2: {'✅ passa' if p['passa'] else '❌ não passa'} → {p['decisao']} "
          f"(versão {p['versao_modelo2']}, peso do Modelo 1 {p['peso_modelo1']:.2f}; 2026: "
          f"{p['log_loss_2026_combinacao']:.4f} x {p['log_loss_2026_modelo1']:.4f})")
    print(f"Bootstrap em 2026: {p['ganho_2026_bootstrap']}")
    print(f"Jogos de treino do Modelo 2 (média por mês): {r['treino_modelo2_media']}")


if __name__ == "__main__":
    main()
