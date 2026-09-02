"""
Q-Learning tabular "de manual". Es la ablacion, no un intento de ganar.

Reproduce la receta estandar (estado discretizado con topes, SCORE colapsada en
{todo, mitad}, gamma < 1) para poder medir cuanto cuesta cada decision de
modelado con el mismo presupuesto de episodios que el agente principal. Las
banderas --preset, --gamma y --score-space encienden y apagan una por vez.
"""

from __future__ import annotations

import argparse
import os
import pickle
import time
from collections import defaultdict

import numpy as np

from config import HORIZON, SHIELD_COST, STORE_DIE_COST, get_new_dice_cost, get_upgrade_cost
from env import GoldDiceEnv, PASS, SCORE, BUY_DICE, UPGRADE, BUY_SHIELD, STORE_BEST_DIE
from evaluate import TRAIN_SEED_BASE, evaluate, OPTIMAL

ARTIFACT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "artifacts")

# Espacio de acciones envuelto: SCORE parametrica no entra en una tabla Q.
Q_PASS, Q_SCORE_ALL, Q_SCORE_HALF, Q_BUY_DICE, Q_UPGRADE, Q_BUY_SHIELD, Q_STORE = range(7)
N_Q_ACTIONS = 7


# --------------------------------------------------------------------------
# Discretizaciones. "tight" son los topes tipicos; "wide" es la misma receta
# pero con rangos que si cubren lo que visita el juego optimo.
# --------------------------------------------------------------------------
PRESETS = {
    # Topes tipicos. El juego optimo llega a 9 dados, bonus 8 y 797 de oro
    # (docs/01_REGLAS_OCULTAS.md 8-bis): todo eso cae en la ultima celda.
    "tight": dict(gold_width=6, gold_cap=240, dice_cap=5, bonus_cap=4, shield_cap=2, turn_width=2),
    # Misma receta tabular, rangos honestos.
    "wide": dict(gold_width=4, gold_cap=800, dice_cap=9, bonus_cap=8, shield_cap=3, turn_width=1),
}


def make_discretizer(preset: str):
    p = PRESETS[preset]

    def discretize(obs):
        turns_left = HORIZON - obs["turn"]
        # El ultimo turno va en su propio bucket: ahi el oro se evapora y el
        # comportamiento correcto es cualitativamente distinto.
        tl_bin = 0 if turns_left == 0 else 1 + (turns_left - 1) // p["turn_width"]
        return (
            tl_bin,
            min(int(obs["gold"]), p["gold_cap"]) // p["gold_width"],
            min(int(obs["num_dice"]), p["dice_cap"]),
            min(int(obs["dice_bonus"]), p["bonus_cap"]),
            min(int(obs["shields"]), p["shield_cap"]),
        )

    return discretize


def valid_q_actions(obs, score_space: str = "all_half"):
    gold = obs["gold"]
    out = [Q_PASS, Q_SCORE_ALL]
    if score_space == "all_half":
        out.append(Q_SCORE_HALF)
    if gold >= get_new_dice_cost(obs["num_dice"]):
        out.append(Q_BUY_DICE)
    if gold >= get_upgrade_cost(obs["dice_bonus"]):
        out.append(Q_UPGRADE)
    if gold >= SHIELD_COST:
        out.append(Q_BUY_SHIELD)
    if gold >= STORE_DIE_COST and obs["roll_max"] > 0:
        out.append(Q_STORE)
    return out


