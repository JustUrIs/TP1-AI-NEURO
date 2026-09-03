/*
 * Juega partidas completas a traves de la interfaz real, sin navegador.
 *
 * Los tres chequeos de verificar.js prueban la logica: el motor, los agentes y
 * el analisis. Ninguno toca la pantalla. Este simula un DOM minimo, carga el
 * index.html de verdad y aprieta los botones: empezar, elegir jugada, mover el
 * slider de puntuar, terminar, jugar otra. Si algo del render se rompe -un id
 * que no existe, una funcion que quedo sin definir- aparece acá.
 *
 *     node verificar/simular_ui.js
 */

"use strict";

const fs = require("fs");
const path = require("path");
const vm = require("vm");

// ------------------------------------------------------------------ DOM falso
function Elemento(tag, id) {
  this.tagName = tag;
  this.id = id || "";
  this.hijos = [];
  this.atributos = {};
  this._html = "";
  this._texto = "";
  this.style = {};
  this.dataset = {};
  this.disabled = false;
  this.value = "";
  this.onclick = null;
  this.oninput = null;
  var clases = new Set();
  this.classList = {
    add: function () { for (var i = 0; i < arguments.length; i++) clases.add(arguments[i]); },
    remove: function () { for (var i = 0; i < arguments.length; i++) clases.delete(arguments[i]); },
    contains: function (c) { return clases.has(c); },
  };
  Object.defineProperty(this, "className", {
    get: function () { return Array.from(clases).join(" "); },
    set: function (v) { clases = new Set(String(v).split(/\s+/).filter(Boolean)); },
  });
}
Elemento.prototype.appendChild = function (n) { this.hijos.push(n); n.parentElement = this; return n; };
Elemento.prototype.setAttribute = function (k, v) { this.atributos[k] = String(v); };
Elemento.prototype.getAttribute = function (k) { return this.atributos[k]; };
Elemento.prototype.querySelectorAll = function (sel) { return buscarEn(this, sel); };
Object.defineProperty(Elemento.prototype, "innerHTML", {
  get: function () { return this._html; },
  set: function (v) { this._html = String(v); this.hijos = desdeHTML(String(v), this); },
});
Object.defineProperty(Elemento.prototype, "textContent", {
  get: function () { return this._texto; },
  set: function (v) { this._texto = String(v); this.hijos = []; },
});

/**
 * Parser minimo: solo saca las etiquetas de apertura para poder responder
 * querySelectorAll sobre clases y data-*. No arma un arbol real, y no hace
 * falta: el objetivo es detectar referencias rotas, no renderizar.
 */
function desdeHTML(html, padre) {
  var out = [];
  var re = /<(\w+)([^>]*)>/g, m;
  while ((m = re.exec(html))) {
    var el = new Elemento(m[1]);
    el.parentElement = padre;
    var attrs = m[2];
    var a = /([\w-]+)="([^"]*)"/g, x;
    while ((x = a.exec(attrs))) {
      if (x[1] === "class") el.className = x[2];
      else if (x[1] === "id") el.id = x[2];
      else if (x[1].indexOf("data-") === 0) el.dataset[x[1].slice(5)] = x[2];
      else el.setAttribute(x[1], x[2]);
    }
    out.push(el);
  }
  return out;
}

function buscarEn(nodo, sel) {
  var res = [];
  (function recorrer(n) {
    n.hijos.forEach(function (h) {
      if (coincide(h, sel)) res.push(h);
      recorrer(h);
    });
  })(nodo);
  return res;
}
function coincide(el, sel) {
  if (sel[0] === ".") return el.classList.contains(sel.slice(1));
  if (sel[0] === "[") {
    var k = sel.slice(1, -1).split("=")[0].replace("data-", "");
    return el.dataset[k] !== undefined;
  }
  return el.tagName === sel;
}

const raiz = path.join(__dirname, "..");
const html = fs.readFileSync(path.join(raiz, "index.html"), "utf8");

// Los elementos que el script busca por id salen del propio index.html.
const porId = {};
const reId = /<(\w+)[^>]*\bid="([^"]+)"[^>]*>/g;
let m;
while ((m = reId.exec(html))) porId[m[2]] = new Elemento(m[1], m[2]);

