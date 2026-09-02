"""
Tabla de valores sobre afterstates.

Tres decisiones, todas salidas de mirar por que la version ingenua se clavaba
en el 70% del optimo:

  * se aprende el RESIDUO sobre un potencial Phi, no el valor. El retorno tiene
    sigma ~130 y las decisiones tempranas valen 1 o 2 puntos: aprender V directo
    es medir 1 adentro de 130 de ruido.
  * paso de aprendizaje por peso (Robbins-Monro), no global.
  * el oro va en grilla no uniforme con interpolacion lineal, no en buckets: con
    buckets, 41 y 42 de oro caen en la misma celda y el agente no distingue
    "puedo comprar el dado" de "no puedo".
"""

from __future__ import annotations

import pickle

from afterstate import GOLD_NODES, gold_features, potential, is_terminal


class ValueTable:
    def __init__(self, alpha_min: float = 0.01, alpha_decay: float = 0.55,
                 potential_scale: float = 1.0, gold_nodes: list[int] | None = None):
        # clave -> [residuo, visitas]
        self.theta: dict[tuple, list] = {}
        self.alpha_min = alpha_min
        self.alpha_decay = alpha_decay
        # potential_scale = 0 apaga Phi y hace que la tabla aprenda V directo.
        # Existe solo como perilla de ablacion: sirve para medir cuanto aporta
        # el potencial, con todo lo demas igual.
        self.potential_scale = potential_scale
        # La grilla de oro define el significado de las claves (que guardan
        # indices de nodo), asi que viaja con la tabla y se persiste con ella.
        self.gold_nodes = list(GOLD_NODES) if gold_nodes is None else list(gold_nodes)

    # Topes de la clave. Los rangos salen de medir que visita el juego optimo
    # (docs/01_REGLAS_OCULTAS.md 8-bis): dados hasta 9, bonus hasta 8, escudos
    # casi nunca mas de 1. Por encima del tope los estados comparten peso: son
    # estados que solo se alcanzan explorando y no vale gastar parametros ahi.
    N_CAP = 9
    B_CAP = 8
    S_CAP = 3

    @staticmethod
    def _key(afterstate: tuple, node: int) -> tuple:
        """
        Clave de un peso. Notar que `carry` NO entra.

        El oro guardado por STORE_BEST_DIE ya esta contemplado exactamente en
        Phi (que lo suma con coeficiente 1). Lo unico que el residuo no puede
        expresar es que ese oro guardado no sufre la tormenta de este turno,
        una diferencia de 0.15 * carry / 2 <= 1 punto. A cambio, sacar `carry`
        de la clave divide por siete la cantidad de pesos justo en la accion
        mas usada del juego, que es donde mas falta hacen las muestras.
        """
        turn, _gold, n, b, s, _carry = afterstate
        return (
            turn,
            node,
            n if n <= ValueTable.N_CAP else ValueTable.N_CAP,
            b if b <= ValueTable.B_CAP else ValueTable.B_CAP,
            s if s <= ValueTable.S_CAP else ValueTable.S_CAP,
        )

    # -- lectura ------------------------------------------------------------
    def value(self, afterstate: tuple) -> float:
        """V(f) = Phi(f) + R(f), con R interpolado entre dos nodos de oro."""
        if is_terminal(afterstate):
            return 0.0
        theta = self.theta
        i, j, w = gold_features(afterstate[1], self.gold_nodes)
        ri = theta.get(self._key(afterstate, i))
        ri = ri[0] if ri is not None else 0.0
        if i == j:
            residual = ri
        else:
            rj = theta.get(self._key(afterstate, j))
            rj = rj[0] if rj is not None else 0.0
            residual = (1.0 - w) * ri + w * rj
        return self.potential_scale * potential(afterstate) + residual

    def features(self, afterstate: tuple) -> tuple:
        """
        Los (a lo sumo dos) pesos activos y sus coeficientes.

        Es el gradiente de V respecto de theta: V = Phi + sum_i c_i * R_i, con
        sum c_i = 1. Se expone para poder llevar trazas de elegibilidad afuera
        de la tabla.
        """
        i, j, w = gold_features(afterstate[1], self.gold_nodes)
        if i == j:
            return ((self._key(afterstate, i), 1.0),)
        return ((self._key(afterstate, i), 1.0 - w), (self._key(afterstate, j), w))

    def bump(self, key: tuple, delta_theta: float) -> None:
        """Suma `delta_theta` al peso `key` (usado por el bucle con trazas)."""
        entry = self.theta.get(key)
        if entry is None:
            self.theta[key] = [delta_theta, 0]
        else:
            entry[0] += delta_theta

    def alpha_for(self, key: tuple, visit: bool = True) -> float:
        """Paso de aprendizaje del peso `key`, con su contador de visitas."""
        entry = self.theta.get(key)
        if entry is None:
            entry = self.theta[key] = [0.0, 0]
        if visit:
            entry[1] += 1
        return max(self.alpha_min, (1.0 + entry[1]) ** -self.alpha_decay)

    # -- escritura ----------------------------------------------------------
    def update(self, afterstate: tuple, target: float, alpha_scale: float = 1.0) -> float:
        """Paso semi-gradiente de R hacia `target`. Devuelve el error TD."""
        if is_terminal(afterstate):
            return 0.0
        theta = self.theta
        i, j, w = gold_features(afterstate[1], self.gold_nodes)
        ki = self._key(afterstate, i)
        ei = theta.get(ki)
        if ei is None:
            ei = theta[ki] = [0.0, 0]

        if i == j:
            delta = target - (self.potential_scale * potential(afterstate) + ei[0])
            ei[1] += 1
            alpha = max(self.alpha_min, (1.0 + ei[1]) ** -self.alpha_decay) * alpha_scale
            ei[0] += alpha * delta
            return delta

        kj = self._key(afterstate, j)
        ej = theta.get(kj)
        if ej is None:
            ej = theta[kj] = [0.0, 0]

        delta = target - (self.potential_scale * potential(afterstate) + (1.0 - w) * ei[0] + w * ej[0])
        ei[1] += 1
        ej[1] += 1
        ai = max(self.alpha_min, (1.0 + ei[1]) ** -self.alpha_decay) * alpha_scale
        aj = max(self.alpha_min, (1.0 + ej[1]) ** -self.alpha_decay) * alpha_scale
        ei[0] += ai * (1.0 - w) * delta
        ej[0] += aj * w * delta
        return delta

    # -- persistencia -------------------------------------------------------
    def __len__(self) -> int:
        return len(self.theta)

    def save(self, path: str) -> None:
        with open(path, "wb") as fh:
            pickle.dump(
                {
                    "theta": {k: (v[0], v[1]) for k, v in self.theta.items()},
                    "alpha_min": self.alpha_min,
                    "alpha_decay": self.alpha_decay,
                    "potential_scale": self.potential_scale,
                    "gold_nodes": self.gold_nodes,
                },
                fh,
                protocol=4,
            )

    @classmethod
    def load(cls, path: str) -> "ValueTable":
        with open(path, "rb") as fh:
            blob = pickle.load(fh)
        table = cls(alpha_min=blob["alpha_min"], alpha_decay=blob["alpha_decay"],
                    potential_scale=blob.get("potential_scale", 1.0),
                    gold_nodes=blob.get("gold_nodes"))
        table.theta = {k: [v[0], v[1]] for k, v in blob["theta"].items()}
        return table
