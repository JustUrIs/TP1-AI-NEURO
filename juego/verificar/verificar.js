/*
 * Verifica el juego sin abrir un navegador.
 *
 * Tres chequeos, y los tres buscan errores que no se notan jugando:
 *
 *   1. El motor contra env.py. Se reproducen partidas jugadas en el Python
 *      original con azar guionado y se compara TODO el estado en cada turno.
 *      Si el juego del navegador difiere del que usamos para entrenar, todo lo
 *      que muestra la pagina deja de significar algo.
 *
 *   2. Las politicas contra los agentes de Python, sobre los mismos estados.
 *      Un indice mal calculado al empaquetar los pesos haria que el Campeon
 *      juegue distinto acá, sin dar ningun error.
 *
 *   3. Partidas completas de punta a punta: cada agente juega 400 partidas y
 *      su promedio tiene que dar cerca del que reporta el informe.
 *
 *     node verificar/verificar.js
 */

"use strict";

const fs = require("fs");
const path = require("path");

// Los archivos del juego se registran en `window`, que en Node no existe.
globalThis.window = globalThis;
globalThis.atob = (s) => Buffer.from(s, "base64").toString("binary");

const raiz = path.join(__dirname, "..");
require(path.join(raiz, "data.js"));
require(path.join(raiz, "motor.js"));
require(path.join(raiz, "agentes.js"));

const M = GD.motor;
const A = GD.agentes;
const mundo = A.cargar(window.GOLD_DICE_DATA);

let fallas = 0;
function titulo(t) { console.log("\n" + t); }
function ok(t) { console.log("  OK   " + t); }
function mal(t) { fallas += 1; console.log("  MAL  " + t); }

// ---------------------------------------------------------------- 1. motor
titulo("1. El motor contra env.py");
{
  const trazas = JSON.parse(fs.readFileSync(path.join(__dirname, "trazas.json"), "utf8"));
  let comparaciones = 0;
  let diferencias = 0;
  const ejemplos = [];

  for (const traza of trazas) {
    const p = new M.Partida(M.azarGuionado(traza.dice, traza.storms));
    traza.actions.forEach(([accion, cuanto], i) => {
      const esperado = traza.states[i];
      const reg = p.jugar(accion, cuanto);
      // env.py devuelve el estado DESPUES de tirar el turno siguiente, asi que
      // hay que leer la partida y no el registro del turno.
      const obtenido = {
        turn: reg.turno, points: p.puntos, gold: p.oro, numDice: p.dados,
        diceBonus: p.bonus, shields: p.escudos,
        storm: reg.tormenta, stormBlocked: reg.bloqueada,
      };
      for (const k of Object.keys(esperado)) {
        comparaciones += 1;
        if (obtenido[k] !== esperado[k]) {
          diferencias += 1;
          if (ejemplos.length < 5) ejemplos.push(`traza ${traza.seed} turno ${esperado.turn}: ${k} = ${obtenido[k]}, esperaba ${esperado[k]}`);
        }
      }
    });
    comparaciones += 1;
    if (p.puntos !== traza.finalPoints) {
      diferencias += 1;
      ejemplos.push(`traza ${traza.seed}: puntaje final ${p.puntos}, esperaba ${traza.finalPoints}`);
    }
  }

  if (diferencias === 0) ok(`${trazas.length} partidas, ${comparaciones.toLocaleString("es")} comparaciones, 0 diferencias`);
  else { mal(`${diferencias} diferencias sobre ${comparaciones}`); ejemplos.forEach((e) => console.log("       " + e)); }
}

