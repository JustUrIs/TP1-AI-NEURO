# Juego web

Esta carpeta contiene una versión jugable de Gold Dice RL. Se puede abrir `index.html` con doble clic; no requiere servidor ni conexión a internet.

## Archivos

| Archivo | Función |
|---|---|
| `index.html` | Interfaz, estilos y flujo de una partida. |
| `motor.js` | Reproduce las reglas de `env.py` en el navegador. |
| `agentes.js` | Ejecuta el agente principal, dos variantes tabulares y la referencia DP. |
| `explicar.js` | Arma la explicación de cada acción a partir de los valores calculados. |
| `data.js` | Contiene los pesos y valores precalculados en base64. |

Usamos scripts clásicos para que el navegador también los pueda cargar desde `file://`.

## Cómo se compara una partida

Después de cada elección calculamos la diferencia entre el valor de la mejor acción según la DP y el valor de la acción jugada. La diferencia vale cero cuando ambas coinciden.

```text
calidad = 642,45 - suma de puntos perdidos por las decisiones
suerte  = puntaje real - calidad
```

La tabla de posiciones se guarda en `localStorage`; los datos no salen del navegador.

Los jugadores y agentes reciben los mismos dados y tormentas dentro del juego web. Esto permite comparar sus decisiones durante una partida concreta.
