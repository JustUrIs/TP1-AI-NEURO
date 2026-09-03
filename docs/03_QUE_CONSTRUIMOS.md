# De qué partimos y qué construimos

Este documento cuenta el trabajo entero: qué había al empezar, qué archivo se agregó, para qué
sirve cada uno, y en qué orden fueron pasando las cosas. Está escrito para que se entienda sin
saber aprendizaje por refuerzos: cada término técnico se explica la primera vez que aparece.

Si querés los números finales, están en [`02_RESULTADOS.md`](02_RESULTADOS.md). Si querés el
análisis del ambiente, en [`01_REGLAS_OCULTAS.md`](01_REGLAS_OCULTAS.md). Esto es el mapa.

---

## 1. El punto de partida

La cátedra entregó seis archivos. Nada más:

| Archivo | Líneas | Qué es |
|---|---:|---|
| `env.py` | 304 | **El juego.** No se puede tocar. |
| `config.py` | 30 | Los números del juego: costos, 30 turnos, tormenta al 15 %. Tampoco se toca. |
| `agents.py` | 153 | Dos jugadores de ejemplo: uno que juega al azar y uno con una fórmula simple. |
| `evaluate_agents.py` | 42 | Corre 1000 partidas y devuelve el promedio. |
| `renderer.py` | 120 | Gráficos de una partida. |
| `run_example.py` | 32 | Un ejemplo de cómo se usa el ambiente. |

Y los dos jugadores de ejemplo sacaban esto:

```
RandomLegal         63.0 puntos    (juega cualquier cosa legal)
SimpleExpectancy   343.4 puntos    (calcula si una compra se paga sola)
```

La consigna: entrenar un agente que saque más. Y ahí está el problema con el que arrancamos.

## 2. El problema de no tener contra qué comparar

Supongamos que entrenamos algo y saca 480. ¿Eso es bueno?

No hay manera de saberlo. Es mejor que 343, sí. ¿Pero faltaban 20 puntos para el máximo posible
o faltaban 200? Sin esa respuesta uno queda ajustando parámetros a ciegas, sin saber si está
cerca del techo o lejísimos.

Así que antes de entrenar nada nos hicimos otra pregunta: **¿cuánto vale este juego jugado
perfecto?**

Parece imposible de responder —hay dados de por medio— pero no lo es, y la razón es una
observación sobre el código:

> En `env.py`, la variable `points` no aparece en ninguna transición. No cambia la tirada, no
> cambia los costos, no cambia la tormenta. Solo se acumula.

Eso quiere decir que para decidir bien **no importa cuántos puntos llevás**. Importa el turno, el
oro, cuántos dados tenés, cuánto bonus y cuántos escudos. Cinco números, todos acotados. Y con un
problema así de chico se puede calcular la respuesta exacta hacia atrás: en el turno 30 la mejor
jugada es obvia (puntuar todo, porque el oro que sobra se pierde), y sabiendo el turno 30 se
puede resolver el 29, y con el 29 el 28, y así hasta el 1.

Eso es **programación dinámica**, y tardó 17 segundos:

```
El juego vale 642.45 puntos jugado perfecto.
```

De golpe todo cambió de significado. El baseline de la cátedra no saca "343 puntos": saca el
**53 % de lo que hay**. Deja casi la mitad sobre la mesa. Y cualquier cosa que entrenáramos iba a
tener un denominador honesto.

A esa tabla la llamamos **el oráculo**. Es importante decir qué no es: **no se entrega al torneo**.
No es un agente que aprende —le dimos las reglas y calculó— y la consigna pide un agente
entrenado. El oráculo es la vara con la que medimos, no el competidor.

## 3. La historia, en el orden en que pasó

### Primer intento: mirar el ambiente en serio

Antes de escribir el agente leímos `env.py` línea por línea, no el PDF. Aparecieron cuatro cosas
que no están en el enunciado y cambian la estrategia (el detalle está en
[`01_REGLAS_OCULTAS.md`](01_REGLAS_OCULTAS.md)):

