# Gold Dice RL

**Trabajo Práctico 1, Reinforcement Learning, Inteligencia Artificial y Neurociencias**

## 1. Cómo encaramos el problema

Al leer el enunciado nos quedaron tres preguntas. ¿Cuánto se puede obtener si se juega bien? ¿Qué parte de la observación necesita recordar el agente? ¿Cómo representamos `SCORE`, que permite elegir cualquier cantidad de oro, dentro de una tabla con pocas acciones?

Uno de nosotros viene de competir en ICPC y reconoció un problema de horizonte finito. Antes de entrenar resolvimos el juego con programación dinámica. El archivo `sol_dp.cpp` contiene esa solución en menos de 100 líneas de C++. Definimos

```text
DP[t][dados][bonus][escudos][oro]
```

como los puntos esperados desde el turno `t`, antes de tirar. No incluimos los puntos acumulados porque no cambian las tiradas, los precios ni las tormentas. Calculamos los turnos desde el 30 hacia el 1 y, para cada estado, probamos las acciones legales. La distribución conjunta de la suma y el máximo de los dados se obtiene por convolución; no usamos simulaciones en esta cuenta. Con una grilla de oro acotada en 700, igual a la usada durante el análisis, la DP estima **642,45 puntos** al comienzo. Los comentarios del `.cpp` explican la recurrencia y el tratamiento de `SCORE`, tormentas y `STORE_BEST_DIE`.

La DP no participa del torneo y no es un modelo de Reinforcement Learning. La usamos para medir el margen disponible y revisar nuestras decisiones de diseño.

La primera intuición que descartamos fue que hacía falta conservar cientos de acciones `SCORE(k)`. Volvimos a correr la DP restringiendo esa acción. Permitir sólo `SCORE(todo)` no cambió el valor calculado: la política de la DP convierte el oro en puntos al final. Por eso el agente aprendido trabaja con seis opciones: pasar, puntuar todo, comprar un dado, mejorar los dados, comprar un escudo o guardar el mejor dado.

## 2. Estado, acciones y recompensa

La observación original tiene nueve campos. Para aprender usamos el estado posterior a la acción, llamado *afterstate*:

```text
(turno, oro, cantidad de dados, bonus, escudos, dado guardado)
```

El efecto inmediato de una compra es determinista; el azar aparece después, con la tormenta y la próxima tirada. Aprender el valor del *afterstate* permite que dos jugadas que dejan la misma situación compartan experiencia. Los puntos acumulados no cambian el futuro, `roll_sum` ya se sumó al oro y `roll_max` sólo se usa al evaluar `STORE_BEST_DIE`.

El oro no tiene un límite declarado. Usamos una grilla no uniforme: conserva cada entero entre 0 y 96, donde están los umbrales de compra, y separa más los valores altos. Interpolamos entre dos nodos vecinos. Así, 41 y 42 no caen en la misma casilla cuando 42 habilita una compra.

La recompensa es la que entrega el ambiente: la cantidad convertida en puntos mediante `SCORE`; las demás acciones dan cero. Como casi toda la recompensa llega tarde, inicializamos el valor con una cuenta de referencia:

```text
Φ = oro + dado_guardado + 5·escudos
    + turnos_restantes·dados·(3,5 + bonus)
```

La tabla aprende una corrección sobre `Φ`. Esta cuenta valora la caja y la producción esperada si no se comprara nada más. No contiene la probabilidad de tormenta ni decide cuándo conviene comprar: eso queda a cargo del entrenamiento.

## 3. Modelo y entrenamiento

El modelo entregado es **Q-Learning tabular**, una de las técnicas propuestas en el enunciado. Lo formulamos sobre *afterstates* y usamos **Double Q-Learning**: una tabla elige la mejor continuación y la otra la evalúa. La versión de una tabla empezó a empeorar con más episodios por el sesgo que produce tomar el máximo entre estimaciones ruidosas.

| Hiperparámetro | Valor |
|---|---:|
| episodios | 1.500.000 |
| γ | 1 |
| ε | 0,15 → 0,02 durante el 60 % inicial |
| escala de α | 0,03 |
| α mínimo por peso | 0,002 |
| evaluación de checkpoint | 4.000 partidas cada 100.000 episodios |

