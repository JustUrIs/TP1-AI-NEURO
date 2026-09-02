/**
 * Los agentes entrenados, corriendo en el navegador.
 *
 * Nada de esto llama a ninguna API. Los pesos se bajan una vez como binarios
 * int16 (170 KB el Campeon, comprimido) y las politicas se evaluan aca, lo que
 * hace que el rival responda instantaneamente y que la pagina funcione sin
 * servidor.
 *
 * Hay dos familias, y no por capricho: son exactamente los dos enfoques que se
 * compararon en el trabajo.
 *
 *   afterstate  aprende V(estado posterior a la accion) y elige
 *               argmax_a [ puntos_inmediatos(a) + V(afterstate(a)) ].
 *               Es el agente bueno.
 *
 *   tabular     Q(estado discretizado, accion) con la receta clasica. Son las
 *               ablaciones del informe, y sirven de rivales de menor nivel:
 *               juegan distinto, no solo peor.
 */

import {
  BUY_DICE,
  BUY_SHIELD,
  HORIZON,
  PASS,
  SCORE,
  SHIELD_COST,
  STORE_BEST_DIE,
  STORE_DIE_COST,
  UPGRADE,
  newDiceCost,
  upgradeCost,
  type Action,
  type Obs,
} from "./engine.ts";

export interface Move {
  action: Action;
  scoreAmount: number | null;
}

export interface ScoredMove extends Move {
  value: number;
  label: string;
}

export interface Model {
  id: string;
  label: string;
  algo: string;
  mean: number;
  pct: number;
  /** Valor de cada accion legal, de mejor a peor. */
  rank(obs: Obs): ScoredMove[];
  act(obs: Obs): Move;
}

// --------------------------------------------------------------------------
// Utilidades comunes
// --------------------------------------------------------------------------
const MEAN_FACE = 3.5;

/** Interpolacion lineal sobre la grilla no uniforme de oro. */
export function goldFeatures(gold: number, nodes: number[]): [number, number, number] {
  const last = nodes.length - 1;
  if (gold >= nodes[last]) return [last, last, 0];
  let lo = 0;
  let hi = last;
  while (lo < hi) {
    const mid = (lo + hi + 1) >> 1;
    if (nodes[mid] <= gold) lo = mid;
    else hi = mid - 1;
  }
  if (nodes[lo] === gold) return [lo, lo, 0];
  return [lo, lo + 1, (gold - nodes[lo]) / (nodes[lo + 1] - nodes[lo])];
}

export interface Afterstate {
  turn: number;
  gold: number;
  numDice: number;
  diceBonus: number;
  shields: number;
  carry: number;
}

/** Efecto determinista de una accion sobre el estado. Espeja `afterstate.py`. */
export function applyAction(obs: Obs, action: Action): { after: Afterstate; points: number; amount: number | null } {
  const base = {
    turn: obs.turn,
    gold: obs.gold,
    numDice: obs.numDice,
    diceBonus: obs.diceBonus,
    shields: obs.shields,
    carry: 0,
  };
  switch (action) {
    case PASS:
      return { after: base, points: 0, amount: null };
    case SCORE:
      return { after: { ...base, gold: 0 }, points: obs.gold, amount: obs.gold };
    case BUY_DICE:
      return {
        after: { ...base, gold: obs.gold - newDiceCost(obs.numDice), numDice: obs.numDice + 1 },
        points: 0,
        amount: null,
      };
    case UPGRADE:
      return {
        after: { ...base, gold: obs.gold - upgradeCost(obs.diceBonus), diceBonus: obs.diceBonus + 1 },
        points: 0,
        amount: null,
      };
    case BUY_SHIELD:
      return {
        after: { ...base, gold: obs.gold - SHIELD_COST, shields: obs.shields + 1 },
        points: 0,
        amount: null,
      };
    case STORE_BEST_DIE:
      return {
        after: { ...base, gold: obs.gold - STORE_DIE_COST, carry: obs.rollMax },
        points: 0,
        amount: null,
      };
  }
}

export function legalActions(obs: Obs): Action[] {
  const out: Action[] = [PASS, SCORE];
  if (obs.gold >= newDiceCost(obs.numDice)) out.push(BUY_DICE);
  if (obs.gold >= upgradeCost(obs.diceBonus)) out.push(UPGRADE);
  if (obs.gold >= SHIELD_COST) out.push(BUY_SHIELD);
  if (obs.gold >= STORE_DIE_COST && obs.rollMax > 0) out.push(STORE_BEST_DIE);
  return out;
}

/**
 * Valuacion contable: caja, mas activos a valor de costo, mas el ingreso futuro
 * si no se compra nada mas. La tabla aprende el RESIDUO sobre esto.
 */
export function potential(a: Afterstate): number {
  const turnsLeft = HORIZON - a.turn;
  return a.gold + a.carry + a.shields * SHIELD_COST + turnsLeft * a.numDice * (MEAN_FACE + a.diceBonus);
}