const almacen = {};
const contexto = {
  console: console,
  Math: Math, JSON: JSON, Date: Date, Object: Object, Array: Array, Number: Number,
  String: String, Set: Set, Buffer: Buffer, isFinite: isFinite, NaN: NaN, Infinity: Infinity,
  parseFloat: parseFloat, parseInt: parseInt, Uint8Array: Uint8Array, Uint32Array: Uint32Array,
  Int16Array: Int16Array, Float32Array: Float32Array,
  atob: (s) => Buffer.from(s, "base64").toString("binary"),
  localStorage: {
    getItem: (k) => (k in almacen ? almacen[k] : null),
    setItem: (k, v) => { almacen[k] = String(v); },
  },
  document: {
    getElementById: (id) => porId[id] || null,
    querySelectorAll: (sel) => Object.values(porId).reduce(function (acc, el) {
      return acc.concat(coincide(el, sel) ? [el] : [], buscarEn(el, sel));
    }, []),
    createElement: (t) => new Elemento(t),
    addEventListener: () => {},
  },
};
contexto.window = contexto;
contexto.globalThis = contexto;
vm.createContext(contexto);

// Carga en el mismo orden que el HTML.
["data.js", "motor.js", "agentes.js", "explicar.js"].forEach(function (f) {
  vm.runInContext(fs.readFileSync(path.join(raiz, f), "utf8"), contexto, { filename: f });
});
vm.runInContext(html.match(/<script>([\s\S]*?)<\/script>\s*<\/body>/)[1], contexto, { filename: "index.html" });

// ------------------------------------------------------------------ el test
let fallas = 0;
function ok(t) { console.log("  OK   " + t); }
function mal(t) { fallas++; console.log("  MAL  " + t); }

console.log("\nJugando por la interfaz");

try {
  porId.nombre.value = "Prueba";
  porId.empezar.onclick();
  if (!porId.partida.classList.contains("oculto")) ok("arranca la partida");
  else mal("la partida no se mostro");

  // 30 turnos, alternando jugadas para pasar por todas las ramas del render.
  for (var turno = 1; turno <= 30; turno++) {
    if (!porId.final.classList.contains("oculto")) break;
    var botones = porId.acciones.hijos.filter(function (b) { return !b.disabled; });
    if (!botones.length) { mal("turno " + turno + ": ningun boton habilitado"); break; }

    if (turno % 5 === 0) porId.btnPista.onclick();          // pedir pista

    if (turno === 7) {
      botones[0].onclick();                                  // abre el panel de puntuar
      porId.cancelarPuntuar.onclick();                       // y se arrepiente
      botones[botones.length - 1].onclick();
    } else {
      botones[turno % botones.length].onclick();
    }

    // Puntuar no avanza el turno solo: abre el panel del monto y espera. Es a
    // proposito, asi que el test tiene que confirmar como haria una persona.
    if (!porId.zonaPuntuar.classList.contains("oculto")) {
      porId.monto.oninput.call(porId.monto);
      porId.confirmarPuntuar.onclick();
    }
  }

  if (!porId.final.classList.contains("oculto")) ok("la partida llega al final y muestra el balance");
  else mal("la partida no termino en 30 turnos");

  var guardado = JSON.parse(almacen["goldDice.tabla.v1"] || "[]");
  if (guardado.length === 1 && guardado[0].nombre === "Prueba") ok("el resultado quedo guardado en la tabla");
  else mal("no se guardo la partida (" + guardado.length + " filas)");
  if (typeof guardado[0].nota === "number" && guardado[0].nota >= 0) ok("la nota de decisiones se calculo: " + guardado[0].nota.toFixed(1) + " %");
  else mal("la nota salio mal");

  // "Jugar otra" tiene que reiniciar y volver a guardar.
  porId.otra.onclick();
  if (!porId.partida.classList.contains("oculto")) ok("«jugar otra» reinicia");
  else mal("«jugar otra» no reinicio");
  while (porId.final.classList.contains("oculto")) {
    var b = porId.acciones.hijos.filter(function (x) { return !x.disabled; });
    b[0].onclick();
    if (!porId.zonaPuntuar.classList.contains("oculto")) porId.confirmarPuntuar.onclick();
  }
  var g2 = JSON.parse(almacen["goldDice.tabla.v1"] || "[]");
  if (g2.length === 2) ok("la segunda partida tambien quedo guardada");
  else mal("la segunda partida no se guardo (" + g2.length + " filas)");

  porId.volver.onclick();
  if (!porId.inicio.classList.contains("oculto")) ok("«cambiar modo» vuelve al inicio");
  else mal("«cambiar modo» no volvio");
} catch (e) {
  mal("se rompio: " + e.message);
  console.log(e.stack.split("\n").slice(0, 4).join("\n"));
}

console.log("");
if (fallas) { console.log(fallas + " chequeo(s) fallaron."); process.exit(1); }
console.log("La interfaz completa dos partidas sin romperse.");
