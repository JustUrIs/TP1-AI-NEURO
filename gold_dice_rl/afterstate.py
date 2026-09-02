"""
Representacion por afterstates: el estado DESPUES de la accion, antes del azar.

El efecto de una accion es completamente determinista (pagar 42 y sumar un dado
es aritmetica); el azar viene despues. En ese caso conviene aprender
V(afterstate) en vez de Q(s, a) -- Sutton & Barto 6.8, la representacion de
TD-Gammon.

El espacio de acciones se reduce a seis: medimos con el solver que dejar SCORE
en "puntuar todo" cuesta 0.00 (docs/01_REGLAS_OCULTAS.md 6).
"""

from __future__ import annotations

import bisect
import os

from config import (
    HORIZON,
    DICE_FACES,
    SHIELD_COST,
    STORE_DIE_COST,
    get_new_dice_cost,
    get_upgrade_cost,
)
from env import PASS, SCORE, BUY_DICE, UPGRADE, BUY_SHIELD, STORE_BEST_DIE


# Las seis acciones con las que trabaja el agente. SCORE significa "puntuar
# todo el oro" (ver docstring: costo medido 0.00 frente a la version libre).
ACTIONS = (PASS, SCORE, BUY_DICE, UPGRADE, BUY_SHIELD, STORE_BEST_DIE)

MEAN_FACE = sum(DICE_FACES) / len(DICE_FACES)   # 3.5


# --------------------------------------------------------------------------
# Grilla de oro
# --------------------------------------------------------------------------
def build_gold_nodes(kind: str = "fine") -> list[int]:
    """
    Construye la grilla de nodos de oro. `kind` es "fine" o "coarse".

    La grilla forma parte de la definicion de los pesos (las claves guardan
    INDICES de nodo), asi que viaja adentro del artefacto entrenado y no se
    elige por variable de entorno: un agente cargado con otra grilla que la de
    su entrenamiento leeria basura sin dar error.

    "coarse" ralea la zona de arriba de 96

    Sale del diagnostico: en la decision del escudo del turno 23 el optimo
    separa la mejor accion de la peor por 13.6 puntos sobre un valor de 600
    (2.3 %), y el error de estimacion del agente es de 18 a 29. Con muestras
    de desviacion 130, resolver 13 puntos pide del orden de mil muestras
    independientes POR PESO. Menos pesos = mas muestras por peso. Arriba de 96
    de oro no hay ningun umbral de compra y el valor es casi lineal, asi que
    ahi la grilla se puede ralear casi gratis.
    """
    nodes = list(range(0, 97))                 # 0..96 de a 1: todos los umbrales
    if kind == "coarse":
        nodes += list(range(110, 201, 15))
        nodes += list(range(230, 401, 35))
        nodes += list(range(460, 901, 90))
    else:
        nodes += list(range(100, 201, 4))      # 100..200 de a 4
        nodes += list(range(208, 401, 8))      # 208..400 de a 8
        nodes += list(range(420, 901, 20))     # 420..900 de a 20
    return nodes


GOLD_NODES = build_gold_nodes(os.environ.get("GOLD_GRID", "fine"))
N_GOLD_NODES = len(GOLD_NODES)


def gold_features(gold: int, nodes: list[int] | None = None) -> tuple[int, int, float]:
    """
    Devuelve (i, j, w): el oro cae entre los nodos i y j, con peso w sobre j.

        V(oro) = (1 - w) * theta[i] + w * theta[j]

    Por encima del ultimo nodo se satura (el juego optimo nunca llega ahi;
    esos estados solo aparecen explorando).
    """
    nodes = GOLD_NODES if nodes is None else nodes
    last = len(nodes) - 1
    if gold >= nodes[last]:
        return last, last, 0.0
    k = bisect.bisect_right(nodes, gold) - 1
    lo, hi = nodes[k], nodes[k + 1]
    if lo == gold:
        return k, k, 0.0
    return k, k + 1, (gold - lo) / (hi - lo)


