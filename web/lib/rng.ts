/**
 * Azar reproducible y COMPARTIBLE entre jugadores.
 *
 * `rollDice` es funcion pura de (semilla, turno, indice), no consume un flujo
 * secuencial. Por eso dos partidas paralelas ven los mismos dados -- el que
 * tiene 5 usa los primeros 5 valores del turno, el que tiene 3 los primeros 3 --
 * y las tormentas caen en los mismos turnos. Cuando el jugador compite contra
 * los modelos, la diferencia de puntaje no tiene suerte adentro.
 *
 * env.py no puede dar esto: un unico generador sirve dados y tormentas y
 * `size=num_dice` depende de la politica.
 */

import { DICE_FACES, STORM_PROB, type Randomness } from "./engine.ts";

/** Mezclador entero de 32 bits (finalizador estilo murmur3). */
function mix(x: number): number {
  x = Math.imul(x ^ (x >>> 16), 0x85ebca6b);
  x = Math.imul(x ^ (x >>> 13), 0xc2b2ae35);
  return (x ^ (x >>> 16)) >>> 0;
}

function hash3(seed: number, a: number, b: number): number {
  return mix(mix(mix(seed >>> 0) ^ Math.imul(a + 1, 0x9e3779b1)) ^ Math.imul(b + 1, 0x85ebca6b));
}

const STORM_STREAM = 0x7fff_0000;

export function makeRandomness(seed: number): Randomness {
  return {
    rollDice(turn: number, count: number): number[] {
      const out: number[] = new Array(count);
      for (let i = 0; i < count; i += 1) {
        out[i] = DICE_FACES[hash3(seed, turn, i) % DICE_FACES.length];
      }
      return out;
    },
    storm(turn: number): boolean {
      return hash3(seed, turn, STORM_STREAM) / 0x1_0000_0000 < STORM_PROB;
    },
  };
}

/** Azar fijo, para reproducir una partida guardada o verificar el motor. */
export function makeScriptedRandomness(dice: number[][], storms: boolean[]): Randomness {
  return {
    rollDice(turn: number, count: number): number[] {
      const row = dice[turn - 1] ?? [];
      return row.slice(0, count);
    },
    storm(turn: number): boolean {
      return storms[turn - 1] ?? false;
    },
  };
}

/** Semilla legible que se puede compartir y volver a jugar. */
export function randomSeed(): number {
  return (Math.random() * 0xffffff) >>> 0;
}
