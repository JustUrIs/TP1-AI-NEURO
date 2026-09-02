# Resultados

> Protocolo: n = 20.000 episodios por agente, intervalo de confianza al 95 %,
> banda de semillas **desarrollo** (base 1.000.000). Todas las decisiones de diseño se
> tomaron mirando esta banda. La banda pública (seed 0, la del enunciado) y la de control
> (2.000.000) se miran una sola vez, al cerrar.
>
> Reproducible con `python results.py desarrollo 20000`.

---

## 1. Tabla principal

| Agente | Media | IC 95 % | % del óptimo | σ |
|---|---:|---|---:|---:|
| **Oráculo** (DP exacta, *no compite*) | 644.10 | [642.23, 645.97] | 100.3 % | 134.9 |
| **GoldDiceAgent** (Double TD sobre afterstates) | **527.06** | [525.16, 528.97] | **82.0 %** | 137.2 |
| Solo potencial Φ (cero aprendizaje) | 490.41 | [488.03, 492.79] | 76.3 % | 171.5 |
| Q clásico — rangos amplios + `SCORE_ALL` | 364.21 | [363.69, 364.73] | 56.7 % | 37.8 |
| Q clásico — rangos amplios, γ=1 | 354.83 | [354.34, 355.32] | 55.2 % | 35.2 |
| Q clásico — rangos amplios, γ=0.995 | 354.60 | — | 55.2 % | — |
| `SimpleExpectancy` (baseline de la cátedra) | 343.40 | [341.96, 344.85] | 53.5 % | 104.2 |
| Q clásico — topes chicos, γ=0.995 | 314.58 | [314.05, 315.11] | 49.0 % | 38.1 |
| Q clásico — topes chicos, γ=1 | 292.63 | [292.04, 293.22] | 45.5 % | 42.6 |
| Double TD **sin** potencial (Φ apagado) | 105.06 | — | 16.4 % | — |
| `RandomLegal` (baseline de la cátedra) | 63.03 | [62.50, 63.57] | 9.8 % | 38.8 |

El agente entregado saca **52 % más** que el mejor baseline provisto y **casi el doble** que un
Q-Learning tabular armado con la receta estándar.

---

## 2. Ablaciones: qué cuesta cada decisión de modelado

Todas con el mismo presupuesto (400.000 episodios), cambiando **una** cosa por vez.

| Cambio | De | A | Δ |
|---|---:|---:|---:|
| Topes de estado: `dados≤5, bonus≤4, oro≤240` → rangos que cubren el juego óptimo | 292.63 | 354.83 | **+62.2** |
| Espacio de `SCORE`: `{TODO, MITAD}` → `{TODO}` | 354.83 | 364.21 | **+9.4** |
| γ = 0.995 → 1, **con rangos amplios** | 354.60 | 354.83 | **+0.2** (nulo) |
| γ = 0.995 → 1, **con topes chicos** | 314.58 | 292.63 | **−21.9** |
| Representación: tabla Q discretizada → afterstates + Φ + Double | 364.21 | 527.06 | **+162.9** |
| Potencial Φ: apagado → encendido | 105.06 | 527.06 | **+422.0** |

### 2.1 Tres resultados que contradicen la intuición

**(a) Mutilar `SCORE` casi no cuesta.** La hipótesis de trabajo inicial era que colapsar una
acción de 401 valores en dos era *el* error caro. Medido sobre el óptimo exacto
(`oracle_dp.solve(score_mode=...)`), el costo es **0.00**: el juego óptimo puntúa una sola vez,
en el turno 30, y puntúa todo. El control negativo confirma que la medición discrimina —
prohibir "puntuar todo" y dejar solo "la mitad" sí cuesta 1.12 puntos.

En un agente subóptimo el efecto es algo mayor (+9.4) porque ese agente sí acumula oro en
estados donde puntuar parcial ayuda. Pero no es la explicación de nada.

**(b) Los topes de estado cuestan 62 puntos.** El juego óptimo llega a 9 dados, bonus 8 y 797
de oro. Con `dados≤5, bonus≤4, oro≤240`, el **38 %** de las decisiones óptimas y todo el
endgame caen en una única celda de la tabla. El agente no aprende mal: no puede ver.