# --------------------------------------------------------------------------
# Afterstates
# --------------------------------------------------------------------------
def legal_actions(obs: dict) -> list[int]:
    """Las acciones de ACTIONS que son legales en `obs`, con los costos de config.py."""
    gold = obs["gold"]
    out = [PASS, SCORE]                        # SCORE(0) siempre es legal
    if gold >= get_new_dice_cost(obs["num_dice"]):
        out.append(BUY_DICE)
    if gold >= get_upgrade_cost(obs["dice_bonus"]):
        out.append(UPGRADE)
    if gold >= SHIELD_COST:
        out.append(BUY_SHIELD)
    if gold >= STORE_DIE_COST and obs["roll_max"] > 0:
        out.append(STORE_BEST_DIE)
    return out


def apply(obs: dict, action: int) -> tuple[tuple, int, int | None]:
    """
    Aplica `action` a `obs` sin tocar el ambiente y devuelve

        (afterstate, puntos_inmediatos, score_amount)

    El afterstate es la tupla (turno, oro, dados, bonus, escudos, guardado)
    tal como queda DESPUES de la accion y ANTES de la tormenta. Es exactamente
    lo que el agente controla.
    """
    turn = obs["turn"]
    gold = obs["gold"]
    n = obs["num_dice"]
    b = obs["dice_bonus"]
    s = obs["shields"]

    if action == PASS:
        return (turn, gold, n, b, s, 0), 0, None
    if action == SCORE:
        return (turn, 0, n, b, s, 0), gold, int(gold)
    if action == BUY_DICE:
        return (turn, gold - get_new_dice_cost(n), n + 1, b, s, 0), 0, None
    if action == UPGRADE:
        return (turn, gold - get_upgrade_cost(b), n, b + 1, s, 0), 0, None
    if action == BUY_SHIELD:
        return (turn, gold - SHIELD_COST, n, b, s + 1, 0), 0, None
    if action == STORE_BEST_DIE:
        return (turn, gold - STORE_DIE_COST, n, b, s, obs["roll_max"]), 0, None
    raise ValueError(f"Accion desconocida: {action}")


def potential(afterstate: tuple) -> float:
    """
    Valuacion contable barata de un afterstate: activos a valor de libros mas
    ingreso futuro esperado si no se compra nada mas.

        oro + guardado + escudos * 5 + turnos_restantes * dados * (3.5 + bonus)

    Cada termino tiene una lectura clara:

      * oro y guardado    -- caja, convertible a puntos uno a uno
      * escudos * 5       -- a valor de COSTO. No es una estimacion de lo que
                             vale un escudo (eso lo tiene que aprender el
                             agente): es simplemente no contarlo como perdida.
      * ingreso futuro    -- lo que producen los dados si se dejan de comprar

    El termino de escudos parece un detalle y no lo es. Sin el, Phi valua
    BUY_SHIELD como "perder 5 de oro a cambio de nada", un sesgo sistematico
    contra la unica accion que hace posible acumular en el endgame. El
    diagnostico contra el oraculo lo mostro sin ambiguedad: el error mas
    frecuente del agente era no comprar el escudo (1488 veces sobre 300
    partidas), y sin escudo terminaba con 174 de oro contra los 484 del optimo.

    Contabilizar un activo comprado a su costo es una eleccion neutral: no le
    dice al agente que el escudo sea bueno, solo deja de decirle que es malo.

    Formalmente esto es shaping basado en potencial (Ng, Harada & Russell,
    1999) escrito como reparametrizacion V = Phi + R. Como R puede ser
    cualquier funcion, la clase de funciones representables no cambia: Phi
    mueve el punto de partida de la busqueda, no su destino.
    """
    turn, gold, n, b, s, carry = afterstate
    turns_left = HORIZON - turn
    return gold + carry + s * SHIELD_COST + turns_left * n * (MEAN_FACE + b)


def is_terminal(afterstate: tuple) -> bool:
    """
    Despues de la accion del turno 30 el episodio termina y no hay otra tirada
    (`_advance_turn` sale por `done` antes de `_roll_for_current_turn`). El
    valor de cualquier afterstate del turno 30 es exactamente 0.

    Esto NO se aprende: es una propiedad del horizonte, igual que saber que un
    episodio de ajedrez termina en jaque mate. Y hace que el argmax elija solo
    SCORE(todo) en el ultimo turno, sin ningun `if` especial en la politica.
    """
    return afterstate[0] >= HORIZON
