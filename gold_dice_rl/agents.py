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
# Nuestros agentes
#
# El que se entrega al torneo es GoldDiceAgent. Los dos comparten la misma
# forma de elegir jugada y se diferencian solo en la tabla de valores que
# consultan, asi que esa logica vive una sola vez, en _AfterstatePolicy.
# ==========================================================================

import os

from afterstate import apply as apply_action, legal_actions
from value_table import ValueTable

ARTIFACTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "artifacts")
DEFAULT_WEIGHTS = os.path.join(ARTIFACTS, "gold_dice_agent.pkl")


class _AfterstatePolicy:
    """
    Elige la jugada mirando en que estado te deja cada opcion.

    La idea: en este juego lo que hace tu accion es totalmente predecible
    (pagar 42 y sumar un dado es aritmetica). El azar viene despues. Entonces
    para cada jugada posible calculamos donde quedariamos, le preguntamos a la
    tabla cuanto vale ese lugar, le sumamos los puntos que cobramos en el acto,
    y nos quedamos con la mejor suma.

        jugada = la que maximiza   puntos_ahora + valor_del_estado_resultante
    """

    def __init__(self, table: ValueTable):
        self.table = table

    def act(self, obs, env=None):
        best_action, best_total, best_amount = None, float("-inf"), None
        for action in legal_actions(obs):
            after, points, amount = apply_action(obs, action)
            total = points + self.table.value(after)
            if total > best_total:
                best_action, best_total, best_amount = action, total, amount
        return best_action, best_amount


class GoldDiceAgent(_AfterstatePolicy):
    """
    El agente que entregamos.

    Aprendio jugando: nadie le dijo la probabilidad de tormenta ni como estan
    hechos los dados. Carga los pesos que dejo el entrenamiento y juega siempre
    su mejor jugada, sin azar y sin que nadie lo ayude.
    """

    def __init__(self, weights_path: str = DEFAULT_WEIGHTS):
        super().__init__(ValueTable.load(weights_path))


class PotentialAgent(_AfterstatePolicy):
    """
    El mismo agente pero SIN nada aprendido: la tabla arranca vacia, asi que
    solo usa la cuenta a mano ("si no compro nada mas, cuanto saco al final").

    Existe para poder responder una pregunta incomoda: de los puntos que saca
    el agente entrenado, cuantos vienen de haber aprendido y cuantos vienen de
    como escribimos el problema. Sin este control no se puede separar una cosa
    de la otra.
    """

    def __init__(self):
        super().__init__(ValueTable())
