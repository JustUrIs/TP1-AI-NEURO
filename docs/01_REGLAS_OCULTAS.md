# Gold Dice RL — las reglas que el enunciado no cuenta

> Este documento sale de leer `env.py` y `config.py` línea por línea, no de leer el PDF.
> El enunciado describe el juego. El código **es** el juego. Cuando difieren, gana el código.
>
> Todo lo que está acá está verificado contra el código fuente y, donde correspondía, contra
> el solver exacto (`oracle_dp.py`). Nada es una intuición.

---

## 0. El resumen en una frase

El juego parece "tirar dados y decidir en qué gastar". En realidad es un problema de
**control óptimo estocástico con horizonte finito, una sola acción por turno y un activo
riesgoso**. Y —esto es lo importante— es **lo bastante chico como para resolverlo exacto**.
Sabemos cuál es la respuesta perfecta: **642.45 puntos esperados**. Todo el trabajo práctico
se mide contra ese número.

Para referencia inmediata:

| Agente | Puntaje medio (20.000 partidas, banda desarrollo) | % del óptimo |
|---|---:|---:|
| Óptimo teórico (programación dinámica exacta) | **642.45** | 100 % |
| `SimpleExpectancy` (baseline provisto por la cátedra) | 343.4 | 53 % |
| `RandomLegal` (baseline provisto) | 63.0 | 10 % |

El baseline "bueno" de la cátedra deja **casi la mitad de los puntos sobre la mesa**. Eso no
es un detalle: es el espacio entero donde vive este trabajo práctico.

---

## 1. El orden de operaciones dentro de un turno

Esto es lo primero que hay que fijar, porque de acá salen la mitad de los casos borde.

Leyendo `env.step()` → `_apply_action()` → `_apply_storm()` → `_advance_turn()` →
`_roll_for_current_turn()`, la secuencia real es:

```
TURNO t
  1. TIRADA      gold += roll_sum + stored_value ;  stored_value = 0
  2. OBSERVACIÓN el agente ve el estado (el oro de la tirada YA está sumado)
  3. ACCIÓN      exactamente UNA acción
  4. TORMENTA    con p = 0.15
  5. t := t + 1  ; si t > 30 → fin (y NO se vuelve a tirar)
```

Escrito así, tres cosas saltan a la vista. Ninguna de las tres está en el PDF.

---

## 2. Caso borde #1 — La tormenta llega **después** de tu acción

`_apply_action` corre antes que `_apply_storm`. Siempre.

**Consecuencia:** los puntos son inmunes. La tormenta solo puede tocar el **oro que decidiste
no puntuar**. Si en un turno puntuás todo tu oro, la tormenta de ese turno te pega a un
cofre vacío y no te hace absolutamente nada.

> **La analogía:** el oro es plata en efectivo arriba de la mesa; los puntos son plata en el
> banco. El ladrón pasa una vez por turno, después de que vos hiciste tu movida. Si depositaste,
> no encuentra nada.

Esto reordena por completo la lógica del escudo. El escudo **no** te protege del riesgo del
juego: te protege del riesgo de una decisión que ya tomaste voluntariamente (guardar oro).
Un agente que compra escudos "por las dudas" mientras puntúa todo cada turno está quemando
5 de oro por nada.

**Corolario duro:** `SCORE` no es solo la forma de ganar puntos. Es el instrumento de
cobertura de riesgo del juego. Es la única acción que convierte un activo volátil en uno
seguro, y lo hace a paridad 1:1 sin comisión.

---

## 3. Caso borde #2 — El turno 30 no tiene tirada después

En `_advance_turn`:

```python
self.turn += 1
if self.turn > HORIZON:
    self.done = True
    return self.get_obs(), reward, True, info      # ← sale ANTES de _roll_for_current_turn()
self._roll_for_current_turn()
```

**Consecuencia:** todo el oro que sobreviva al turno 30 sin haber sido puntuado **se pierde**.
No se convierte, no se arrastra, no vale nada.

Y por lo tanto, en el turno 30:

- `BUY_DICE` → tirás entre 18 y 90 de oro a la basura. El dado nunca se tira.
- `UPGRADE` → lo mismo.
- `BUY_SHIELD` → comprás protección para un cofre que ya no importa.
- `STORE_BEST_DIE` → pagás 4 por un valor que se cobraría en el turno 31, que no existe.
- `PASS` → perdés todo el oro.
- `SCORE(gold)` → **única jugada no dominada.**

El solver exacto lo confirma sin que se lo digamos: `V*(t=30, gold=g, ...) = g` exactamente,
para todo `n`, `b`, `s`. La estructura del último turno no se aprende: se deduce, y conviene
codificarla.

*Nota práctica:* `SimpleExpectancy` acierta este caso (`if turns_left == 0: return SCORE, gold`),
pero por la razón equivocada — lo trata como "el final del plan", no como "el oro se evapora".
Un agente tabular que agrupa el turno 30 con el 29 en el mismo bucket de estado pierde ~40
puntos de una y no se entera nunca.

---

## 4. Caso borde #3 — `STORE_BEST_DIE` **clona** un dado, no lo guarda

Este es el más contraintuitivo, y el que más gente lee mal.

El nombre sugiere "aparto este dado para usarlo después". Lo que el código hace es otra cosa.
En `_roll_for_current_turn`, la suma completa de la tirada —incluido el dado más alto— **ya
se sumó al oro**:

```python
self.gold += self.roll_sum + self.stored_value
```

Después, `STORE_BEST_DIE` solo hace:

```python
self.gold -= STORE_DIE_COST      # -4
self.stored_value = self.roll_max
```

Y `roll_max` vuelve a entrar al oro en la tirada siguiente. O sea: **cobraste ese dado dos
veces**. No es un traslado, es una fotocopia.

**Economía de la jugada:** pagás 4, cobrás `roll_max` el turno siguiente. Como `roll_max`
incluye el bonus (`current_roll = raw + dice_bonus`), con `bonus = 3` y 4 dados el valor
esperado del máximo ronda 8.2, o sea **+4.2 de oro neto por 4 de costo**. Con el motor
desarrollado es una de las acciones más rentables del juego, y es la que casi nadie usa.

**Pero** consume tu única acción del turno. El costo de oportunidad no es "lo que hubieras
puntuado" (ver §5: eso es falso), sino la tormenta esperada sobre el oro que dejás expuesto:
`0.075 x oro`. Con poco oro, o detrás de un escudo, `STORE_BEST_DIE` es casi gratis y rinde.
Con 400 de oro sin escudo cuesta ~30 puntos y no vale la pena.

Por eso el juego óptimo la usa muchísimo (§8-bis): **es la acción dominante en los turnos
1-13, cuando el oro es chico, y otra vez en los turnos 24-29, cuando ya hay un escudo puesto.**

---

## 5. Caso borde #4 — Una sola acción por turno (y qué cuesta de verdad)

`step()` toma una acción. Una. No podés puntuar y comprar en el mismo turno.

La lectura tentadora es: "entonces gastar un turno cuesta lo que hubieras puntuado".
**Es falsa**, y el solver lo dice sin ambigüedad. No puntuar no destruye el oro: sigue ahí
el turno siguiente, y un solo `SCORE` convierte *todo* tu oro de una. Lo único que perdés
por no puntuar es la exposición a **una** tormenta.

Medido con el oráculo — `V*(puntuar todo)` contra `V*(pasar)` en el mismo estado:

| turno | oro | escudos | V\*(SCORE) | V\*(PASS) | **costo del turno** | |
|---:|---:|---:|---:|---:|---:|---|
| 27 | 300 | 0 | 437.71 | 414.95 | **22.76** | = 7.59 % del oro |
| 27 | 300 | **1** | 444.15 | 444.11 | **0.04** | el escudo lo anula |
| 20 | 150 | 0 | 516.62 | 493.69 | **22.93** | |
| 10 | 60 | 0 | 900.55 | 900.55 | **0.00** | |
| 3 | 20 | 0 | 759.51 | 759.51 | **0.00** | |

`0.15 × 300/2 = 22.5`. La medición da 22.76. **El costo de gastar un turno es exactamente
la tormenta esperada sobre el oro que dejás expuesto: 7.5 % de ese oro, y nada más.**

