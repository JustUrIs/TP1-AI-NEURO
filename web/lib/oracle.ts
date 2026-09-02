/**
 * El oraculo: la solucion exacta del juego, en el navegador.
 *
 * No es un agente entrenado. Es la tabla que sale de resolver el MDP por
 * induccion hacia atras (`oracle_dp.py`), y dice, para cualquier estado,
 * cuantos puntos se esperan jugando perfecto. Con eso se puede hacer lo que sin
 * ella es imposible: **separar habilidad de suerte**.
 *
 * Para cada decision del jugador,
 *
 *     arrepentimiento = V*(antes) - [ puntos_inmediatos + V*(despues) ]
 *
 * Es siempre >= 0 y vale exactamente 0 cuando la jugada fue optima. Sumado
 * sobre la partida da todo lo que se perdio por decidir mal. Y entonces
 *
 *     calidad  = 642.45 - suma de arrepentimientos     <- lo que hiciste
 *     suerte   = puntaje real - calidad                <- lo que te paso
 *
 * Las dos suman tu puntaje final, exacto. Es el mismo principio que el
 * "EV-adjusted winnings" de los solvers de poker: alguien puede sacar 700
 * jugando mal y con suerte, y 400 jugando perfecto y con mala suerte. El
 * ranking por calidad de decisiones no se puede farmear tirando de nuevo.
 *
 * El binario pesa 1.3 MB comprimido y se carga en diferido: solo hace falta al
 * terminar la partida, para el analisis.
 */

import {
  HORIZON,
  SCORE,
  SHIELD_COST,
  STORE_DIE_COST,
  STORM_PROB,
  newDiceCost,
  upgradeCost,
  type Action,
  type Obs,
  type TurnRecord,
} from "./engine.ts";
import { actionLabel, applyAction, goldFeatures, legalActions, type Move } from "./models.ts";

interface OracleMeta {
  file: string;
  scale: number;
  gold_nodes: number[];
  optimal: number;
  dims: { t: number; n: [number, number]; b: [number, number]; s: [number, number]; node: number };
}

export class Oracle {
  readonly optimal: number;
  private data: Int16Array;
  private nodes: number[];
  private scale: number;
  private dims: OracleMeta["dims"];
  private strideS: number;
  private strideB: number;
  private strideN: number;
  private strideT: number;

  constructor(meta: OracleMeta, buffer: ArrayBuffer) {
    this.data = new Int16Array(buffer);
    this.nodes = meta.gold_nodes;
    this.scale = meta.scale;
    this.dims = meta.dims;
    this.optimal = meta.optimal;

    const nNode = meta.dims.node;
    const nS = meta.dims.s[1] - meta.dims.s[0] + 1;
    const nB = meta.dims.b[1] - meta.dims.b[0] + 1;
    const nN = meta.dims.n[1] - meta.dims.n[0] + 1;
    this.strideS = nNode;
    this.strideB = nS * nNode;
    this.strideN = nB * nS * nNode;
    this.strideT = nN * nB * nS * nNode;
  }

  /** U[t, n, b, s, oro]: puntos esperados ANTES de tirar los dados del turno t. */
  private u(t: number, gold: number, n: number, b: number, s: number): number {
    if (t > this.dims.t) return 0;
    const d = this.dims;
    const ni = Math.min(Math.max(n, d.n[0]), d.n[1]) - d.n[0];
    const bi = Math.min(Math.max(b, d.b[0]), d.b[1]) - d.b[0];
    const si = Math.min(Math.max(s, d.s[0]), d.s[1]) - d.s[0];
    const base = (t - 1) * this.strideT + ni * this.strideN + bi * this.strideB + si * this.strideS;
    const [i, j, w] = goldFeatures(gold, this.nodes);
    const vi = this.data[base + i] / this.scale;
    if (i === j) return vi;
    return (1 - w) * vi + w * this.data[base + j] / this.scale;
  }

  /**
   * Valor de terminar el turno `t` con este oro y esta maquinaria, integrando
   * la tormenta y la tirada del turno siguiente.
   *
   * `carry` es lo guardado por STORE_BEST_DIE: entra al oro recien en la tirada
   * del turno siguiente, o sea DESPUES de la tormenta. Por eso lo guardado no
   * se puede partir al medio.
   */
  private tail(t: number, gold: number, n: number, b: number, s: number, carry = 0): number {
    if (t >= HORIZON) return 0;
    const keep = gold + carry;
    let value = (1 - STORM_PROB) * this.u(t + 1, keep, n, b, s);
    if (s > 0) {
      value += STORM_PROB * this.u(t + 1, keep, n, b, s - 1);
    } else {
      value += STORM_PROB * this.u(t + 1, Math.floor(gold / 2) + carry, n, b, 0);
    }
    return value;
  }

