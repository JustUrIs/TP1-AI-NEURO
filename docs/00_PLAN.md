# Plan de acción — TP 1: Gold Dice RL

**Materia:** Inteligencia Artificial y Neurociencias (UTDT)
**Entrega:** miércoles 2/9, 23:59 hs → **queda ~1 día**
**Estado del repo hoy:** solo el código provisto por la cátedra. Cero código propio. Cero informe.

---

## 0. La decisión que define todo el trabajo

Antes de escribir una línea de agente, resolvimos el juego **exacto** por programación dinámica
(`docs/01_REGLAS_OCULTAS.md` §9). El número es:

```
Óptimo teórico  =  642.45 puntos esperados
```

Ese número reencuadra el trabajo práctico entero:

| | Puntaje | % del óptimo |
|---|---:|---:|
| **Óptimo (DP exacta)** | **642.45** | **100 %** |
| `SimpleExpectancy` (baseline de la cátedra) | 343.4 | 53 % |
| `RandomLegal` (baseline de la cátedra) | 63.0 | 10 % |
| Q-Learning tabular "de manual" (referencia externa vista) | ~276 | 43 % |

Dos lecturas, y las dos importan:

1. **Hay muchísimo lugar arriba.** El baseline "inteligente" de la cátedra deja el 46 % de los
   puntos sobre la mesa. El torneo se gana por márgenes enormes, no por décimas.
2. **Un Q-Learning tabular estándar pierde contra el baseline.** No por falta de episodios: por
   cómo representa el estado. Y no por las razones que uno supondría — las medimos una por una
   con el oráculo y la hipótesis obvia resultó falsa. Ver §2.1.

**La tesis del trabajo, en una línea:**

> En este problema, el techo no lo pone el algoritmo de aprendizaje: lo pone la representación.
> Vamos a demostrarlo midiendo contra el óptimo exacto, no contra un baseline arbitrario.

Eso es lo que hace que este TP no se parezca a los otros treinta.

---

## 1. Entregables

### Bloque A — El TP (ruta crítica, vence mañana)

| # | Entregable | Requisito del enunciado |
|---|---|---|
| A1 | Agente entrenado con una técnica de RL, que juega solo | obligatorio |
| A2 | Todo el código de entrenamiento | obligatorio |
| A3 | `qtable` / pesos entrenados, cargables sin reentrenar | obligatorio |
| A4 | Informe de **hasta 3 páginas** | obligatorio |
| A5 | Un agente elegido para el torneo | obligatorio |
| A6 | Suite de evaluación con intervalos de confianza | nuestro |
| A7 | Solver DP exacto como oráculo y techo | nuestro |

### Bloque B — El juego web (después de la entrega)

| # | Entregable |
|---|---|
| B1 | Jugar Gold Dice RL solo, en el navegador |
| B2 | Jugar **contra 1 o contra 3** agentes entrenados, turno a turno, en paralelo |
| B3 | Botón "?" → el agente explica su jugada con los números reales (sin llamadas a ninguna API) |
| B4 | Panel "qué hubiera hecho el modelo" después de cada jugada tuya |
| B5 | **Descomposición habilidad / suerte** usando el oráculo exacto |
| B6 | Leaderboard sin login (nombre + puntaje), doble ranking: crudo y ajustado por suerte |
| B7 | Estadísticas agregadas de cada modelo |
| B8 | Deploy en Vercel |

---

## 2. Diseño técnico del agente

### 2.1 Por qué el enfoque tabular estándar se estrella

Medimos cada decisión de modelado por separado con el oráculo, en vez de suponer cuál duele.
El resultado no fue el que esperábamos:

| Decisión típica | Costo medido | Veredicto |
|---|---|---|
| Discretizar `SCORE` en `{TODO, MITAD}` | **0.00 puntos** | **Inofensiva.** El juego óptimo puntúa una sola vez, en el turno 30, y puntúa todo. Nuestra hipótesis inicial era que ésta era *la* decisión cara. Estaba mal. |
| Capear `num_dice` en 5 y `dice_bonus` en 4 | **catastrófica** | El 38 % de las decisiones óptimas ocurren con más de 5 dados; el 36 % con bonus > 4. Todo el endgame cae en una sola celda de la tabla. |
| Capear el oro en 240 (bucket de ancho 6) | **catastrófica** | El juego óptimo acumula hasta 797 de oro entre los turnos 24 y 30. El agente no distingue 240 de 700. |
| `γ = 0.995` | sesgo sistemático | Multiplica el pago del turno 30 por 0.865, en un juego cuyo **único** cobro grande es ese. Sesga en contra de acumular. |

Las tres que importan ocurren **antes** de la primera actualización de Q, y ninguna cantidad
de episodios las arregla. La que parecía obvia no costaba nada.

> Esto ya es un resultado del trabajo: cuando una decisión de diseño se puede medir, no se
> opina sobre ella. Reportamos las dos cosas: la hipótesis que descartamos y la que confirmamos.

### 2.2 La idea central — aprender *afterstates*, no pares (estado, acción)

En este juego, el efecto de tu acción sobre el estado es **completamente determinista**. Gastar
18 de oro y sumar un dado no tiene ninguna incertidumbre. Todo el azar viene después: la
tormenta y la tirada siguiente.

Cuando pasa eso, Sutton & Barto (§6.8) es explícito: conviene aprender el valor del **estado
posterior a la acción** (*afterstate*) en lugar de `Q(s, a)`. Es la técnica de TD-Gammon.

Concretamente, en vez de aprender

```
Q(turno, oro, dados, bonus, escudos, roll_max ; acción)      ← 7 acciones discretizadas
```

aprendemos

```
V(turno, oro', dados', bonus', escudos')                     ← el estado DESPUÉS de la acción
```

y la política elige:

```
acción = argmax  [ puntos_inmediatos + V(afterstate) ]
```

Esto compra tres cosas de una:

1. **Muchos pares (s, a) distintos colapsan al mismo afterstate.** Comprar un dado desde 50 de
   oro y desde 60 de oro con distinto `roll_max` terminan en estados posteriores parecidos y
   comparten experiencia. La tabla aprende mucho más rápido con los mismos datos.
2. **El espacio de acciones queda en 6 acciones discretas, con costo medido en 0.00.**
   `SCORE` se reduce a `SCORE(todo)` porque el solver demuestra que la versión paramétrica no
   agrega valor (§6 de `01_REGLAS_OCULTAS.md`). No es una aproximación cómoda: es una
   reducción verificada, y el mismo solver da el control negativo que prueba que la medición
   distingue restricciones que sí duelen.
3. **`roll_max` sale del estado aprendido.** Solo afecta a `STORE_BEST_DIE`, y en esa rama
   entra como un corrimiento aditivo conocido sobre el afterstate. Una dimensión menos.

Es una variante de Q-Learning tabular, no otro algoritmo: misma regla TD, mismo bootstrap,
mismo control off-policy. Cambia el espacio sobre el que se aprende. Justificable en dos
oraciones frente a la cátedra.

### 2.3 Reward shaping (potential-based), para el crédito temprano

El problema de crédito es brutal: comprar un dado en el turno 4 da recompensa 0, y su efecto
se cobra veinte turnos después repartido entre muchas jugadas.

Usamos shaping basado en potencial (Ng, Harada & Russell, 1999):

```
r'(s, a, s') = r + Φ(s') − Φ(s)     con   Φ(s) = valor esperado de la maquinaria + oro
```

El teorema de esos autores garantiza que **la política óptima no cambia** — el shaping
acelera el aprendizaje sin introducir sesgo. Es la respuesta técnicamente correcta a "la
recompensa es dispersa", y es citable.

### 2.4 Lo que vamos a entrenar