Y la segunda fila es la que importa: **con un escudo el costo cae a 0.04.** Para eso sirve el
escudo. No te protege del juego: te compra el derecho a usar tus turnos en algo que no sea cobrar.

### Dónde sí aparece la escasez de acciones

En el valor marginal del oro — cuántos puntos vale una moneda:

```
 turno       10       30       60      120      250      ← oro
     2   13.898   11.693    4.330    0.955    0.368
     6   10.323   10.294    4.082    0.947    0.368
    14    5.022    1.080    1.422    0.811    0.977
    22    1.648    0.989    1.001    1.000    1.000
    30    1.000    1.000    1.000    1.000    1.000
```

- **Turno 2, 10 de oro: una moneda vale 13.9 puntos.** Desbloquea la primera mejora (cuesta 8),
  y esa mejora rinde durante 28 turnos.
- **Turno 2, 250 de oro: una moneda vale 0.37 puntos.** Vale *menos* que un punto.

Ese segundo número es la escasez de acciones. Con 250 de oro en el turno 2 tenés **más plata
que turnos para gastarla**: solo podés hacer una compra por turno, y el sobrante no hace nada
más que juntar riesgo de tormenta. El cuello de botella no es "el turno vale lo que puntuarías",
es **"no podés convertir oro en maquinaria más rápido que una compra por turno"**.

## 6. Caso borde #5 — `SCORE` no es una acción, son 401 (y por qué eso igual no importa)

`get_action_mask()` marca `SCORE` como siempre válida, con este comentario en el código:

```python
# SCORE is valid because score_amount=0 is always legal.
```

Dos hechos:

**(a) `PASS` es redundante.** `SCORE(0)` hace exactamente lo mismo.

**(b) El espacio de acciones real es paramétrico.** `get_valid_score_amounts()` devuelve
literalmente `range(gold + 1)`: con 400 de oro hay **404 acciones legales**.

### La hipótesis obvia, y por qué es falsa

La conclusión tentadora es: "un agente tabular que discretiza `SCORE` en `{TODO, MITAD}` tira
el problema a la basura". Lo medimos re-resolviendo el juego entero con el espacio de `SCORE`
mutilado a propósito:

| Espacio de `SCORE` permitido | Valor óptimo | Costo |
|---|---:|---:|
| `k` libre en `[0, oro]` (401 acciones) | 642.45 | — |
| Solo `SCORE(oro)` — **una sola acción** | **642.45** | **0.00** |
| Solo `SCORE(oro)` o `SCORE(oro//2)` | 642.45 | 0.00 |
| Solo `SCORE(oro//2)` *(control negativo)* | 641.33 | 1.12 |

**Reducir `SCORE` de 401 acciones a una sola no cuesta nada.** El control negativo confirma que
la medición no es un artefacto: cuando sacamos la opción de puntuar todo, el valor sí cae.

### Por qué no importa

Porque el juego óptimo **puntúa una sola vez, en el turno 30, y puntúa todo** (ver §9). Los
estados donde puntuar parcial ayuda existen —a turno 18 con 188 de oro, guardar 30 en vez de
puntuar todo vale 15.36 puntos— pero son estados a los que el juego óptimo **nunca llega**.
Solo se visitan jugando mal.

Es un caso borde real del ambiente y hay que conocerlo. Pero como decisión de modelado
está **medida en cero**, y eso permite reducir el espacio de acciones a **6 acciones discretas
sin perder un solo punto**. Ese es un resultado útil: no porque revele una trampa, sino
porque descarta una.

> Anotarlo importa por método: la intuición decía que ésta era *la* decisión de modelado cara.
> El solver dice que vale 0.00. Cuando se puede medir, no se opina.

## 7. Caso borde #6 — La tormenta usa división entera

```python
self.gold = self.gold // 2
```

- Con oro impar te quedás con el redondeo hacia arriba en la práctica (39 → 19, perdés 20).
- Con oro = 1 → 0.
- **Con oro = 0 la tormenta es gratis.** No hay penalización fija, no hay pérdida de puntos,
  no pasa nada.

