"""Teste: Modelo 1 aprendendo com uma mistura de gols e xG.

A força de ataque e defesa de cada time sai de um "alvo" que mistura gols e xG de cada jogo:
    alvo = alfa × gols + (1 − alfa) × xG      (alfa = 1: só gols, como o Dixon-Coles)
Jogos sem xG (antes de 2023) usam só os gols. O resto é igual ao Modelo 1: Poisson com mando, decaimento
temporal com o mesmo xi e a correção de Dixon-Coles para placares baixos (rho).

Rodar da raiz:  python -m src.models.poisson_xg
- 2025 escolhe o alfa (semana a semana, cada jogo previsto só com o passado);
- 2026 confirma uma única vez. Observação honesta: 2026 já serviu de prova no Portão 2.
"""

import json
import sys

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.stats import poisson

from src.config import DATA_PROCESSED
from src.features.variaveis import estatisticas_por_jogo
from src.models.dixon_coles import ANOS_DE_TREINO, MAX_GOLS, ModeloDixonColes, Previsao
from src.models.xgb_model import resultado

ALFAS = (1.0, 0.75, 0.5, 0.25, 0.0)


def _tau(grade: np.ndarray, lm: float, lv: float, rho: float) -> np.ndarray:
    """Correção de Dixon-Coles nos placares 0x0, 1x0, 0x1 e 1x1."""
    g = grade.copy()
    g[0, 0] *= 1 - lm * lv * rho
    g[0, 1] *= 1 + lm * rho
    g[1, 0] *= 1 + lv * rho
    g[1, 1] *= 1 - rho
    return g


class ModeloPoissonXG:
    def __init__(self, xi: float, alfa: float, rho: float = -0.03):
        self.xi, self.alfa, self.rho = xi, alfa, rho
        self.times: set[str] = set()

    def ajustar(self, jogos: pd.DataFrame, data_corte: pd.Timestamp) -> "ModeloPoissonXG":
        inicio = data_corte - pd.DateOffset(years=ANOS_DE_TREINO)
        t = jogos[jogos["encerrado"] & (jogos["data"] < data_corte) & (jogos["data"] >= inicio)]
        times = sorted(set(t["mandante"]) | set(t["visitante"]))
        idx = {n: i for i, n in enumerate(times)}
        k = len(times)
        im, iv = t["mandante"].map(idx).to_numpy(dtype=np.int64), t["visitante"].map(idx).to_numpy(dtype=np.int64)
        tem_xg = t["xg_m"].notna().to_numpy() & t["xg_v"].notna().to_numpy()
        gm, gv = t["gols_mandante"].to_numpy(dtype=float), t["gols_visitante"].to_numpy(dtype=float)
        xm, xv = t["xg_m"].to_numpy(dtype=float, na_value=0.0), t["xg_v"].to_numpy(dtype=float, na_value=0.0)
        ym = np.where(tem_xg, self.alfa * gm + (1 - self.alfa) * xm, gm)
        yv = np.where(tem_xg, self.alfa * gv + (1 - self.alfa) * xv, gv)
        w = np.exp(-self.xi * (data_corte - t["data"]).dt.days.to_numpy(dtype=float))

        def perda(p):  # Poisson ponderado (aceita alvo não inteiro) + penalidade que centra os ataques
            mu, casa, atq, dfs = p[0], p[1], p[2:2 + k], p[2 + k:]
            lm = np.exp(mu + casa + atq[im] + dfs[iv])
            lv = np.exp(mu + atq[iv] + dfs[im])
            f = -np.sum(w * (ym * np.log(lm) - lm + yv * np.log(lv) - lv)) + 10 * atq.sum() ** 2 + 1e-3 * (atq @ atq + dfs @ dfs)
            rm, rv = w * (ym - lm), w * (yv - lv)
            g = np.zeros_like(p)
            g[0] = -(rm.sum() + rv.sum())
            g[1] = -rm.sum()
            g[2:2 + k] = -(np.bincount(im, rm, k) + np.bincount(iv, rv, k)) + 20 * atq.sum() + 2e-3 * atq
            g[2 + k:] = -(np.bincount(iv, rm, k) + np.bincount(im, rv, k)) + 2e-3 * dfs
            return f, g

        r = minimize(perda, np.zeros(2 + 2 * k), jac=True, method="L-BFGS-B")
        self._p, self._idx, self._k = r.x, idx, k
        self.times = set(times)
        return self

    def prever(self, mandante: str, visitante: str) -> Previsao:
        p, i, j, k = self._p, self._idx[mandante], self._idx[visitante], self._k
        lm = np.exp(p[0] + p[1] + p[2 + i] + p[2 + k + j])
        lv = np.exp(p[0] + p[2 + j] + p[2 + k + i])
        gols = np.arange(MAX_GOLS)
        grade = _tau(np.outer(poisson.pmf(gols, lm), poisson.pmf(gols, lv)), lm, lv, self.rho)
        return Previsao(mandante, visitante, grade / grade.sum())


