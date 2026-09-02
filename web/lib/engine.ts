/**
 * Motor de Gold Dice RL.
 *
 * Es un port fiel de `env.py`. La fidelidad no es opcional: si el juego del
 * navegador difiere del ambiente en el que se entrenaron los agentes, todo lo
 * que muestre la pagina —el valor de las jugadas, el arrepentimiento, la
 * separacion entre habilidad y suerte— queda sin sentido.
 *
 * `scripts/check_engine.ts` verifica el port contra una traza generada por el
 * Python original: mismas tiradas, mismas tormentas, mismos estados turno a
 * turno.
 *
 * CRONOLOGIA DE UN TURNO (leida de env.py, no del enunciado)
 *
 *   1. TIRADA     gold += rollSum + storedValue ; storedValue = 0
 *   2. DECISION   el agente ve el estado (el oro de la tirada YA esta sumado)
 *   3. ACCION     exactamente una
 *   4. TORMENTA   p = 0.15  -> con escudo se pierde el escudo; sin escudo,
 *                              gold = floor(gold / 2)
 *   5. t += 1     ; si t > 30 -> fin, y NO se vuelve a tirar
 *
 * De ese orden salen los dos hechos que gobiernan la estrategia: los puntos son
 * inmunes a la tormenta (se cobran antes), y el oro que sobrevive al turno 30
 * sin puntuar se evapora.
 */

export const HORIZON = 30;
export const STORM_PROB = 0.15;
export const DICE_FACES = [1, 2, 3, 4, 5, 6] as const;

export const INITIAL_NUM_DICE = 1;
export const INITIAL_DICE_BONUS = 0;

export const BASE_NEW_DICE_COST = 18;
export const NEW_DICE_COST_GROWTH = 8;
export const BASE_UPGRADE_COST = 8;
export const UPGRADE_COST_GROWTH = 8;
export const SHIELD_COST = 5;
export const STORE_DIE_COST = 4;

export const newDiceCost = (numDice: number) =>
  BASE_NEW_DICE_COST + NEW_DICE_COST_GROWTH * (numDice - 1);
export const upgradeCost = (diceBonus: number) =>
  BASE_UPGRADE_COST + UPGRADE_COST_GROWTH * diceBonus;

export const PASS = 0;
export const SCORE = 1;
export const BUY_DICE = 2;
export const UPGRADE = 3;
export const BUY_SHIELD = 4;
export const STORE_BEST_DIE = 5;

export type Action = 0 | 1 | 2 | 3 | 4 | 5;

export const ACTION_NAMES: Record<Action, string> = {
  0: "PASAR",
  1: "PUNTUAR",
  2: "COMPRAR DADO",
  3: "MEJORAR",
  4: "COMPRAR ESCUDO",
  5: "GUARDAR DADO",
};

export interface Obs {
  turn: number;
  points: number;
  gold: number;
  numDice: number;
  diceBonus: number;
  shields: number;
  storedValue: number;
  rollSum: number;
  rollMax: number;
}

export interface StepInfo {
  turn: number;
  action: Action;
  scoreAmount: number | null;
  goldBeforeAction: number;
  storm: boolean;
  stormBlocked: boolean;
  goldLostToStorm: number;
}

export interface TurnRecord extends StepInfo {
  rawRoll: number[];
  roll: number[];
  pointsAfter: number;
  goldAfter: number;
  numDiceAfter: number;
  diceBonusAfter: number;
  shieldsAfter: number;
}

/**
 * Fuentes de azar, inyectadas.
 *
 * `rollDice(turn, count)` recibe el turno para que varias partidas paralelas
 * puedan compartir la MISMA tirada: el jugador con 5 dados obtiene los primeros
 * 5 valores del turno y el que tiene 3 obtiene los primeros 3, o sea que la
 * suerte de los dados es literalmente la misma y todo lo que los separa son sus
 * decisiones. `storm(turn)` se comparte igual, y como se consume exactamente
 * una vez por turno sin importar la politica, los mismos turnos tienen tormenta
 * para todos.
 *
 * Esto es justamente lo que `env.py` NO puede dar: alli un unico generador
 * sirve dados y tormentas, y `size=num_dice` depende de la politica, asi que
 * dos agentes con la misma semilla ven azares distintos.
 */