Combinado con §2: **si tu oro es 0, comprar un escudo es tirar 5 monedas.** El escudo solo
vale por el oro que efectivamente vas a tener expuesto en el momento en que caiga la próxima
tormenta.

**Cuándo conviene un escudo (cuenta rápida).** Cuesta 5. La tormenta pega con p = 0.15 y te
saca `gold/2`. Como pérdida esperada de un solo turno, conviene si `0.15 · gold/2 > 5`, o sea
`gold > 67`. Pero el escudo **no vence**: sigue ahí hasta que una tormenta lo consuma. Sobre
`T` turnos restantes la probabilidad de que se use es `1 − 0.85^T` (99 % con 28 turnos por
delante), y lo que bloquea es la mitad del oro *en el momento de la tormenta*, no el de hoy.
El umbral real es bastante más bajo que 67 y depende del horizonte. Es exactamente el tipo de
cuenta que una fórmula cerrada hace mal y una tabla de valores hace bien.

---

## 8. Caso borde #7 — Las semillas **no** son comparables entre agentes

Este es el caso borde metodológico, y es el que más caro sale si se ignora.

`env.rng` es **un solo generador** que sirve dos cosas distintas:

```python
self.raw_roll = self.rng.choice(DICE_FACES, size=self.num_dice, ...)   # consume ~num_dice draws
...
if self.rng.random() >= STORM_PROB: return                             # consume 1 draw
```

`size=self.num_dice` **cambia con la política**. Un agente que compró 5 dados consume 5 draws
por turno; uno que se quedó con 1 consume 1. A partir del primer turno en que dos agentes
difieren en cantidad de dados, **sus flujos de aleatoriedad se desincronizan por completo**.

**Consecuencia:** correr dos agentes con `seed=0` **no** les da las mismas tiradas ni las
mismas tormentas. La técnica estándar de *common random numbers* —comparar políticas sobre
el mismo azar para cancelar varianza— **no está disponible acá**. No hay forma de conseguirla
sin tocar `env.py`, que el enunciado prohíbe.

**Qué implica en números.** Con `n_episodes = 1000` y una desviación estándar típica de ~100
puntos, el error estándar de la media es `100/√1000 ≈ 3.2` puntos. El intervalo de confianza
al 95 % es de **±6.3 puntos**. Entonces:

- Una diferencia de 4 puntos entre dos agentes en el leaderboard **no es una diferencia**.
- Con desvíos altos (una política agresiva puede tener σ ≈ 150) el intervalo se abre a ±9.
- El torneo final usa **semillas privadas**: cualquier ajuste fino contra `seed=0` es sobreajuste
  a ruido.

Por eso todo resultado que reportemos va con `n = 20.000` episodios e intervalo de confianza,
no con `n = 1000` y un número pelado. No es prolijidad: es la diferencia entre medir y adivinar.

---

## 8-bis. Qué hace realmente el juego óptimo (400 partidas del oráculo)

Todo lo anterior son piezas sueltas. Así se arman:

```
turno       oro      dados    bonus   escudos   acción dominante
  1-13     4 -> 30   1 -> 3.1  0 -> 2.3   0.00   STORE_BEST_DIE   (36-51 %)
 14-22    34 -> 81  3.5 -> 7.2 2.6 -> 5.4 0.00   BUY_DICE         (36-68 %)
    23       101      7.5      6.1      0.26     BUY_SHIELD       (61 %)
 24-29   155 -> 459   7.5      6.1      ~0.80    STORE_BEST_DIE   (75-86 %)
    30       463      7.5      6.1      0.58     SCORE            (100 %)
```

Leído como estrategia:

1. **Turnos 1-13 - construir barato.** Casi no hay oro. `STORE_BEST_DIE` cuesta 4 y devuelve
   `roll_max`; con poco oro expuesto la tormenta no duele. Se acumulan mejoras (baratas al
   principio: 8, 16, 24) más que dados.
2. **Turnos 14-22 - construir caro.** Ya entra oro suficiente para dados (42, 50, 58...). El
   motor llega a ~7.5 dados y bonus ~6, o sea ~72 de oro por turno.
