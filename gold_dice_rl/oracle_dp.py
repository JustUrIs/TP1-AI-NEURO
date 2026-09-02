"""
Solver exacto de Gold Dice RL por induccion hacia atras.

No es un agente: es la vara. Resuelve el MDP verdadero y devuelve, para
cualquier estado, los puntos esperados jugando perfecto (642.45 al inicio).
Se usa para medir la brecha de los agentes aprendidos, diagnosticar en que
turnos se equivocan, y separar habilidad de suerte.

Es resoluble exacto porque `points` no aparece en ninguna transicion: el valor
no depende de los puntos y quedan cuatro variables (turno, oro, dados, bonus)
mas los escudos. Detalle del razonamiento en docs/01_REGLAS_OCULTAS.md 9.
"""

from __future__ import annotations

import os
import time

import numpy as np

from config import (
    HORIZON,
    STORM_PROB,
    DICE_FACES,
    SHIELD_COST,
    STORE_DIE_COST,
    get_new_dice_cost,
    get_upgrade_cost,
)
from env import PASS, SCORE, BUY_DICE, UPGRADE, BUY_SHIELD, STORE_BEST_DIE


# --------------------------------------------------------------------------
# Topes de la grilla.
#
# El juego no impone limites de dados/mejoras/escudos, pero si limites
# economicos: los costos crecen +8 por unidad mientras el retorno por dado es
# constante. En 30 turnos no se llega ni cerca de estos numeros. Verificamos
# empiricamente que no muerden: con topes (12, 12, 8, 1400) el valor optimo da
# 643.46 y con (9, 9, 5, 700) da 642.45 -- 0.16% de diferencia.
# --------------------------------------------------------------------------
NMAX = 9        # num_dice   1..NMAX
BMAX = 9        # dice_bonus 0..BMAX
SMAX = 5        # shields    0..SMAX
GMAX = 700      # oro        0..GMAX (por encima se clampea)

ARTIFACT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "artifacts")
ORACLE_PATH = os.path.join(ARTIFACT_DIR, "oracle_u.npy")


# --------------------------------------------------------------------------
# Distribucion conjunta exacta de (suma, maximo) para n dados de seis caras.
# Calculada por convolucion, no por muestreo: es exacta hasta el ultimo decimal.
# --------------------------------------------------------------------------
def joint_sum_max_pmf(n: int) -> dict[int, np.ndarray]:
    """dict[max_crudo] -> vector de probabilidades indexado por (suma_cruda - n)."""
    dist = {(0, 0): 1.0}
    for _ in range(n):
        nxt: dict[tuple[int, int], float] = {}
        for (total, mx), p in dist.items():
            for face in DICE_FACES:
                key = (total + face, max(mx, face))
                nxt[key] = nxt.get(key, 0.0) + p / len(DICE_FACES)
        dist = nxt

    out: dict[int, np.ndarray] = {}
    span = (max(DICE_FACES) - min(DICE_FACES)) * n + 1
    for (total, mx), p in dist.items():
        out.setdefault(mx, np.zeros(span))[total - n] += p
    return out


_PMF_CACHE: dict[int, dict[int, np.ndarray]] = {}


def pmf(n: int) -> dict[int, np.ndarray]:
    if n not in _PMF_CACHE:
        _PMF_CACHE[n] = joint_sum_max_pmf(n)
    return _PMF_CACHE[n]