1. **La tormenta cae después de tu acción.** Los puntos ya están cobrados: son inmunes. Solo se
   te puede llevar el oro que decidiste no puntuar.
2. **El turno 30 no tiene tirada después.** El oro que quede sin convertir se evapora.
3. **`STORE_BEST_DIE` no guarda el dado: lo clona.** La suma de la tirada ya se cobró, y la
   acción paga 4 para volver a cobrar el dado más alto el turno siguiente.
4. **Dos agentes con la misma semilla no ven el mismo azar.** El mismo generador sirve los dados
   y las tormentas, y la cantidad de dados depende de la política. Esto rompe la forma estándar
   de comparar agentes y obliga a usar muchas más partidas.

### La hipótesis que teníamos, y que resultó falsa

La acción `SCORE` del juego no es una acción sola: elegís *cuánto* oro convertís. Con 400 de oro
hay 401 versiones distintas de esa jugada. Nuestra teoría era que ahí estaba el error caro del
enfoque tabular clásico, que colapsa eso en dos opciones ("todo" o "la mitad").

Como teníamos el solver, en vez de discutirlo lo medimos: volvimos a resolver el juego prohibiendo
todo salvo "puntuar todo".

```
SCORE con k libre (401 acciones)   642.45
solo "puntuar todo" (1 acción)     642.45     <-- cuesta 0.00
```

**Cero.** La hipótesis era falsa. La razón, que descubrimos mirando cómo juega el óptimo: puntúa
**una sola vez, en el turno 30, y puntúa todo**. Los estados donde puntuar parcial ayuda existen,
pero jugando bien nunca se llega a ellos.

Para asegurarnos de que la medición no estaba rota corrimos un control: prohibir "puntuar todo" y
dejar solo "la mitad". Eso sí bajó el valor (641.33). O sea que la herramienta distingue
restricciones que duelen; simplemente ésta no dolía.

### Lo que sí costaba

Con el mismo método probamos la otra sospecha: los topes. Un agente tabular necesita acotar las
variables, y lo natural es poner algo como "hasta 5 dados, hasta 4 de bonus, hasta 240 de oro".

Miramos qué hace el juego óptimo, y ahí estaba:

```
llega a 9 dados, 8 de bonus y 797 de oro
el 38 % de sus decisiones ocurren con más de 5 dados
```

Con esos topes, **todo el final de la partida —donde se define el 70 % del puntaje— cae en una
sola celda de la tabla**. El agente no aprende mal: no puede ver la diferencia entre el turno 24
con 160 de oro y el turno 29 con 500. Medido, cuesta 62 puntos.

### El agente

De ahí salió el diseño. Dos decisiones, las dos con motivo:

**Aprender el estado posterior a la acción, no el par (estado, acción).** En este juego, lo que
hace tu acción es completamente predecible: pagar 42 y sumar un dado es aritmética, no tiene azar.
El azar viene *después* (la tormenta y la tirada siguiente). Cuando pasa eso conviene aprender el
valor del estado en que quedás, no de la combinación estado-acción. Se llaman *afterstates* y es
la técnica con la que se hizo TD-Gammon, el programa que juega backgammon a nivel mundial.

La ventaja concreta: muchas situaciones distintas terminan en el mismo estado posterior y
comparten aprendizaje, así que se necesitan muchas menos partidas.

**Aprender la corrección, no el valor entero.** Una partida puede terminar en 300 o en 900: el
ruido es enorme. Y las decisiones de los primeros turnos valen uno o dos puntos. Aprender el valor
directo es tratar de medir 1 punto adentro de 130 de ruido, y no converge nunca.

La solución fue calcular a mano la parte fácil y predecible —"si no compro nada más y cobro al
final, ¿cuánto saco?"— y hacer que la tabla aprenda solo la diferencia. Es una técnica con nombre
(*potential-based reward shaping*) y con un teorema detrás que garantiza que no cambia cuál es la
política óptima: solo cambia desde dónde arranca la búsqueda.

