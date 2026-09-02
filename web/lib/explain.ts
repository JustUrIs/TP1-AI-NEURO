/**
 * Explicaciones de jugadas.
 *
 * Sin llamadas a ninguna API y sin texto escrito a mano por jugada. Cada frase
 * se arma con los numeros que el agente REALMENTE calculo en ese estado: su
 * valuacion de la mejor jugada, la de la segunda, y la aritmetica del juego
 * (cuanto rinde un dado por turno, en cuantos turnos se paga, cuanto oro se
 * espera perder por tormenta).
 *
 * Si el agente cambia de opinion, la explicacion cambia sola. Eso importa: una
 * explicacion escrita aparte del razonamiento se desincroniza y termina
 * mintiendo.
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
  STORM_PROB,
  UPGRADE,
  newDiceCost,
  upgradeCost,
  type Obs,
} from "./engine.ts";
import type { ScoredMove } from "./models.ts";

const n1 = (x: number) => x.toFixed(1);
const n0 = (x: number) => Math.round(x).toString();

export interface Explanation {
  headline: string;
  reasons: string[];
  runnerUp: string | null;
}

export function explain(obs: Obs, ranked: ScoredMove[]): Explanation {
  const best = ranked[0];
  const second = ranked[1];
  const turnsLeft = HORIZON - obs.turn;
  const incomePerTurn = obs.numDice * (3.5 + obs.diceBonus);
  const exposure = STORM_PROB * (obs.gold / 2);

  const reasons: string[] = [];
  let headline = "";

  switch (best.action) {
    case SCORE: {
      headline = `Puntúo ${best.scoreAmount} de oro.`;
      reasons.push(
        `Los puntos son inmunes a la tormenta: se cobran antes de que caiga. Cada moneda que dejo sobre la mesa vale ${n1(STORM_PROB * 50)} % menos en promedio, porque hay ${Math.round(STORM_PROB * 100)} % de probabilidad de perder la mitad.`,
      );
      if (obs.turn === HORIZON) {
        reasons.push("Además es el último turno: el oro que no puntúe ahora se evapora. No hay turno 31.");
      } else if (obs.gold > 0) {
        reasons.push(
          `Con ${obs.gold} de oro expuesto, no puntuar cuesta ${n1(exposure)} puntos esperados por turno${obs.shields > 0 ? ", aunque el escudo lo cubriría" : ""}.`,
        );
      }
      break;
    }
    case BUY_DICE: {
      const cost = newDiceCost(obs.numDice);
      const extra = 3.5 + obs.diceBonus;
      const payback = extra > 0 ? cost / extra : Infinity;
      headline = `Compro un dado (${obs.numDice} → ${obs.numDice + 1}). Cuesta ${cost}.`;
      reasons.push(
        `Un dado más produce ${n1(extra)} de oro por turno, así que se paga solo en ${n1(payback)} turnos y quedan ${turnsLeft}.`,
      );
      reasons.push(
        `Hasta el final me va a devolver unos ${n0(extra * turnsLeft)} de oro. Puntuar esos ${cost} ahora me daría ${cost} puntos fijos.`,
      );
      break;
    }
    case UPGRADE: {
      const cost = upgradeCost(obs.diceBonus);
      const extra = obs.numDice;
      headline = `Mejoro los dados (bonus ${obs.diceBonus} → ${obs.diceBonus + 1}). Cuesta ${cost}.`;
      reasons.push(
        `El bonus se aplica a los ${obs.numDice} dados, incluidos los que compre después, así que suma ${extra} de oro por turno: se paga en ${n1(cost / extra)} turnos.`,
      );
      reasons.push(
        `Mejorar rinde más que comprar un dado cuando tengo más de ${n1(3.5 + obs.diceBonus)} dados, y tengo ${obs.numDice}.`,
      );
      break;
    }
    case BUY_SHIELD: {
      headline = `Compro un escudo. Cuesta ${SHIELD_COST}.`;
      reasons.push(
        `El escudo no me protege del juego: me compra el derecho a usar mis turnos en algo que no sea cobrar. Con escudo, no puntuar deja de costar ${n1(exposure)} puntos por turno.`,
      );
      reasons.push(
        `Quedan ${turnsLeft} turnos, o sea ${n1(turnsLeft * STORM_PROB)} tormentas esperadas. Un escudo bloquea una.`,
      );
      break;
    }
    case STORE_BEST_DIE: {
      headline = `Guardo el mejor dado (vale ${obs.rollMax}). Cuesta ${STORE_DIE_COST}.`;
      reasons.push(
        `No lo aparto: lo clono. La suma de la tirada ya se cobró, y guardar hace que ese ${obs.rollMax} se vuelva a cobrar el turno que viene. Pago ${STORE_DIE_COST} y recibo ${obs.rollMax}: neto ${obs.rollMax - STORE_DIE_COST > 0 ? "+" : ""}${obs.rollMax - STORE_DIE_COST}.`,
      );
      if (obs.gold > 60 && obs.shields === 0) {
        reasons.push(
          `Con ${obs.gold} de oro y sin escudo esto arriesga ${n1(exposure)} puntos por tormenta, pero igual es la mejor de las opciones disponibles.`,
        );
      }
      break;
    }
    case PASS: {
      headline = "Paso.";
      reasons.push(
        `Con ${obs.gold} de oro no me alcanza para nada que valga la pena, y prefiero acumular: la próxima compra útil cuesta ${Math.min(newDiceCost(obs.numDice), upgradeCost(obs.diceBonus))}.`,
      );
      break;
    }
  }

  reasons.push(
    `Mi motor produce ${n1(incomePerTurn)} de oro por turno (${obs.numDice} dados con bonus +${obs.diceBonus}) y quedan ${turnsLeft} turnos.`,
  );

  const runnerUp =
    second && Number.isFinite(second.value)
      ? `Mi segunda opción era ${second.label}: la valúo en ${n1(second.value)} contra ${n1(best.value)}, una diferencia de ${n1(best.value - second.value)} puntos.`
      : null;

  return { headline, reasons, runnerUp };
}

/** Texto corto para la comparación entre lo que jugaste y lo que hubiera jugado el modelo. */
export function compareMoves(
  yours: string,
  theirs: string,
  gap: number,
): { verdict: string; tone: "same" | "close" | "worse" } {
  if (yours === theirs) return { verdict: "Jugaste igual que el modelo.", tone: "same" };
  if (gap < 1) return { verdict: `El modelo prefería ${theirs}, pero por menos de 1 punto: es un empate.`, tone: "close" };
  return { verdict: `El modelo prefería ${theirs} — lo valúa ${gap.toFixed(1)} puntos por encima.`, tone: "worse" };
}
