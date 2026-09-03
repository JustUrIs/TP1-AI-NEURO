/*
 * Los agentes entrenados y la DP, corriendo en el navegador.
 *
 * Nada de esto llama a ninguna API. Los pesos vienen embebidos en data.js y
 * todo se calcula acá, asi que el rival responde al instante y la pagina anda
 * incluso sin internet.
 *
 * Hay dos clases de agente, y no por capricho: son los dos enfoques que
 * comparamos en el trabajo.
 *
 *   Campeon   aprende cuanto vale el lugar donde quedás DESPUES de jugar, y
 *             elige la jugada que maximiza (puntos ahora + valor de ese lugar)
 *   Tabulares la receta clasica, con el estado agrupado en casillas. Son las
 *             ablaciones del informe y juegan distinto, no solo peor
 *
 * La DP no aprendio: contiene el juego resuelto por programacion dinamica.
 * Con ella se separa cuanto del resultado fue decision y cuanto fue suerte.
 */
(function (global) {
  "use strict";

  var M = global.GD.motor;

  function desb64(texto, Tipo) {
    var bin = atob(texto);
    var bytes = new Uint8Array(bin.length);
    for (var i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    return new Tipo(bytes.buffer);
  }

  /** Ubica un monto de oro entre dos puntos de la grilla, con su peso. */
  function enGrilla(oro, nodos) {
    var ultimo = nodos.length - 1;
    if (oro >= nodos[ultimo]) return [ultimo, ultimo, 0];
    var lo = 0, hi = ultimo;
    while (lo < hi) {
      var mid = (lo + hi + 1) >> 1;
      if (nodos[mid] <= oro) lo = mid; else hi = mid - 1;
    }
    if (nodos[lo] === oro) return [lo, lo, 0];
    return [lo, lo + 1, (oro - nodos[lo]) / (nodos[lo + 1] - nodos[lo])];
  }

  /** Busca una clave en un arreglo ordenado. Devuelve la posicion o -1. */
  function buscar(claves, clave, n) {
    var lo = 0, hi = n - 1;
    while (lo <= hi) {
      var mid = (lo + hi) >> 1;
      if (claves[mid] === clave) return mid;
      if (claves[mid] < clave) lo = mid + 1; else hi = mid - 1;
    }
    return -1;
  }

  // ------------------------------------------------------- jugadas posibles
  function legales(s) {
    var out = [M.PASAR, M.PUNTUAR];
    if (s.oro >= M.costoDado(s.dados)) out.push(M.COMPRAR_DADO);
    if (s.oro >= M.costoMejora(s.bonus)) out.push(M.MEJORAR);
    if (s.oro >= M.SHIELD_COST) out.push(M.ESCUDO);
    if (s.oro >= M.STORE_COST && s.mejorDado > 0) out.push(M.GUARDAR);
    return out;
  }

  /** Donde quedás despues de jugar. Sin azar: es aritmetica. */
  function resultado(s, accion) {
    var base = { turno: s.turno, oro: s.oro, dados: s.dados, bonus: s.bonus, escudos: s.escudos, guardado: 0 };
    switch (accion) {
      case M.PASAR: return { estado: base, puntos: 0, cuanto: null };
      case M.PUNTUAR: return { estado: Object.assign({}, base, { oro: 0 }), puntos: s.oro, cuanto: s.oro };
      case M.COMPRAR_DADO:
        return { estado: Object.assign({}, base, { oro: s.oro - M.costoDado(s.dados), dados: s.dados + 1 }), puntos: 0, cuanto: null };
      case M.MEJORAR:
        return { estado: Object.assign({}, base, { oro: s.oro - M.costoMejora(s.bonus), bonus: s.bonus + 1 }), puntos: 0, cuanto: null };
      case M.ESCUDO:
        return { estado: Object.assign({}, base, { oro: s.oro - M.SHIELD_COST, escudos: s.escudos + 1 }), puntos: 0, cuanto: null };
      case M.GUARDAR:
        return { estado: Object.assign({}, base, { oro: s.oro - M.STORE_COST, guardado: s.mejorDado }), puntos: 0, cuanto: null };
    }
  }

  function etiqueta(accion, cuanto) {
    if (accion === M.PUNTUAR) return cuanto > 0 ? "puntuar " + cuanto : "puntuar 0";
    return M.NOMBRES[accion].toLowerCase();
  }

  /**
   * La cuenta a mano: la plata que tenés, mas los activos a lo que costaron,
   * mas lo que van a producir tus dados si no comprás nada mas.
   *
   * El agente no aprende el valor entero: aprende la CORRECCION sobre esto.
   * Es la diferencia entre medir 1 punto adentro de 130 de ruido y medirlo
   * adentro de casi nada.
   */
  function cuentaAMano(e) {
    var turnosQueQuedan = M.HORIZON - e.turno;
    return e.oro + e.guardado + e.escudos * M.SHIELD_COST + turnosQueQuedan * e.dados * (3.5 + e.bonus);
  }

  // ------------------------------------------------------------- el campeon
  function Campeon(meta) {
    this.id = meta.id; this.label = meta.label; this.algo = meta.algo; this.mean = meta.mean;
    this.claves = desb64(meta.keys, Uint32Array);
    this.vals = desb64(meta.vals, Int16Array);
    this.n = meta.count;
    this.escala = meta.scale;
    this.nodos = meta.nodes;
  }

  Campeon.prototype.residuo = function (e, nodo) {
    var n = Math.min(Math.max(e.dados, 1), 9) - 1;
    var b = Math.min(Math.max(e.bonus, 0), 8);
    var s = Math.min(Math.max(e.escudos, 0), 3);
    var clave = ((e.turno - 1) * 128 + nodo) * 400 + (n * 9 + b) * 4 + s;
    var i = buscar(this.claves, clave, this.n);
    return i < 0 ? 0 : this.vals[i] / this.escala;
  };

  Campeon.prototype.valor = function (e) {
    // Despues de jugar en el turno 30 no queda nada: el oro que sobre se
    // evapora. Ese lugar vale exactamente cero, y de ahi sale solo que la
    // ultima jugada sea puntuar todo.
    if (e.turno >= M.HORIZON) return 0;
    var g = enGrilla(e.oro, this.nodos);
    var r = g[0] === g[1]
      ? this.residuo(e, g[0])
      : (1 - g[2]) * this.residuo(e, g[0]) + g[2] * this.residuo(e, g[1]);
    return cuentaAMano(e) + r;
  };

  Campeon.prototype.ranking = function (s) {
    var self = this;
    return legales(s).map(function (a) {
      var r = resultado(s, a);
      return { accion: a, cuanto: r.cuanto, valor: r.puntos + self.valor(r.estado), texto: etiqueta(a, r.cuanto) };
    }).sort(function (x, y) { return y.valor - x.valor; });
  };

  // ---------------------------------------------------------- los tabulares
  var Q_PASAR = 0, Q_TODO = 1, Q_MITAD = 2, Q_DADO = 3, Q_MEJORA = 4, Q_ESCUDO = 5, Q_GUARDAR = 6;

  function Tabular(meta) {
    this.id = meta.id; this.label = meta.label; this.algo = meta.algo; this.mean = meta.mean;
    this.claves = desb64(meta.keys, Uint32Array);
    this.orden = desb64(meta.order, Uint8Array);
    this.top2 = desb64(meta.top2, Int16Array);
    this.n = meta.count;
    this.escala = meta.scale;
    this.p = meta.preset;
    this.espacio = meta.score_space;
  }

  Tabular.prototype.casilla = function (s) {
    var p = this.p;
    var quedan = M.HORIZON - s.turno;
    var tl = quedan === 0 ? 0 : 1 + Math.floor((quedan - 1) / p.turn_width);
    var oro = Math.floor(Math.min(s.oro, p.gold_cap) / p.gold_width);
    var d = Math.min(s.dados, p.dice_cap);
    var b = Math.min(s.bonus, p.bonus_cap);
    var e = Math.min(s.escudos, p.shield_cap);
    return (((tl * 256 + oro) * 16 + d) * 16 + b) * 8 + e;
  };

  Tabular.prototype.aJugada = function (q, s) {
    switch (q) {
      case Q_PASAR: return { accion: M.PASAR, cuanto: null };
      case Q_TODO: return { accion: M.PUNTUAR, cuanto: s.oro };
      case Q_MITAD: return { accion: M.PUNTUAR, cuanto: Math.floor(s.oro / 2) };
      case Q_DADO: return { accion: M.COMPRAR_DADO, cuanto: null };
      case Q_MEJORA: return { accion: M.MEJORAR, cuanto: null };
      case Q_ESCUDO: return { accion: M.ESCUDO, cuanto: null };
      default: return { accion: M.GUARDAR, cuanto: null };
    }
  };

  Tabular.prototype.ranking = function (s) {
    var i = buscar(this.claves, this.casilla(s), this.n);
    var posibles = legales(s);

    // Estado que nunca visito mientras entrenaba: no tiene nada que decir y se
    // queda con la primera jugada de la lista, que es pasar. Es exactamente lo
    // que hace la version de Python.
    if (i < 0) {
      return [{ accion: M.PASAR, cuanto: null, valor: NaN, texto: etiqueta(M.PASAR, null) }];
    }

    // Recorre su orden de preferencia y se queda con la primera jugada que hoy
    // pueda hacer. Guardar solo la mejor no alcanzaria: puede no ser legal.
    var elegida = null;
    for (var k = 0; k < 7 && !elegida; k++) {
      var q = this.orden[i * 7 + k];
      // Cada agente se entreno con su propio menu: el que no aprendio a
      // puntuar la mitad no puede elegirla ahora, aunque la tenga rankeada.
      if (q === Q_MITAD && this.espacio === "all") continue;
      var j = this.aJugada(q, s);
      if (posibles.indexOf(j.accion) >= 0) elegida = j;
    }
    if (!elegida) elegida = { accion: M.PASAR, cuanto: null };

    return [{
      accion: elegida.accion, cuanto: elegida.cuanto,
      valor: this.top2[i * 2] / this.escala,
      segundo: this.top2[i * 2 + 1] / this.escala,
      texto: etiqueta(elegida.accion, elegida.cuanto),
    }];
  };

  // ---------------------------------------------------------------- DP
  function DP(meta) {
    this.datos = desb64(meta.data, Int16Array);
    this.escala = meta.scale;
    this.nodos = meta.nodes;
    this.optimo = meta.optimal;
    var nn = meta.nodes.length;
    this.pS = nn; this.pB = 4 * nn; this.pN = 9 * 4 * nn; this.pT = 9 * 9 * 4 * nn;
  }

  /** Puntos esperados ANTES de tirar los dados del turno t, con ese oro. */
  DP.prototype.u = function (t, oro, n, b, s) {
    if (t > M.HORIZON) return 0;
    n = Math.min(Math.max(n, 1), 9) - 1;
    b = Math.min(Math.max(b, 0), 8);
    s = Math.min(Math.max(s, 0), 3);
    var base = (t - 1) * this.pT + n * this.pN + b * this.pB + s * this.pS;
    var g = enGrilla(oro, this.nodos);
    var vi = this.datos[base + g[0]] / this.escala;
    if (g[0] === g[1]) return vi;
    return (1 - g[2]) * vi + g[2] * (this.datos[base + g[1]] / this.escala);
  };

  /** Cuanto vale terminar el turno con ese oro, contando tormenta y tirada. */
  DP.prototype.cola = function (t, oro, n, b, s, guardado) {
    if (t >= M.HORIZON) return 0;
    guardado = guardado || 0;
    var queda = oro + guardado;
    var v = (1 - M.STORM_PROB) * this.u(t + 1, queda, n, b, s);
    if (s > 0) v += M.STORM_PROB * this.u(t + 1, queda, n, b, s - 1);
    else v += M.STORM_PROB * this.u(t + 1, Math.floor(oro / 2) + guardado, n, b, 0);
    return v;
  };

  /** Lo que vale una jugada concreta, incluyendo cuanto oro puntuaste. */
  DP.prototype.valorDe = function (s, accion, cuanto) {
    if (accion === M.PUNTUAR) {
      var k = Math.max(0, Math.min(Math.floor(cuanto || 0), s.oro));
      return k + this.cola(s.turno, s.oro - k, s.dados, s.bonus, s.escudos);
    }
    var r = resultado(s, accion);
    var e = r.estado;
    return r.puntos + this.cola(s.turno, e.oro, e.dados, e.bonus, e.escudos, e.guardado);
  };

  DP.prototype.ranking = function (s) {
    var self = this;
    var out = [];
    legales(s).forEach(function (a) {
      if (a === M.PUNTUAR) {
        // Puntuar es parametrica: se prueba dejar cada monto de la grilla y se
        // elige el mejor corte. Casi siempre es puntuar todo, pero no siempre.
        var mejor = { valor: -Infinity, deja: 0 };
        for (var i = 0; i < self.nodos.length; i++) {
          var deja = self.nodos[i];
          if (deja > s.oro) break;
          var v = (s.oro - deja) + self.cola(s.turno, deja, s.dados, s.bonus, s.escudos);
          if (v > mejor.valor) mejor = { valor: v, deja: deja };
        }
        var cuanto = s.oro - mejor.deja;
        out.push({ accion: a, cuanto: cuanto, valor: mejor.valor, texto: etiqueta(a, cuanto) });
      } else {
        var r = resultado(s, a);
        out.push({ accion: a, cuanto: r.cuanto, valor: self.valorDe(s, a, r.cuanto), texto: etiqueta(a, r.cuanto) });
      }
    });
    return out.sort(function (x, y) { return y.valor - x.valor; });
  };

  /**
   * Separa habilidad de suerte.
   *
   * Para cada jugada calculamos cuanto valor destruyo: lo que valia la
   * situacion antes, menos lo que vale despues de tu jugada. Da cero si
   * jugaste optimo y nunca da negativo. Sumado sobre la partida:
   *
   *     calidad = 642.45 - (todo lo que destruiste)     <- lo que hiciste vos
   *     suerte  = puntaje real - calidad                <- lo que te pasó
   *
   * Las dos suman tu puntaje final, exacto. Es la misma idea con la que los
   * jugadores de poker separan una buena decision de un buen resultado.
   */
  DP.prototype.analizar = function (situaciones, historia, pistas) {
    var self = this;
    var turnos = [];
    var perdidoTotal = 0;

    historia.forEach(function (reg, i) {
      var s = situaciones[i];
      var jugado = self.valorDe(s, reg.accion, reg.cuanto);
      var mejor = self.ranking(s)[0];
      var perdido = Math.max(0, mejor.valor - jugado);
      perdidoTotal += perdido;
      turnos.push({
        turno: reg.turno,
        jugaste: etiqueta(reg.accion, reg.cuanto),
        convenia: mejor.texto,
        perdido: perdido,
      });
    });

    var puntaje = historia.length ? historia[historia.length - 1].puntosDespues : 0;
    var calidad = this.optimo - perdidoTotal;
    var penalizacion = (pistas || 0) * 1.5;
    return {
      optimo: this.optimo,
      puntaje: puntaje,
      perdido: perdidoTotal,
      calidad: calidad,
      suerte: puntaje - calidad,
      // Cada pista pedida descuenta: la ayuda existe, pero no es gratis.
      nota: Math.max(0, 100 * (1 - perdidoTotal / this.optimo) - penalizacion),
      pistas: pistas || 0,
      turnos: turnos,
      peores: turnos.slice().sort(function (a, b) { return b.perdido - a.perdido; }).slice(0, 3),
    };
  };

  // ------------------------------------------------------------- carga
  function cargar(datos) {
    var agentes = datos.agents.map(function (m) {
      return m.kind === "champion" ? new Campeon(m) : new Tabular(m);
    });
    agentes.sort(function (a, b) { return b.mean - a.mean; });
    return { agentes: agentes, dp: new DP(datos.dp), optimo: datos.optimal };
  }

  global.GD.agentes = {
    cargar: cargar, legales: legales, resultado: resultado,
    etiqueta: etiqueta, cuentaAMano: cuentaAMano,
    Campeon: Campeon, Tabular: Tabular, DP: DP,
  };
})(typeof globalThis !== "undefined" ? globalThis : this);
