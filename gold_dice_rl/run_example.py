from env import GoldDiceEnv, ACTION_NAMES
from agents import SimpleExpectancyAgent
from renderer import plot_episode


env = GoldDiceEnv(obs_mode="dict", seed=42, track_history=True)
agent = SimpleExpectancyAgent()

obs = env.reset(seed=42)
done = False
total_reward = 0

while not done:
    action, score_amount = agent.act(obs, env)
    next_obs, reward, done, info = env.step(action, score_amount=score_amount)

    print(f"Turn {info['turn']}")
    print("Obs:", obs)
    print("Action:", ACTION_NAMES[action])
    print("Score amount:", score_amount)
    print("Reward:", reward)
    print("Storm:", info["storm"], "Blocked:", info["storm_blocked"])
    print("Next obs:", next_obs)
    print("-" * 80)

    total_reward += reward
    obs = next_obs

print("Final points:", env.points)
print("Total reward:", total_reward)

plot_episode(env.history)