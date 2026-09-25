"""Checagens 2 a 4 antes de publicar (a checagem 1 fica em checagem1.py)."""

UFMG = {"chance_queda_corinthians": 0.214, "data": "2026-09-22", "fonte": "UFMG, via Exame"}
TOLERANCIA_SOMA_QUEDA = 0.01
TOLERANCIA_SOMA_JOGO = 5e-4  # probabilidades gravadas com 4 casas decimais
LIMITE_DIFERENCA_UFMG = 0.15


def checagem2(chances_queda: dict[str, float]) -> dict:
    """As chances de queda dos 20 times somam 4,00 (4 vagas na zona de queda)."""
    soma = sum(chances_queda.values())
    ok = len(chances_queda) == 20 and abs(soma - 4) <= TOLERANCIA_SOMA_QUEDA
    return {"aprovada": ok, "soma": round(soma, 4), "times": len(chances_queda)}


def checagem3(jogos: list[dict]) -> dict:
    """Vitória + empate + derrota = 100% em cada jogo."""
    ruins = [
        f"{j['mandante']} x {j['visitante']}"
        for j in jogos
        if abs(j["p_mandante"] + j["p_empate"] + j["p_visitante"] - 1) > TOLERANCIA_SOMA_JOGO
    ]
    return {"aprovada": not ruins and bool(jogos), "jogos": len(jogos), "fora_de_100": ruins}


def checagem4(chance_corinthians: float) -> dict:
    """Diferença para a UFMG acima de 15 pontos percentuais exige explicação antes de publicar."""
    diferenca = chance_corinthians - UFMG["chance_queda_corinthians"]
    return {
        "aprovada": abs(diferenca) <= LIMITE_DIFERENCA_UFMG,
        "modelo": round(chance_corinthians, 4),
        "ufmg": UFMG["chance_queda_corinthians"],
        "diferenca_pp": round(100 * diferenca, 1),
        "referencia": UFMG,
    }
