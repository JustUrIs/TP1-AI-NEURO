"""
Empaqueta los agentes y el oraculo en un solo archivo .js.

El juego tiene que andar de dos maneras: subido a un servidor, y abierto con
doble clic desde el disco. Lo segundo prohibe `fetch`, asi que los datos no
pueden ser archivos aparte: van embebidos en base64 dentro de un .js que se
carga con <script src>, que si funciona desde file://.

Para que no pese de mas:
  * el agente principal va disperso (solo las casillas que aprendio algo),
  * los tabulares guardan su orden de preferencia entre las siete jugadas mas
    las dos mejores valuaciones, que es lo que hace falta para jugar igual que
    en Python y para explicar la eleccion,
  * el oraculo usa una grilla de oro mas rala, porque su valor es casi una
    recta y interpolar apenas cuesta precision.

    python export_game.py
"""

from __future__ import annotations

import base64
import gzip
import json
import os
import pickle

import numpy as np

import oracle_dp as O
from value_table import ValueTable

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.abspath(os.path.join(HERE, "..", "juego"))

N_LO, N_HI = 1, 9
B_LO, B_HI = 0, 8
S_LO, S_HI = 0, 3
T_MAX = 30


def oracle_gold_nodes() -> list[int]:
    """Grilla del oraculo: fina donde estan los precios, rala donde no pasa nada."""
    nodes = list(range(0, 97, 2))          # 0..96 de a 2
    nodes += list(range(104, 201, 12))     # 104..200
    nodes += list(range(224, 401, 32))     # 224..400
    nodes += list(range(464, 897, 72))     # 464..896
    return nodes


def b64(arr: np.ndarray) -> str:
    return base64.b64encode(arr.tobytes()).decode("ascii")


def export_champion(pkl: str) -> dict:
    """Disperso: solo las casillas donde la tabla aprendio algo."""
    table = ValueTable.load(os.path.join(HERE, "artifacts", pkl))
    keys, vals = [], []
    for (t, node, n, b, s), (residual, _v) in sorted(table.theta.items()):
        if not (1 <= t <= T_MAX and N_LO <= n <= N_HI and B_LO <= b <= B_HI and S_LO <= s <= S_HI):
            continue
        # Los cinco indices entran holgados en 32 bits.
        keys.append(((t - 1) * 128 + node) * 400 + ((n - N_LO) * 9 + (b - B_LO)) * 4 + (s - S_LO))
        vals.append(residual)
    order = np.argsort(keys)
    return {
        "kind": "champion",
        "keys": b64(np.array(keys, dtype="<u4")[order]),
        "vals": b64(np.clip(np.round(np.array(vals)[order] * 100), -32768, 32767).astype("<i2")),
        "count": len(keys),
        "scale": 100,
        "nodes": table.gold_nodes,
    }


def export_tabular(pkl: str) -> dict:
    """
    De cada estado guardamos el ORDEN de preferencia de las siete jugadas y las
    dos mejores valuaciones.

    Guardar solo la mejor no alcanza: si esa jugada no es legal en el momento
    (no te alcanza el oro), Python elige la mejor de las que si podes hacer. Con
    el orden completo se reproduce esa eleccion exactamente.
    """
    blob = pickle.load(open(os.path.join(HERE, "artifacts", pkl), "rb"))
    q, preset, score_space = blob["q"], blob["preset"], blob["score_space"]
    from train_tabular_classic import PRESETS

    keys, orden, top2 = [], [], []
    for state in sorted(q):
        tl, gold, dice, bonus, shield = state
        keys.append((((tl * 256 + gold) * 16 + dice) * 16 + bonus) * 8 + shield)
        values = q[state]
        # `stable` para que los empates queden en orden de accion, igual que el
        # max() de Python sobre la lista de acciones.
        preferencia = np.argsort(-values, kind="stable")
        orden.append(preferencia)
        top2.append([values[preferencia[0]], values[preferencia[1]]])

    return {
        "kind": "tabular",
        "keys": b64(np.array(keys, dtype="<u4")),
        "order": b64(np.array(orden, dtype="<u1").ravel()),
        "top2": b64(np.clip(np.round(np.array(top2) * 64), -32768, 32767).astype("<i2").ravel()),
        "count": len(keys),
        "scale": 64,
        "preset": PRESETS[preset],
        "score_space": score_space,
    }


def export_oracle() -> dict:
    U = O.get()
    nodes = oracle_gold_nodes()
    idx = np.minimum(np.array(nodes), O.GMAX)
    shape = (T_MAX, N_HI - N_LO + 1, B_HI - B_LO + 1, S_HI - S_LO + 1, len(nodes))
    dense = np.zeros(shape, dtype=np.float32)
    for t in range(1, T_MAX + 1):
        for n in range(N_LO, N_HI + 1):
            for b in range(B_LO, B_HI + 1):
                for s in range(S_LO, S_HI + 1):
                    dense[t - 1, n - N_LO, b - B_LO, s - S_LO] = U[t, n, b, s][idx]
    return {
        "kind": "oracle",
        "data": b64(np.clip(np.round(dense * 8), -32768, 32767).astype("<i2")),
        "scale": 8,
        "nodes": nodes,
        "optimal": float(U[1, 1, 0, 0, 0]),
    }


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    bundle = {
        "optimal": 642.452,
        "agents": [
            {"id": "campeon", "label": "Campeón", "algo": "TD sobre afterstates con dos tablas",
             "mean": 527.06, **export_champion("gold_dice_agent.pkl")},
            {"id": "aprendiz", "label": "Aprendiz", "algo": "Q-Learning tabular, rangos amplios",
             "mean": 364.21, **export_tabular("classic_D_wide_g1_scoreall.pkl")},
            {"id": "novato", "label": "Novato", "algo": "Q-Learning tabular, topes chicos",
             "mean": 314.58, **export_tabular("classic_A_tight_g995.pkl")},
        ],
        "oracle": {"label": "Juego perfecto", "mean": 644.10, **export_oracle()},
    }

    payload = json.dumps(bundle, ensure_ascii=False, separators=(",", ":"))
    path = os.path.join(OUT, "data.js")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("// Generado por gold_dice_rl/export_game.py. No editar a mano.\n")
        fh.write("window.GOLD_DICE_DATA = ")
        fh.write(payload)
        fh.write(";\n")

    raw = os.path.getsize(path)
    packed = len(gzip.compress(payload.encode(), 6))
    print(f"{path}")
    print(f"  {raw / 1e6:.2f} MB en disco, {packed / 1e6:.2f} MB comprimido")
    for a in bundle["agents"]:
        print(f"  {a['id']:<10} {a['count']:>7,} estados")