| ID | Agente | Para qué está |
|---|---|---|
| `A0` | `RandomLegal` (provisto) | piso |
| `A1` | `SimpleExpectancy` (provisto) | baseline a superar |
| `A2` | **Q-Learning tabular clásico** (discretización + `SCORE_ALL/HALF` + `γ=0.995`) | la ablación honesta: reproducimos el enfoque estándar para **medir cuánto cuesta cada decisión de modelado** |
| `A3` | **SARSA(λ)** sobre afterstates | on-policy vs off-policy, con trazas |
| `A4` | **Monte Carlo** every-visit sobre afterstates | sin bootstrap, para aislar su efecto |
| `A5` | **TD-Afterstate tabular** ← *candidato al torneo* | la propuesta |
| `A6` | **DQN sobre afterstates** (estado continuo, sin discretizar) | aproximación de función; generaliza entre oros vecinos |
| `ORACLE` | **DP exacta** | techo y oráculo de diagnóstico. **No compite.** |

`A2` no está de relleno. Es lo que convierte el informe en un experimento: entrenando A2 y A5
con el **mismo presupuesto de episodios** y variando una decisión de modelado por vez
(discretización de `SCORE`, `γ`, shaping, afterstates), obtenemos una **tabla de ablaciones**
que atribuye puntos concretos a cada decisión. Eso es lo que separa "entrenamos un agente y
anduvo" de "sabemos por qué anduvo".

### 2.5 Qué entregamos al torneo

**El agente aprendido (`A5` o `A6`, el que gane la evaluación), no el oráculo.**

El enunciado pide un agente entrenado con una técnica vista en clase. La DP se entrega como
**herramienta de análisis y techo de referencia**, explicitado en el informe. Presentarla como
"nuestro agente de RL" sería, además de discutible, desperdiciar la mejor parte del trabajo:
el valor de tener el óptimo es poder **medir la brecha**, no ocultarla.

---

## 3. Protocolo de evaluación

Del caso borde §8 de `01_REGLAS_OCULTAS.md`: **las semillas no son comparables entre agentes**
(el RNG de dados y el de tormentas es el mismo stream, y `size=num_dice` cambia con la política).
No hay *common random numbers* posible sin tocar `env.py`, que está prohibido.

Por lo tanto:

- **n = 20.000 episodios** por agente (no 1.000). Error estándar ≈ 0.7 puntos en vez de 3.2.
- **Intervalo de confianza al 95 %** reportado siempre. Una diferencia de 4 puntos con n=1000
  no es una diferencia.
- **Tres bloques de semillas**: `seed=0` (el del leaderboard público), `seed=10^6` y `seed=10^7`
  (proxies del torneo privado). Si un agente rinde distinto entre bloques, está sobreajustado.
- Reporte de **media, desvío, cuantiles y % del óptimo**. El % del óptimo es la métrica que
  encabeza todas las tablas.

---

## 4. Cronograma

### Fase 0 — Reconocimiento ✅ *hecha*
Leer `env.py`/`config.py` línea por línea, documentar casos borde, correr baselines,
prototipar la DP y obtener el óptimo (643.5).

### Fase 1 — Núcleo (ruta crítica) — hoy
1. `oracle_dp.py` — solver exacto, limpio, con política y valores exportables.
2. `afterstate.py` — representación de afterstate, transiciones deterministas, resolución
   exacta de `SCORE` por máximo prefijo.
3. `train_afterstate.py` — TD-Afterstate tabular (`A5`), `γ = 1`, shaping potencial,
   exploración por inicialización optimista + ε decreciente.
4. `evaluate.py` — protocolo de §3, con intervalos de confianza.
5. **Puerta de control:** `A5` ≥ 600 (93 % del óptimo). Si no llega, diagnosticar con el
   oráculo (arrepentimiento por turno) antes de tocar hiperparámetros a ciegas.

### Fase 2 — Ablaciones y agentes de contraste — hoy/mañana temprano
`A2` (tabular clásico), `A3` (SARSA(λ)), `A4` (MC), `A6` (DQN). Tabla de ablaciones que
atribuye puntos a cada decisión de modelado. Gráficos: curvas de aprendizaje, mapa de
arrepentimiento por turno, política óptima vs aprendida.

### Fase 3 — Informe — mañana
3 páginas, castellano, tono Feynman (§5). Estructura fijada por el enunciado: estado, acciones,
recompensa, algoritmo, hiperparámetros, resultados, comparación contra baselines, qué anduvo
mejor y peor. Más: casos borde, trabajo futuro, y qué aprendimos.

