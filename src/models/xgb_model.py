"""Modelo 2: XGBoost de time, multiclasse (vitória do mandante / empate / vitória do visitante).

Três versões, que o backtest compara (src.models.ensemble):
- base:     Elo, desempenho em casa e fora, pontos nos últimos 5 jogos, descanso (treina de 2012 em diante)
- no_alvo:  base + finalizações no alvo criadas e cedidas nos últimos 5 e 10 jogos (de 2017 em diante)
- xg:       base + xG e finalizações dentro da área, criados e cedidos (de 2023 em diante)
"""

import numpy as np
import pandas as pd
import xgboost as xgb

BASE = ["elo_m", "elo_v", "elo_diff", "pts_casa5_m", "sg_casa5_m", "pts_fora5_v", "sg_fora5_v",
        "pts5_m", "pts5_v", "descanso_m", "descanso_v"]


def _chances(stat: str) -> list[str]:
    return [f"{stat}_{tipo}{n}_{lado}" for tipo in ("pro", "contra") for n in (5, 10) for lado in ("m", "v")]


VERSOES = {
    "base": {"variaveis": BASE, "desde": 2012},
    "no_alvo": {"variaveis": BASE + _chances("no_alvo"), "desde": 2017},
    "xg": {"variaveis": BASE + _chances("xg") + _chances("area"), "desde": 2023},
}

PARAMETROS = {  # escolha manual e conservadora: árvores rasas e aprendizado lento, para pouca amostra
    "objective": "multi:softprob", "num_class": 3, "n_estimators": 250, "max_depth": 3, "learning_rate": 0.04,
    "subsample": 0.8, "colsample_bytree": 0.8, "min_child_weight": 10, "reg_lambda": 2.0, "eval_metric": "mlogloss",
    "tree_method": "hist", "random_state": 2026, "n_jobs": 4,
}


def resultado(gm, gv) -> np.ndarray:
    gm, gv = np.asarray(gm, dtype=int), np.asarray(gv, dtype=int)
    return np.where(gm > gv, 0, np.where(gm == gv, 1, 2))


class ModeloXGB:
    def __init__(self, versao: str):
        self.versao = versao
        self.variaveis = VERSOES[versao]["variaveis"]
        self.desde = VERSOES[versao]["desde"]
        self._modelo = None

    def linhas_de_treino(self, v: pd.DataFrame, data_corte: pd.Timestamp) -> pd.DataFrame:
        """Jogos encerrados antes da data de corte, na janela da versão, com as chances criadas disponíveis."""
        t = v[v["encerrado"] & (v["data"] < data_corte) & (v["temporada"] >= self.desde)]
        if self.versao != "base":
            t = t.dropna(subset=[self.variaveis[-1]])  # a média de 10 jogos exige histórico mínimo do dado
        return t

    def ajustar(self, v: pd.DataFrame, data_corte: pd.Timestamp) -> "ModeloXGB":
        t = self.linhas_de_treino(v, data_corte)
        self._modelo = xgb.XGBClassifier(**PARAMETROS)
        self._modelo.fit(t[self.variaveis], resultado(t["gols_mandante"], t["gols_visitante"]))
        self.n_treino = len(t)
        return self

    def prever(self, linhas: pd.DataFrame) -> np.ndarray:
        """Probabilidades [mandante, empate, visitante] para cada linha."""
        return self._modelo.predict_proba(linhas[self.variaveis])

    def importancia(self) -> dict[str, float]:
        ganho = self._modelo.get_booster().get_score(importance_type="gain")
        total = sum(ganho.values()) or 1
        return {k: round(v / total, 3) for k, v in sorted(ganho.items(), key=lambda x: -x[1])}
