# Qué construimos y para qué sirve cada archivo

La carpeta del TP quedó dividida entre archivos provistos, tres módulos Python propios, una solución de programación dinámica en C++ y los pesos entrenados. Durante el desarrollo usamos más scripts para barridos, gráficos y verificaciones; los retiramos porque no hacen falta para ejecutar, entrenar ni entender el agente.

## Punto de partida: seis archivos de la cátedra

| Archivo | Qué hacía al recibirlo | Qué hicimos nosotros |
|---|---|---|
| `config.py` | Define horizonte, tormentas, dados y precios. | No cambiamos su lógica. |
| `env.py` | Implementa el ambiente y sus seis acciones. | No cambiamos su lógica. |
| `agents.py` | Incluía `RandomLegalAgent` y `SimpleExpectancyAgent`. | Agregamos `GoldDiceAgent`, que carga los pesos y juega sin intervención. |
| `renderer.py` | Grafica una partida. | Lo conservamos como material provisto. |
| `evaluate_agents.py` | Ejecuta muchas partidas y resume puntajes. | Lo usamos para comparar y para elegir checkpoints. |
| `run_example.py` | Muestra cómo conectar ambiente y agente. | Lo conservamos como ejemplo. |

## Los tres Python que agregamos

### `afterstate.py`: representar una jugada

Este archivo reúne la parte determinista del problema. Evita copiar la misma lógica en el agente y en el entrenamiento.

| Función | Responsabilidad |
|---|---|
| `build_gold_nodes()` | Construye la grilla no uniforme del oro. |
| `gold_features(gold)` | Devuelve los dos nodos vecinos y el peso de interpolación. |
| `legal_actions(obs)` | Filtra acciones según el oro, precios y tirada actual. |
| `apply(obs, action)` | Calcula el *afterstate*, la recompensa inmediata y el parámetro de `SCORE`. |
| `potential(afterstate)` | Calcula `Φ`, la estimación contable desde la que empieza a aprender la tabla. |
| `is_terminal(afterstate)` | Marca el estado posterior a la acción del turno 30. |

Lo separamos porque tanto `GoldDiceAgent` como `train_qlearning.py` necesitan transformar una observación en posibles estados posteriores.

### `value_table.py`: guardar lo aprendido

`ValueTable` asocia cada *afterstate* discretizado con una corrección sobre `Φ`.

| Método | Responsabilidad |
|---|---|
| `value()` | Interpola los pesos y devuelve el valor estimado. |
| `update()` | Aplica el error temporal a uno o dos nodos de oro. |
| `alpha_for()` | Ajusta la tasa de aprendizaje según visitas. |
| `save()` / `load()` | Escribe y recupera el archivo `.pkl`. |

Separar la tabla permite que el agente final cargue los mismos pesos que generó el entrenamiento. El archivo `artifacts/gold_dice_agent.pkl` es el resultado de esa etapa; no es código Python.

### `train_qlearning.py`: entrenar

Contiene Double Q-Learning sobre *afterstates*. Mantiene dos `ValueTable`: en cada actualización una elige la mejor acción siguiente y la otra calcula su valor. La clase `DoubleAgent` sirve durante el entrenamiento y `merged()` combina las tablas para guardar un único modelo.

La función `train()` controla episodios, ε-greedy, actualización TD y checkpoints. Cada 100.000 partidas evalúa el agente sobre un rango fijo de desarrollo y conserva el mejor. El archivo tiene menos de 100 líneas de código para que se pueda seguir de punta a punta.

## El cambio dentro de `agents.py`

`GoldDiceAgent` hereda una política común que hace tres pasos:

1. pide a `legal_actions` las opciones válidas;
2. usa `apply` para ver dónde deja cada opción;
3. elige la que maximiza puntos inmediatos más `ValueTable.value`.

Al construirlo carga `artifacts/gold_dice_agent.pkl`. Durante el torneo no entrena, no explora y no consulta la DP.

## `sol_dp.cpp`: la referencia de programación dinámica

La DP nació de una forma de pensar propia de ICPC: buscar un estado mínimo, un caso base y un orden de cálculo. Usa

```text
DP[turno][dados][bonus][escudos][oro]
```

y recorre los turnos hacia atrás. Sólo conserva dos capas de tiempo. Para cada estado integra la probabilidad de tormenta, prueba compras y resuelve todos los valores posibles de `SCORE(k)` con un máximo prefijo. Después promedia sobre la distribución exacta de suma y máximo de los dados.

El programa imprime el valor inicial. No se importa desde Python ni forma parte del agente. Lo agregamos para responder cuánto margen había entre los baselines, nuestro modelo y una política calculada con conocimiento completo del ambiente.

## Documentación Markdown

El informe principal tiene el límite de tres carillas. Dejamos fuera de ese texto dos explicaciones que queríamos conservar:

| Archivo | Contenido |
|---|---|
| `docs/01_REGLAS_OCULTAS.md` | Casos borde encontrados al leer `env.py` y cómo afectan la estrategia. |
| `docs/02_RESULTADOS.md` | Tablas completas, definición de puntos perdidos por decisión y pruebas descartadas. |
| `docs/03_QUE_CONSTRUIMOS.md` | Este inventario del código y de las decisiones de estructura. |

Son parte de la documentación, no programas necesarios para jugar.

## Flujo para reproducir

```bash
cd gold_dice_rl

# Entrenar de nuevo y guardar artifacts/gold_dice_agent.pkl
python train_qlearning.py

# Evaluar el agente ya entrenado con el protocolo de la cátedra
python -c "from agents import GoldDiceAgent; from evaluate_agents import evaluate; print(evaluate(GoldDiceAgent(), 1000, 0))"

# Calcular la referencia por DP
g++ -O2 -std=c++17 sol_dp.cpp -o sol_dp
./sol_dp
```
