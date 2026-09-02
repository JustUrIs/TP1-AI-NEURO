"""
Genera trazas de referencia con el `env.py` original, para verificar el port a
TypeScript.

El port del motor tiene que ser exacto. Si el juego del navegador difiere del
ambiente en el que se entrenaron los agentes, todo lo que muestre la pagina
—el valor de cada jugada, el arrepentimiento, la separacion entre habilidad y
suerte— queda sin sentido, y el error seria silencioso.

En vez de confiar en la lectura, se inyecta un generador de azar guionado en el
ambiente ORIGINAL (sin tocar env.py: solo se reemplaza el atributo `rng`), se
juegan partidas con acciones aleatorias legales —incluyendo cantidades parciales
de SCORE, que son el caso mas facil de portar mal— y se guarda el estado turno a
turno. `check_engine.ts` reproduce las mismas tiradas y las mismas acciones y
compara.

    python gen_trace.py > traces.json
"""

from __future__ import annotations

import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "gold_dice_rl")))

from env import GoldDiceEnv, SCORE, HORIZON  # noqa: E402

N_TRACES = 60


class ScriptedRng:
    """
    Reemplaza a numpy.random.Generator con solo los dos metodos que usa env.py.

    El orden de consumo dentro de un turno es: primero `choice` (la tirada),
    despues `random` (la tormenta).
    """

    def __init__(self, dice_rows, storms):
        self.dice_rows = dice_rows
        self.storms = storms
        self.turn = 0

    def choice(self, faces, size=None, replace=True):
        row = self.dice_rows[self.turn][: int(size)]
        self.turn += 1
        return np.array(row, dtype=np.int64)

    def random(self):
        return 0.0 if self.storms[self.turn - 1] else 0.9


def make_trace(seed: int) -> dict:
    rng = np.random.default_rng(seed)
    # Doce dados por turno alcanzan: el juego optimo no pasa de nueve, y las
    # acciones aleatorias tampoco compran tanto en treinta turnos.
    dice = rng.integers(1, 7, size=(HORIZON, 12)).tolist()
    storms = (rng.random(HORIZON) < 0.15).tolist()

    env = GoldDiceEnv(obs_mode="dict", seed=0, track_history=False)
    env.rng = ScriptedRng(dice, storms)
    obs = env.reset()

    actions, states = [], []
    done = False
    while not done:
        valid = env.get_valid_actions()
        action = int(rng.choice(valid))
        amount = None
        if action == SCORE:
            # Cantidades parciales a proposito: es lo mas facil de portar mal.
            amount = int(rng.integers(0, env.gold + 1))
        actions.append([action, amount])
        obs, _reward, done, info = env.step(action, score_amount=amount)
        states.append(
            {
                "turn": int(info["turn"]),
                "points": int(env.points),
                "gold": int(env.gold),
                "numDice": int(env.num_dice),
                "diceBonus": int(env.dice_bonus),
                "shields": int(env.shields),
                "storm": bool(info["storm"]),
                "stormBlocked": bool(info["storm_blocked"]),
            }
        )

    return {
        "seed": seed,
        "dice": dice,
        "storms": [bool(x) for x in storms],
        "actions": actions,
        "states": states,
        "finalPoints": int(env.points),
    }


if __name__ == "__main__":
    traces = [make_trace(s) for s in range(N_TRACES)]
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "traces.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(traces, fh, separators=(",", ":"))
    total = sum(len(t["states"]) for t in traces)
    print(f"{len(traces)} trazas, {total} turnos -> {out}")
