# Resultados explicados

Este archivo amplía las tablas del informe. Usamos 20.000 partidas por agente porque el puntaje cambia mucho entre semillas. Con 1.000 partidas, una diferencia de unos pocos puntos puede ser azar.

## Resultado principal

| Agente | Media | Intervalo de confianza 95 % | Desvío |
|---|---:|---:|---:|
| DP, referencia de juego | 644,10 | [642,23; 645,97] | 134,9 |
| **GoldDiceAgent** | **527,06** | **[525,17; 528,96]** | 136,7 |
| Sólo la cuenta `Φ`, sin entrenamiento | 490,41 | [488,04; 492,78] | 171,1 |
| Q-Learning clásico, mejor variante | 364,21 | [363,70; 364,72] | 36,8 |
| `SimpleExpectancy` | 343,40 | [341,99; 344,82] | 102,1 |
| `RandomLegal` | 63,03 | [62,50; 63,56] | 38,1 |

La media resume el rendimiento. El intervalo marca una zona razonable para la media verdadera: dos resultados separados por menos que esos márgenes no alcanzan para afirmar que uno mejoró. El desvío mide cuánto varían las partidas individuales.

La DP da 642,45 antes de tirar el primer dado. Al simular su política aparece 644,10; la diferencia de 1,65 entra en el intervalo de la simulación. Nuestro agente obtiene el 82 % de esa referencia y supera por 184 puntos al mejor baseline provisto.

## Tres rangos de semillas

| Rango | Uso | Media del agente |
|---|---|---:|
| desarrollo | tomar decisiones durante el trabajo | 527,06 |
| control | comprobar el resultado al final | 526,27 |
| público | protocolo `seed=0` del enunciado | 525,42 |

Los tres números son compatibles con el mismo rendimiento. Separar las semillas evitó elegir hiperparámetros por casualidad sobre el conjunto que usa la cátedra.

## Qué aportó cada decisión

Comparamos variantes con el mismo presupuesto de 400.000 partidas.

| Cambio | Antes | Después | Diferencia |
|---|---:|---:|---:|
| ampliar los límites de dados, bonus y oro | 292,6 | 354,8 | +62,2 |
| usar sólo `SCORE(todo)` en vez de todo/mitad | 354,8 | 364,2 | +9,4 |
| tabla Q convencional → afterstates + `Φ` + Double Q | 364,2 | 527,1 | +162,9 |
| apagar `Φ` → usar `Φ` | 105,1 | 527,1 | +422,0 |

Los límites chicos eran un problema concreto. La política de la DP llega a 9 dados, bonus 8 y cerca de 800 de oro. Si la representación corta en 5 dados, bonus 4 y 240 de oro, estados muy distintos terminan en la misma casilla.

La cuenta `Φ` explica una parte grande del puntaje. Sin entrenamiento obtiene 490,41 y la tabla aprendida lleva el resultado a 527,06. Por eso no atribuimos los 527 puntos completos a Q-Learning: unos 37 aparecen después de aprender y el resto proviene de una representación útil del estado.

## Dónde falla el agente

Para cada situación calculamos dos números con la DP:

1. el valor de la mejor acción disponible;
2. el valor de la acción que eligió nuestro agente.

La resta entre ambos es la cantidad esperada de **puntos perdidos por esa decisión**. Si el agente elige una acción óptima, la resta vale cero. Es una comparación de decisiones, no una penalización usada durante el entrenamiento.

La mayor pérdida aparece al final. La DP compra un escudo cerca del turno 23, conserva el oro detrás de ese escudo y puntúa en el turno 30. Nuestro agente suele cobrar antes y termina con menos oro acumulado. El escudo sólo resulta útil si después se cambia también la política de ahorro; ε-greedy rara vez descubre ambas decisiones juntas.

## Pruebas que descartamos

| Prueba | Resultado |
|---|---|
| trazas de elegibilidad con λ = 0,3; 0,5; 0,9 | empeoraron el promedio |
| ε inicial entre 0,3 y 0,6 | más exploración no encontró la secuencia del escudo |
| exploración sostenida durante varios turnos | no rompió la política local |
| 1,5 → 5 millones de episodios | no mejoró el resultado |
| grilla de oro más chica | sumó cerca de 3 puntos, lejos de cerrar la brecha |

Estos resultados cambiaron nuestra explicación del error. El agente no necesita repetir más veces los mismos estados; necesita visitar la secuencia completa de comprar un escudo y acumular después.

## Modelos presentes

El modelo que entregamos es Q-Learning tabular con dos tablas y representación por *afterstates*. Durante el desarrollo también probamos trazas de elegibilidad, cercanas a una variante de Q(λ), pero no las conservamos como otro archivo porque rindieron peor. No implementamos SARSA, Monte Carlo ni Deep Q-Learning: la consigna pide al menos una técnica justificada, y Q-Learning cumple ese requisito.
