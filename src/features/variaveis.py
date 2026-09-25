"""Variáveis do Modelo 2, uma linha por jogo, calculadas só com jogos ANTERIORES (sem vazamento).

Rodar da raiz:  python -m src.features.variaveis   (gera data/processed/variaveis.parquet)

Para cada jogo, do ponto de vista do mandante (_m) e do visitante (_v):
- Elo antes do jogo;
- desempenho em casa do mandante e fora do visitante (pontos por jogo e saldo nos últimos 5 jogos naquele mando);
- pontos por jogo nos últimos 5 jogos (qualquer mando);
- dias de descanso desde o jogo anterior na Série A (limitado a 14; não vemos Copa do Brasil nem torneios continentais);
- chances criadas e cedidas nos últimos 5 e 10 jogos com o dado: xG, finalizações no alvo e dentro da área.

Os jogos ainda não disputados (depois da 28ª rodada) recebem as variáveis congeladas no estado após a 28ª rodada;
só os dias de descanso usam o calendário, que já é conhecido.
"""

import sys
from collections import defaultdict, deque

import numpy as np
import pandas as pd

from src.config import DATA_PROCESSED, RAIZ
from src.ingest import api_football, historico
from src.ingest.times import padronizar

ELO_INICIAL = 1500
ELO_NOVATO = 1450          # time sem nenhum jogo anterior na base
ELO_K = 20
ELO_MANDO = 60             # vantagem de jogar em casa, em pontos de Elo, só para o resultado esperado
ELO_REGRESSAO = 0.2        # a cada temporada, 20% do caminho de volta à média
DESCANSO_MAX = 14
STATS = ("xg", "no_alvo", "area")


# ---------- estatísticas por jogo (API-Football de 2022 em diante; histórico de 2017 a 2021) ----------

def estatisticas_por_jogo() -> pd.DataFrame:
    """Uma linha por jogo: xG, finalizações no alvo e dentro da área de cada lado (NaN quando não há)."""
    partes = []
    for ano in range(2022, 2027):
        if not (api_football.PASTA / f"partidas_{ano}.json").exists():
            continue
        t = api_football.tabela_estatisticas(ano)
        partes.append(pd.DataFrame({
            "temporada": t["temporada"], "mandante": t["mandante"], "visitante": t["visitante"],
            "xg_m": t["xg_mandante"], "xg_v": t["xg_visitante"],
            "no_alvo_m": t["no_alvo_mandante"], "no_alvo_v": t["no_alvo_visitante"],
            "area_m": t["dentro_area_mandante"], "area_v": t["dentro_area_visitante"],
        }))

    jogos = historico.carregar("partidas")
    stats = historico.carregar("estatisticas").merge(
        jogos[["ID", "temporada", "mandante", "visitante"]], left_on="partida_id", right_on="ID")
    stats = stats[stats["temporada"].between(2017, 2021)]
    # a base histórica usa 0 no lugar de "sem dado": jogo sem finalização no alvo dos dois lados = sem dado
    lado_m = stats[stats["clube"] == stats["mandante"]].set_index("partida_id")
    lado_v = stats[stats["clube"] == stats["visitante"]].set_index("partida_id")
    h = lado_m[["temporada", "mandante", "visitante"]].join(
        lado_m["chutes_no_alvo"].rename("no_alvo_m")).join(lado_v["chutes_no_alvo"].rename("no_alvo_v"))
    h = h[(h["no_alvo_m"].fillna(0) + h["no_alvo_v"].fillna(0)) > 0]
    h["mandante"] = padronizar(h["mandante"], "historico")
    h["visitante"] = padronizar(h["visitante"], "historico")
    partes.append(h.reset_index(drop=True).assign(xg_m=np.nan, xg_v=np.nan, area_m=np.nan, area_v=np.nan))
    return pd.concat(partes, ignore_index=True)


# ---------- Elo ----------

def _multiplicador_gols(saldo: int) -> float:
    saldo = abs(saldo)
    return 1.0 if saldo <= 1 else 1.5 if saldo == 2 else (11 + saldo) / 8


class Elo:
    def __init__(self):
        self.nota: dict[str, float] = {}
        self.temporada: dict[str, int] = {}

    def antes_do_jogo(self, time: str, temporada: int) -> float:
        if time not in self.nota:
            self.nota[time] = ELO_NOVATO
        elif self.temporada[time] != temporada:  # primeira partida do time na temporada
            ausente = temporada - self.temporada[time] > 1  # voltou da Série B
            fator = 0.5 if ausente else ELO_REGRESSAO
            alvo = ELO_NOVATO if ausente else ELO_INICIAL
            self.nota[time] += fator * (alvo - self.nota[time])
        self.temporada[time] = temporada
        return self.nota[time]

    def atualizar(self, m: str, v: str, gm: int, gv: int) -> None:
        esperado_m = 1 / (1 + 10 ** ((self.nota[v] - self.nota[m] - ELO_MANDO) / 400))
        real_m = 1.0 if gm > gv else 0.5 if gm == gv else 0.0
        delta = ELO_K * _multiplicador_gols(gm - gv) * (real_m - esperado_m)
        self.nota[m] += delta
        self.nota[v] -= delta


