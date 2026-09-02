"""
Barrido de configuraciones.

No es ajuste fino: responde una pregunta concreta. La politica que usa solo el
potencial (cero aprendizaje) saca 490.4, y las primeras versiones entrenadas
sacaban menos -- el aprendizaje estaba empeorando una inicializacion buena.
Este barrido separa si la culpa es el paso, las trazas o la exploracion.
"""

from __future__ import annotations

import os
import sys

from train_afterstate import train

ARTIFACTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "artifacts")

CONFIGS = {
    "td0_a1":      dict(lam=0.0,  alpha_scale=1.00, alpha_min=0.02, alpha_decay=0.50, eps_start=0.30),
    "td0_a03":     dict(lam=0.0,  alpha_scale=0.30, alpha_min=0.01, alpha_decay=0.50, eps_start=0.30),
    "td0_a01":     dict(lam=0.0,  alpha_scale=0.10, alpha_min=0.005, alpha_decay=0.50, eps_start=0.30),
    "lam5_a03":    dict(lam=0.5,  alpha_scale=0.30, alpha_min=0.01, alpha_decay=0.50, eps_start=0.30),
    "lam9_a01":    dict(lam=0.9,  alpha_scale=0.10, alpha_min=0.005, alpha_decay=0.50, eps_start=0.30),
    "td0_a03_eps6": dict(lam=0.0, alpha_scale=0.30, alpha_min=0.01, alpha_decay=0.50, eps_start=0.60),
    # --- segunda tanda: el barrido mostro que el paso era el problema ---
    "td0_a003":     dict(lam=0.0, alpha_scale=0.03, alpha_min=0.002, alpha_decay=0.50, eps_start=0.30),
    "td0_a001":     dict(lam=0.0, alpha_scale=0.01, alpha_min=0.001, alpha_decay=0.50, eps_start=0.30),
    "td0_a003_eps15": dict(lam=0.0, alpha_scale=0.03, alpha_min=0.002, alpha_decay=0.50, eps_start=0.15),
    "td0_a01_slow": dict(lam=0.0, alpha_scale=0.10, alpha_min=0.005, alpha_decay=0.30, eps_start=0.30),
    "lam3_a003":    dict(lam=0.3, alpha_scale=0.03, alpha_min=0.002, alpha_decay=0.50, eps_start=0.30),
}


if __name__ == "__main__":
    name = sys.argv[1]
    episodes = int(sys.argv[2]) if len(sys.argv) > 2 else 400_000
    cfg = CONFIGS[name]
    print(f"=== {name}  {cfg}  ({episodes:,} episodios) ===", flush=True)
    train(
        n_episodes=episodes,
        eval_every=max(1, episodes // 8),
        eval_episodes=2000,
        path=os.path.join(ARTIFACTS, f"sweep_{name}_{episodes}.pkl"),
        **cfg,
    )