export function actionLabel(action: Action, amount: number | null): string {
  switch (action) {
    case PASS:
      return "pasar";
    case SCORE:
      return amount && amount > 0 ? `puntuar ${amount}` : "puntuar 0";
    case BUY_DICE:
      return "comprar un dado";
    case UPGRADE:
      return "mejorar los dados";
    case BUY_SHIELD:
      return "comprar un escudo";
    case STORE_BEST_DIE:
      return "guardar el mejor dado";
  }
}

// --------------------------------------------------------------------------
// Agente por afterstates
// --------------------------------------------------------------------------
interface AfterstateMeta {
  label: string;
  algo: string;
  mean: number;
  pct: number;
  scale: number;
  gold_nodes: number[];
  dims: { t: number; node: number; n: [number, number]; b: [number, number]; s: [number, number] };
}

export class AfterstateModel implements Model {
  readonly id: string;
  readonly label: string;
  readonly algo: string;
  readonly mean: number;
  readonly pct: number;

  private data: Int16Array;
  private nodes: number[];
  private scale: number;
  private dims: AfterstateMeta["dims"];
  private strideNode: number;
  private strideT: number;
  private strideN: number;
  private strideB: number;

  constructor(id: string, meta: AfterstateMeta, buffer: ArrayBuffer) {
    this.id = id;
    this.label = meta.label;
    this.algo = meta.algo;
    this.mean = meta.mean;
    this.pct = meta.pct;
    this.data = new Int16Array(buffer);
    this.nodes = meta.gold_nodes;
    this.scale = meta.scale;
    this.dims = meta.dims;

    const nS = meta.dims.s[1] - meta.dims.s[0] + 1;
    const nB = meta.dims.b[1] - meta.dims.b[0] + 1;
    const nN = meta.dims.n[1] - meta.dims.n[0] + 1;
    this.strideB = nS;
    this.strideN = nB * nS;
    this.strideNode = nN * nB * nS;
    this.strideT = meta.dims.node * this.strideNode;
  }

  private residual(a: Afterstate, node: number): number {
    const { n, b, s } = this.dims;
    const ni = Math.min(Math.max(a.numDice, n[0]), n[1]) - n[0];
    const bi = Math.min(Math.max(a.diceBonus, b[0]), b[1]) - b[0];
    const si = Math.min(Math.max(a.shields, s[0]), s[1]) - s[0];
    const idx =
      (a.turn - 1) * this.strideT + node * this.strideNode + ni * this.strideN + bi * this.strideB + si;
    return this.data[idx] / this.scale;
  }

  value(a: Afterstate): number {
    // Despues de la accion del turno 30 el episodio termina: no hay otra tirada
    // y el oro que quede se evapora. Ese estado vale exactamente 0, y de ahi
    // sale solo que la mejor jugada del ultimo turno sea puntuar todo.
    if (a.turn >= HORIZON) return 0;
    const [i, j, w] = goldFeatures(a.gold, this.nodes);
    const r = i === j ? this.residual(a, i) : (1 - w) * this.residual(a, i) + w * this.residual(a, j);
    return potential(a) + r;
  }

  rank(obs: Obs): ScoredMove[] {
    return legalActions(obs)
      .map((action) => {
        const { after, points, amount } = applyAction(obs, action);
        return {
          action,
          scoreAmount: amount,
          value: points + this.value(after),
          label: actionLabel(action, amount),
        };
      })
      .sort((x, y) => y.value - x.value);
  }

  act(obs: Obs): Move {
    const best = this.rank(obs)[0];
    return { action: best.action, scoreAmount: best.scoreAmount };
  }
}

// --------------------------------------------------------------------------
// Agente Q tabular clasico
// --------------------------------------------------------------------------
const Q_PASS = 0;
const Q_SCORE_ALL = 1;
const Q_SCORE_HALF = 2;
const Q_BUY_DICE = 3;
const Q_UPGRADE = 4;
const Q_BUY_SHIELD = 5;
const Q_STORE = 6;

interface TabularMeta {
  label: string;
  algo: string;
  mean: number;
  pct: number;
  scale: number;
  count: number;
  score_space: "all" | "all_half";
  preset: {
    gold_width: number;
    gold_cap: number;
    dice_cap: number;
    bonus_cap: number;
    shield_cap: number;
    turn_width: number;
  };
}

export class TabularModel implements Model {
  readonly id: string;
  readonly label: string;
  readonly algo: string;
  readonly mean: number;
  readonly pct: number;

  private keys: Int16Array;
  private vals: Int16Array;
  private scale: number;
  private count: number;
  private preset: TabularMeta["preset"];
  private scoreSpace: "all" | "all_half";

  constructor(id: string, meta: TabularMeta, keys: ArrayBuffer, vals: ArrayBuffer) {
    this.id = id;
    this.label = meta.label;
    this.algo = meta.algo;
    this.mean = meta.mean;
    this.pct = meta.pct;
    this.keys = new Int16Array(keys);
    this.vals = new Int16Array(vals);
    this.scale = meta.scale;
    this.count = meta.count;
    this.preset = meta.preset;
    this.scoreSpace = meta.score_space;
  }

