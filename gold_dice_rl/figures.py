"""
Figuras del informe.

Una sola figura de dos paneles, porque el informe tiene tope de 3 paginas y
solo entra una. Los dos paneles cuentan la misma historia desde dos angulos:

  izquierda  el oro turno a turno del optimo contra el del agente. Se ve de un
             vistazo que el agente construye un motor parecido pero no acumula:
             cobra temprano en vez de esperar al turno 30 detras de un escudo.

  derecha    el arrepentimiento por turno -- cuantos puntos destruye cada
             decision, medido exacto contra el oraculo. Muestra que la perdida
             no esta repartida: se concentra en la apertura y en el momento del
             escudo.

    python figures.py
"""

from __future__ import annotations

import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from env import GoldDiceEnv, HORIZON
from oracle_dp import OracleAgent
from agents import GoldDiceAgent
from diagnose import regret_profile

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "informe")

INK = "#16181d"
ACCENT = "#1b3a6b"
WARM = "#b4531f"
GRID = "#dfe2e8"


def trajectory(agent, n_episodes: int = 500, base: int = 1_000_000) -> np.ndarray:
    """Oro medio por turno."""
    gold = np.zeros(HORIZON + 1)
    count = np.zeros(HORIZON + 1)
    for ep in range(n_episodes):
        seed = base + ep
        env = GoldDiceEnv(obs_mode="dict", seed=seed, track_history=False)
        obs = env.reset(seed=seed)
        done = False
        while not done:
            gold[obs["turn"]] += obs["gold"]
            count[obs["turn"]] += 1
            action, amount = agent.act(obs, env)
            obs, _r, done, _i = env.step(action, score_amount=amount)
    return np.divide(gold, count, out=np.zeros_like(gold), where=count > 0)


def main() -> None:
    oracle = OracleAgent()
    agent = GoldDiceAgent()

    g_oracle = trajectory(oracle)
    g_agent = trajectory(agent)
    regret, _totals, _conf = regret_profile(agent, n_episodes=400)

    turns = np.arange(1, HORIZON + 1)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9.6, 2.9))

    # -- panel izquierdo: oro por turno
    ax1.plot(turns, g_oracle[1:], color=ACCENT, lw=2.0, label="óptimo (DP exacta)")
    ax1.plot(turns, g_agent[1:], color=WARM, lw=2.0, ls="--", label="nuestro agente")
    ax1.axvline(23, color="#9aa1ae", lw=0.8, ls=":")
    ax1.annotate(
        "el óptimo compra\nun escudo y acumula",
        xy=(23.4, 300), fontsize=7.2, color=ACCENT, va="center",
    )
    ax1.set_xlabel("turno", fontsize=8)
    ax1.set_ylabel("oro medio", fontsize=8)
    ax1.set_title("Oro acumulado por turno", fontsize=8.8, color=INK, loc="left")
    ax1.legend(fontsize=7.2, frameon=False, loc="upper left")

    # -- panel derecho: arrepentimiento por turno
    ax2.bar(turns, regret[1:], color=WARM, width=0.72)
    ax2.set_xlabel("turno", fontsize=8)
    ax2.set_ylabel("puntos perdidos por decisión", fontsize=8)
    ax2.set_title("Dónde se pierden los puntos", fontsize=8.8, color=INK, loc="left")
    ax2.annotate(
        "apertura:\nno usa STORE",
        xy=(3.5, regret[1:8].max() * 0.92), fontsize=7.2, color=INK, va="top",
    )
    ax2.annotate(
        "no compra\nel escudo",
        xy=(21.5, regret[23:30].max() * 1.02), fontsize=7.2, color=INK, va="bottom",
    )

    for ax in (ax1, ax2):
        ax.grid(True, color=GRID, lw=0.6)
        ax.set_axisbelow(True)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            ax.spines[side].set_color("#b7bcc7")
        ax.tick_params(labelsize=7.2, colors=INK, length=3)
        ax.set_xlim(0.5, 30.5)

    fig.tight_layout(pad=0.5)
    path = os.path.abspath(os.path.join(OUT, "figura.png"))
    fig.savefig(path, dpi=220, bbox_inches="tight", facecolor="white")
    print("figura ->", path)


if __name__ == "__main__":
    main()