**(c) γ < 1 solo ayuda cuando la representación está rota.** Con rangos amplios, γ=0.995 y γ=1
dan lo mismo (354.60 contra 354.83, indistinguibles). Con topes chicos, **γ=0.995 es 21.9 puntos
mejor que γ=1**.

La explicación es incómoda y vale la pena decirla: con una representación que no distingue el
endgame, la política correcta es imposible de expresar, y una política miope —cobrar temprano—
es lo mejor disponible. El descuento hace al agente miope. O sea que **γ<1 estaba tapando una
falla de representación, no resolviendo un problema de horizonte.** Si uno solo mira el número,
concluye "γ=0.995 funciona mejor" y se lleva la lección exactamente al revés.

---

## 3. De dónde sale el 81.5 %: descomposición

| Componente | Aporte |
|---|---:|
| Potencial Φ solo (representación, cero aprendizaje) | 490.4 |
| + aprendizaje TD sobre afterstates | +36.7 |
| **Total** | **527.1** |

Esta descomposición es incómoda a propósito: **la mayor parte del puntaje viene del diseño de la
representación, no del aprendizaje.** Sin el control "Φ solo" no habría forma de saberlo, y sería
fácil atribuirle al algoritmo un mérito que es del modelado. Reportarlo es parte del trabajo.

Al mismo tiempo, el control inverso muestra que Φ solo tampoco alcanza: apagar Φ y aprender V
directo hunde al agente a 105 puntos. Φ y el aprendizaje se necesitan mutuamente.

---

## 4. Arrepentimiento: dónde se pierden los 119 puntos que faltan

Con el oráculo se puede calcular, para cada decisión, cuánto valor destruyó exactamente:

```
arrepentimiento(o, a) = V*(o) − [ r(o, a) + E V*(s') ]     ≥ 0,  = 0 si la jugada es óptima
```

Perfil del agente entregado (300 partidas, banda desarrollo):

| Bloque de turnos | Arrepentimiento acumulado |
|---|---:|
| 1 – 6 | 52.8 |
| 7 – 13 | 28.6 |
| 14 – 22 | 9.9 |
| 23 – 29 | 26.7 |
| 30 | 0.0 |
| **total** | **118.0** |

Errores más frecuentes:

| Debería | Eligió | Veces |
|---|---|---:|
| `STORE_BEST_DIE` | `PASS` | 1022 |
| `BUY_SHIELD` | `STORE_BEST_DIE` | 895 |
| `BUY_SHIELD` | `SCORE` | 582 |

Y el efecto sobre la partida:

| | dados (t=30) | bonus (t=30) | escudos (t23–29) | oro final |
|---|---:|---:|---:|---:|
| óptimo | 7.61 | 6.17 | **0.73** | **483.6** |
| agente | 6.94 | 5.52 | **0.01** | **183.1** |

---

## 5. Por qué no cierra: dos causas, y ninguna es "faltan episodios"

### 5.1 Un óptimo local de política, no de valores

El agente casi nunca compra el escudo del turno 23, y por eso tampoco acumula. Las dos cosas se
sostienen mutuamente: **el escudo solo rinde si después acumulás, y acumular solo conviene si
tenés escudo.** Salir de ahí exige cambiar dos decisiones a la vez. ε-greedy explora desviaciones
de un paso: prueba el escudo, ve que con su política actual no sirve, y lo descarta.

Se probaron tres esquemas de exploración pensados para este problema. Ninguno rompió el óptimo
local:

| Exploración | Mejor resultado |
|---|---:|
| ε-greedy fijo (ε₀ = 0.15) | **523.5** |
| ε-greedy fijo (ε₀ = 0.30 / 0.50) | 513.2 / 515.9 |
| ε por episodio, log-uniforme (estilo Ape-X) | 520.9 |
| ε-z-greedy, exploración temporalmente extendida (Dabney et al., 2020) | 503.8 |

Es un resultado negativo y se reporta como tal.

### 5.2 El límite es de resolución, no de razonamiento

En el estado típico donde el óptimo compra el escudo (t=23, 104 de oro, 7 dados, bonus 6):

