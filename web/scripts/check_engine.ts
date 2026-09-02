/**
 * Verifica que el motor en TypeScript coincida turno a turno con `env.py`.
 *
 * Las trazas las genera `gen_trace.py` inyectando un azar guionado en el
 * ambiente original. Aca se reproducen las mismas tiradas, las mismas tormentas
 * y las mismas acciones, y se compara TODO el estado en cada turno -- no solo
 * el puntaje final, que puede coincidir por casualidad con reglas distintas.
 *
 *   node --experimental-strip-types scripts/check_engine.ts
 */

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { GoldDiceGame, type Action } from "../lib/engine.ts";
import { makeScriptedRandomness } from "../lib/rng.ts";

interface Trace {
  seed: number;
  dice: number[][];
  storms: boolean[];
  actions: [number, number | null][];
  states: {
    turn: number;
    points: number;
    gold: number;
    numDice: number;
    diceBonus: number;
    shields: number;
    storm: boolean;
    stormBlocked: boolean;
  }[];
  finalPoints: number;
}

const here = dirname(fileURLToPath(import.meta.url));
const traces: Trace[] = JSON.parse(readFileSync(join(here, "traces.json"), "utf8"));

let checked = 0;
const failures: string[] = [];

for (const trace of traces) {
  const game = new GoldDiceGame(makeScriptedRandomness(trace.dice, trace.storms));

  trace.actions.forEach(([action, amount], i) => {
    const expected = trace.states[i];
    const record = game.step(action as Action, amount);
    // env.py devuelve la observacion DESPUES de `_advance_turn`, o sea con la
    // tirada del turno siguiente ya sumada al oro. Para comparar peras con
    // peras hay que leer el estado del juego, no el del registro del turno.
    const got = {
      turn: record.turn,
      points: game.points,
      gold: game.gold,
      numDice: game.numDice,
      diceBonus: game.diceBonus,
      shields: game.shields,
      storm: record.storm,
      stormBlocked: record.stormBlocked,
    };
    for (const key of Object.keys(expected) as (keyof typeof expected)[]) {
      checked += 1;
      if (got[key] !== expected[key]) {
        failures.push(
          `traza ${trace.seed} turno ${expected.turn}: ${key} = ${got[key]}, esperado ${expected[key]}`,
        );
      }
    }
  });

  checked += 1;
  if (game.points !== trace.finalPoints) {
    failures.push(`traza ${trace.seed}: puntos finales ${game.points}, esperado ${trace.finalPoints}`);
  }
}

if (failures.length) {
  console.error(`FALLA: ${failures.length} discrepancias con env.py`);
  failures.slice(0, 12).forEach((f) => console.error("  " + f));
  process.exit(1);
}

console.log(`motor verificado contra env.py: ${traces.length} partidas, ${checked} comparaciones, 0 discrepancias`);