def _log_loss(p: np.ndarray, y: np.ndarray) -> float:
    return float(-np.mean(np.log(np.clip(p[np.arange(len(y)), y], 1e-12, 1))))


def backtest(jogos: pd.DataFrame, partidas: pd.DataFrame, xi: float) -> dict:
    alvo = jogos[jogos["encerrado"] & jogos["temporada"].isin([2025, 2026])].copy()
    alvo["semana"] = alvo["data"].dt.to_period("W-MON").dt.start_time
    probs = {a: [] for a in ALFAS} | {"dixon_coles": []}
    y, temporada = [], []
    for semana, grupo in alvo.groupby("semana"):
        dc = ModeloDixonColes(xi).ajustar(partidas, semana)
        modelos = {a: ModeloPoissonXG(xi, a, rho=dc.parametros["rho"]).ajustar(jogos, semana) for a in ALFAS}
        for j in grupo.itertuples():
            if j.mandante not in dc.times or j.visitante not in dc.times:
                continue
            p = dc.prever(j.mandante, j.visitante)
            probs["dixon_coles"].append([p.p_mandante, p.p_empate, p.p_visitante])
            for a, m in modelos.items():
                q = m.prever(j.mandante, j.visitante)
                probs[a].append([q.p_mandante, q.p_empate, q.p_visitante])
            y.append(resultado(j.gols_mandante, j.gols_visitante).item())
            temporada.append(j.temporada)
    y, temporada = np.array(y), np.array(temporada)
    tabela = {str(nome): {str(ano): round(_log_loss(np.array(p)[temporada == ano], y[temporada == ano]), 4)
                          for ano in (2025, 2026)} for nome, p in probs.items()}
    alfa = min(ALFAS, key=lambda a: tabela[str(a)]["2025"])
    ganha_2025 = tabela[str(alfa)]["2025"] < tabela["dixon_coles"]["2025"]
    ganha_2026 = tabela[str(alfa)]["2026"] < tabela["dixon_coles"]["2026"]
    return {"jogos": len(y), "log_loss": tabela, "alfa_escolhido": alfa,
            "adotar": bool(alfa < 1 and ganha_2025 and ganha_2026)}


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    partidas = pd.read_parquet(DATA_PROCESSED / "partidas.parquet")
    jogos = partidas.merge(estatisticas_por_jogo()[["temporada", "mandante", "visitante", "xg_m", "xg_v"]],
                           on=["temporada", "mandante", "visitante"], how="left")
    xi = json.loads((DATA_PROCESSED / "backtest_modelo1.json").read_text(encoding="utf-8"))["xi_escolhido"]
    r = backtest(jogos, partidas, xi)
    (DATA_PROCESSED / "backtest_poisson_xg.json").write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Jogos: {r['jogos']} · log-loss (menor é melhor)")
    for nome, v in r["log_loss"].items():
        rotulo = "Dixon-Coles (Modelo 1)" if nome == "dixon_coles" else f"alfa {nome} ({round(100 * float(nome))}% gols)"
        print(f"  {rotulo:>26}: 2025 {v['2025']:.4f} · 2026 {v['2026']:.4f}")
    print(f"alfa escolhido em 2025: {r['alfa_escolhido']} → {'adotar' if r['adotar'] else 'não adotar'}")


if __name__ == "__main__":
    main()