### Fase 4 — Empaquetado y entrega — mañana
ZIP con `env.py`/`config.py` **intactos**, `agents.py` con el agente entrenado, todo el código
de entrenamiento, los pesos, y el informe en PDF. Verificación final: `evaluate_agents.py`
corre nuestro agente sin intervención manual, desde cero, en una carpeta limpia.

### Fase 5 — Juego web — después de la entrega
Ver §6.

---

## 5. El informe: el estándar Feynman

Restricción dura: **3 páginas**. Esto es una ventaja, no un problema. Obliga a que cada
oración cargue peso.

**Regla de escritura:** tiene que funcionar para dos lectores a la vez.

- Un pibe de 13 años sin contexto **entiende cómo funciona y por qué es interesante**.
- Un profesional con 20 años de experiencia **no encuentra nada impreciso ni hueco**.

No son dos objetivos en tensión. Es lo mismo: la precisión sin jerga.

**Cómo se logra, en concreto:**

| Hacer | No hacer |
|---|---|
| "El oro es plata arriba de la mesa; los puntos son plata en el banco. El ladrón pasa después de tu movida." | "Se observa una asimetría temporal en la aplicación del operador estocástico de penalización." |
| "Con 400 de oro tenés 404 acciones legales." | "El espacio de acciones presenta alta cardinalidad." |
| Números concretos: 643.5, 54 %, ±6.3 | "resultados prometedores", "mejoras significativas" |
| Decir en qué nos equivocamos primero y qué lo arregló | Presentar el resultado final como si hubiera salido derecho |
| Voz activa, oraciones cortas, primera persona del plural | Voz pasiva impersonal, subordinadas de cinco líneas |

**Anti-patrones de texto generado por IA, prohibidos explícitamente:**
"es importante destacar", "cabe mencionar", "en el mundo de", "no solo… sino que también",
listas de tres adjetivos, párrafos que abren repitiendo el título de la sección, conclusiones
que resumen lo que se acaba de decir sin agregar nada, y entusiasmo genérico sin números atrás.

**Prueba de fuego antes de entregar:** tapar todos los números del informe. Si el texto sigue
sonando bien, está mal escrito — significa que las afirmaciones no dependían de la evidencia.

**Secciones extra pedidas** (dentro de las 3 páginas, comprimidas):
- **Casos borde del ambiente** — el orden tormenta/acción, la evaporación del oro en el turno 30,
  `STORE_BEST_DIE` como duplicador, `SCORE` como acción continua, y la no comparabilidad de
  semillas. Con la consecuencia estratégica de cada uno, no como lista de curiosidades.
- **Qué sigue** — DQN con red de política, MCTS con el modelo conocido, análisis de sensibilidad
  a `STORM_PROB` (¿la política óptima cambia de forma o solo de escala?), y qué pasaría si el
  torneo cambiara el horizonte.
- **Qué aprendimos** — la parte honesta. Que resolver el juego exacto *primero* cambió todo lo
  demás. Que el techo lo puso la representación, no el algoritmo. Y qué intentamos que no funcionó.

---

## 6. El juego web

### 6.1 Stack
Next.js (App Router) + TypeScript + Tailwind, deploy en Vercel. Sin login.
Leaderboard en Supabase (tabla única, insert público con RLS, lectura pública).
**Fallback obligatorio:** si no hay variables de entorno de base, el leaderboard usa
`localStorage` y el juego funciona igual. Debe poder deployarse y jugarse sin configurar nada.

### 6.2 Los oponentes corren en el cliente
Los tres agentes se **destilan** a redes chicas (MLP de 2 capas, ~5 mil parámetros, ~20 KB
cada una) que aproximan su función de valor, y se ejecutan con un forward pass escrito a mano
en TypeScript. Sin dependencias, sin latencia, sin costo. La destilación de políticas
(Rusu et al., 2016) es además material citable para el informe.

