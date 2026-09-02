"""
Exporta los modelos y el oraculo a binarios que el navegador lee sin servidor.

Todo va como int16 con escala: los valores estan en las centenas y las
decisiones difieren en unidades, asi que 0.125 de precision sobra. Los arreglos
son densos porque se indexan con aritmetica y comprimen bien (gzip los deja en
1.9 MB entre todos). El oro usa la misma grilla no uniforme que el agente.
"""

from __future__ import annotations

import gzip
import json
import os
import pickle

import numpy as np

import oracle_dp as O
from afterstate import build_gold_nodes
from value_table import ValueTable

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.abspath(os.path.join(HERE, "..", "web", "public", "models"))

# Rangos que se exportan. Salen de medir que visita el juego optimo
# (docs/01_REGLAS_OCULTAS.md 8-bis): dados hasta 9, bonus hasta 8, escudos
# rara vez mas de 1. Por encima el cliente satura, igual que el agente.
T_MAX = 30
N_LO, N_HI = 1, 9
B_LO, B_HI = 0, 8
S_LO, S_HI = 0, 3

SCALE_AGENT = 100.0     # residuo: rango medido [-10.4, 83.2]
SCALE_ORACLE = 8.0      # valores: hasta ~4200 en estados inalcanzables


def _q(arr: np.ndarray, scale: float) -> np.ndarray:
    return np.clip(np.round(arr * scale), -32768, 32767).astype("<i2")


def _write(name: str, data: np.ndarray) -> dict:
    os.makedirs(OUT, exist_ok=True)
    raw = data.tobytes()
    path = os.path.join(OUT, name)
    with open(path, "wb") as fh:
        fh.write(raw)
    packed = len(gzip.compress(raw, 6))
    print(f"  {name:<22} {len(raw) / 1e6:6.2f} MB   gzip {packed / 1e6:5.2f} MB")
    return {"file": name, "bytes": len(raw), "gzip": packed}


# --------------------------------------------------------------------------
# Agente por afterstates
# --------------------------------------------------------------------------
def export_afterstate(pkl: str, name: str) -> dict:
    table = ValueTable.load(os.path.join(HERE, "artifacts", pkl))
    nodes = table.gold_nodes
    n_nodes = len(nodes)
    shape = (T_MAX, n_nodes, N_HI - N_LO + 1, B_HI - B_LO + 1, S_HI - S_LO + 1)
    dense = np.zeros(shape, dtype=np.float32)

    for (t, node, n, b, s), (residual, _visits) in table.theta.items():
        if not (1 <= t <= T_MAX and 0 <= node < n_nodes):
            continue
        if not (N_LO <= n <= N_HI and B_LO <= b <= B_HI and S_LO <= s <= S_HI):
            continue
        dense[t - 1, node, n - N_LO, b - B_LO, s - S_LO] = residual

    meta = _write(f"{name}.bin", _q(dense, SCALE_AGENT))
    meta.update(
        kind="afterstate", scale=SCALE_AGENT, gold_nodes=nodes,
        dims=dict(t=T_MAX, node=n_nodes, n=[N_LO, N_HI], b=[B_LO, B_HI], s=[S_LO, S_HI]),
    )
    return meta


# --------------------------------------------------------------------------
# Agentes Q tabulares clasicos (las ablaciones, que sirven como rivales de
# distinto nivel)
# --------------------------------------------------------------------------
def export_tabular(pkl: str, name: str) -> dict:
    from train_tabular_classic import PRESETS

    blob = pickle.load(open(os.path.join(HERE, "artifacts", pkl), "rb"))
    q, preset, score_space = blob["q"], blob["preset"], blob["score_space"]
    p = PRESETS[preset]

    keys = sorted(q.keys())
    index = np.array(keys, dtype="<i2")                       # (m, 5)
    # Escala 64: los Q llegan a 399 (64*399 = 25536, entra en int16) y la
    # precision queda en 0.016. Con escala 10 el redondeo borraba brechas de
    # 0.03-0.1 entre la mejor accion y la segunda, y el agente del navegador
    # elegia distinto que el de Python en el 0.4% de los estados.
    values = _q(np.array([q[k] for k in keys], dtype=np.float32), 64.0)   # (m, 7)

    meta_i = _write(f"{name}_keys.bin", index)
    meta_v = _write(f"{name}_vals.bin", values)
    return {
        "kind": "tabular",
        "keys": meta_i["file"],
        "vals": meta_v["file"],
        "bytes": meta_i["bytes"] + meta_v["bytes"],
        "gzip": meta_i["gzip"] + meta_v["gzip"],
        "count": len(keys),
        "scale": 64.0,
        "preset": p,
        "score_space": score_space,
    }


# --------------------------------------------------------------------------
# Oraculo
# --------------------------------------------------------------------------
def export_oracle(name: str = "oracle") -> dict:
    U = O.get()
    nodes = build_gold_nodes("coarse")
    idx = np.array(nodes)
    idx = np.minimum(idx, O.GMAX)

    shape = (T_MAX, N_HI - N_LO + 1, B_HI - B_LO + 1, S_HI - S_LO + 1, len(nodes))
    dense = np.zeros(shape, dtype=np.float32)
    for t in range(1, T_MAX + 1):
        for n in range(N_LO, N_HI + 1):
            for b in range(B_LO, B_HI + 1):
                for s in range(S_LO, S_HI + 1):
                    dense[t - 1, n - N_LO, b - B_LO, s - S_LO] = U[t, n, b, s][idx]

    meta = _write(f"{name}.bin", _q(dense, SCALE_ORACLE))
    meta.update(
        kind="oracle", scale=SCALE_ORACLE, gold_nodes=nodes,
        dims=dict(t=T_MAX, n=[N_LO, N_HI], b=[B_LO, B_HI], s=[S_LO, S_HI], node=len(nodes)),
        optimal=float(U[1, 1, 0, 0, 0]),
    )
    return meta


if __name__ == "__main__":
    print("exportando a", OUT)
    manifest = {
        "optimal": 642.452,
        "agents": {
            "campeon": {
                "label": "Campeón",
                "algo": "Double TD sobre afterstates",
                "mean": 527.06,
                "pct": 82.0,
                **export_afterstate("gold_dice_agent.pkl", "campeon"),
            },
            "aprendiz": {
                "label": "Aprendiz",
                "algo": "Q-Learning tabular, rangos amplios",
                "mean": 364.21,
                "pct": 56.7,
                **export_tabular("classic_D_wide_g1_scoreall.pkl", "aprendiz"),
            },
            "novato": {
                "label": "Novato",
                "algo": "Q-Learning tabular, topes chicos",
                "mean": 314.58,
                "pct": 49.0,
                **export_tabular("classic_A_tight_g995.pkl", "novato"),
            },
        },
        "oracle": {"label": "Juego perfecto", "mean": 644.10, "pct": 100.0, **export_oracle()},
    }
    with open(os.path.join(OUT, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, separators=(",", ":"))
    total = sum(a["gzip"] for a in manifest["agents"].values()) + manifest["oracle"]["gzip"]
    print(f"\n  total comprimido: {total / 1e6:.2f} MB")