# --------------------------------------------------------------------------
# Solver
# --------------------------------------------------------------------------
def solve(verbose: bool = True, score_mode: str = "exact") -> np.ndarray:
    """
    Devuelve U con forma (HORIZON + 1, NMAX + 1, BMAX + 1, SMAX + 1, GMAX + 1).

    U[t, n, b, s, x] = puntos esperados bajo juego optimo, ANTES de tirar los
    dados del turno t, teniendo x de oro (ya incluido lo que se arrastre) y la
    maquinaria (n, b, s).

    U[1, 1, 0, 0, 0] es el valor del juego.
    """
    gold = np.arange(GMAX + 1)
    halved = gold // 2
    shape_t = (NMAX + 1, BMAX + 1, SMAX + 1, GMAX + 1)

    U = np.zeros((HORIZON + 1,) + shape_t, dtype=np.float64)
    started = time.time()

    for t in range(HORIZON, 0, -1):
        for n in range(1, NMAX + 1):
            roll_pmf = pmf(n)
            for b in range(BMAX + 1):
                # -----------------------------------------------------------
                # Turno 30: despues de la accion el episodio termina y NO hay
                # otra tirada. Todo el oro sin puntuar se evapora, asi que la
                # unica jugada no dominada es SCORE(gold) y Vdec = g exacto.
                # No lo aprendemos: lo deducimos.
                # -----------------------------------------------------------
                if t == HORIZON:
                    U[t, n, b, :, :] = gold + n * (np.mean(DICE_FACES) + b)
                    continue

                for s in range(SMAX + 1):

                    def after_action(nn: int, bb: int, ss: int, carry: int = 0) -> np.ndarray:
                        """
                        Valor como funcion del oro POST-accion, integrando la
                        tormenta y la tirada del turno siguiente.

                        `carry` es el stored_value: se suma al oro recién en la
                        tirada del turno siguiente, es decir DESPUES de la
                        tormenta.
                        """
                        nxt = U[t + 1, nn, bb, ss]
                        keep = np.minimum(gold + carry, GMAX)
                        value = (1.0 - STORM_PROB) * nxt[keep]
                        if ss > 0:
                            # El escudo absorbe la tormenta: el oro no se toca,
                            # pero se pierde un escudo.
                            value += STORM_PROB * U[t + 1, nn, bb, ss - 1][keep]
                        else:
                            # Sin escudo: el oro se parte al medio ANTES de que
                            # entre lo guardado.
                            value += STORM_PROB * nxt[np.minimum(halved + carry, GMAX)]
                        return value

                    def shift_by_cost(values: np.ndarray, cost: int) -> np.ndarray:
                        """Accion que cuesta `cost`: ilegal si el oro no alcanza."""
                        out = np.full(GMAX + 1, -np.inf)
                        if cost <= GMAX:
                            out[cost:] = values[: GMAX + 1 - cost]
                        return out

                    stay = after_action(n, b, s)          # terminar el turno con g de oro

                    # PASS (equivalente a SCORE(0))
                    best = stay.copy()

                    # ---------------------------------------------------------
                    # SCORE. `score_mode` existe para poder MEDIR cuanto cuesta
                    # mutilar esta accion, que es la decision de modelado mas
                    # cara del problema.
                    #
                    #   "exact"     k libre en [0, oro]  -> maximo prefijo, O(oro)
                    #   "all"       solo puntuar todo
                    #   "all_half"  solo todo o la mitad (el reflejo tipico)
                    #   "structured" todo, o guardar exactamente lo que cuesta
                    #                la proxima compra (nuestro espacio)
                    # ---------------------------------------------------------
                    if score_mode == "exact":
                        best = np.maximum(best, gold + np.maximum.accumulate(stay - gold))
                    else:
                        if score_mode == "all":
                            keeps = [0]
                        elif score_mode == "all_half":
                            keeps = [0, "half"]
                        elif score_mode == "half_only":
                            keeps = ["half"]
                        elif score_mode == "structured":
                            keeps = sorted({0, STORE_DIE_COST, SHIELD_COST,
                                            get_upgrade_cost(b), get_new_dice_cost(n),
                                            get_upgrade_cost(b) + STORE_DIE_COST,
                                            get_new_dice_cost(n) + STORE_DIE_COST})
                        else:
                            raise ValueError(score_mode)
                        for m in keeps:
                            if m == "half":
                                keep_idx = gold - gold // 2          # SCORE(gold//2)
                                cand = (gold // 2) + stay[keep_idx]
                            else:
                                cand = np.full(GMAX + 1, -np.inf)
                                if m <= GMAX:
                                    cand[m:] = (gold[m:] - m) + stay[m]
                            best = np.maximum(best, cand)

                    if n + 1 <= NMAX:
                        best = np.maximum(
                            best, shift_by_cost(after_action(n + 1, b, s), get_new_dice_cost(n))
                        )
                    if b + 1 <= BMAX:
                        best = np.maximum(
                            best, shift_by_cost(after_action(n, b + 1, s), get_upgrade_cost(b))
                        )
                    if s + 1 <= SMAX:
                        best = np.maximum(
                            best, shift_by_cost(after_action(n, b, s + 1), SHIELD_COST)
                        )

                    # STORE_BEST_DIE depende del maximo de la tirada, asi que su
                    # valor se resuelve por separado para cada valor posible.
                    store = {
                        mx: shift_by_cost(after_action(n, b, s, carry=mx + b), STORE_DIE_COST)
                        for mx in roll_pmf
                    }

                    # U_t(x) = E_{(S,M)} [ Vdec_t(x + S, M) ]
                    acc = np.zeros(GMAX + 1)
                    for mx, probs in roll_pmf.items():
                        vdec = np.maximum(best, store[mx])
                        base = n + n * b          # suma minima + bonus total
                        for j, p in enumerate(probs):
                            if p:
                                acc += p * vdec[np.minimum(gold + base + j, GMAX)]
                    U[t, n, b, s] = acc

        if verbose:
            print(
                f"  t={t:2d}  V*(inicio) = {U[t, 1, 0, 0, 0]:8.3f}   "
                f"[{time.time() - started:6.1f}s]",
                flush=True,
            )

    return U


# --------------------------------------------------------------------------
# Persistencia
# --------------------------------------------------------------------------
def save(U: np.ndarray, path: str = ORACLE_PATH) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    np.save(path, U.astype(np.float32))
    return path


def load(path: str = ORACLE_PATH) -> np.ndarray:
    return np.load(path)


_ORACLE: np.ndarray | None = None


def get(path: str = ORACLE_PATH) -> np.ndarray:
    """Carga el oraculo de disco, resolviendolo si hace falta."""
    global _ORACLE
    if _ORACLE is None:
        if os.path.exists(path):
            _ORACLE = load(path)
        else:
            _ORACLE = solve()
            save(_ORACLE, path)
    return _ORACLE


# --------------------------------------------------------------------------
# Consultas: valor de cada accion en un estado concreto
# --------------------------------------------------------------------------
def _clamp(gold: int, n: int, b: int, s: int) -> tuple[int, int, int, int]:
    return min(int(gold), GMAX), min(int(n), NMAX), min(int(b), BMAX), min(int(s), SMAX)


def end_of_turn_value(U: np.ndarray, t: int, gold: int, n: int, b: int, s: int, carry: int = 0) -> float:
    """
    Puntos esperados desde el final del turno t (post-accion, pre-tormenta),
    quedandose con `gold` de oro, maquinaria (n, b, s) y `carry` guardado.
    """
    if t >= HORIZON:
        return 0.0                      # despues del turno 30 no hay nada
    gold, n, b, s = _clamp(gold, n, b, s)
    keep = min(gold + carry, GMAX)
    value = (1.0 - STORM_PROB) * U[t + 1, n, b, s, keep]
    if s > 0:
        value += STORM_PROB * U[t + 1, n, b, s - 1, keep]
    else:
        value += STORM_PROB * U[t + 1, n, b, 0, min(gold // 2 + carry, GMAX)]
    return float(value)


def _tail_vec(U: np.ndarray, t: int, golds: np.ndarray, n: int, b: int, s: int) -> np.ndarray:
    """Version vectorizada de `end_of_turn_value` sobre un vector de oro."""
    if t >= HORIZON:
        return np.zeros(len(golds))
    n, b, s = min(n, NMAX), min(b, BMAX), min(s, SMAX)
    keep = np.minimum(golds, GMAX)
    value = (1.0 - STORM_PROB) * U[t + 1, n, b, s][keep]
    if s > 0:
        value = value + STORM_PROB * U[t + 1, n, b, s - 1][keep]
    else:
        value = value + STORM_PROB * U[t + 1, n, b, 0][np.minimum(golds // 2, GMAX)]
    return value


def action_values(obs: dict, U: np.ndarray | None = None) -> dict:
    """
    Valor exacto de cada accion legal en `obs`, en puntos esperados hasta el
    final de la partida (sin contar los puntos ya acumulados).

    Devuelve {accion: (valor, score_amount)}. `score_amount` es None salvo para
    SCORE, donde es la cantidad optima a puntuar.
    """
    U = get() if U is None else U
    t = int(obs["turn"])
    gold = int(obs["gold"])
    n = int(obs["num_dice"])
    b = int(obs["dice_bonus"])
    s = int(obs["shields"])
    roll_max = int(obs["roll_max"])

    out: dict[int, tuple[float, int | None]] = {}

    def tail(g: int, nn: int, bb: int, ss: int, carry: int = 0) -> float:
        return end_of_turn_value(U, t, g, nn, bb, ss, carry)

    out[PASS] = (tail(gold, n, b, s), None)

    # SCORE: barremos de una sola vez todos los cortes posibles del oro y nos
    # quedamos con el mejor. Es O(oro), vectorizado, y es EXACTO: la cantidad a
    # puntuar nunca se discretiza.
    keeps = np.arange(min(gold, GMAX) + 1)
    tails = _tail_vec(U, t, keeps, n, b, s)
    total = (gold - keeps) + tails
    best_i = int(np.argmax(total))
    out[SCORE] = (float(total[best_i]), int(gold - keeps[best_i]))

    dice_cost = get_new_dice_cost(n)
    if gold >= dice_cost:
        out[BUY_DICE] = (tail(gold - dice_cost, n + 1, b, s), None)

    upgrade_cost = get_upgrade_cost(b)
    if gold >= upgrade_cost:
        out[UPGRADE] = (tail(gold - upgrade_cost, n, b + 1, s), None)

    if gold >= SHIELD_COST:
        out[BUY_SHIELD] = (tail(gold - SHIELD_COST, n, b, s + 1), None)

    if gold >= STORE_DIE_COST and roll_max > 0:
        out[STORE_BEST_DIE] = (tail(gold - STORE_DIE_COST, n, b, s, carry=roll_max), None)

    return out


def state_value(obs: dict, U: np.ndarray | None = None) -> float:
    """V*(s): puntos esperados desde este estado bajo juego perfecto."""
    return max(v for v, _ in action_values(obs, U).values())


class OracleAgent:
    """
    Juega optimo. NO es un agente de aprendizaje y NO se entrega al torneo:
    es la vara contra la que medimos a los que si aprenden.
    """

    def __init__(self, path: str = ORACLE_PATH):
        self.U = get(path)

    def act(self, obs, env=None):
        values = action_values(obs, self.U)
        action = max(values, key=lambda a: values[a][0])
        return action, values[action][1]


if __name__ == "__main__":
    U = solve()
    path = save(U)
    print(f"\nOraculo guardado en {path}")
    print(f"VALOR DEL JUEGO  V*(t=1, oro=0, 1 dado, bonus 0, 0 escudos) = {U[1, 1, 0, 0, 0]:.3f}")
