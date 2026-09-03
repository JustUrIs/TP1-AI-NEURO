# El juego

Gold Dice jugable, con los agentes que entrenamos para el TP corriendo adentro
del navegador. Al terminar la partida te dice **cuánto de tu resultado fue
decisión tuya y cuánto fue suerte**, comparándote contra el juego resuelto exacto.

## Abrirlo

Doble clic en `index.html`. No hace falta instalar nada, ni servidor, ni internet.

Para publicarlo (Vercel, Netlify, GitHub Pages), subís esta carpeta y listo: son
cinco archivos estáticos.

## Cómo está armado

| Archivo | Qué hace |
|---|---|
| `index.html` | la pantalla: estilos y la lógica de la interfaz |
| `motor.js` | el juego. Port de `env.py`, verificado turno a turno |
| `agentes.js` | los tres agentes entrenados y el oráculo |
| `explicar.js` | las explicaciones, armadas con los números que el agente calculó |
| `data.js` | los pesos, en base64. Lo genera `gold_dice_rl/export_game.py` |

Son scripts clásicos, no módulos. Es a propósito: los módulos ES están
bloqueados por seguridad cuando abrís un archivo con doble clic, y queríamos que
el juego ande sin servidor.

## Tres decisiones de diseño

**No te marcamos la jugada buena antes de que elijas.** Resaltarla convierte el
juego en apretar el botón iluminado. Elegís a ciegas y recién después te
mostramos qué hizo el Campeón y cuánto costó la diferencia. Ahí está la tensión.

**La pista existe pero cuesta.** Podés preguntarle al Campeón qué haría en tu
lugar, y cada consulta te descuenta 1,5 de la nota de decisiones. La ayuda no es
gratis, así que la usás cuando de verdad no sabés.

**Todos juegan con los mismos dados.** El azar es una función de la semilla, el
turno y el número de dado, no una secuencia: el que tiene 5 dados usa los
primeros 5 valores del turno y el que tiene 3 usa los primeros 3, y las
tormentas caen en los mismos turnos para todos. **La diferencia de puntaje
contra los modelos no tiene nada de suerte adentro.**

Eso es justamente lo que `env.py` no puede dar: ahí un solo generador sirve los
dados y las tormentas, y cuántos dados tirás depende de cómo venís jugando, así
que dos agentes con la misma semilla ven azares distintos.

## Habilidad y suerte

Para cada jugada tuya calculamos cuánto valor destruyó: lo que valía la
situación antes, menos lo que vale después de jugar. Da cero si jugaste óptimo y
nunca da negativo.

```
calidad = 642.45 − (todo lo que perdiste decidiendo)     ← lo que hiciste vos
suerte  = tu puntaje real − calidad                      ← lo que te pasó
```

Las dos suman tu puntaje final, exacto (está verificado). Es la misma idea con
la que en póker se separa una buena decisión de un buen resultado: alguien puede
sacar 700 jugando mal con suerte, y 400 jugando perfecto con mala suerte.

Por eso la tabla tiene dos rankings, y el de **decisiones** es el interesante:
no se puede mejorar volviendo a tirar.

La tabla se guarda en tu navegador (`localStorage`), así que es tuya y local.

## Verificarlo

```bash
node verificar/verificar.js     # motor, políticas, partidas completas
node verificar/simular_ui.js    # juega dos partidas por la interfaz, sin navegador
```

Lo que comprueban, y por qué cada uno importa:

| Chequeo | Qué error atrapa | Resultado |
|---|---|---|
| El motor contra `env.py` | que el juego del navegador difiera del que entrenó a los agentes | 60 partidas, 14.460 comparaciones, **0 diferencias** |
| Las políticas contra Python | que empaquetar los pesos haya corrompido alguna jugada | 6.600 estados, **los tres agentes al 100 %** |
| Partidas completas | que un agente esté roto de una forma que no se ve estado por estado | 530 / 366 / 315, coinciden con el informe |
| Habilidad + suerte | que la descomposición no cierre | exacta en 60 partidas |
| La interfaz | un `id` roto, una función sin definir | completa dos partidas |

Estas pruebas encontraron tres errores reales que jugando no se notaban: una
cuantización que borraba diferencias de 0,03 puntos entre jugadas, un agente que
elegía mal cuando su jugada preferida no era legal, y otro que usaba una acción
con la que nunca había entrenado.

Para regenerar los datos de prueba (necesita Python con el TP al lado):

```bash
cd verificar
python generar_trazas.py    # partidas de referencia jugadas con env.py
python generar_sonda.py     # 6.600 estados con la jugada de cada agente
```
