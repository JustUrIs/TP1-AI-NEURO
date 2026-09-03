# Gold Dice RL — Trabajo Práctico 1

Aprendizaje por Refuerzos · Inteligencia Artificial y Neurociencias · UTDT

Un agente que juega Gold Dice RL, la solución exacta del juego para medirlo, y
una versión jugable en el navegador.

| | Media (n = 20.000) | % del óptimo |
|---|---:|---:|
| Óptimo exacto — programación dinámica, **no compite** | 644.10 | 100 % |
| **`GoldDiceAgent`** — el agente entregado | **527.06** | **82.0 %** |
| `SimpleExpectancy` — mejor baseline provisto | 343.40 | 53.5 % |
| `RandomLegal` — baseline provisto | 63.03 | 9.8 % |

---

## La idea

Casi cualquier informe de este TP puede decir "nuestro agente sacó X, el
baseline sacó Y". El problema es que ese par de números no dice si X es bueno:
¿faltaban 10 puntos o 300?

Así que antes de entrenar nada resolvimos el juego **exacto**. `points` no
aparece en ninguna transición de `env.py`, así que la función de valor no
depende de los puntos y el MDP se reduce a cuatro variables: se resuelve por
inducción hacia atrás en 17 segundos.

> **El juego vale 642.45 puntos esperados jugado perfecto.**

Ese número convierte cada decisión de diseño en algo medible, y ahí aparecieron
los resultados que no esperábamos:

- **Colapsar `SCORE` de 401 valores a uno cuesta 0.00 puntos.** Era nuestra
  hipótesis principal sobre por qué falla el enfoque tabular, y era falsa.
- **Los topes típicos de discretización cuestan 62 puntos.** Con
  `dados ≤ 5, bonus ≤ 4, oro ≤ 240`, el 38 % de las decisiones óptimas queda
  fuera de rango y todo el endgame cae en una sola celda de la tabla.
- **`γ < 1` solo ayuda cuando la representación está rota.** Con rangos amplios
  no cambia nada; con topes chicos es 22 puntos *mejor*, porque tapa la falla en
  vez de resolverla. Mirar solo el número lleva a la conclusión opuesta.
- **De los 527 puntos, 490 vienen de la representación y 37 del aprendizaje.**
  Lo reportamos porque es verdad.

El agente entregado usa TD de control off-policy sobre *afterstates* con Double
learning y `γ = 1`. La brecha que falta hasta el óptimo está diagnosticada, no
escondida: es un óptimo local de política alrededor del escudo del turno 23.
Hicimos dos predicciones cuantitativas sobre cómo cerrarla y **una falló**, lo
que identificó la causa real — qué estados se visitan, no cuántas veces.

## El repositorio

```
gold_dice_rl/     el TP. env.py y config.py son de la cátedra y están intactos
informe/          informe.tex / .pdf (3 páginas) y apéndice técnico (8)
docs/             plan, análisis del ambiente y resultados completos
juego/            el juego, en HTML puro (doble clic y anda)
package.py        arma el ZIP de entrega y lo prueba en carpeta limpia
```

## Correrlo

```bash
cd gold_dice_rl
python oracle_dp.py                 # resuelve el juego exacto (~17 s)
python results.py desarrollo 20000  # la tabla del informe
python diagnose.py artifacts/gold_dice_agent.pkl
python train_double.py              # reentrenar el agente
```

El agente entregado se usa igual que los baselines:

```python
from agents import GoldDiceAgent
from evaluate_agents import evaluate
print(evaluate(GoldDiceAgent(), n_episodes=1000, seed=0))
```

## El juego

`juego/index.html` se abre con doble clic: no necesita servidor, ni instalación,
ni internet. Jugás solo, contra el Campeón, o contra los tres agentes a la vez.
Al terminar se analiza tu partida contra la solución exacta y se separa **cuánto
de tu resultado fue decisión y cuánto fue suerte**:

```
arrepentimiento = V*(antes) − [ puntos + V*(después) ]     ≥ 0, cero si jugaste óptimo
calidad = 642.45 − Σ arrepentimiento          suerte = puntaje real − calidad
```

Las dos suman tu puntaje final, exacto. El leaderboard tiene doble ranking, y el
de decisiones no se puede farmear volviendo a tirar.

Los agentes corren enteros en el navegador y explican cada jugada con los
números que realmente calcularon, sin llamar a ninguna API. No te marcamos la
jugada buena antes de que elijas —eso arruina el juego—: te la mostramos después,
con lo que costó la diferencia. Detalle en [`juego/LEEME.md`](juego/LEEME.md).

## Verificación

Nada de lo de arriba se afirma sin comprobarlo.

| Qué | Cómo | Resultado |
|---|---|---|
| `env.py` y `config.py` intactos | `filecmp` byte a byte en `package.py` | idénticos |
| La entrega corre sola | carpeta limpia + `evaluate_agents.py` original | sin intervención manual |
| El motor del navegador | 60 partidas con azar guionado contra `env.py` | 14.460 comparaciones, **0 diferencias** |
| Las políticas exportadas | 6.600 estados contra los agentes de Python | **los tres al 100 %** |
| La interfaz del juego | dos partidas completas con un DOM simulado | sin errores |
| Sin sobreajuste | tres bandas de semillas disjuntas | 527.06 / 526.27 / 525.42 |

Esas verificaciones encontraron **tres errores reales** que jugando no se
notaban: una cuantización que borraba diferencias de 0,03 puntos entre jugadas,
un agente que elegía mal cuando su jugada preferida no era legal en ese momento,
y otro que usaba una acción con la que nunca había entrenado.

```bash
python package.py                    # verifica y arma la entrega
node juego/verificar/verificar.js    # motor, políticas y partidas completas
node juego/verificar/simular_ui.js   # la interfaz, sin navegador
```

## Lectura

- **[`informe/informe.pdf`](informe/informe.pdf)** — 3 páginas, lo que se entrega.
- [`informe/apendice.pdf`](informe/apendice.pdf) — el detalle que no entra.
- [`docs/01_REGLAS_OCULTAS.md`](docs/01_REGLAS_OCULTAS.md) — el ambiente leído
  línea por línea: los casos borde que no están en el enunciado y cambian la
  estrategia.
- [`docs/02_RESULTADOS.md`](docs/02_RESULTADOS.md) — todas las tablas y ablaciones.
- [`docs/03_QUE_CONSTRUIMOS.md`](docs/03_QUE_CONSTRUIMOS.md) — de qué partimos, qué archivo
  hace qué, y en qué orden fueron pasando las cosas. Escrito para leerse sin saber RL.