# ---------- montagem ----------

def _media(fila, n):
    ultimos = list(fila)[-n:]
    return float(np.mean(ultimos)) if ultimos else np.nan


def montar(partidas: pd.DataFrame, estatisticas: pd.DataFrame) -> pd.DataFrame:
    chave = ["temporada", "mandante", "visitante"]
    jogos = partidas.merge(estatisticas, on=chave, how="left", validate="one_to_one")
    jogos = jogos.sort_values(["data", "mandante"], na_position="last", kind="stable").reset_index(drop=True)

    elo = Elo()
    pts_geral = defaultdict(lambda: deque(maxlen=5))
    pts_casa = defaultdict(lambda: deque(maxlen=5))
    sg_casa = defaultdict(lambda: deque(maxlen=5))
    pts_fora = defaultdict(lambda: deque(maxlen=5))
    sg_fora = defaultdict(lambda: deque(maxlen=5))
    criadas = {s: defaultdict(lambda: deque(maxlen=10)) for s in STATS}
    cedidas = {s: defaultdict(lambda: deque(maxlen=10)) for s in STATS}
    ultimo_jogo: dict[str, pd.Timestamp] = {}

    linhas = []
    for j in jogos.itertuples(index=False):
        m, v = j.mandante, j.visitante
        linha = {"elo_m": elo.antes_do_jogo(m, j.temporada), "elo_v": elo.antes_do_jogo(v, j.temporada)}
        linha["elo_diff"] = linha["elo_m"] - linha["elo_v"]
        linha |= {
            "pts_casa5_m": _media(pts_casa[m], 5), "sg_casa5_m": _media(sg_casa[m], 5),
            "pts_fora5_v": _media(pts_fora[v], 5), "sg_fora5_v": _media(sg_fora[v], 5),
            "pts5_m": _media(pts_geral[m], 5), "pts5_v": _media(pts_geral[v], 5),
        }
        for lado, time in (("m", m), ("v", v)):
            anterior = ultimo_jogo.get(time)
            dias = (j.data - anterior).days if anterior is not None and pd.notna(j.data) else np.nan
            linha[f"descanso_{lado}"] = min(dias, DESCANSO_MAX) if pd.notna(dias) else DESCANSO_MAX
            for s in STATS:
                for n in (5, 10):
                    linha[f"{s}_pro{n}_{lado}"] = _media(criadas[s][time], n)
                    linha[f"{s}_contra{n}_{lado}"] = _media(cedidas[s][time], n)
        linhas.append(linha)

        if pd.notna(j.data):
            ultimo_jogo[m] = ultimo_jogo[v] = j.data  # o calendário é conhecido, mesmo para jogos futuros
        if not j.encerrado:
            continue  # jogos futuros: o resto do estado fica congelado após a 28ª rodada

        gm, gv = int(j.gols_mandante), int(j.gols_visitante)
        elo.atualizar(m, v, gm, gv)
        pm = 3 if gm > gv else 1 if gm == gv else 0
        pv = 3 if gv > gm else 1 if gm == gv else 0
        pts_geral[m].append(pm)
        pts_geral[v].append(pv)
        pts_casa[m].append(pm)
        sg_casa[m].append(gm - gv)
        pts_fora[v].append(pv)
        sg_fora[v].append(gv - gm)
        for s in STATS:
            vm, vv = getattr(j, f"{s}_m"), getattr(j, f"{s}_v")
            if pd.notna(vm) and pd.notna(vv):
                criadas[s][m].append(vm)
                cedidas[s][m].append(vv)
                criadas[s][v].append(vv)
                cedidas[s][v].append(vm)

    return pd.concat([jogos[["temporada", "data", "rodada", "mandante", "visitante", "gols_mandante",
                             "gols_visitante", "encerrado"]], pd.DataFrame(linhas)], axis=1)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    partidas = pd.read_parquet(DATA_PROCESSED / "partidas.parquet")
    v = montar(partidas, estatisticas_por_jogo())
    saida = DATA_PROCESSED / "variaveis.parquet"
    v.to_parquet(saida, index=False)
    cobertura = v.groupby("temporada")[["xg_pro5_m", "no_alvo_pro5_m", "area_pro5_m"]].apply(lambda g: g.notna().mean())
    print(f"{len(v)} jogos · {v.shape[1]} colunas → {saida.relative_to(RAIZ)}")
    print("Jogos com a média de chances dos últimos 5 jogos disponível (por temporada):")
    print((100 * cobertura.tail(10)).round(0).to_string())


if __name__ == "__main__":
    main()
