import numpy as np

from config import (
    HORIZON,
    INITIAL_GOLD,
    INITIAL_POINTS,
    INITIAL_NUM_DICE,
    INITIAL_DICE_BONUS,
    INITIAL_SHIELDS,
    INITIAL_STORED_VALUE,
    STORM_PROB,
    DICE_FACES,
    SHIELD_COST,
    STORE_DIE_COST,
    get_new_dice_cost,
    get_upgrade_cost,
)


PASS = 0
SCORE = 1
BUY_DICE = 2
UPGRADE = 3
BUY_SHIELD = 4
STORE_BEST_DIE = 5

ACTION_NAMES = {
    PASS: "PASS",
    SCORE: "SCORE",
    BUY_DICE: "BUY_DICE",
    UPGRADE: "UPGRADE",
    BUY_SHIELD: "BUY_SHIELD",
    STORE_BEST_DIE: "STORE_BEST_DIE",
}

N_ACTIONS = len(ACTION_NAMES)


class InvalidActionError(Exception):
    pass


class GoldDiceEnv:
    """
    Gold Dice RL.

    step API:
        obs, reward, done, info = env.step(action, score_amount=None)

    SCORE is parameterized:
        env.step(SCORE, score_amount=k)
    """

    def __init__(self, obs_mode="vector", seed=None, track_history=True):
        assert obs_mode in ("vector", "dict")
        self.obs_mode = obs_mode
        self.track_history = track_history
        self.rng = np.random.default_rng(seed)
        self.reset(seed=seed)

    def reset(self, seed=None):
        if seed is not None:
            self.rng = np.random.default_rng(seed)

        self.turn = 1
        self.gold = INITIAL_GOLD
        self.points = INITIAL_POINTS
        self.num_dice = INITIAL_NUM_DICE
        self.dice_bonus = INITIAL_DICE_BONUS
        self.shields = INITIAL_SHIELDS
        self.stored_value = INITIAL_STORED_VALUE
        self.done = False

        self.raw_roll = []
        self.current_roll = []
        self.roll_sum = 0
        self.roll_max = 0
        self.history = []

        self._roll_for_current_turn()
        return self.get_obs()

    def step(self, action, score_amount=None):
        if self.done:
            raise RuntimeError("Episode is done. Call reset() before step().")

        action = int(action)

        valid, reason = self._is_action_valid(action, score_amount)
        if not valid:
            raise InvalidActionError(reason)

        info = {
            "turn": self.turn,
            "action": action,
            "action_name": ACTION_NAMES[action],
            "score_amount": int(score_amount) if action == SCORE else None,
            "valid_action": True,
            "gold_before_action": self.gold,
            "points_before_action": self.points,
            "storm": False,
            "storm_blocked": False,
        }

        reward = self._apply_action(action, score_amount)
        self._apply_storm(info)

        return self._advance_turn(reward, info)

    def _advance_turn(self, reward, info):
        if self.track_history:
            self.history.append(self._history_row(reward, info))

        self.turn += 1

        if self.turn > HORIZON:
            self.done = True
            return self.get_obs(), reward, True, info

        self._roll_for_current_turn()
        return self.get_obs(), reward, False, info

    def _is_action_valid(self, action, score_amount=None):
        if action not in ACTION_NAMES:
            return False, f"Unknown action: {action}"

        if action == PASS:
            return True, ""

        if action == SCORE:
            if score_amount is None:
                return False, "SCORE requires score_amount."
            try:
                score_amount = int(score_amount)
            except Exception:
                return False, "score_amount must be an integer."
            if score_amount < 0:
                return False, "score_amount must be >= 0."
            if score_amount > self.gold:
                return False, f"Cannot score {score_amount}: only {self.gold} gold available."
            return True, ""

        if action == BUY_DICE:
            cost = get_new_dice_cost(self.num_dice)
            if self.gold < cost:
                return False, f"Cannot buy dice: need {cost} gold, have {self.gold}."
            return True, ""

        if action == UPGRADE:
            cost = get_upgrade_cost(self.dice_bonus)
            if self.gold < cost:
                return False, f"Cannot upgrade: need {cost} gold, have {self.gold}."
            return True, ""

        if action == BUY_SHIELD:
            if self.gold < SHIELD_COST:
                return False, f"Cannot buy shield: need {SHIELD_COST} gold, have {self.gold}."
            return True, ""

        if action == STORE_BEST_DIE:
            if self.gold < STORE_DIE_COST:
                return False, f"Cannot store die: need {STORE_DIE_COST} gold, have {self.gold}."
            if self.roll_max <= 0:
                return False, "Cannot store die: no current roll."
            return True, ""

        return False, f"Unhandled action: {action}"

    def _apply_action(self, action, score_amount=None):
        if action == PASS:
            return 0

        if action == SCORE:
            score_amount = int(score_amount)
            self.gold -= score_amount
            self.points += score_amount
            return score_amount

        if action == BUY_DICE:
            self.gold -= get_new_dice_cost(self.num_dice)
            self.num_dice += 1
            return 0

        if action == UPGRADE:
            self.gold -= get_upgrade_cost(self.dice_bonus)
            self.dice_bonus += 1
            return 0

        if action == BUY_SHIELD:
            self.gold -= SHIELD_COST
            self.shields += 1
            return 0

        if action == STORE_BEST_DIE:
            self.gold -= STORE_DIE_COST
            self.stored_value = self.roll_max
            return 0

        raise InvalidActionError(f"Cannot apply unknown action: {action}")

    def _roll_for_current_turn(self):
        self.raw_roll = self.rng.choice(DICE_FACES, size=self.num_dice, replace=True).astype(int).tolist()
        self.current_roll = [int(value + self.dice_bonus) for value in self.raw_roll]
        self.roll_sum = int(sum(self.current_roll))
        self.roll_max = int(max(self.current_roll)) if self.current_roll else 0

        self.gold += self.roll_sum + self.stored_value
        self.stored_value = 0

    def _apply_storm(self, info):
        if self.rng.random() >= STORM_PROB:
            return

        info["storm"] = True

        if self.shields > 0:
            self.shields -= 1
            info["storm_blocked"] = True
        else:
            self.gold = self.gold // 2
            info["storm_blocked"] = False

    def get_obs(self):
        if self.obs_mode == "dict":
            return {
                "turn": self.turn,
                "points": self.points,
                "gold": self.gold,
                "num_dice": self.num_dice,
                "dice_bonus": self.dice_bonus,
                "shields": self.shields,
                "stored_value": self.stored_value,
                "roll_sum": self.roll_sum,
                "roll_max": self.roll_max,
            }

        return np.array(
            [
                self.turn,
                self.points,
                self.gold,
                self.num_dice,
                self.dice_bonus,
                self.shields,
                self.stored_value,
                self.roll_sum,
                self.roll_max,
            ],
            dtype=np.float32,
        )

    def get_action_mask(self):
        mask = np.zeros(N_ACTIONS, dtype=np.int8)
        for action in range(N_ACTIONS):
            if action == SCORE:
                # SCORE is valid because score_amount=0 is always legal.
                mask[action] = 1
            else:
                valid, _ = self._is_action_valid(action)
                mask[action] = int(valid)
        return mask

    def get_valid_actions(self):
        return [action for action in range(N_ACTIONS) if self.get_action_mask()[action] == 1]

    def get_valid_score_amounts(self):
        return list(range(self.gold + 1))

    def render(self):
        print(f"Turn: {self.turn}/{HORIZON}")
        print(f"Points: {self.points}")
        print(f"Gold: {self.gold}")
        print(f"Dice: {self.num_dice}")
        print(f"Dice bonus: +{self.dice_bonus}")
        print(f"Shields: {self.shields}")
        print(f"Stored value: {self.stored_value}")
        print(f"Raw roll: {self.raw_roll}")
        print(f"Modified roll: {self.current_roll}")
        print(f"Roll sum: {self.roll_sum}")
        print(f"Roll max: {self.roll_max}")
        print(f"Valid actions: {self.get_valid_actions()}")
        print("-" * 50)

    def _history_row(self, reward, info):
        return {
            "turn": self.turn,
            "action": info["action"],
            "action_name": info["action_name"],
            "score_amount": info["score_amount"],
            "reward": reward,
            "points": self.points,
            "gold": self.gold,
            "num_dice": self.num_dice,
            "dice_bonus": self.dice_bonus,
            "shields": self.shields,
            "stored_value": self.stored_value,
            "raw_roll": self.raw_roll.copy(),
            "roll": self.current_roll.copy(),
            "roll_sum": self.roll_sum,
            "roll_max": self.roll_max,
            "storm": info["storm"],
            "storm_blocked": info["storm_blocked"],
        }
