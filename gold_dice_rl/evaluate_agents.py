import numpy as np

from env import GoldDiceEnv
from agents import RandomLegalAgent, SimpleExpectancyAgent


def evaluate(agent, n_episodes=1000, seed=0, obs_mode="dict"):
    scores = []

    for ep in range(n_episodes):
        env = GoldDiceEnv(obs_mode=obs_mode, seed=seed + ep, track_history=False)
        obs = env.reset(seed=seed + ep)
        done = False

        while not done:
            action, score_amount = agent.act(obs, env)
            obs, reward, done, info = env.step(action, score_amount=score_amount)

        scores.append(env.points)

    scores = np.array(scores)

    return {
        "mean": float(scores.mean()),
        "std": float(scores.std()),
        "min": int(scores.min()),
        "p25": float(np.percentile(scores, 25)),
        "median": float(np.percentile(scores, 50)),
        "p75": float(np.percentile(scores, 75)),
        "max": int(scores.max()),
    }


if __name__ == "__main__":
    agents = {
        "RandomLegal": RandomLegalAgent(seed=123),
        "SimpleExpectancy": SimpleExpectancyAgent(),
    }

    for name, agent in agents.items():
        print(name, evaluate(agent, n_episodes=1000, seed=123))
