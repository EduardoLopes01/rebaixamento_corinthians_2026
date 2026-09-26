"""Registra a previsão da pausa: predictions/AAAA-MM-DD_pausa.json, um snapshot único, nunca editado.

É a base do post-mortem do fim do campeonato (02/12). Guarda a previsão exatamente como está no site
(site/data/previsao.json) e um cabeçalho de registro com a impressão digital (SHA-256) desse arquivo: quem
quiser confere que o site mostra os mesmos números. A data vem do commit e da Release no GitHub.

Rodar da raiz, uma única vez, depois das checagens 1 a 4:
    python -m src.publish.registro
"""

import hashlib
import json
import sys
from datetime import datetime

from src.config import FUSO, RAIZ, SITE_DATA

PASTA = RAIZ / "predictions"


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    existentes = sorted(PASTA.glob("*_pausa.json"))
    if existentes:
        raise RuntimeError(f"já existe um snapshot ({existentes[0].name}); ele nunca é editado nem refeito")
    arquivo_site = SITE_DATA / "previsao.json"
    conteudo = arquivo_site.read_bytes()
    previsao = json.loads(conteudo)
    if not all(previsao["checagens"].values()):
        raise RuntimeError(f"checagem reprovada, não registro: {previsao['checagens']}")

    agora = datetime.now(FUSO)
    registro = {
        "o_que_e": "Previsão única feita na pausa da Data Fifa, antes da volta do Brasileirão 2026. "
                   "Nunca editada: base do post-mortem do fim do campeonato.",
        "registrado_em": agora.isoformat(timespec="seconds"),
        "dados_ate": previsao["dados"]["ate"],
        "rodada": previsao["dados"]["rodada"],
        "jogos_previstos": previsao["dados"]["jogos_restantes"],
        "simulacoes": previsao["dados"]["simulacoes"],
        "chance_queda_corinthians": previsao["corinthians"]["chance_queda"],
        "arquivo_do_site": arquivo_site.relative_to(RAIZ).as_posix(),
        "sha256_do_arquivo_do_site": hashlib.sha256(conteudo).hexdigest(),
        "checagens": previsao["checagens"],
    }
    PASTA.mkdir(exist_ok=True)
    destino = PASTA / f"{agora:%Y-%m-%d}_pausa.json"
    destino.write_text(json.dumps({"registro": registro, "previsao": previsao}, ensure_ascii=False, indent=1) + "\n",
                       encoding="utf-8", newline="\n")
    print(f"{destino.relative_to(RAIZ).as_posix()}: chance de queda do Corinthians "
          f"{100 * registro['chance_queda_corinthians']:.1f}%, sha256 do site {registro['sha256_do_arquivo_do_site'][:16]}…")


if __name__ == "__main__":
    main()