export interface Randomness {
  rollDice(turn: number, count: number): number[];
  storm(turn: number): boolean;
}

export class GoldDiceGame {
  turn = 1;
  gold = 0;
  points = 0;
  numDice = INITIAL_NUM_DICE;
  diceBonus = INITIAL_DICE_BONUS;
  shields = 0;
  storedValue = 0;
  done = false;

  rawRoll: number[] = [];
  roll: number[] = [];
  rollSum = 0;
  rollMax = 0;
  history: TurnRecord[] = [];

  private rng: Randomness;

  constructor(rng: Randomness) {
    this.rng = rng;
    this.rollForCurrentTurn();
  }

  obs(): Obs {
    return {
      turn: this.turn,
      points: this.points,
      gold: this.gold,
      numDice: this.numDice,
      diceBonus: this.diceBonus,
      shields: this.shields,
      storedValue: this.storedValue,
      rollSum: this.rollSum,
      rollMax: this.rollMax,
    };
  }

  validActions(): Action[] {
    // PASS y SCORE siempre son legales: SCORE(0) no requiere oro.
    const out: Action[] = [PASS, SCORE];
    if (this.gold >= newDiceCost(this.numDice)) out.push(BUY_DICE);
    if (this.gold >= upgradeCost(this.diceBonus)) out.push(UPGRADE);
    if (this.gold >= SHIELD_COST) out.push(BUY_SHIELD);
    if (this.gold >= STORE_DIE_COST && this.rollMax > 0) out.push(STORE_BEST_DIE);
    return out;
  }

  step(action: Action, scoreAmount: number | null = null): TurnRecord {
    if (this.done) throw new Error("La partida terminó. Llamá a reset().");

    const info: StepInfo = {
      turn: this.turn,
      action,
      scoreAmount: action === SCORE ? Math.floor(scoreAmount ?? 0) : null,
      goldBeforeAction: this.gold,
      storm: false,
      stormBlocked: false,
      goldLostToStorm: 0,
    };

    this.applyAction(action, info.scoreAmount);
    this.applyStorm(info);

    const record: TurnRecord = {
      ...info,
      rawRoll: [...this.rawRoll],
      roll: [...this.roll],
      pointsAfter: this.points,
      goldAfter: this.gold,
      numDiceAfter: this.numDice,
      diceBonusAfter: this.diceBonus,
      shieldsAfter: this.shields,
    };
    this.history.push(record);

    this.turn += 1;
    if (this.turn > HORIZON) {
      this.done = true;
    } else {
      this.rollForCurrentTurn();
    }
    return record;
  }

  private applyAction(action: Action, scoreAmount: number | null) {
    switch (action) {
      case PASS:
        return;
      case SCORE: {
        const k = Math.max(0, Math.min(Math.floor(scoreAmount ?? 0), this.gold));
        this.gold -= k;
        this.points += k;
        return;
      }
      case BUY_DICE:
        this.gold -= newDiceCost(this.numDice);
        this.numDice += 1;
        return;
      case UPGRADE:
        this.gold -= upgradeCost(this.diceBonus);
        this.diceBonus += 1;
        return;
      case BUY_SHIELD:
        this.gold -= SHIELD_COST;
        this.shields += 1;
        return;
      case STORE_BEST_DIE:
        this.gold -= STORE_DIE_COST;
        // No aparta el dado: lo CLONA. La suma de la tirada ya se cobró, y
        // roll_max se vuelve a cobrar en la tirada siguiente.
        this.storedValue = this.rollMax;
        return;
    }
  }

  private applyStorm(info: StepInfo) {
    if (!this.rng.storm(this.turn)) return;
    info.storm = true;
    if (this.shields > 0) {
      this.shields -= 1;
      info.stormBlocked = true;
    } else {
      const before = this.gold;
      this.gold = Math.floor(this.gold / 2);
      info.goldLostToStorm = before - this.gold;
    }
  }

  private rollForCurrentTurn() {
    this.rawRoll = this.rng.rollDice(this.turn, this.numDice);
    this.roll = this.rawRoll.map((v) => v + this.diceBonus);
    this.rollSum = this.roll.reduce((a, b) => a + b, 0);
    this.rollMax = this.roll.length ? Math.max(...this.roll) : 0;
    this.gold += this.rollSum + this.storedValue;
    this.storedValue = 0;
  }
}
