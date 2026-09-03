# Gold Dice RL

Trabajo Práctico 1 de Reinforcement Learning, Inteligencia Artificial y Neurociencias, UTDT.

El agente entregado usa Q-Learning tabular sobre *afterstates* con Double Q-Learning. Logró una media de **527,06 puntos** en 20.000 partidas, frente a 343,40 de `SimpleExpectancy` y 63,03 de `RandomLegal`.

## Entrega

- `TP1_GoldDiceRL_entrega.zip`: archivo final preparado para subir al campus.
- `gold_dice_rl/`: los seis archivos provistos, tres `.py` propios, `sol_dp.cpp` y los pesos entrenados.
- `informe/informe.tex`: fuente LaTeX del informe principal.
- `informe/informe.pdf`: informe final de tres carillas.
- `docs/01_REGLAS_OCULTAS.md`: casos borde del ambiente.
- `docs/02_RESULTADOS.md`: resultados y experimentos completos.
- `docs/03_QUE_CONSTRUIMOS.md`: inventario y justificación de cada archivo.
- `juego/`: versión jugable en HTML, CSS y JavaScript, separada del código que se entrega al torneo.

El plan de trabajo, los scripts de uso interno y los generadores de archivos no forman parte de la entrega.

## Probar el agente

```bash
cd gold_dice_rl
python -c "from agents import GoldDiceAgent; from evaluate_agents import evaluate; print(evaluate(GoldDiceAgent(), 1000, 0))"
```

## Entrenar de nuevo

```bash
cd gold_dice_rl
python train_qlearning.py
```

## Ejecutar la DP en C++

```bash
cd gold_dice_rl
g++ -O2 -std=c++17 sol_dp.cpp -o sol_dp
./sol_dp
```

## Jugar

Se puede abrir `juego/index.html` con doble clic. El juego funciona sin instalar dependencias y sin conexión a internet.
