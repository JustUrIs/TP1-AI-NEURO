"""
Muestrea estados y guarda la jugada de cada agente Python.

`check_policy.ts` compara contra los binarios exportados. Es la prueba que un
click no da: un stride mal calculado en el export haria que el Campeon juegue
distinto en el navegador que en Python, sin error y sin que se note.

    python gen_policy_probe.py
"""

from __future__ import annotations

import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "gold_dice_rl")))

from agents import GoldDiceAgent  # noqa: E402
from env import GoldDiceEnv, SCORE  # noqa: E402
from train_tabular_classic import TabularQAgent  # noqa: E402

ART = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "gold_dice_rl", "artifacts"))
N_GAMES = 220


def probe() -> list[dict]:
    """
    Estados de partidas jugadas con una mezcla de politica del agente y ruido:
    asi la muestra cubre tanto la trayectoria buena como estados raros donde un
    error de indice tendria mas chances de aparecer.
    """
    rng = np.random.default_rng(11)
    champion = GoldDiceAgent(os.path.join(ART, "gold_dice_agent.pkl"))
    agents = {
        "campeon": champion,
        "aprendiz": TabularQAgent(os.path.join(ART, "classic_D_wide_g1_scoreall.pkl")),
        "novato": TabularQAgent(os.path.join(ART, "classic_A_tight_g995.pkl")),
    }

    rows = []
    for ep in range(N_GAMES):
        seed = 700_000_000 + ep
        env = GoldDiceEnv(obs_mode="dict", seed=seed, track_history=False)
        obs = env.reset(seed=seed)
        done = False
        while not done:
            rows.append(
                {
                    "obs": {k: int(v) for k, v in obs.items()},
                    "moves": {
                        name: [int(a), None if amt is None else int(amt)]
                        for name, (a, amt) in ((n, ag.act(obs, env)) for n, ag in agents.items())
                    },
                }
            )
            if rng.random() < 0.35:
                valid = env.get_valid_actions()
                action = int(rng.choice(valid))
                amount = int(rng.integers(0, env.gold + 1)) if action == SCORE else None
            else:
                action, amount = champion.act(obs, env)
            obs, _r, done, _i = env.step(action, score_amount=amount)
    return rows


if __name__ == "__main__":
    rows = probe()
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sonda.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(rows, fh, separators=(",", ":"))
    print(f"{len(rows)} estados -> {out}")