def to_env_action(q_action, obs):
    gold = int(obs["gold"])
    return {
        Q_PASS: (PASS, None),
        Q_SCORE_ALL: (SCORE, gold),
        Q_SCORE_HALF: (SCORE, gold // 2),
        Q_BUY_DICE: (BUY_DICE, None),
        Q_UPGRADE: (UPGRADE, None),
        Q_BUY_SHIELD: (BUY_SHIELD, None),
        Q_STORE: (STORE_BEST_DIE, None),
    }[q_action]


class TabularQAgent:
    def __init__(self, q_table, preset: str = "tight", score_space: str = "all_half"):
        if isinstance(q_table, str):
            with open(q_table, "rb") as fh:
                blob = pickle.load(fh)
            q_table, preset, score_space = blob["q"], blob["preset"], blob["score_space"]
        self.q = q_table
        self.discretize = make_discretizer(preset)
        self.score_space = score_space

    def act(self, obs, env=None):
        actions = valid_q_actions(obs, self.score_space)
        values = self.q.get(self.discretize(obs))
        if values is None:
            best = actions[0]
        else:
            best = max(actions, key=lambda a: values[a])
        return to_env_action(best, obs)


def train(
    n_episodes: int = 400_000,
    preset: str = "tight",
    score_space: str = "all_half",
    gamma: float = 0.995,
    alpha: float = 0.15,
    eps_start: float = 1.0,
    eps_end: float = 0.03,
    eps_frac: float = 0.70,
    optimistic: float = 150.0,
    eval_every: int = 50_000,
    eval_episodes: int = 2_000,
    seed: int = 7,
    path: str | None = None,
    verbose: bool = True,
):
    rng = np.random.default_rng(seed)
    discretize = make_discretizer(preset)
    q = defaultdict(lambda: np.full(N_Q_ACTIONS, optimistic, dtype=np.float64))
    env = GoldDiceEnv(obs_mode="dict", track_history=False)

    decay_until = max(1, int(eps_frac * n_episodes))
    started = time.time()

    for episode in range(n_episodes):
        eps = eps_start + min(1.0, episode / decay_until) * (eps_end - eps_start)
        obs = env.reset(seed=TRAIN_SEED_BASE + episode)
        done = False

        while not done:
            state = discretize(obs)
            actions = valid_q_actions(obs, score_space)
            if rng.random() < eps:
                a = actions[int(rng.integers(len(actions)))]
            else:
                a = max(actions, key=lambda x: q[state][x])

            env_action, amount = to_env_action(a, obs)
            next_obs, reward, done, _info = env.step(env_action, score_amount=amount)

            if done:
                target = reward
            else:
                nxt = q[discretize(next_obs)]
                target = reward + gamma * max(nxt[x] for x in valid_q_actions(next_obs, score_space))

            q[state][a] += alpha * (target - q[state][a])
            obs = next_obs

        if verbose and (episode + 1) % eval_every == 0:
            plain = dict(q)
            result = evaluate(
                TabularQAgent(plain, preset, score_space),
                name="A2", n_episodes=eval_episodes, band="desarrollo",
            )
            print(
                f"  ep {episode + 1:>9,}  eps={eps:.3f}  estados={len(q):>8,}  "
                f"media={result.mean:7.2f} ({100 * result.mean / OPTIMAL:5.1f}% del optimo)  "
                f"[{time.time() - started:6.0f}s]",
                flush=True,
            )

    plain = dict(q)
    if path:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as fh:
            pickle.dump({"q": plain, "preset": preset, "score_space": score_space}, fh, protocol=4)
    return plain


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--episodes", type=int, default=400_000)
    parser.add_argument("--preset", choices=list(PRESETS), default="tight")
    parser.add_argument("--score-space", choices=["all_half", "all"], default="all_half")
    parser.add_argument("--gamma", type=float, default=0.995)
    parser.add_argument("--tag", type=str, default="tight")
    args = parser.parse_args()

    print(
        f"=== A2 preset={args.preset} score={args.score_space} gamma={args.gamma} "
        f"({args.episodes:,} episodios) ===",
        flush=True,
    )
    train(
        n_episodes=args.episodes,
        preset=args.preset,
        score_space=args.score_space,
        gamma=args.gamma,
        path=os.path.join(ARTIFACT_DIR, f"classic_{args.tag}.pkl"),
    )