Cuánto importó: **sin eso, el agente saca 105 puntos. Con eso, 527.**

### El agente empeoraba cuanto más entrenaba

Este fue el momento más raro. La primera versión funcionaba, pero al dejarla entrenar de más el
puntaje bajaba:

```
250 mil partidas   81.0 % del óptimo
500 mil            80.0 %
750 mil            79.5 %
```

No es ruido: baja siempre. La causa tiene nombre —**sesgo de maximización**— y la idea es simple.
El agente se pregunta "¿cuál es la mejor acción?" y se queda con el valor de esa mejor. Pero sus
valores son estimaciones con error, y quedarse siempre con el máximo de varios números ruidosos da
un resultado sistemáticamente más alto que la realidad. El error se concentra en los estados que
visitó poco (los más ruidosos), y el agente termina persiguiendo lugares que parecen buenos solo
porque están mal medidos. Cuanto más entrena, peor.

La solución es de manual: **dos tablas en vez de una**. Una elige cuál es la mejor acción, la otra
dice cuánto vale. Como sus errores son independientes, el sesgo se cancela.

### La segunda hipótesis que resultó falsa

Con todo eso el agente llegó a 527 (82 % del óptimo) y ahí se quedó. Usamos el oráculo para
averiguar dónde perdía, y la respuesta fue muy concreta: **no compra el escudo del turno 23**. El
óptimo lo compra y después acumula oro protegido hasta cobrar 463 de una vez. El nuestro no, y
termina con 183.

Es una trampa de las lindas: el escudo solo sirve si después acumulás, y acumular solo conviene si
tenés escudo. Hay que cambiar **dos decisiones a la vez**, y la exploración estándar prueba una
sola cosa por vez. Probamos tres esquemas pensados justamente para eso. Ninguno lo resolvió.

Pero mirando los valores apareció algo más profundo. En ese estado, la mejor jugada y la peor
están separadas por **13.6 puntos sobre un valor de 600: un 2.3 %**. Nuestro agente estima ese
valor con un error de 18 a 29 puntos. O sea:

> El agente no razona mal. Su estimación es correcta al 4 %, y la decisión requiere 2 %.

De ahí salió una predicción con números: para distinguir 13.6 puntos con ese nivel de ruido hacen
falta unas 1.400 muestras por estado, y teníamos 250. Faltaba un factor de seis.

**La probamos y falló.** Subimos de 1,5 a 5 millones de partidas y no cambió nada. Achicar la tabla
(la otra mitad de la predicción) ayudó 3 puntos, no los 100 que hubiera correspondido.

Y ese fracaso fue lo más útil de todo el trabajo, porque señaló la causa verdadera: **el problema
no es cuántas muestras hay, sino de dónde vienen.** Los estados que importan solo se visitan
cuando la exploración compra el escudo por casualidad, y al turno siguiente el agente vuelve a
jugar como siempre. Multiplicar las partidas multiplica muestras que nunca contienen la
continuación correcta.

---

## 4. Qué archivo hace qué

`env.py` y `config.py` quedaron **intactos**, y hay una verificación automática que lo comprueba
byte a byte antes de armar la entrega.

### El solver exacto

**`oracle_dp.py`** (369 líneas) — resuelve el juego hacia atrás.

| Función | Qué hace |
|---|---|
| `joint_sum_max_pmf(n)` | La probabilidad exacta de cada resultado posible de tirar `n` dados. No se estima tirando: se calcula. |
| `solve()` | El solver. Va del turno 30 al 1 calculando el valor de cada situación. |
| `action_values(obs)` | Para una situación dada, cuánto vale cada jugada posible. |
| `end_of_turn_value(...)` | Cuánto vale terminar el turno con cierto oro, contando la tormenta y la tirada siguiente. |
| `save` / `load` / `get` | Guardar la tabla en disco para no recalcularla. |
| `OracleAgent` | Un jugador que usa la tabla. Sirve para medir; **no se entrega.** |

