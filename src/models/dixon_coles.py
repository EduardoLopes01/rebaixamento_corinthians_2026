"""Modelo 1: Dixon-Coles (penaltyblog), com ataque e defesa por time, mando de campo e decaimento temporal.

O decaimento (xi, por dia) dá mais peso aos jogos recentes: peso = exp(-xi × dias até a data de corte).
O valor de xi sai do backtest (python -m src.models.dixon_coles), não de escolha manual.
"""

import json
import sys
from dataclasses import dataclass

import numpy as np
import pandas as pd
import penaltyblog as pb

from src.config import DATA_PROCESSED

ANOS_DE_TREINO = 8  # com o decaimento escolhido (xi = 0,001), um jogo de 8 anos atrás pesa ~5% de um de hoje
MAX_GOLS = 11  # grade de placares de 0 a 10 gols por time
XI_CANDIDATOS = (0.0005, 0.001, 0.0015, 0.002, 0.003, 0.004)
TEMPORADAS_BACKTEST = (2022, 2023, 2024, 2025)
LIMITE_EQUILIBRADO = 0.10  # selo "jogo equilibrado": |P(mandante) − P(visitante)| < 10 pontos percentuais


@dataclass
class Previsao:
    mandante: str
    visitante: str
    grade: np.ndarray  # grade[i, j] = P(mandante marca i, visitante marca j)

    @property
    def p_mandante(self) -> float:
        return float(np.tril(self.grade, -1).sum())

    @property
    def p_empate(self) -> float:
        return float(np.trace(self.grade))

    @property
    def p_visitante(self) -> float:
        return float(np.triu(self.grade, 1).sum())

    @property
    def gols_esperados(self) -> tuple[float, float]:
        gols = np.arange(self.grade.shape[0])
        return float(self.grade.sum(axis=1) @ gols), float(self.grade.sum(axis=0) @ gols)

    @property
    def placar_mais_provavel(self) -> tuple[int, int]:
        i, j = np.unravel_index(self.grade.argmax(), self.grade.shape)
        return int(i), int(j)

    def resumo(self) -> dict:
        gm, gv = self.gols_esperados
        pm, pe, pv = self.p_mandante, self.p_empate, self.p_visitante
        return {
            "mandante": self.mandante,
            "visitante": self.visitante,
            "p_mandante": round(pm, 4),
            "p_empate": round(pe, 4),
            "p_visitante": round(pv, 4),
            "gols_esperados": [round(gm, 2), round(gv, 2)],
            "placar_mais_provavel": list(self.placar_mais_provavel),
            "p_placar_mais_provavel": round(float(self.grade.max()), 4),
            "equilibrado": abs(pm - pv) < LIMITE_EQUILIBRADO,
        }


class ModeloDixonColes:
    def __init__(self, xi: float):
        self.xi = xi
        self._modelo = None
        self.times: set[str] = set()

    def ajustar(self, partidas: pd.DataFrame, data_corte: pd.Timestamp) -> "ModeloDixonColes":
        """Aprende só com jogos encerrados ANTES da data de corte (sem vazamento)."""
        inicio = data_corte - pd.DateOffset(years=ANOS_DE_TREINO)
        treino = partidas[partidas["encerrado"] & (partidas["data"] < data_corte) & (partidas["data"] >= inicio)]
        pesos = np.array(pb.models.dixon_coles_weights(treino["data"], self.xi, base_date=data_corte), dtype=float)
        # cópias graváveis: no pandas 3 (copy-on-write) to_numpy() pode vir só leitura, e o código compilado
        # do penaltyblog exige arrays graváveis (o erro aparece no Linux)
        self._modelo = pb.models.DixonColesGoalModel(
            np.array(treino["gols_mandante"], dtype=np.int64),
            np.array(treino["gols_visitante"], dtype=np.int64),
            np.array(treino["mandante"], dtype=object),
            np.array(treino["visitante"], dtype=object),
            weights=pesos,
        )
        self._modelo.fit()
        self.times = set(treino["mandante"]) | set(treino["visitante"])
        return self

    def prever(self, mandante: str, visitante: str) -> Previsao:
        grade = np.asarray(self._modelo.predict(mandante, visitante, max_goals=MAX_GOLS).grid, dtype=float)
        return Previsao(mandante, visitante, grade / grade.sum())

    @property
    def parametros(self) -> dict:
        p = self._modelo.get_params()
        return {"mando": float(p["home_advantage"]), "rho": float(p["rho"])}