  /** Valor exacto de una jugada concreta, incluyendo cuanto oro se puntuo. */
  valueOf(obs: Obs, action: Action, amount: number | null): number {
    if (action === SCORE) {
      const k = Math.max(0, Math.min(Math.floor(amount ?? 0), obs.gold));
      return k + this.tail(obs.turn, obs.gold - k, obs.numDice, obs.diceBonus, obs.shields);
    }
    const { after, points } = applyAction(obs, action);
    return points + this.tail(obs.turn, after.gold, after.numDice, after.diceBonus, after.shields, after.carry);
  }

  /** Todas las jugadas legales, ordenadas de mejor a peor. */
  rank(obs: Obs): (Move & { value: number; label: string })[] {
    const out: (Move & { value: number; label: string })[] = [];
    for (const action of legalActions(obs)) {
      if (action === SCORE) {
        // SCORE es parametrica. Se barre el oro que queda sobre los nodos de la
        // grilla y se elige el mejor corte: el optimo casi siempre es puntuar
        // todo, pero no siempre, y la diferencia se puede ver.
        let best = { value: -Infinity, keep: 0 };
        for (const keep of this.nodes) {
          if (keep > obs.gold) break;
          const v = obs.gold - keep + this.tail(obs.turn, keep, obs.numDice, obs.diceBonus, obs.shields);
          if (v > best.value) best = { value: v, keep };
        }
        const amount = obs.gold - best.keep;
        out.push({ action, scoreAmount: amount, value: best.value, label: actionLabel(action, amount) });
      } else {
        const { amount } = applyAction(obs, action);
        out.push({
          action,
          scoreAmount: amount,
          value: this.valueOf(obs, action, amount),
          label: actionLabel(action, amount),
        });
      }
    }
    return out.sort((a, b) => b.value - a.value);
  }

  best(obs: Obs) {
    return this.rank(obs)[0];
  }
}

// --------------------------------------------------------------------------
// Analisis de una partida terminada
// --------------------------------------------------------------------------
export interface TurnAnalysis {
  turn: number;
  played: string;
  playedValue: number;
  bestMove: Move;
  bestLabel: string;
  bestValue: number;
  regret: number;
}

export interface GameAnalysis {
  optimal: number;
  finalScore: number;
  /** Suma de lo que se perdio por decidir mal. */
  totalRegret: number;
  /** 642.45 - arrepentimiento: lo que valia la partida jugada como la jugaste. */
  skill: number;
  /** Puntaje real menos calidad: lo que aporto (o saco) el azar. */
  luck: number;
  /** Porcentaje del optimo capturado por tus decisiones. */
  decisionScore: number;
  turns: TurnAnalysis[];
  worst: TurnAnalysis[];
}

export function analyze(oracle: Oracle, observations: Obs[], history: TurnRecord[]): GameAnalysis {
  const turns: TurnAnalysis[] = [];
  let totalRegret = 0;

  history.forEach((record, i) => {
    const obs = observations[i];
    const played = oracle.valueOf(obs, record.action, record.scoreAmount);
    const best = oracle.best(obs);
    const regret = Math.max(0, best.value - played);
    totalRegret += regret;
    turns.push({
      turn: record.turn,
      played: actionLabel(record.action, record.scoreAmount),
      playedValue: played,
      bestMove: { action: best.action, scoreAmount: best.scoreAmount },
      bestLabel: best.label,
      bestValue: best.value,
      regret,
    });
  });

  const finalScore = history.length ? history[history.length - 1].pointsAfter : 0;
  const skill = oracle.optimal - totalRegret;
  return {
    optimal: oracle.optimal,
    finalScore,
    totalRegret,
    skill,
    luck: finalScore - skill,
    decisionScore: 100 * (1 - totalRegret / oracle.optimal),
    turns,
    worst: [...turns].sort((a, b) => b.regret - a.regret).slice(0, 3),
  };
}

let cached: Promise<Oracle> | null = null;

export function loadOracle(meta: OracleMeta): Promise<Oracle> {
  if (!cached) {
    cached = fetch(`/models/${meta.file}`)
      .then((r) => {
        if (!r.ok) throw new Error("No se pudo cargar el oráculo");
        return r.arrayBuffer();
      })
      .then((buf) => new Oracle(meta, buf));
  }
  return cached;
}

/** Costos, para las explicaciones. */
export const costs = { newDiceCost, upgradeCost, SHIELD_COST, STORE_DIE_COST };
