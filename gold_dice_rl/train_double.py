"""
Double TD sobre afterstates. Es el agente que se entrega.

Con una sola tabla el agente EMPEORA con mas entrenamiento (81.0% del optimo a
250k episodios, 80.0% a 500k, 79.5% a 750k). Es sesgo de maximizacion: el
objetivo es un max sobre valores con ruido, y el maximo de variables ruidosas
supera al maximo de sus medias. Double learning (van Hasselt, 2010) usa dos
tablas -- una elige la accion, la otra la valua -- y el sesgo se cancela.

gamma = 1: horizonte finito y conocido, no hay nada que descontar.
Se guarda el mejor checkpoint segun la banda de desarrollo.
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
DEFAULT_PATH = os.path.join(ARTIFACT_DIR, "gold_dice_agent.pkl")


class DoubleAgent:
    """Politica greedy sobre el promedio de las dos tablas."""

    def __init__(self, a: ValueTable, b: ValueTable):
        self.a, self.b = a, b

    def value(self, after) -> float:
        return 0.5 * (self.a.value(after) + self.b.value(after))

    def act(self, obs, env=None):
        best_action, best_value, best_amount = None, float("-inf"), None
        for action in legal_actions(obs):
            after, points, amount = apply(obs, action)
            total = points + self.value(after)
            if total > best_value:
                best_action, best_value, best_amount = action, total, amount
        return best_action, best_amount

    def merged(self) -> ValueTable:
        """
        Fusiona A y B en una sola tabla promediando los residuos.

        Es exacto: V = Phi + R con el mismo Phi en las dos, asi que promediar
        R es promediar V. El agente entregado carga esta unica tabla.
        """
        out = ValueTable(alpha_min=self.a.alpha_min, alpha_decay=self.a.alpha_decay,
                         potential_scale=self.a.potential_scale,
                         gold_nodes=self.a.gold_nodes)
        for key in set(self.a.theta) | set(self.b.theta):
            ra = self.a.theta.get(key)
            rb = self.b.theta.get(key)
            visits = (ra[1] if ra else 0) + (rb[1] if rb else 0)
            out.theta[key] = [0.5 * ((ra[0] if ra else 0.0) + (rb[0] if rb else 0.0)), visits]
        return out


def train(
    n_episodes: int = 1_500_000,
    alpha_scale: float = 0.03,
    alpha_min: float = 0.002,
    alpha_decay: float = 0.50,
    eps_start: float = 0.15,
    eps_end: float = 0.02,
    eps_frac: float = 0.60,
    potential_scale: float = 1.0,
    eps_mode: str = "fixed",
    eval_every: int = 100_000,
    eval_episodes: int = 4_000,
    seed: int = 20260901,
    path: str = DEFAULT_PATH,
    verbose: bool = True,
):
    rng = np.random.default_rng(seed)
    ta = ValueTable(alpha_min=alpha_min, alpha_decay=alpha_decay, potential_scale=potential_scale)
    tb = ValueTable(alpha_min=alpha_min, alpha_decay=alpha_decay, potential_scale=potential_scale)
    env = GoldDiceEnv(obs_mode="dict", track_history=False)

    decay_until = max(1, int(eps_frac * n_episodes))
    started = time.time()
    best_mean, curve = -1.0, []

    for episode in range(n_episodes):
        eps = eps_start + min(1.0, episode / decay_until) * (eps_end - eps_start)
        if eps_mode == "diverse":
            # epsilon por episodio, log-uniforme entre eps/8 y 4*eps
            eps = float(np.exp(rng.uniform(np.log(eps / 8.0), np.log(min(0.9, eps * 4.0)))))
        obs = env.reset(seed=TRAIN_SEED_BASE + episode)
        prev_after = None
        done = False
        run_action, run_left = None, 0          # exploracion sostenida (zgreedy)

        while not done:
            actions = legal_actions(obs)

            # -- objetivo del paso anterior, con seleccion y valuacion
            #    desacopladas (esa es toda la idea de Double)
            if prev_after is not None:
                if rng.random() < 0.5:
                    chooser, evaluator, target_table = ta, tb, ta
                else:
                    chooser, evaluator, target_table = tb, ta, tb

                best_a, best_v = None, float("-inf")
                for a in actions:
                    after, points, _ = apply(obs, a)
                    total = points + chooser.value(after)
                    if total > best_v:
                        best_a, best_v = a, total

                after_star, points_star, _ = apply(obs, best_a)
                target = points_star + evaluator.value(after_star)
                target_table.update(prev_after, target, alpha_scale)

            # -- accion: greedy sobre el promedio, con exploracion
            if run_left > 0 and run_action in actions:
                action = run_action
                run_left -= 1
            elif rng.random() < eps:
                action = actions[int(rng.integers(len(actions)))]
                if eps_mode == "zgreedy":
                    # duracion de cola pesada: mayormente 1, a veces muchos turnos
                    run_action = action
                    run_left = min(12, int(rng.pareto(1.0)) )
            else:
                run_left = 0
                action, best_v = None, float("-inf")
                for a in actions:
                    after, points, _ = apply(obs, a)
                    total = points + 0.5 * (ta.value(after) + tb.value(after))
                    if total > best_v:
                        action, best_v = a, total

            after, _points, amount = apply(obs, action)
            prev_after = after
            obs, _reward, done, _info = env.step(action, score_amount=amount)

        # El afterstate del turno 30 vale 0 por definicion; el objetivo del
        # ultimo paso ya se aplico dentro del bucle, en el turno 30.

        if (episode + 1) % eval_every == 0:
            agent = DoubleAgent(ta, tb)
            result = evaluate(agent, name="A5", n_episodes=eval_episodes, band="desarrollo")
            curve.append((episode + 1, result.mean, result.stderr))
            flag = ""
            if result.mean > best_mean:
                best_mean = result.mean
                os.makedirs(os.path.dirname(path), exist_ok=True)
                agent.merged().save(path)
                flag = "  <- guardado"
            if verbose:
                print(
                    f"  ep {episode + 1:>9,}  eps={eps:.3f}  pesos={len(ta) + len(tb):>8,}  "
                    f"media={result.mean:7.2f} ({100 * result.mean / OPTIMAL:5.1f}% del optimo)"
                    f"{flag}  [{time.time() - started:6.0f}s]",
                    flush=True,
                )

    if curve:
        np.save(path.replace(".pkl", "_curve.npy"), np.array(curve))
    if verbose:
        print(f"\nMejor checkpoint: {best_mean:.2f} ({100 * best_mean / OPTIMAL:.1f}%) -> {path}")
    return best_mean


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--episodes", type=int, default=1_500_000)
    parser.add_argument("--alpha-scale", type=float, default=0.03)
    parser.add_argument("--alpha-min", type=float, default=0.002)
    parser.add_argument("--eps-start", type=float, default=0.15)
    parser.add_argument("--potential-scale", type=float, default=1.0)
    parser.add_argument("--eps-mode", choices=["fixed", "diverse", "zgreedy"], default="fixed")
    parser.add_argument("--eval-every", type=int, default=100_000)
    parser.add_argument("--path", type=str, default=DEFAULT_PATH)
    args = parser.parse_args()

    train(
        n_episodes=args.episodes,
        alpha_scale=args.alpha_scale,
        alpha_min=args.alpha_min,
        eps_start=args.eps_start,
        potential_scale=args.potential_scale,
        eps_mode=args.eps_mode,
        eval_every=args.eval_every,
        path=args.path,
    )