Elegimos `γ = 1` porque la partida dura 30 turnos y queremos maximizar la suma final sin descontar puntos tardíos. Durante la evaluación el agente deja de explorar: carga `artifacts/gold_dice_agent.pkl` y elige siempre la acción con mayor valor.

## 4. Resultados y qué aprendimos

Evaluamos 20.000 partidas por agente en semillas separadas de las usadas para entrenar.

| Agente | Media | IC 95 % | Parte del valor DP |
|---|---:|---:|---:|
| DP, sólo como referencia | 644,10 | [642,2; 646,0] | 100,3 % |
| **Nuestro Q-Learning** | **527,06** | **[525,2; 529,0]** | **82,0 %** |
| `SimpleExpectancy` | 343,40 | [342,0; 344,8] | 53,5 % |
| `RandomLegal` | 63,03 | [62,5; 63,6] | 9,8 % |

El agente supera los dos baselines. Aprende a invertir en dados y mejoras durante los primeros turnos, usa `STORE_BEST_DIE` y posterga buena parte del cobro. En tres rangos de semillas obtuvo 527,06, 526,27 y 525,42 puntos; las diferencias entran en el error estadístico.

La representación aportó más que seguir agregando episodios. Un agente que usa `Φ` sin valores aprendidos logra 490,41 puntos, mientras que el entrenamiento suma unos 37 puntos. También probamos una tabla Q convencional con *buckets* y límites chicos; obtuvo entre 293 y 365 puntos según la configuración. Esto mostró que agrupar todo el final de la partida en pocas casillas impedía representar una buena política.

La principal falla del agente final aparece cerca del turno 23. La DP compra un escudo y acumula oro hasta el último turno. Nuestro agente compra pocos escudos y cobra antes. Para ubicar este error comparamos, en cada estado visitado, el valor de la acción elegida con el valor de la mejor acción según la DP. Llamamos **puntos perdidos por la decisión** a esa diferencia; vale cero si ambas elecciones coinciden. La definición, los experimentos descartados y las tablas completas están en `docs/02_RESULTADOS.md`.

Probamos más exploración, trazas de elegibilidad y hasta cinco millones de episodios. Ninguna variante cerró la brecha. El problema requiere descubrir varias decisiones coordinadas: comprar el escudo y luego conservar el oro. La exploración ε-greedy cambia una acción por vez y visita poco esa secuencia completa.

## 5. Archivos entregados

La cátedra proporcionó `config.py`, `env.py`, `agents.py`, `renderer.py`, `evaluate_agents.py` y `run_example.py`. Mantuvimos intacta la lógica de `config.py` y `env.py`; agregamos `GoldDiceAgent` dentro de `agents.py`.

Sólo agregamos tres archivos Python:

| Archivo propio | Motivo |
|---|---|
| `afterstate.py` | Define las acciones del agente, calcula el estado posterior y la cuenta `Φ`. Sus funciones centrales son `legal_actions`, `apply`, `potential` y `gold_features`. |
| `value_table.py` | Guarda, interpola, actualiza y carga la tabla aprendida. `value` consulta un estado, `update` aplica el paso TD y `save/load` manejan los pesos. |
| `train_qlearning.py` | Contiene el entrenamiento Double Q-Learning, la política temporal de dos tablas y el guardado del mejor checkpoint. |

`sol_dp.cpp` es una herramienta de análisis independiente. `gold_dice_agent.pkl` contiene los pesos ya entrenados. Un inventario de los archivos provistos y propios, con la relación entre sus funciones, está en `docs/03_QUE_CONSTRUIMOS.md` porque no entra en el límite de tres carillas.

También adjuntamos tres Markdown complementarios. `01_REGLAS_OCULTAS.md` reúne casos borde que encontramos al leer el ambiente; `02_RESULTADOS.md` explica los números con más espacio; `03_QUE_CONSTRUIMOS.md` documenta el código. Los incluimos porque queríamos dejar el proceso reproducible sin convertir el informe principal en un documento más largo que el permitido.