# ---------- backtest walk-forward para escolher xi ----------

def _resultado(gm: int, gv: int) -> int:
    return 0 if gm > gv else (1 if gm == gv else 2)


def backtest(partidas: pd.DataFrame, xis=XI_CANDIDATOS, temporadas=TEMPORADAS_BACKTEST) -> dict:
    """Para cada semana das temporadas testadas: treina com tudo o que veio antes e prevê a semana.

    Jogos com time sem nenhum jogo no período de treino (recém-promovido sem histórico recente) ficam de fora
    e são contados. Referência mínima: modelo "só mando", com as frequências de vitória/empate/derrota do treino.
    """
    alvo = partidas[partidas["encerrado"] & partidas["temporada"].isin(temporadas)].copy()
    alvo["semana"] = alvo["data"].dt.to_period("W-MON").dt.start_time
    probs = {xi: [] for xi in xis}
    probs["so_mando"] = []
    reais, pulados = [], 0

    for semana, jogos in alvo.groupby("semana"):
        treino = partidas[partidas["encerrado"] & (partidas["data"] < semana)]
        recente = treino[treino["data"] >= semana - pd.DateOffset(years=ANOS_DE_TREINO)]
        freq = np.bincount(
            [_resultado(a, b) for a, b in zip(recente["gols_mandante"], recente["gols_visitante"], strict=True)],
            minlength=3,
        ) / len(recente)
        modelos = {xi: ModeloDixonColes(xi).ajustar(partidas, semana) for xi in xis}
        for j in jogos.itertuples():
            if j.mandante not in modelos[xis[0]].times or j.visitante not in modelos[xis[0]].times:
                pulados += 1
                continue
            reais.append(_resultado(j.gols_mandante, j.gols_visitante))
            probs["so_mando"].append(freq)
            for xi, m in modelos.items():
                p = m.prever(j.mandante, j.visitante)
                probs[xi].append([p.p_mandante, p.p_empate, p.p_visitante])

    y = np.eye(3)[reais]
    metricas = {}
    for nome, lista in probs.items():
        p = np.clip(np.asarray(lista), 1e-12, 1)
        metricas[str(nome)] = {
            "log_loss": round(float(-np.mean(np.log((p * y).sum(axis=1)))), 4),
            "brier": round(float(np.mean(((p - y) ** 2).sum(axis=1))), 4),
        }
    melhor = min(xis, key=lambda xi: metricas[str(xi)]["log_loss"])
    return {
        "temporadas": list(temporadas),
        "jogos_avaliados": len(reais),
        "jogos_pulados_sem_historico": pulados,
        "metricas": metricas,
        "xi_escolhido": melhor,
        "calibracao": _calibracao(np.asarray(probs[melhor]), y),
    }


def _calibracao(p: np.ndarray, y: np.ndarray, faixas: int = 10) -> list[dict]:
    """Probabilidade prevista x frequência real, em faixas de 10 pontos (os três resultados juntos)."""
    prev, real = p.ravel(), y.ravel()
    idx = np.minimum((prev * faixas).astype(int), faixas - 1)
    return [
        {"faixa": f"{k * 10}–{(k + 1) * 10}%", "jogos": int((idx == k).sum()),
         "previsto": round(float(prev[idx == k].mean()), 3), "real": round(float(real[idx == k].mean()), 3)}
        for k in range(faixas) if (idx == k).any()
    ]


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    partidas = pd.read_parquet(DATA_PROCESSED / "partidas.parquet")
    r = backtest(partidas)
    (DATA_PROCESSED / "backtest_modelo1.json").write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Jogos avaliados: {r['jogos_avaliados']} (pulados: {r['jogos_pulados_sem_historico']})")
    for nome, m in r["metricas"].items():
        print(f"  {nome:>9}: log-loss {m['log_loss']:.4f} · Brier {m['brier']:.4f}")
    print(f"xi escolhido: {r['xi_escolhido']}")
    for c in r["calibracao"]:
        print(f"  {c['faixa']:>8}: previsto {c['previsto']:.3f} · real {c['real']:.3f} ({c['jogos']} casos)")


if __name__ == "__main__":
    main()
