"""
TD(lambda) sobre afterstates con una sola tabla.

Es la version previa a Double, y queda como ablacion: sirve para medir cuanto
aporta desacoplar seleccion de valuacion (ver train_double.py). Tambien
implementa las trazas de elegibilidad con corte de Watkins, que probamos y
empeoraron -- resultado negativo, reportado en el informe.
"""

from __future__ import annotations

import argparse
import os
import time

import numpy as np

from env import GoldDiceEnv
from afterstate import apply, legal_actions
from value_table import ValueTable
from evaluate import TRAIN_SEED_BASE, evaluate, OPTIMAL

ARTIFACT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "artifacts")
DEFAULT_PATH = os.path.join(ARTIFACT_DIR, "afterstate_v.pkl")

TRACE_FLOOR = 1e-3      # por debajo de esto una traza no mueve la aguja


class AfterstateAgent:
    """
    Juega greedy sobre la tabla de valores. Sin exploracion, sin aleatoriedad y
    sin intervencion manual: `act` es una funcion pura de la observacion.
    """

    def __init__(self, table: ValueTable | str = DEFAULT_PATH):
        self.table = ValueTable.load(table) if isinstance(table, str) else table

    def act(self, obs, env=None):
        best_action, best_value, best_amount = None, -float("inf"), None
        for action in legal_actions(obs):
            after, points, amount = apply(obs, action)
            total = points + self.table.value(after)
            if total > best_value:
                best_action, best_value, best_amount = action, total, amount
        return best_action, best_amount


def _greedy(table: ValueTable, obs: dict):
    """Devuelve (mejor_accion, valor_greedy) en `obs`."""
    best_action, best_value = None, -float("inf")
    for action in legal_actions(obs):
        after, points, _ = apply(obs, action)
        total = points + table.value(after)
        if total > best_value:
            best_action, best_value = action, total
    return best_action, best_value


def train(
    n_episodes: int = 1_500_000,
    lam: float = 0.90,
    alpha_scale: float = 1.0,
    alpha_min: float = 0.02,
    alpha_decay: float = 0.50,
    eps_start: float = 0.30,
    eps_end: float = 0.02,
    eps_frac: float = 0.70,
    eval_every: int = 100_000,
    eval_episodes: int = 3_000,
    seed: int = 20260901,
    table: ValueTable | None = None,
    path: str = DEFAULT_PATH,
    verbose: bool = True,
) -> ValueTable:
    rng = np.random.default_rng(seed)
    table = table if table is not None else ValueTable(alpha_min=alpha_min, alpha_decay=alpha_decay)
    env = GoldDiceEnv(obs_mode="dict", track_history=False)

    decay_until = max(1, int(eps_frac * n_episodes))
    started = time.time()
    curve: list[tuple[int, float, float]] = []

    for episode in range(n_episodes):
        frac = min(1.0, episode / decay_until)
        eps = eps_start + frac * (eps_end - eps_start)

        obs = env.reset(seed=TRAIN_SEED_BASE + episode)
        trace: dict[tuple, float] = {}
        prev_after = None
        done = False

        while not done:
            actions = legal_actions(obs)
            greedy_action, greedy_value = _greedy(table, obs)

            # -- error TD del paso anterior, propagado por la traza ----------
            if prev_after is not None:
                delta = greedy_value - table.value(prev_after)
                for key, elig in trace.items():
                    table.bump(key, table.alpha_for(key, visit=False) * alpha_scale * delta * elig)

            # -- eleccion epsilon-greedy -----------------------------------
            exploring = rng.random() < eps
            action = actions[int(rng.integers(len(actions)))] if exploring else greedy_action

            after, _points, amount = apply(obs, action)

            # -- decaer e incorporar el afterstate elegido a la traza -------
            if exploring:
                # Corte de Watkins: mas atras de una accion no-greedy el
                # objetivo off-policy deja de ser valido.
                trace = {}
            else:
                trace = {k: v * lam for k, v in trace.items() if v * lam > TRACE_FLOOR}
            for key, coeff in table.features(after):
                table.alpha_for(key, visit=True)          # cuenta la visita
                trace[key] = trace.get(key, 0.0) + coeff

            prev_after = after
            obs, _reward, done, _info = env.step(action, score_amount=amount)

        # Fin de episodio: el afterstate del turno 30 vale 0 por definicion
        # (`is_terminal`), asi que el objetivo del ultimo paso es 0.
        if prev_after is not None:
            delta = 0.0 - table.value(prev_after)
            for key, elig in trace.items():
                table.bump(key, table.alpha_for(key, visit=False) * alpha_scale * delta * elig)

        if verbose and (episode + 1) % eval_every == 0:
            result = evaluate(
                AfterstateAgent(table), name="A5", n_episodes=eval_episodes, band="desarrollo"
            )
            curve.append((episode + 1, result.mean, result.stderr))
            print(
                f"  ep {episode + 1:>9,}  eps={eps:.3f}  pesos={len(table):>8,}  "
                f"media={result.mean:7.2f} ({100 * result.mean / OPTIMAL:5.1f}% del optimo)  "
                f"[{time.time() - started:6.0f}s]",
                flush=True,
            )

    os.makedirs(os.path.dirname(path), exist_ok=True)
    table.save(path)
    if curve:
        np.save(path.replace(".pkl", "_curve.npy"), np.array(curve))
    if verbose:
        print(f"\nTabla guardada en {path}  ({len(table):,} pesos)")
    return table


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--episodes", type=int, default=1_500_000)
    parser.add_argument("--lam", type=float, default=0.90)
    parser.add_argument("--alpha-scale", type=float, default=1.0)
    parser.add_argument("--alpha-min", type=float, default=0.02)
    parser.add_argument("--alpha-decay", type=float, default=0.50)
    parser.add_argument("--eps-start", type=float, default=0.30)
    parser.add_argument("--eps-end", type=float, default=0.02)
    parser.add_argument("--eval-every", type=int, default=100_000)
    parser.add_argument("--path", type=str, default=DEFAULT_PATH)
    args = parser.parse_args()

    train(
        n_episodes=args.episodes,
        lam=args.lam,
        alpha_scale=args.alpha_scale,
        alpha_min=args.alpha_min,
        alpha_decay=args.alpha_decay,
        eps_start=args.eps_start,
        eps_end=args.eps_end,
        eval_every=args.eval_every,
        path=args.path,
    )