  private discretize(obs: Obs): [number, number, number, number, number] {
    const p = this.preset;
    const turnsLeft = HORIZON - obs.turn;
    const tl = turnsLeft === 0 ? 0 : 1 + Math.floor((turnsLeft - 1) / p.turn_width);
    return [
      tl,
      Math.floor(Math.min(obs.gold, p.gold_cap) / p.gold_width),
      Math.min(obs.numDice, p.dice_cap),
      Math.min(obs.diceBonus, p.bonus_cap),
      Math.min(obs.shields, p.shield_cap),
    ];
  }

  /** Las claves estan ordenadas: se busca por biseccion sobre el arreglo plano. */
  private lookup(key: number[]): number {
    let lo = 0;
    let hi = this.count - 1;
    while (lo <= hi) {
      const mid = (lo + hi) >> 1;
      const off = mid * 5;
      let cmp = 0;
      for (let d = 0; d < 5; d += 1) {
        if (this.keys[off + d] !== key[d]) {
          cmp = this.keys[off + d] < key[d] ? -1 : 1;
          break;
        }
      }
      if (cmp === 0) return mid;
      if (cmp < 0) lo = mid + 1;
      else hi = mid - 1;
    }
    return -1;
  }

  private qActions(obs: Obs): number[] {
    const out = [Q_PASS, Q_SCORE_ALL];
    if (this.scoreSpace === "all_half") out.push(Q_SCORE_HALF);
    if (obs.gold >= newDiceCost(obs.numDice)) out.push(Q_BUY_DICE);
    if (obs.gold >= upgradeCost(obs.diceBonus)) out.push(Q_UPGRADE);
    if (obs.gold >= SHIELD_COST) out.push(Q_BUY_SHIELD);
    if (obs.gold >= STORE_DIE_COST && obs.rollMax > 0) out.push(Q_STORE);
    return out;
  }

  private toMove(q: number, obs: Obs): Move {
    switch (q) {
      case Q_PASS:
        return { action: PASS, scoreAmount: null };
      case Q_SCORE_ALL:
        return { action: SCORE, scoreAmount: obs.gold };
      case Q_SCORE_HALF:
        return { action: SCORE, scoreAmount: Math.floor(obs.gold / 2) };
      case Q_BUY_DICE:
        return { action: BUY_DICE, scoreAmount: null };
      case Q_UPGRADE:
        return { action: UPGRADE, scoreAmount: null };
      case Q_BUY_SHIELD:
        return { action: BUY_SHIELD, scoreAmount: null };
      default:
        return { action: STORE_BEST_DIE, scoreAmount: null };
    }
  }

  rank(obs: Obs): ScoredMove[] {
    const row = this.lookup(this.discretize(obs));
    return this.qActions(obs)
      .map((q) => {
        const move = this.toMove(q, obs);
        // Estado nunca visitado en el entrenamiento: el agente no tiene nada
        // que decir. Se ordena por el indice de accion, igual que en Python.
        const value = row < 0 ? -q : this.vals[row * 7 + q] / this.scale;
        return { ...move, value, label: actionLabel(move.action, move.scoreAmount) };
      })
      .sort((x, y) => y.value - x.value);
  }

  act(obs: Obs): Move {
    const best = this.rank(obs)[0];
    return { action: best.action, scoreAmount: best.scoreAmount };
  }
}

// --------------------------------------------------------------------------
// Carga
// --------------------------------------------------------------------------
export interface Manifest {
  optimal: number;
  agents: Record<string, AfterstateMeta | (TabularMeta & { keys: string; vals: string })>;
  oracle: {
    label: string;
    mean: number;
    pct: number;
    file: string;
    scale: number;
    gold_nodes: number[];
    optimal: number;
    dims: { t: number; n: [number, number]; b: [number, number]; s: [number, number]; node: number };
  };
}

async function fetchBuffer(path: string): Promise<ArrayBuffer> {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`No se pudo cargar ${path}`);
  return res.arrayBuffer();
}

export async function loadModels(): Promise<{ manifest: Manifest; models: Model[] }> {
  const manifest: Manifest = await (await fetch("/models/manifest.json")).json();
  const models: Model[] = [];
  for (const [id, meta] of Object.entries(manifest.agents)) {
    if ((meta as AfterstateMeta).gold_nodes) {
      const m = meta as AfterstateMeta & { file: string };
      models.push(new AfterstateModel(id, m, await fetchBuffer(`/models/${m.file}`)));
    } else {
      const m = meta as TabularMeta & { keys: string; vals: string };
      models.push(
        new TabularModel(id, m, await fetchBuffer(`/models/${m.keys}`), await fetchBuffer(`/models/${m.vals}`)),
      );
    }
  }
  models.sort((a, b) => b.mean - a.mean);
  return { manifest, models };
}
