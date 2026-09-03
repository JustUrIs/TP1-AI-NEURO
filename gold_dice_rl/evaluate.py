"""
Protocolo de evaluacion.

`evaluate_agents.py` corre 1000 episodios y devuelve una media pelada. Con
sigma ~100 eso da un intervalo de +-6.3: una diferencia de 4 puntos no es una
diferencia. Aca se agrega n = 20.000, intervalos de confianza, y tres bandas de
semillas disjuntas (desarrollo para decidir, control para verificar, publica
solo para reportar).

No se pueden usar numeros aleatorios comunes: en env.py un unico generador
sirve dados y tormentas y `size=num_dice` depende de la politica, asi que dos
agentes con la misma semilla ven azares distintos.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from env import GoldDiceEnv


# Bandas de semillas. Disjuntas por construccion.
SEED_BANDS = {
    "publica": 0,             # la del enunciado; solo para el reporte final
    "desarrollo": 1_000_000,  # aca se toman las decisiones
    "control": 2_000_000,     # se mira una sola vez, al cerrar el trabajo
}

# El entrenamiento vive lejos de las tres bandas de evaluacion.
TRAIN_SEED_BASE = 500_000_000

# Valor del juego bajo juego perfecto (oracle_dp.solve()). Todas las tablas se
# reportan como fraccion de este numero: un puntaje absoluto no dice nada si no
# se sabe cuanto habia para ganar.
OPTIMAL = 642.452


@dataclass
class Result:
    name: str
    n_episodes: int
    seed: int
    scores: np.ndarray = field(repr=False)

    @property
    def mean(self) -> float:
        return float(self.scores.mean())

    @property
    def std(self) -> float:
        return float(self.scores.std(ddof=1))

    @property
    def stderr(self) -> float:
        return self.std / math.sqrt(len(self.scores))

    @property
    def ci95(self) -> tuple[float, float]:
        half = 1.96 * self.stderr
        return self.mean - half, self.mean + half

    @property
    def pct_optimal(self) -> float:
        return 100.0 * self.mean / OPTIMAL

    def row(self) -> str:
        lo, hi = self.ci95
        return (
            f"{self.name:<22}"
            f"{self.mean:>9.2f}"
            f"  [{lo:>7.2f}, {hi:>7.2f}]"
            f"{self.pct_optimal:>8.1f}%"
            f"{self.std:>9.1f}"
            f"{int(self.scores.min()):>7}"
            f"{np.percentile(self.scores, 50):>8.0f}"
            f"{int(self.scores.max()):>7}"
        )


HEADER = (
    f"{'agente':<22}{'media':>9}{'   IC 95%':>19}{'% opt':>8}"
    f"{'sigma':>9}{'min':>7}{'mediana':>8}{'max':>7}"
)


def play_episode(agent, seed: int, obs_mode: str = "dict") -> int:
    env = GoldDiceEnv(obs_mode=obs_mode, seed=seed, track_history=False)
    obs = env.reset(seed=seed)
    done = False
    while not done:
        action, score_amount = agent.act(obs, env)
        obs, _, done, _ = env.step(action, score_amount=score_amount)
    return int(env.points)


def evaluate(
    agent,
    name: str = "agente",
    n_episodes: int = 20_000,
    band: str = "desarrollo",
    seed: int | None = None,
    obs_mode: str = "dict",
) -> Result:
    """
    Corre `n_episodes` partidas independientes y devuelve el resultado con su
    intervalo de confianza.

    `band` elige una de las tres bandas de semillas. `seed` la pisa si hace
    falta un rango a medida.
    """
    base = SEED_BANDS[band] if seed is None else seed
    scores = np.fromiter(
        (play_episode(agent, base + i, obs_mode) for i in range(n_episodes)),
        dtype=np.int64,
        count=n_episodes,
    )
    return Result(name=name, n_episodes=n_episodes, seed=base, scores=scores)


def compare(agents: dict, n_episodes: int = 20_000, band: str = "desarrollo") -> list[Result]:
    """Evalua varios agentes en la misma banda y los imprime ordenados."""
    results = [evaluate(a, name=n, n_episodes=n_episodes, band=band) for n, a in agents.items()]
    results.sort(key=lambda r: -r.mean)

    print(f"\nBanda '{band}' (seed base {SEED_BANDS[band]}), n = {n_episodes} episodios")
    print(f"Optimo teorico = {OPTIMAL:.2f}")
    print(HEADER)
    print("-" * len(HEADER))
    for r in results:
        print(r.row())
    return results


if __name__ == "__main__":
    from agents import RandomLegalAgent, SimpleExpectancyAgent
    from oracle_dp import OracleAgent

    compare(
        {
            "RandomLegal": RandomLegalAgent(seed=123),
            "SimpleExpectancy": SimpleExpectancyAgent(),
            "Oracle (DP, no compite)": OracleAgent(),
        },
        n_episodes=20_000,
        band="desarrollo",
    )