`solve()` tiene un parámetro `score_mode` que existe solo para el experimento de la sección 3:
permite resolver el juego con la acción `SCORE` mutilada a propósito y ver cuánto cuesta.

### La representación del agente

**`afterstate.py`** (189 líneas) — cómo describimos una situación.

| Función | Qué hace |
|---|---|
| `apply(obs, accion)` | Calcula en qué estado quedás después de una jugada. Sin azar: es aritmética. |
| `legal_actions(obs)` | Qué podés hacer con el oro que tenés. |
| `potential(estado)` | La cuenta fácil: caja más lo que van a producir tus dados si no comprás nada más. |
| `build_gold_nodes()` | La grilla con la que representamos el oro. |
| `gold_features(oro)` | Ubica un monto entre dos puntos de la grilla. |
| `is_terminal(estado)` | Después del turno 30 no hay nada: vale cero. |

Sobre la grilla, que es más importante de lo que parece: el oro va de 0 a 800, y no se puede tener
una casilla por cada valor. Pero tampoco se puede agrupar de a diez, porque los precios del juego
son 18, 26, 34, 42... y si 41 y 42 caen en la misma casilla **el agente no distingue "puedo comprar
el dado" de "no puedo"**. La solución fue una grilla fina abajo (de a 1 hasta 96, donde están todos
los precios) y cada vez más gruesa arriba, con interpolación entre puntos.

**`value_table.py`** (174 líneas) — la tabla que se aprende. Guarda la *corrección* sobre la cuenta
fácil, no el valor entero. Cada casilla lleva su propio contador de visitas para ajustar cuánto
aprende de cada experiencia nueva: las que vio mil veces se mueven poco, las nuevas se mueven mucho.

### Los entrenamientos

| Archivo | Qué entrena | Para qué |
|---|---|---|
| `train_double.py` | El agente que se entrega | Dos tablas, para el problema de la sección 3 |
| `train_afterstate.py` | La versión de una tabla | Comparación: cuánto aporta la segunda tabla |
| `train_tabular_classic.py` | El método clásico | El experimento de control (ver abajo) |
| `sweep.py` | Varias configuraciones a la vez | Responder si el problema era el paso de aprendizaje |

**`train_tabular_classic.py` merece una explicación**, porque no es un intento de ganar. Es el
control experimental: reproduce la receta estándar —con sus topes, su `SCORE` colapsada, su
descuento— para poder medir **cuánto cuesta cada decisión de modelado con el mismo presupuesto de
partidas**. Sin ese control, decir "nuestro agente saca más" no prueba nada: podría ser más
entrenamiento, otra semilla, o suerte. Tiene banderas para prender y apagar una cosa por vez.

### Medición y diagnóstico

**`evaluate.py`** (161 líneas) — el protocolo de evaluación.

El `evaluate_agents.py` de la cátedra corre 1000 partidas y devuelve un promedio pelado. El
problema: con la variabilidad de este juego, ese promedio tiene un margen de error de ±6 puntos.
**Una diferencia de 4 puntos entre dos agentes no es una diferencia**, es ruido, y uno puede pasar
horas "mejorando" algo que no mejoró.

Este archivo agrega 20.000 partidas, márgenes de error en todo, y tres conjuntos de semillas
separados: uno para decidir, uno para verificar al final, y el público del enunciado. Así no nos
engañamos solos.

**`diagnose.py`** (106 líneas) — dónde se pierden los puntos.

Con el oráculo se puede calcular, jugada por jugada, cuánto valor destruyó exactamente esa
decisión. Eso convierte "el agente anda mal" en "el agente no compra el escudo del turno 23 y eso
le cuesta 27 puntos por partida". Es la diferencia entre saber que algo falla y saber qué.