3. **Turno 23 - levantar el muro.** Un escudo. Uno solo.
4. **Turnos 24-29 - acumular detrás del muro.** El oro sube de 155 a 459 **sin puntuar**. Con
   escudo, no puntuar cuesta 0.04 puntos por turno (§5), así que la acción libre se usa en
   `STORE_BEST_DIE` para seguir sumando.
5. **Turno 30 - cobrar.** Un único `SCORE` de ~463 de oro.

**El juego óptimo casi no puntúa hasta el último turno.** De ahí sale, retroactivamente, por
qué la granularidad de `SCORE` no importa (§6): se usa una vez, y se usa entera.

**Por qué un solo escudo y no cinco:** un escudo bloquea *una* tormenta. Entre el turno 23 y
el 30 hay 7 tormentas potenciales a p=0.15, o sea ~1.05 esperadas. Comprar exactamente uno
-y recomprarlo cuando se consume, que es por qué el promedio de escudos baja de 0.86 a 0.58-
es la cobertura justa. Ni de más ni de menos.

### El costo de no poder ver ese endgame

Esta trayectoria dice exactamente qué tiene que representar el estado:

| Variable | Rango que visita el juego óptimo |
|---|---|
| `num_dice` | hasta **9** (mediana 8 al final) |
| `dice_bonus` | hasta **8** (mediana 6) |
| `gold` | hasta **797** |
| `shields` | 0 ó 1, casi nunca más |

Una discretización que capee `num_dice` en 5, `dice_bonus` en 4 y el oro en 240 -una elección
que parece razonable *antes* de mirar la trayectoria- colapsa todo el endgame en una sola
celda de la tabla:

- **38.0 %** de las decisiones óptimas ocurren con `num_dice > 5`
- **35.7 %** ocurren con `dice_bonus > 4`
- el oro llega a 797, más de 3x el tope

Un agente con esos topes **no puede distinguir el turno 24 con 160 de oro del turno 29 con
500**, y ahí se decide el 70 % del puntaje. No aprende mal: no puede ver. Ninguna cantidad de
episodios lo arregla.

---

## 9. La consecuencia constructiva: el juego se puede resolver exacto

Los casos borde anteriores no son curiosidades. Juntos dicen que este MDP es **chico**.

**Observación clave — los puntos no son parte del estado.** `points` no aparece en ninguna
transición: no afecta la tirada, ni los costos, ni la tormenta. Solo se acumula. Entonces el
retorno es separable y la función de valor **no depende de los puntos**:

```
V_t(gold, num_dice, dice_bonus, shields)   ← cuatro variables, no nueve
```

Esto saca `points` (no acotado) del estado de un plumazo. Y `stored_value` se puede plegar en
la transición (entra como un corrimiento aditivo sobre el oro del turno siguiente), y
`roll_sum` ya está adentro de `gold` en el momento de decidir. De nueve variables observadas
quedan **cuatro que importan, más el `roll_max` del turno, que solo afecta a una acción**.

**El truco que hace tratable a `SCORE`.** Con `f(m)` = valor de terminar el turno con `m` de oro:

```
max_{0 ≤ k ≤ g} [ k + f(g − k) ]  =  g + max_{m ≤ g} [ f(m) − m ]
```

El término de la derecha es un **máximo prefijo**: se calcula una vez por estado, en O(oro),
y sirve para todos los valores de `g` a la vez. La acción "continua" deja de ser un problema.

**Resultado.** Inducción hacia atrás sobre `t = 30 … 1`, con la distribución conjunta exacta
de `(suma, máximo)` de `n` dados (calculada por convolución, no por muestreo):

```
V*(t=1, gold=0, dados=1, bonus=0, escudos=0)  =  643.46 puntos
```

Verificado con topes `n ≤ 12`, `bonus ≤ 12`, `escudos ≤ 8`, `oro ≤ 1400`. Con topes más
chicos (`9/9/5/700`) da 642.45 — una diferencia de 0.16 %, o sea los topes prácticamente no
muerden y el número es sólido.

**Para qué sirve tener el óptimo.** No para entregarlo (el enunciado pide un agente
*aprendido*). Sirve para tres cosas que sin él son imposibles:

1. **Un denominador honesto.** "Nuestro agente saca 610" no dice nada. "Nuestro agente
   captura el 95 % del óptimo teórico, contra el 54 % del baseline de la cátedra" dice todo.
2. **Diagnóstico por decisión.** Para cada jugada del agente aprendido podemos calcular el
   *arrepentimiento* exacto: `V*(s) − [r + V*(s′)]`. Eso nos dice **en qué turnos y en qué
   estados** el agente se equivoca, en vez de solo cuánto. Es la diferencia entre "el modelo
   anda mal" y "el modelo sub-invierte en bonus entre los turnos 5 y 9".
3. **Separar habilidad de suerte** (en el juego web): la diferencia entre lo que valía tu
   partida y lo que sacaste es, exactamente, suerte.

---

## 10. Casos borde menores (verificados, sin impacto estratégico)

| # | Observación en el código | Impacto |
|---|---|---|
| 10.1 | `stored_value` se **sobrescribe** (`= self.roll_max`), no se acumula. Como se consume en cada tirada, no se puede apilar de todas formas. | Ninguno. |
| 10.2 | El oro guardado se suma **al inicio** del turno siguiente, o sea queda expuesto a la tormenta de ese turno. | Chico; el solver lo tiene en cuenta. |
| 10.3 | `__init__` llama `default_rng(seed)` y después `reset(seed)`, que lo vuelve a llamar. Doble inicialización inofensiva. | Ninguno. |
| 10.4 | `roll_max` incluye el bonus; `raw_roll` no. `current_roll = raw + dice_bonus`. | Sube el valor de `STORE_BEST_DIE` con bonus alto. |
| 10.5 | Turno 1: 1 dado, bonus 0 → oro ∈ {1..6}. Todo cuesta ≥ 4, así que la única jugada posible además de `SCORE`/`PASS` es `STORE_BEST_DIE`, y solo si salió 4, 5 o 6. | Micro-decisión de apertura real. |
| 10.6 | No hay tope de dados, mejoras ni escudos, pero los costos crecen linealmente (`+8` cada uno) mientras el retorno por dado es constante (`3.5 + bonus`). | El tope es económico, no reglamentario. Aparece solo. |
| 10.7 | El horizonte es **fijo y conocido** (30 turnos), no hay terminación estocástica. | Justifica `γ = 1`. Ver §11. |

---

## 11. Un caso borde que no está en el ambiente sino en cómo se lo modela: `γ`

El retorno real del problema es la suma **sin descontar** de los puntos: `G = Σ r_t`. El
episodio termina siempre en 30 pasos, así que no hay ningún problema de convergencia que
justifique descontar.

Usar `γ = 0.995` —un valor que parece inocente— multiplica el pago del turno 30 por
`0.995²⁹ ≈ 0.865`. Es decir: **le decís al agente que los puntos del final valen 13.5 % menos
que los del principio**, en un juego cuyo único momento de cobro grande es el final. El
descuento sesga sistemáticamente en contra de la estrategia correcta (invertir temprano,
cobrar tarde) y es una de esas decisiones que se copian de un tutorial sin pensarlas.

**En este problema `γ = 1` es lo correcto y hay que decir por qué:** horizonte finito, fijo,
conocido, y episodio garantizado a terminar. El descuento acá no es un regularizador, es un
sesgo.

---

## 12. Checklist: qué tiene que respetar cualquier agente que hagamos

De todo lo anterior, las condiciones que un agente debe cumplir para no estar roto de entrada:

- [ ] En `t = 30` hace `SCORE(gold)`. Siempre. Sin excepción, sin aprenderlo.
- [ ] Representa `num_dice` hasta 9, `dice_bonus` hasta 8 y oro hasta ~800 **sin saturar**.
- [ ] Entrena con `γ = 1`.
- [ ] No compra escudos cuando el oro expuesto no lo justifica.
- [ ] Sabe que `STORE_BEST_DIE` duplica, y compite contra el costo de oportunidad del turno.
- [ ] Se evalúa con `n ≥ 20.000` episodios e intervalo de confianza, nunca con 1000 a secas.
- [ ] Se reporta como fracción del óptimo (642.45), no como número absoluto.