// ------------------------------------------------------------ 2. politicas
titulo("2. Las politicas contra los agentes de Python");
{
  const sonda = JSON.parse(fs.readFileSync(path.join(__dirname, "sonda.json"), "utf8"));
  const porId = {};
  mundo.agentes.forEach((a) => { porId[a.id] = a; });

  for (const id of Object.keys(porId)) {
    let coinciden = 0;
    const ejemplos = [];
    for (const fila of sonda) {
      const o = fila.obs;
      const s = {
        turno: o.turn, puntos: o.points, oro: o.gold, dados: o.num_dice,
        bonus: o.dice_bonus, escudos: o.shields, guardado: o.stored_value,
        sumaTirada: o.roll_sum, mejorDado: o.roll_max,
      };
      const [accionPy, cuantoPy] = fila.moves[id];
      const mia = porId[id].ranking(s)[0];
      const mismaAccion = mia.accion === accionPy;
      const mismoMonto = cuantoPy === null || mia.cuanto === cuantoPy;
      if (mismaAccion && mismoMonto) coinciden += 1;
      else if (ejemplos.length < 3) {
        ejemplos.push(`t=${s.turno} oro=${s.oro} ${s.dados}d+${s.bonus}: acá ${M.NOMBRES[mia.accion]}, Python ${M.NOMBRES[accionPy]}`);
      }
    }
    const pct = (100 * coinciden) / sonda.length;
    const linea = `${porId[id].label}: ${coinciden}/${sonda.length} (${pct.toFixed(2)} %)`;
    // Los tabulares pueden desempatar distinto cuando dos jugadas valen casi
    // igual y el redondeo cae para el otro lado. Medio punto de margen.
    if (pct >= 99.5) ok(linea);
    else { mal(linea); ejemplos.forEach((e) => console.log("       " + e)); }
  }
}

// --------------------------------------------------------- 3. punta a punta
titulo("3. Partidas completas (400 cada uno)");
{
  const esperado = {};
  window.GOLD_DICE_DATA.agents.forEach((a) => { esperado[a.id] = a.mean; });

  for (const agente of mundo.agentes) {
    let total = 0;
    for (let i = 0; i < 400; i++) {
      const p = new M.Partida(M.azar(900000 + i));
      while (!p.terminada) {
        const jugada = agente.ranking(p.situacion())[0];
        p.jugar(jugada.accion, jugada.cuanto);
      }
      total += p.puntos;
    }
    const media = total / 400;
    const ref = esperado[agente.id];
    // 400 partidas con sigma ~135 dan un error estandar de ~7 puntos; 30 de
    // margen es holgado y aun asi detecta un agente roto.
    const linea = `${agente.label}: ${media.toFixed(1)} (el informe reporta ${ref.toFixed(1)})`;
    if (Math.abs(media - ref) < 30) ok(linea); else mal(linea);
  }

  // El oraculo tiene que dar cerca de 642 y ser un techo: ningun agente arriba.
  let total = 0;
  for (let i = 0; i < 400; i++) {
    const p = new M.Partida(M.azar(900000 + i));
    while (!p.terminada) {
      const j = mundo.oraculo.ranking(p.situacion())[0];
      p.jugar(j.accion, j.cuanto);
    }
    total += p.puntos;
  }
  const media = total / 400;
  if (Math.abs(media - 642) < 35) ok(`Juego perfecto: ${media.toFixed(1)} (el solver exacto dice 642.45)`);
  else mal(`Juego perfecto: ${media.toFixed(1)}, esperaba ~642`);
}

// ------------------------------------------------------- 4. habilidad/suerte
titulo("4. La descomposicion habilidad / suerte cierra");
{
  let peor = 0;
  for (let i = 0; i < 60; i++) {
    const p = new M.Partida(M.azar(500000 + i));
    const situaciones = [];
    while (!p.terminada) {
      situaciones.push(p.situacion());
      const legales = p.jugadasLegales();
      const a = legales[Math.floor(Math.random() * legales.length)];
      p.jugar(a, a === M.PUNTUAR ? Math.floor(Math.random() * (p.oro + 1)) : null);
    }
    const an = mundo.oraculo.analizar(situaciones, p.historia, 0);
    // calidad + suerte tiene que dar el puntaje real, exacto.
    peor = Math.max(peor, Math.abs(an.calidad + an.suerte - an.puntaje));
  }
  if (peor < 1e-6) ok("calidad + suerte = puntaje final en las 60 partidas");
  else mal(`la descomposicion no cierra: error maximo ${peor}`);
}

console.log("");
if (fallas) { console.log(`${fallas} chequeo(s) fallaron.`); process.exit(1); }
console.log("Todo verificado.");