**`results.py`** y **`figures.py`** — generan las tablas y el gráfico del informe. Ningún número del
informe está escrito a mano: todos salen de correr esto.

### El juego web

**`export_game.py`** empaqueta los agentes y el oráculo en un solo archivo que el navegador puede
leer sin pedirle nada a ningún servidor.

La carpeta `juego/` tiene el juego: HTML, CSS y JavaScript sueltos, sin nada que instalar. Se abre
con doble clic.

Está verificado de cinco maneras, y **tres de ellas encontraron errores reales que jugando no se
notaban**:

| Chequeo | Qué error atrapa | Resultado |
|---|---|---|
| El motor contra `env.py` | que el juego del navegador difiera del que entrenó a los agentes | 14.460 comparaciones, 0 diferencias |
| Las políticas contra Python | que empaquetar los pesos corrompiera alguna jugada | 6.600 estados, los tres al 100 % |
| Partidas completas | un agente roto de una forma que no se ve estado por estado | coinciden con el informe |
| Habilidad + suerte | que la descomposición no cierre | exacta en 60 partidas |
| La interfaz | un `id` roto, una función sin definir | completa dos partidas |

Los tres errores fueron: una compresión que borraba diferencias de 0,03 puntos entre jugadas; un
agente que elegía mal cuando su jugada preferida no era legal en ese momento; y otro que usaba una
acción con la que nunca había entrenado. Ninguno daba error, y ninguno se veía jugando.

**`package.py`** arma el ZIP de entrega: verifica que `env.py` y `config.py` sigan intactos, copia
todo a una carpeta vacía, y **prueba ahí que el agente corra solo** antes de comprimir.

---

## 5. Lo que probamos y no funcionó

Está acá porque es la mitad del trabajo, y porque un informe donde todo salió bien a la primera es
un informe que no cuenta lo que pasó.

| Qué probamos | Qué esperábamos | Qué pasó |
|---|---|---|
| Colapsar `SCORE` en dos opciones era el error caro | Costaría muchos puntos | **Cuesta 0.00.** Hipótesis falsa |
| Trazas de elegibilidad (λ = 0.3, 0.5, 0.9) | Propagar el aprendizaje más rápido | Todas empeoraron |
| Más exploración (ε de 0.3 a 0.6) | Encontrar la jugada del escudo | Empeoró |
| Exploración por episodio, estilo Ape-X | Romper el óptimo local | No lo rompió |
| Exploración sostenida de varios turnos | Descubrir que acumular sirve | No lo rompió |
| Triplicar las partidas (de 1,5 a 5 millones) | Cerrar la brecha | **Ningún cambio.** Predicción falsa |
| Achicar la tabla de 173 a 114 casillas | Cerrar la brecha | Ayudó 3 puntos, no los 100 esperados |

Las dos filas en negrita son predicciones nuestras que fallaron. La segunda es la que identificó
la causa real de la brecha.

---

## 6. Cómo verificar todo esto

Nada de lo de arriba hay que creerlo. Todo se puede correr:

```bash
cd gold_dice_rl
python oracle_dp.py                 # resuelve el juego exacto (17 segundos)
python results.py desarrollo 20000  # la tabla de resultados del informe
python diagnose.py artifacts/gold_dice_agent.pkl   # dónde pierde puntos
python train_double.py              # reentrenar el agente desde cero

cd ..
python package.py                   # verifica y arma la entrega

cd web
npm run verify                      # motor y políticas contra Python
```

Y el resumen de lo que verifica cada cosa:

| Qué | Resultado |
|---|---|
| `env.py` y `config.py` sin modificar | idénticos byte a byte |
| La entrega corre sola en carpeta limpia | sin intervención manual |
| El motor del navegador contra `env.py` | 14.460 comparaciones, 0 diferencias |
| Las políticas exportadas | 6.600 estados, el agente principal 6600/6600 |
| Que no ajustamos a las semillas de prueba | 527.06 / 526.27 / 525.42 en tres conjuntos |
