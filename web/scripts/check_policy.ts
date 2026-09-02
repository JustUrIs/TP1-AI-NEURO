/**
 * Compara los modelos del navegador contra los agentes de Python en los mismos
 * estados. Detecta errores de indexado en el export binario, que son silenciosos.
 *
 *   node --experimental-strip-types scripts/check_policy.ts
 */

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { ACTION_NAMES, type Action, type Obs } from "../lib/engine.ts";
import { AfterstateModel, TabularModel, type Model } from "../lib/models.ts";

const here = dirname(fileURLToPath(import.meta.url));
const models = join(here, "..", "public", "models");
const manifest = JSON.parse(readFileSync(join(models, "manifest.json"), "utf8"));

const buf = (name: string) => {
  const b = readFileSync(join(models, name));
  return b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength) as ArrayBuffer;
};

const loaded: Record<string, Model> = {
  campeon: new AfterstateModel("campeon", manifest.agents.campeon, buf(manifest.agents.campeon.file)),
  aprendiz: new TabularModel(
    "aprendiz",
    manifest.agents.aprendiz,
    buf(manifest.agents.aprendiz.keys),
    buf(manifest.agents.aprendiz.vals),
  ),
  novato: new TabularModel(
    "novato",
    manifest.agents.novato,
    buf(manifest.agents.novato.keys),
    buf(manifest.agents.novato.vals),
  ),
};

interface Row {
  obs: Record<string, number>;
  moves: Record<string, [number, number | null]>;
}

const rows: Row[] = JSON.parse(readFileSync(join(here, "policy_probe.json"), "utf8"));
const mismatches: Record<string, number> = {};
const samples: string[] = [];

for (const row of rows) {
  const o = row.obs;
  const obs: Obs = {
    turn: o.turn,
    points: o.points,
    gold: o.gold,
    numDice: o.num_dice,
    diceBonus: o.dice_bonus,
    shields: o.shields,
    storedValue: o.stored_value,
    rollSum: o.roll_sum,
    rollMax: o.roll_max,
  };
  for (const [name, model] of Object.entries(loaded)) {
    const [wantAction, wantAmount] = row.moves[name];
    const got = model.act(obs);
    const sameAction = got.action === (wantAction as Action);
    const sameAmount = wantAmount === null || got.scoreAmount === wantAmount;
    if (!sameAction || !sameAmount) {
      mismatches[name] = (mismatches[name] ?? 0) + 1;
      if (samples.length < 8) {
        samples.push(
          `${name} t=${obs.turn} oro=${obs.gold} ${obs.numDice}d+${obs.diceBonus} esc=${obs.shields}: ` +
            `TS ${ACTION_NAMES[got.action]}(${got.scoreAmount ?? "-"}) vs PY ${ACTION_NAMES[wantAction as Action]}(${wantAmount ?? "-"})`,
        );
      }
    }
  }
}

const total = rows.length;
console.log(`estados comparados: ${total}`);
let failed = false;
for (const name of Object.keys(loaded)) {
  const bad = mismatches[name] ?? 0;
  const pct = (100 * bad) / total;
  console.log(`  ${name.padEnd(10)} ${total - bad}/${total} coinciden  (${pct.toFixed(2)} % de diferencia)`);
  // Los tabulares pueden desempatar distinto cuando dos acciones valen igual
  // (Python usa `max` sobre una lista, aca se ordena): se tolera un margen.
  if (pct > 0.5) failed = true;
}
if (samples.length) {
  console.log("\nprimeras diferencias:");
  samples.forEach((s) => console.log("  " + s));
}
if (failed) {
  console.error("\nFALLA: los modelos del navegador no reproducen la política entrenada.");
  process.exit(1);
}
console.log("\npolítica verificada: el navegador juega lo mismo que Python.");
