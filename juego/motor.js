/*
 * El juego. Port de env.py, verificado turno a turno contra el original
 * (ver verificar/comprobar_motor.js).
 *
 * La fidelidad no es un detalle: si el juego del navegador difiere del que
 * usamos para entrenar, todo lo que muestra la pagina —cuanto vale cada
 * jugada, cuanto perdiste por decidir mal, cuanto fue suerte— deja de
 * significar algo.
 *
 * COMO ES UN TURNO, leido de env.py y no del enunciado:
 *
 *   1. TIRADA    tiras tus dados y el oro se suma (mas lo que hayas guardado)
 *   2. DECISION  ves la situacion, con ese oro ya sumado
 *   3. ACCION    hacés UNA sola cosa
 *   4. TORMENTA  15 % de probabilidad. Con escudo perdés el escudo; sin
 *                escudo, tu oro se parte al medio
 *   5. siguiente turno; si era el 30, se terminó y NO se vuelve a tirar
 *
 * De ese orden salen las dos reglas que gobiernan la estrategia: los puntos
 * son inmunes a la tormenta (se cobran antes), y el oro que sobrevive al
 * turno 30 sin convertirse se evapora.
 */
(function (global) {
  "use strict";

  var HORIZON = 30;
  var STORM_PROB = 0.15;
  var CARAS = [1, 2, 3, 4, 5, 6];
  var SHIELD_COST = 5;
  var STORE_COST = 4;

  function costoDado(numDados) { return 18 + 8 * (numDados - 1); }
  function costoMejora(bonus) { return 8 + 8 * bonus; }

  var PASAR = 0, PUNTUAR = 1, COMPRAR_DADO = 2, MEJORAR = 3, ESCUDO = 4, GUARDAR = 5;

  var NOMBRES = {
    0: "Pasar",
    1: "Puntuar",
    2: "Comprar dado",
    3: "Mejorar dados",
    4: "Comprar escudo",
    5: "Guardar dado",
  };

  // ---------------------------------------------------------------- azar
  //
  // La tirada es una funcion pura de (semilla, turno, numero de dado): no
  // consume una secuencia. Gracias a eso, varias partidas en paralelo ven
  // exactamente los mismos dados —el que tiene 5 usa los primeros 5 valores
  // del turno, el que tiene 3 usa los primeros 3— y las tormentas caen en los
  // mismos turnos para todos.
  //
  // O sea: cuando jugás contra los modelos, la diferencia de puntaje no tiene
  // nada de suerte adentro. Son las decisiones.
  //
  // env.py no puede ofrecer esto: alli un unico generador sirve los dados y
  // las tormentas, y cuantos dados tirás depende de como venís jugando.
  function mezclar(x) {
    x = Math.imul(x ^ (x >>> 16), 0x85ebca6b);
    x = Math.imul(x ^ (x >>> 13), 0xc2b2ae35);
    return (x ^ (x >>> 16)) >>> 0;
  }

  function hash(semilla, a, b) {
    return mezclar(mezclar(mezclar(semilla >>> 0) ^ Math.imul(a + 1, 0x9e3779b1)) ^ Math.imul(b + 1, 0x85ebca6b));
  }

  function azar(semilla) {
    return {
      tirar: function (turno, cuantos) {
        var out = [];
        for (var i = 0; i < cuantos; i++) out.push(CARAS[hash(semilla, turno, i) % 6]);
        return out;
      },
      tormenta: function (turno) {
        return hash(semilla, turno, 0x7fff0000) / 4294967296 < STORM_PROB;
      },
    };
  }

  /** Azar fijo, para reproducir una partida o verificar el motor. */
  function azarGuionado(dados, tormentas) {
    return {
      tirar: function (turno, cuantos) { return (dados[turno - 1] || []).slice(0, cuantos); },
      tormenta: function (turno) { return !!tormentas[turno - 1]; },
    };
  }

  // ---------------------------------------------------------------- partida
  function Partida(fuente) {
    this.azar = fuente;
    this.turno = 1;
    this.oro = 0;
    this.puntos = 0;
    this.dados = 1;
    this.bonus = 0;
    this.escudos = 0;
    this.guardado = 0;
    this.terminada = false;
    this.historia = [];
    this.tirar();
  }

  Partida.prototype.situacion = function () {
    return {
      turno: this.turno, puntos: this.puntos, oro: this.oro,
      dados: this.dados, bonus: this.bonus, escudos: this.escudos,
      guardado: this.guardado, sumaTirada: this.sumaTirada, mejorDado: this.mejorDado,
    };
  };

  Partida.prototype.jugadasLegales = function () {
    // Pasar y Puntuar siempre se pueden: puntuar 0 no requiere oro.
    var out = [PASAR, PUNTUAR];
    if (this.oro >= costoDado(this.dados)) out.push(COMPRAR_DADO);
    if (this.oro >= costoMejora(this.bonus)) out.push(MEJORAR);
    if (this.oro >= SHIELD_COST) out.push(ESCUDO);
    if (this.oro >= STORE_COST && this.mejorDado > 0) out.push(GUARDAR);
    return out;
  };

  Partida.prototype.jugar = function (accion, cuanto) {
    if (this.terminada) throw new Error("La partida ya terminó");

    var registro = {
      turno: this.turno,
      accion: accion,
      cuanto: accion === PUNTUAR ? Math.floor(cuanto || 0) : null,
      oroAntes: this.oro,
      tirada: this.tirada.slice(),
      tormenta: false,
      bloqueada: false,
      oroPerdido: 0,
    };

    this.aplicar(accion, registro.cuanto);
    this.aplicarTormenta(registro);

    registro.puntosDespues = this.puntos;
    registro.oroDespues = this.oro;
    registro.escudosDespues = this.escudos;
    this.historia.push(registro);

    this.turno += 1;
    if (this.turno > HORIZON) this.terminada = true;
    else this.tirar();
    return registro;
  };

  Partida.prototype.aplicar = function (accion, cuanto) {
    if (accion === PASAR) return;
    if (accion === PUNTUAR) {
      var k = Math.max(0, Math.min(Math.floor(cuanto || 0), this.oro));
      this.oro -= k;
      this.puntos += k;
      return;
    }
    if (accion === COMPRAR_DADO) { this.oro -= costoDado(this.dados); this.dados += 1; return; }
    if (accion === MEJORAR) { this.oro -= costoMejora(this.bonus); this.bonus += 1; return; }
    if (accion === ESCUDO) { this.oro -= SHIELD_COST; this.escudos += 1; return; }
    if (accion === GUARDAR) {
      this.oro -= STORE_COST;
      // Ojo: no aparta el dado, lo CLONA. La suma de la tirada ya se cobró, y
      // este valor se vuelve a cobrar en la tirada siguiente.
      this.guardado = this.mejorDado;
      return;
    }
    throw new Error("Jugada desconocida: " + accion);
  };

  Partida.prototype.aplicarTormenta = function (registro) {
    if (!this.azar.tormenta(this.turno)) return;
    registro.tormenta = true;
    if (this.escudos > 0) {
      this.escudos -= 1;
      registro.bloqueada = true;
    } else {
      var antes = this.oro;
      this.oro = Math.floor(this.oro / 2);
      registro.oroPerdido = antes - this.oro;
    }
  };

  Partida.prototype.tirar = function () {
    this.tirada = this.azar.tirar(this.turno, this.dados);
    var conBonus = [];
    var suma = 0, mejor = 0;
    for (var i = 0; i < this.tirada.length; i++) {
      var v = this.tirada[i] + this.bonus;
      conBonus.push(v);
      suma += v;
      if (v > mejor) mejor = v;
    }
    this.tiradaConBonus = conBonus;
    this.sumaTirada = suma;
    this.mejorDado = mejor;
    this.oro += suma + this.guardado;
    this.guardado = 0;
  };

  global.GD = global.GD || {};
  global.GD.motor = {
    HORIZON: HORIZON, STORM_PROB: STORM_PROB, SHIELD_COST: SHIELD_COST, STORE_COST: STORE_COST,
    PASAR: PASAR, PUNTUAR: PUNTUAR, COMPRAR_DADO: COMPRAR_DADO,
    MEJORAR: MEJORAR, ESCUDO: ESCUDO, GUARDAR: GUARDAR,
    NOMBRES: NOMBRES,
    costoDado: costoDado, costoMejora: costoMejora,
    azar: azar, azarGuionado: azarGuionado,
    Partida: Partida,
  };
})(typeof globalThis !== "undefined" ? globalThis : this);
