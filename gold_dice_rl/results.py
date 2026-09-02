"""
Genera la tabla de resultados del informe.

Todo lo que aparece en el informe sale de correr este archivo. Ningun numero se
escribe a mano.

Protocolo (ver evaluate.py):
  * n = 20.000 episodios por agente y por banda
  * intervalo de confianza al 95 % en todas las medias
  * tres bandas de semillas disjuntas:
        desarrollo (1e6)  -- donde se tomaron todas las decisiones
        control    (2e6)  -- se mira una sola vez, para detectar sobreajuste
        publica    (0)    -- la del enunciado; solo se reporta
"""

from __future__ import annotations

import os
import sys

from evaluate import evaluate, HEADER, OPTIMAL, SEED_BANDS

ARTIFACTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "artifacts")


def build_agents(include_agent: bool = True) -> dict:
    from agents import RandomLegalAgent, SimpleExpectancyAgent, PotentialAgent
    from oracle_dp import OracleAgent
    from train_tabular_classic import TabularQAgent

    agents: dict = {}
    agents["Oraculo (DP exacta, no compite)"] = OracleAgent()

    if include_agent:
        path = os.path.join(ARTIFACTS, "gold_dice_agent.pkl")
        if os.path.exists(path):
            from agents import GoldDiceAgent

            agents["GoldDiceAgent (entregado)"] = GoldDiceAgent(path)

    agents["Solo potencial (sin aprender)"] = PotentialAgent()

    ablations = [
        ("Q clasico  rangos+ SCORE_ALL", "classic_D_wide_g1_scoreall.pkl"),
        ("Q clasico  rangos+ g=1", "classic_C_wide_g1.pkl"),
        ("Q clasico  topes  g=1", "classic_B_tight_g1.pkl"),
        ("Q clasico  topes  g=0.995", "classic_A_tight_g995.pkl"),
    ]
    for label, fname in ablations:
        path = os.path.join(ARTIFACTS, fname)
        if os.path.exists(path):
            agents[label] = TabularQAgent(path)

    agents["SimpleExpectancy (catedra)"] = SimpleExpectancyAgent()
    agents["RandomLegal (catedra)"] = RandomLegalAgent(seed=123)
    return agents


def run(bands=("desarrollo",), n_episodes: int = 20_000) -> dict:
    agents = build_agents()
    out: dict = {}
    for band in bands:
        print(f"\n### banda '{band}'  (seed base {SEED_BANDS[band]:,})   n = {n_episodes:,}")
        print(f"### optimo teorico = {OPTIMAL:.2f}")
        print(HEADER)
        print("-" * len(HEADER))
        results = []
        for name, agent in agents.items():
            r = evaluate(agent, name=name, n_episodes=n_episodes, band=band)
            results.append(r)
            print(r.row(), flush=True)
        out[band] = results
    return out


if __name__ == "__main__":
    bands = sys.argv[1].split(",") if len(sys.argv) > 1 else ["desarrollo"]
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 20_000
    run(bands=bands, n_episodes=n)