### 6.3 El oráculo corre en el servidor
La tabla de valores exacta es demasiado grande para mandarla al navegador. Pero solo se
necesita **después** de la partida, para el análisis. Entonces: el cliente manda las 30
decisiones a una API route de Vercel, y recibe el desglose completo. Payload chico, exacto,
y el binario del oráculo nunca cruza la red.

### 6.4 Habilidad vs. suerte — la métrica principal
Para cada decisión `t` del jugador, con el oráculo exacto:

```
arrepentimiento_t  =  V*(estado antes)  −  [ puntos inmediatos  +  V*(estado después) ]
```

Es siempre ≥ 0, y vale 0 exactamente cuando jugaste óptimo. De ahí:

```
Calidad de decisiones  =  100 · (1 − Σ arrepentimiento_t / 643.5)      ["% de óptimo"]
Suerte                 =  puntaje real  −  ( 643.5 − Σ arrepentimiento_t )
```

La primera es lo que hiciste. La segunda es lo que te pasó. Suman tu puntaje final, exacto.
Es el mismo principio que el "EV-adjusted winnings" de los solvers de póker, y responde
directamente a "me fue bien pero, ¿fue mérito o fue suerte?".

**El leaderboard tiene dos rankings:** puntaje crudo (con suerte) y calidad de decisiones (sin
suerte). El segundo es el interesante, y el que hace que el juego enseñe algo.

### 6.5 El botón "?"
Sin llamadas a API. Plantillas parametrizadas con los números que el agente **realmente**
calculó en ese estado:

> **Compré un dado.** Costó 42 de oro. Quedan 18 turnos. Un dado más produce en promedio
> 3.5 + 2 = 5.5 de oro por turno, o sea ~99 de oro hasta el final. Se paga solo en 8 turnos y
> quedan 18. La alternativa era puntuar esos 42 ahora: 42 puntos seguros contra ~99 esperados.
> *(Mi valuación: comprar 187.3 vs. puntuar 164.8.)*

Los números salen de la función de valor del agente, no de una descripción escrita a mano.
Cuando el agente cambia de opinión, la explicación cambia sola.

### 6.6 Multi-agente en paralelo
Modo "vos + 3 modelos", tableros lado a lado, turno a turno.
**Decisión de equidad:** las tormentas se sortean de un stream compartido (mismos turnos de
tormenta para todos, para que la comparación sea justa), y los dados de streams
independientes por jugador (obligatorio: cada jugador tiene distinta cantidad de dados).
Esto es exactamente el problema de *common random numbers* de §3, resuelto acá porque el
juego web sí puede controlar su propio RNG. Se documenta en el informe como contraste.

---

## 7. Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| El TD-Afterstate no llega al 93 % del óptimo | Diagnóstico con el oráculo (arrepentimiento por turno y por estado) en vez de barrido a ciegas de hiperparámetros. Sabemos exactamente dónde se equivoca. |
| Falta de tiempo para el bloque web | El bloque A se cierra primero, completo. El web es post-entrega y no comparte ruta crítica. |
| El informe se pasa de 3 páginas | Se escribe **último**, con todos los números ya fijos, y con presupuesto de palabras por sección definido de antemano. |
| Sobreajuste a `seed=0` | Tres bloques de semillas, y ninguna decisión se toma mirando `seed=0` sola. |
| El profesor no puede correr la entrega | Prueba final en carpeta limpia, sin red, con `evaluate_agents.py` tal cual lo entrega la cátedra. |

---

## 8. Estructura de archivos

