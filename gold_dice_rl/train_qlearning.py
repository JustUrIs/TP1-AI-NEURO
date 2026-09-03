"""Entrenamiento del agente entregado: Double Q-Learning sobre afterstates."""

import argparse
import os
import time

import numpy as np

from afterstate import apply, legal_actions
from env import GoldDiceEnv
from evaluate_agents import evaluate
from value_table import ValueTable

ARTIFACTS = os.path.join(os.path.dirname(__file__), "artifacts")
DEFAULT_PATH = os.path.join(ARTIFACTS, "gold_dice_agent.pkl")
TRAIN_SEED_BASE = 500_000_000


class DoubleAgent:
    """Politica greedy que promedia las dos tablas usadas al entrenar."""

    def __init__(self, a, b):
        self.a, self.b = a, b

    def act(self, obs, env=None):
        best = (float("-inf"), None, None)
        for action in legal_actions(obs):
            after, points, amount = apply(obs, action)
            value = points + (self.a.value(after) + self.b.value(after)) / 2
            if value > best[0]:
                best = value, action, amount
        return best[1], best[2]

    def merged(self):
        """Promedia ambas tablas para que el agente final cargue un solo archivo."""
        out = ValueTable(
            alpha_min=self.a.alpha_min,
            alpha_decay=self.a.alpha_decay,
            potential_scale=self.a.potential_scale,
            gold_nodes=self.a.gold_nodes,
        )
        for key in set(self.a.theta) | set(self.b.theta):
            va, vb = self.a.theta.get(key), self.b.theta.get(key)
            residue = ((va[0] if va else 0) + (vb[0] if vb else 0)) / 2
            visits = (va[1] if va else 0) + (vb[1] if vb else 0)
            out.theta[key] = [residue, visits]
        return out


def greedy(table, obs):
    """Devuelve la accion con mayor recompensa inmediata mas valor futuro."""
    best = (float("-inf"), None)
    for action in legal_actions(obs):
        after, points, _ = apply(obs, action)
        candidate = points + table.value(after)
        if candidate > best[0]:
            best = candidate, action
    return best[1]


def train(episodes=1_500_000, alpha_scale=0.03, eps_start=0.15,
          eps_end=0.02, seed=20260901, path=DEFAULT_PATH):
    """Entrena dos tablas y conserva el mejor checkpoint cada 100 mil partidas."""
    rng = np.random.default_rng(seed)
    qa = ValueTable(alpha_min=0.002, alpha_decay=0.50)
    qb = ValueTable(alpha_min=0.002, alpha_decay=0.50)
    env = GoldDiceEnv(obs_mode="dict", track_history=False)
    best_mean, started = float("-inf"), time.time()

    for episode in range(episodes):
        frac = min(1.0, episode / max(1, int(0.60 * episodes)))
        epsilon = eps_start + frac * (eps_end - eps_start)
        obs = env.reset(seed=TRAIN_SEED_BASE + episode)
        previous = None

        while True:
            actions = legal_actions(obs)

            # Double Q: una tabla elige la accion y la otra calcula el objetivo.
            if previous is not None:
                chooser, evaluator = (qa, qb) if rng.random() < 0.5 else (qb, qa)
                action_star = greedy(chooser, obs)
                after_star, reward_star, _ = apply(obs, action_star)
                chooser.update(previous, reward_star + evaluator.value(after_star), alpha_scale)

            if rng.random() < epsilon:
                action = actions[int(rng.integers(len(actions)))]
            else:
                action = DoubleAgent(qa, qb).act(obs)[0]

            previous, _, amount = apply(obs, action)
            obs, _, done, _ = env.step(action, score_amount=amount)
            if done:
                break

        if (episode + 1) % 100_000 == 0:
            agent = DoubleAgent(qa, qb)
            result = evaluate(agent, n_episodes=4_000, seed=1_000_000)
            if result["mean"] > best_mean:
                best_mean = result["mean"]
                os.makedirs(os.path.dirname(path), exist_ok=True)
                agent.merged().save(path)
            print(f"ep={episode + 1:,} media={result['mean']:.2f} "
                  f"mejor={best_mean:.2f} tiempo={time.time() - started:.0f}s")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--episodes", type=int, default=1_500_000)
    parser.add_argument("--path", default=DEFAULT_PATH)
    args = parser.parse_args()
    train(episodes=args.episodes, path=args.path)