| Acción | V\* (oráculo) | V (agente) | error |
|---|---:|---:|---:|
| `BUY_SHIELD` | 600.00 | 571.06 | −28.94 |
| `STORE_BEST_DIE` | 594.74 | 576.63 | −18.11 |
| `SCORE` | 594.24 | 573.21 | −21.03 |
| `BUY_DICE` | 592.09 | 570.21 | −21.88 |
| `UPGRADE` | 587.84 | 562.89 | −24.95 |
| `PASS` | 586.44 | 568.47 | −17.97 |

**El óptimo separa la mejor acción de la peor por 13.6 puntos sobre un valor de 600: un 2.3 %.**
El error de estimación del agente es de 18 a 29 puntos — más grande que la diferencia entera que
tiene que detectar.

O sea: el agente no razona mal. Su función de valor es correcta al 4 %, y la decisión pide 2 %.

Es un límite estadístico y se puede escribir como tal. Con muestras de desviación tipica σ ≈ 130
puntos, distinguir una diferencia de 13.6 con 95 % de confianza pide del orden de

```
n ≈ (2 · 1.96 · 130 / 13.6)²  ≈  1.400 muestras independientes por par de estados
```

El agente tiene ~180.000 pesos y ~45 millones de actualizaciones: unas **250 por peso**. Falta un
factor de aproximadamente **seis**. Eso da una predicción concreta y falsable: seis veces más
muestras, o seis veces menos pesos, deberían alcanzar para esta decisión en particular. Las dos
corridas que la prueban (5 millones de episodios, y grilla de oro reducida de 173 a 114 nodos)
están documentadas en §6.

---

## 6. Corridas de verificación

La cuenta de §5.2 predice que **seis veces más muestras, o seis veces menos pesos**, deberían
alcanzar. Las dos mitades de la predicción se probaron por separado:

| Corrida | Qué prueba | Resultado |
|---|---|---|
| `dbl_LONG` — 5.000.000 de episodios | más muestras | **falló.** Meseta en 81 % desde los 500 mil episodios, y después baja. Triplicar los episodios no mueve la aguja. |
| `dbl_COARSE` — grilla de 114 nodos en vez de 173 | menos pesos | **parcial.** 527.06 contra 523.92: +3.1 puntos, la dirección correcta pero un orden de magnitud menos de lo predicho. |

### Por qué falló la mitad de las muestras

Porque la cuenta supone muestras **representativas**, y no lo son. Los estados que deciden el
resultado —turno 24, mucho oro, un escudo puesto— se visitan solo cuando la exploración compra el
escudo, y al turno siguiente la política greedy vuelve a no acumular. Triplicar los episodios
triplica unas muestras que nunca contienen la continuación correcta.

O sea que el cuello de botella no es el **tamaño** de la muestra sino su **distribución**. Es el
problema de exploración profunda de §5.1, visto desde el otro lado: no se puede estimar el valor
de una rama que la política de comportamiento nunca recorre hasta el final.

Es un resultado negativo, y es el más útil del trabajo: descarta "entrenar más" como camino y
deja como única salida cambiar *qué* se visita, no *cuántas veces*.

---

## 7. Verificación contra sobreajuste

Todas las decisiones —hiperparámetros, elección de checkpoint, diseño de la representación— se
tomaron mirando **una sola** banda de semillas. El agente final medido en las tres, n = 20.000
cada una:

| Banda | Semilla base | Media | IC 95 % | % del óptimo |
|---|---|---:|---|---:|
| desarrollo — donde se decidió todo | 1.000.000 | 527.06 | [525.16, 528.97] | 82.0 % |
| control — mirada una sola vez, al cerrar | 2.000.000 | 526.27 | [524.38, 528.15] | 81.9 % |
| pública — la del enunciado | 0 | 525.42 | [523.53, 527.31] | 81.8 % |

Diferencia desarrollo − control: **+0.80**, con error estándar de la diferencia 1.37. Está dentro
del ruido, así que no hay evidencia de sobreajuste a la banda de desarrollo.

Recordar que las semillas **no** son comparables entre agentes (`01_REGLAS_OCULTAS.md` §8): el
generador de dados y el de tormentas es el mismo, y `size=num_dice` depende de la política. No
existen números aleatorios comunes en este ambiente, así que la única defensa contra el ruido es
el tamaño de muestra.