```
TP_RL_2026/
├── docs/
│   ├── 00_PLAN.md                  ← este archivo
│   ├── 01_REGLAS_OCULTAS.md        ← casos borde y análisis del ambiente
│   ├── 02_RESULTADOS.md            ← todos los números, generado por la evaluación
│   └── 03_BITACORA.md              ← qué probamos, qué falló, qué lo arregló
│
├── gold_dice_rl/                   ← paquete de entrega (lo que va al ZIP)
│   ├── config.py                   ← PROVISTO — no se toca
│   ├── env.py                      ← PROVISTO — no se toca
│   ├── renderer.py                 ← PROVISTO
│   ├── run_example.py              ← PROVISTO
│   ├── evaluate_agents.py          ← PROVISTO
│   ├── agents.py                   ← + nuestros agentes
│   ├── afterstate.py               ← representación y transiciones
│   ├── oracle_dp.py                ← solver exacto
│   ├── shaping.py                  ← potencial para reward shaping
│   ├── train_afterstate.py         ← A5
│   ├── train_tabular_classic.py    ← A2 (ablación)
│   ├── train_sarsa_lambda.py       ← A3
│   ├── train_mc.py                 ← A4
│   ├── train_dqn.py                ← A6
│   ├── evaluate.py                 ← protocolo con intervalos de confianza
│   ├── ablations.py                ← tabla de ablaciones
│   ├── figures.py                  ← gráficos del informe
│   └── artifacts/                  ← pesos, tablas, resultados
│
├── informe/
│   ├── informe.md
│   ├── informe.tex
│   └── informe.pdf                 ← lo que se entrega
│
└── web/                            ← Next.js, deploy a Vercel (bloque B)
```

---

## 9. Criterios de "terminado"

### Bloque A — el TP

- [x] Agente entregado: **527.06**, el **82.0 %** del óptimo teórico (642.45), contra 343.40 del
      mejor baseline provisto. No llegó al 93 % que nos habíamos puesto: la brecha está
      diagnosticada, cuantificada y explicada en el informe, incluida una predicción nuestra que
      resultó falsa.
- [x] Sin sobreajuste: 527.06 / 526.27 / 525.42 en las tres bandas de semillas, diferencias
      dentro del ruido.
- [x] Tabla de ablaciones con un número de puntos por cada decisión de modelado.
- [x] Informe de 3 páginas + apéndice técnico de 8, los dos en PDF.
- [x] `env.py` y `config.py` idénticos al original, verificado con `filecmp` en `package.py`.
- [x] La entrega corre en carpeta limpia con `evaluate_agents.py` tal cual, sin intervención
      manual. `python package.py` lo prueba antes de armar el ZIP.
- [x] Cada número del informe sale de `results.py`; ninguno se escribió a mano.

### Bloque B — el juego web

- [x] Jugar solo, contra el Campeón, o contra los tres agentes a la vez.
- [x] Botón "?" con la explicación de cada jugada, armada con los números que el agente calculó.
      Sin llamadas a ninguna API.
- [x] La jugada del Campeón marcada en tu tablero y comparada con la tuya, turno a turno.
- [x] Descomposición habilidad / suerte con el oráculo exacto, y las tres jugadas más caras.
- [x] Leaderboard sin login, con doble ranking. Supabase si hay variables de entorno,
      `localStorage` si no: se deploya sin configurar nada.
- [x] Equidad real entre jugadores: **mismos dados y mismas tormentas** para todos, algo que
      `env.py` no puede dar (§3).
- [x] Motor verificado contra `env.py`: 60 partidas, 14.460 comparaciones, 0 discrepancias.
- [x] Políticas verificadas contra los agentes de Python en 6.600 estados: Campeón y Novato
      6600/6600, Aprendiz 6595/6600 (las 5 son empates por debajo de 0.016 puntos).
- [x] Reescrito en HTML/CSS/JS sueltos: se abre con doble clic, sin instalar nada.
- [x] La jugada buena **no** se marca antes de elegir; la pista existe pero descuenta.
- [x] Interfaz verificada sin navegador, jugando dos partidas con un DOM simulado.
- [ ] Publicarlo — queda del lado del usuario. `juego/LEEME.md` tiene los pasos.

### Lo que quedó afuera, y por qué

- **SARSA(λ) y Monte Carlo como agentes separados** (`A3`, `A4` de §2.4). Las trazas de
  elegibilidad se implementaron y se probaron con λ = 0.3, 0.5 y 0.9: todas empeoraron, así que
  el resultado está en el informe como resultado negativo en vez de como agente aparte.
- **DQN** (`A6`). La brecha que falta no es de capacidad de la función de valor sino de qué
  estados se visitan (§6 del informe), así que una red no la habría cerrado. Queda anotado como
  trabajo futuro, con el motivo.
