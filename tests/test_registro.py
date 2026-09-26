"""O site mostra exatamente a previsão registrada no snapshot da pausa (predictions/)."""

import hashlib
import json

from src.config import SITE_DATA
from src.publish.registro import PASTA


def test_um_unico_snapshot_e_o_site_bate_com_ele():
    snapshots = sorted(PASTA.glob("*_pausa.json"))
    assert len(snapshots) == 1, snapshots
    registrado = json.loads(snapshots[0].read_text(encoding="utf-8"))
    site = (SITE_DATA / "previsao.json").read_bytes()
    assert hashlib.sha256(site).hexdigest() == registrado["registro"]["sha256_do_arquivo_do_site"]
    assert registrado["previsao"] == json.loads(site)
    assert all(registrado["registro"]["checagens"].values())
