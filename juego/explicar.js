/*
 * Explicaciones de jugadas.
 *
 * Ninguna frase esta escrita a mano para una jugada puntual: todas se arman
 * con los numeros que el agente realmente calculo en esa situacion, mas la
 * aritmetica del juego (cuanto rinde un dado por turno, en cuantos turnos se
 * paga, cuanto oro se espera perder por tormenta).
 *
 * Se hizo asi por una razon concreta: una explicacion escrita aparte del
 * razonamiento se desincroniza apenas el agente cambia, y termina mintiendo.
 */
(function (global) {
  "use strict";

  var M = global.GD.motor;
  var un = function (x) { return x.toFixed(1); };
  var cero = function (x) { return Math.round(x).toString(); };

  function explicar(s, ranking) {
    var mejor = ranking[0];
    var segunda = ranking[1];
    var quedan = M.HORIZON - s.turno;
    var porTurno = s.dados * (3.5 + s.bonus);
    var expuesto = M.STORM_PROB * (s.oro / 2);
    var razones = [];
    var titulo = "";

    switch (mejor.accion) {
      case M.PUNTUAR:
        titulo = "Convierto " + mejor.cuanto + " de oro en puntos.";
        razones.push(
          "Los puntos ya no me los puede sacar nadie: la tormenta llega despues de mi jugada, " +
          "asi que lo que convierto queda a salvo y lo que dejo sobre la mesa no."
        );
        if (s.turno === M.HORIZON) {
          razones.push("Ademas es el ultimo turno. No hay tirada 31, asi que el oro que no convierta ahora se evapora.");
        } else if (s.oro > 0) {
          razones.push(
            "Dejar " + s.oro + " de oro sin convertir cuesta " + un(expuesto) + " puntos en promedio por turno" +
            (s.escudos > 0 ? ", aunque el escudo lo cubriria." : ".")
          );
        }
        break;

      case M.COMPRAR_DADO:
        var costo = M.costoDado(s.dados);
        var extra = 3.5 + s.bonus;
        titulo = "Compro un dado. Paso de " + s.dados + " a " + (s.dados + 1) + " y me cuesta " + costo + ".";
        razones.push(
          "Un dado mas produce " + un(extra) + " de oro por turno, asi que se paga solo en " +
          un(costo / extra) + " turnos y quedan " + quedan + "."
        );
        razones.push(
          "De aca al final me va a devolver unos " + cero(extra * quedan) + " de oro. Convertir esos " +
          costo + " ahora me daria " + costo + " puntos y nada mas."
        );
        break;

      case M.MEJORAR:
        var cm = M.costoMejora(s.bonus);
        titulo = "Mejoro los dados. El bonus pasa de " + s.bonus + " a " + (s.bonus + 1) + " y me cuesta " + cm + ".";
        razones.push(
          "El bonus se aplica a los " + s.dados + " dados, incluidos los que compre despues, " +
          "asi que suma " + s.dados + " de oro por turno: se paga en " + un(cm / s.dados) + " turnos."
        );
        razones.push(
          "Mejorar rinde mas que comprar un dado cuando tengo mas de " + un(3.5 + s.bonus) +
          " dados, y tengo " + s.dados + "."
        );
        break;

      case M.ESCUDO:
        titulo = "Compro un escudo. Me cuesta " + M.SHIELD_COST + ".";
        razones.push(
          "El escudo no me protege del juego: me compra el derecho a usar mis turnos en algo que no sea " +
          "cobrar. Con escudo puesto, no convertir deja de costarme " + un(expuesto) + " puntos por turno."
        );
        razones.push(
          "Quedan " + quedan + " turnos, o sea " + un(quedan * M.STORM_PROB) +
          " tormentas esperadas. Un escudo bloquea una."
        );
        break;

      case M.GUARDAR:
        titulo = "Guardo el mejor dado, que vale " + s.mejorDado + ". Me cuesta " + M.STORE_COST + ".";
        razones.push(
          "No lo aparto: lo clono. La suma de la tirada ya la cobre, y guardar hace que ese " +
          s.mejorDado + " se vuelva a cobrar el turno que viene. Pago " + M.STORE_COST +
          " y recibo " + s.mejorDado + ": neto " + (s.mejorDado - M.STORE_COST >= 0 ? "+" : "") +
          (s.mejorDado - M.STORE_COST) + "."
        );
        if (s.oro > 60 && s.escudos === 0) {
          razones.push(
            "Con " + s.oro + " de oro y sin escudo esto expone " + un(expuesto) +
            " puntos a la tormenta, pero sigue siendo lo mejor que tengo disponible."
          );
        }
        break;

      default:
        titulo = "Paso.";
        razones.push(
          "Con " + s.oro + " de oro no me alcanza para nada que valga la pena. La proxima compra util " +
          "cuesta " + Math.min(M.costoDado(s.dados), M.costoMejora(s.bonus)) + ", asi que acumulo."
        );
    }

    razones.push(
      "Mi motor produce " + un(porTurno) + " de oro por turno (" + s.dados + " dados con bonus +" +
      s.bonus + ") y quedan " + quedan + " turnos."
    );

    var alternativa = null;
    if (segunda && isFinite(segunda.valor) && isFinite(mejor.valor)) {
      alternativa = "Mi segunda opcion era " + segunda.texto + ": la valuo en " + un(segunda.valor) +
        " contra " + un(mejor.valor) + ", una diferencia de " + un(mejor.valor - segunda.valor) + " puntos.";
    } else if (isFinite(mejor.valor) && mejor.segundo !== undefined) {
      alternativa = "Entre mi mejor jugada y la siguiente hay " + un(mejor.valor - mejor.segundo) + " puntos de diferencia.";
    }

    return { titulo: titulo, razones: razones, alternativa: alternativa };
  }

  global.GD.explicar = explicar;
})(typeof globalThis !== "undefined" ? globalThis : this);
