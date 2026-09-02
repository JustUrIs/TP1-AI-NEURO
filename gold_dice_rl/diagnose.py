"""
Diagnostico por arrepentimiento (regret) contra el oraculo.

Sin oraculo, cuando un agente rinde mal solo se sabe *cuanto* pierde. Con el
oraculo se sabe *donde*: para cada decision se puede calcular exactamente
cuanto valor destruyo esa jugada concreta.

    arrepentimiento(o, a) = V*(o) - [ r(o, a) + E_{tormenta,tirada} V*(s') ]

Es siempre >= 0 y vale 0 exactamente cuando la jugada es optima. Sumado sobre
un episodio da la perdida total atribuible a decisiones (lo que queda es azar).

Se usa para responder preguntas del tipo "el agente sub-invierte entre los
turnos 5 y 9" en vez de "el agente anda mal".
"""

from __future__ import annotations

import numpy as np

from env import GoldDiceEnv, ACTION_NAMES, HORIZON
import oracle_dp as O


def regret_profile(agent, n_episodes: int = 400, band_seed: int = 1_000_000):
    """
    Corre `agent` y acumula, por turno, el arrepentimiento medio y que accion
    eligio frente a la que correspondia.
    """
    U = O.get()
    per_turn = np.zeros(HORIZON + 1)
    per_turn_n = np.zeros(HORIZON + 1)
    confusion: dict[tuple[int, int], int] = {}
    total_regret = []

    for ep in range(n_episodes):
        seed = band_seed + ep
        env = GoldDiceEnv(obs_mode="dict", seed=seed, track_history=False)
        obs = env.reset(seed=seed)
        done = False
        ep_regret = 0.0

        while not done:
            values = O.action_values(obs, U)
            best_action = max(values, key=lambda a: values[a][0])
            best_value = values[best_action][0]

            action, amount = agent.act(obs, env)
            # Valor exacto de la jugada que EL AGENTE eligio.
            if action in values:
                chosen_value = values[action][0]
                if action == 1 and amount is not None and amount != values[action][1]:
                    # SCORE con una cantidad distinta de la optima: hay que
                    # valuar esa cantidad concreta, no la mejor.
                    chosen_value = amount + O.end_of_turn_value(
                        U, obs["turn"], obs["gold"] - amount,
                        obs["num_dice"], obs["dice_bonus"], obs["shields"],
                    )
            else:
                chosen_value = -1e9

            regret = max(0.0, best_value - chosen_value)
            per_turn[obs["turn"]] += regret
            per_turn_n[obs["turn"]] += 1
            ep_regret += regret
            if regret > 0.5:
                key = (best_action, action)
                confusion[key] = confusion.get(key, 0) + 1

            obs, _r, done, _info = env.step(action, score_amount=amount)

        total_regret.append(ep_regret)

    per_turn_mean = np.divide(
        per_turn, per_turn_n, out=np.zeros_like(per_turn), where=per_turn_n > 0
    )
    return per_turn_mean, np.array(total_regret), confusion


def report(agent, name: str = "agente", n_episodes: int = 400) -> None:
    per_turn, totals, confusion = regret_profile(agent, n_episodes)

    print(f"\n=== ARREPENTIMIENTO DE {name} ({n_episodes} partidas) ===")
    print(f"  perdida total por decisiones : {totals.mean():7.2f} puntos por partida")
    print(f"  optimo teorico               : {O.get()[1, 1, 0, 0, 0]:7.2f}")
    print(f"  techo implicito del agente   : {O.get()[1, 1, 0, 0, 0] - totals.mean():7.2f}")

    print("\n  arrepentimiento medio por turno (puntos perdidos por decision):")
    worst = np.argsort(-per_turn)[:8]
    for t in range(1, HORIZON + 1):
        bar = "#" * int(min(60, per_turn[t] / max(per_turn.max(), 1e-9) * 60))
        flag = "  <<<" if t in worst else ""
        print(f"    t={t:2d}  {per_turn[t]:7.2f}  {bar}{flag}")

    print("\n  errores mas frecuentes (deberia -> eligio):")
    for (should, did), count in sorted(confusion.items(), key=lambda kv: -kv[1])[:8]:
        print(f"    {ACTION_NAMES[should]:<16} -> {ACTION_NAMES[did]:<16} {count:>6} veces")


if __name__ == "__main__":
    import sys
    from train_afterstate import AfterstateAgent

    path = sys.argv[1] if len(sys.argv) > 1 else "artifacts/afterstate_v.pkl"
    report(AfterstateAgent(path), name=path, n_episodes=400)
