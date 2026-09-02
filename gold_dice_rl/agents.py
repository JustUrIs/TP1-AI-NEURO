import numpy as np

from config import (
    HORIZON,
    DICE_FACES,
    SHIELD_COST,
    get_new_dice_cost,
    get_upgrade_cost,
)

from env import (
    PASS,
    SCORE,
    BUY_DICE,
    UPGRADE,
    BUY_SHIELD,
)


class RandomLegalAgent:
    def __init__(self, seed=None):
        self.rng = np.random.default_rng(seed)

    def act(self, obs, env):
        action = int(self.rng.choice(env.get_valid_actions()))
        score_amount = None

        if action == SCORE:
            score_amount = int(self.rng.choice(env.get_valid_score_amounts()))

        return action, score_amount


class SimpleExpectancyAgent:

    def act(self, obs, env=None):
        turn = obs["turn"]
        gold = obs["gold"]
        num_dice = obs["num_dice"]
        dice_bonus = obs["dice_bonus"]
        shields = obs["shields"]

        turns_left = HORIZON - turn

        if turns_left == 0:
            return SCORE, gold

        if shields == 0 and gold >= SHIELD_COST:
            return BUY_SHIELD, None

        best_action = PASS
        best_value = 0.0

        dice_cost = get_new_dice_cost(num_dice)
        if gold >= dice_cost:
            buy_dice_value = (float(np.mean(DICE_FACES)) + dice_bonus) * turns_left - dice_cost
            if buy_dice_value > best_value:
                best_value = buy_dice_value
                best_action = BUY_DICE

        upgrade_cost = get_upgrade_cost(dice_bonus)
        if gold >= upgrade_cost:
            upgrade_value = num_dice * turns_left - upgrade_cost
            if upgrade_value > best_value:
                best_value = upgrade_value
                best_action = UPGRADE

        return best_action, None


# ==========================================================================
# Agentes propios
#
# El agente que se entrega al torneo es GoldDiceAgent (mas abajo): un agente
# de TD tabular sobre afterstates, entrenado unicamente jugando contra el
# ambiente. Carga sus pesos de artifacts/ y juega greedy, sin intervencion
# manual y sin aleatoriedad.
#
# Ver:
#   afterstate.py            representacion y transiciones deterministas
#   value_table.py           tabla de valores (residuo sobre un potencial)
#   train_afterstate.py      entrenamiento
#   oracle_dp.py             solver exacto -- NO es un agente de aprendizaje,
#                            se usa solo para medir y diagnosticar
# ==========================================================================

import os

_ARTIFACTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "artifacts")


class GoldDiceAgent:
    """
    Agente entregado al torneo.

    TD tabular sobre afterstates con gamma = 1. Aprende V(estado posterior a la
    accion) y elige

        accion = argmax_a [ puntos_inmediatos(a) + V(afterstate(a)) ]

    Todo lo que sabe salio de jugar: el ambiente nunca le dijo las
    probabilidades de tormenta ni la distribucion de los dados.
    """

    def __init__(self, weights_path=None):
        from value_table import ValueTable
        from afterstate import apply as _apply, legal_actions as _legal

        if weights_path is None:
            weights_path = os.path.join(_ARTIFACTS, "gold_dice_agent.pkl")
        self._table = ValueTable.load(weights_path)
        self._apply = _apply
        self._legal = _legal

    def act(self, obs, env=None):
        best_action, best_value, best_amount = None, float("-inf"), None
        for action in self._legal(obs):
            after, points, amount = self._apply(obs, action)
            total = points + self._table.value(after)
            if total > best_value:
                best_action, best_value, best_amount = action, total, amount
        return best_action, best_amount


class PotentialAgent:
    """
    Control: la misma politica greedy sobre afterstates pero con el residuo en
    cero, o sea usando SOLO el potencial analitico

        Phi = oro + guardado + turnos_restantes * dados * (3.5 + bonus)

    No aprende nada. Existe para separar "cuanto viene del diseño de la
    representacion" de "cuanto viene del aprendizaje". Sin este control, el
    puntaje del agente entrenado no se puede atribuir.
    """

    def __init__(self):
        from value_table import ValueTable
        from afterstate import apply as _apply, legal_actions as _legal

        self._table = ValueTable()
        self._apply = _apply
        self._legal = _legal

    def act(self, obs, env=None):
        best_action, best_value, best_amount = None, float("-inf"), None
        for action in self._legal(obs):
            after, points, amount = self._apply(obs, action)
            total = points + self._table.value(after)
            if total > best_value:
                best_action, best_value, best_amount = action, total, amount
        return best_action, best_amount
