"""
Arma el ZIP de entrega y lo prueba en una carpeta limpia.

La prueba importa: el paquete tiene que correr en la maquina de la catedra, con
`env.py` y `config.py` tal como los entregaron, sin red y sin reentrenar nada.
Este script

  1. verifica que env.py y config.py esten byte a byte iguales a los originales,
  2. copia el paquete a un directorio temporal vacio,
  3. corre ahi `evaluate_agents.evaluate` sobre el agente entregado -- la misma
     funcion que va a usar el torneo, sin tocarla,
  4. recien entonces arma el ZIP.

    python package.py
"""

from __future__ import annotations

import filecmp
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, "gold_dice_rl")
INFORME = os.path.join(ROOT, "informe")
PRISTINE = os.path.join(ROOT, "tmp", "friend_submission", "TP1_GoldDiceRL")
OUT = os.path.join(ROOT, "TP1_GoldDiceRL_entrega.zip")

PACKAGE_NAME = "TP1_GoldDiceRL"

# Provistos por la catedra. No se tocan; se verifica que sigan intactos.
PROVIDED = ["config.py", "env.py", "renderer.py", "run_example.py", "evaluate_agents.py"]

# Codigo propio.
OURS = [
    "agents.py",
    "afterstate.py",
    "value_table.py",
    "oracle_dp.py",
    "train_double.py",
    "train_afterstate.py",
    "train_tabular_classic.py",
    "sweep.py",
    "evaluate.py",
    "diagnose.py",
    "results.py",
    "figures.py",
]

# El unico artefacto imprescindible: los pesos del agente entregado. El oraculo
# NO va (pesa 50 MB y se recalcula en 17 segundos con `python oracle_dp.py`).
ARTIFACTS = ["gold_dice_agent.pkl"]

DOCS = [
    (os.path.join(INFORME, "informe.pdf"), "informe.pdf"),
    (os.path.join(INFORME, "apendice.pdf"), "apendice.pdf"),
]

README = """# Gold Dice RL - TP 1

Agente entregado: `agents.GoldDiceAgent`. TD de control off-policy sobre
*afterstates* con Double learning, gamma = 1. Carga sus pesos de
`artifacts/gold_dice_agent.pkl` y juega greedy, sin intervencion manual.

## Correrlo

```python
from agents import GoldDiceAgent
from evaluate_agents import evaluate

print(evaluate(GoldDiceAgent(), n_episodes=1000, seed=0))
```

## Resultado

| Agente | Media (n = 20.000) | % del optimo teorico |
|---|---:|---:|
| Optimo exacto (programacion dinamica, NO compite) | 644.10 | 100 % |
| **GoldDiceAgent** | **527.06** | **82.0 %** |
| SimpleExpectancy (baseline provisto) | 343.40 | 53.5 % |
| RandomLegal (baseline provisto) | 63.03 | 9.8 % |

Verificado en tres bandas de semillas disjuntas: 527.06 (desarrollo, donde se
tomaron todas las decisiones), 526.27 (control) y 525.42 (publica, seed 0). La
diferencia esta dentro del ruido: no hay sobreajuste.

## Archivos

Provistos por la catedra, sin modificar: `config.py`, `env.py`, `renderer.py`,
`run_example.py`, `evaluate_agents.py`.

Propios:

| Archivo | Que hace |
|---|---|
| `agents.py` | `GoldDiceAgent` (entregado) y `PotentialAgent` (control sin aprendizaje) |
| `afterstate.py` | representacion por afterstates, transiciones deterministas, potencial |
| `value_table.py` | tabla de valores: residuo sobre el potencial, interpolacion lineal en el oro, paso por peso |
| `train_double.py` | entrenamiento del agente entregado |
| `train_afterstate.py` | variante de una sola tabla (ablacion de Double) |
| `train_tabular_classic.py` | Q tabular clasico, con perillas para las ablaciones |
| `oracle_dp.py` | solver exacto del MDP. **No es un agente de aprendizaje**: se usa solo para medir y diagnosticar |
| `evaluate.py` | protocolo de evaluacion con intervalos de confianza y bandas de semillas |
| `diagnose.py` | arrepentimiento exacto por turno contra el oraculo |
| `results.py` | genera la tabla del informe |
| `figures.py` | figura del informe |

## Reproducir

```bash
python oracle_dp.py                 # resuelve el juego exacto (~17 s)
python train_double.py              # entrena el agente
python results.py desarrollo 20000  # tabla del informe
python diagnose.py artifacts/gold_dice_agent.pkl
```

El entrenamiento usa un rango de semillas disjunto del de evaluacion.

## Informe

`informe.pdf` (3 paginas) y `apendice.pdf` (detalle del ambiente, tabla completa
de ablaciones y verificacion de sobreajuste).
"""

SMOKE = """
import sys, json
from agents import GoldDiceAgent
from evaluate_agents import evaluate
res = evaluate(GoldDiceAgent(), n_episodes=int(sys.argv[1]), seed=0)
print(json.dumps(res))
"""


def check_pristine() -> None:
    print("1. verificando que env.py y config.py esten intactos")
    if not os.path.isdir(PRISTINE):
        print("   (no hay copia original a mano; se omite la comparacion)")
        return
    for name in ("env.py", "config.py"):
        a, b = os.path.join(SRC, name), os.path.join(PRISTINE, name)
        if not filecmp.cmp(a, b, shallow=False):
            raise SystemExit(f"   ERROR: {name} fue modificado. El enunciado lo prohibe.")
        print(f"   {name}: identico al original")


def stage(dest: str) -> None:
    os.makedirs(dest, exist_ok=True)
    for name in PROVIDED + OURS:
        shutil.copy2(os.path.join(SRC, name), dest)
    art = os.path.join(dest, "artifacts")
    os.makedirs(art, exist_ok=True)
    for name in ARTIFACTS:
        shutil.copy2(os.path.join(SRC, "artifacts", name), art)
    for src, name in DOCS:
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(dest, name))
    with open(os.path.join(dest, "README.md"), "w", encoding="utf-8") as fh:
        fh.write(README)


def smoke(dest: str, episodes: int = 300) -> None:
    print(f"2. probando en carpeta limpia ({episodes} episodios, seed=0)")
    script = os.path.join(dest, "_smoke.py")
    with open(script, "w", encoding="utf-8") as fh:
        fh.write(SMOKE)
    proc = subprocess.run(
        [sys.executable, "_smoke.py", str(episodes)],
        cwd=dest, capture_output=True, text=True,
    )
    os.remove(script)
    if proc.returncode != 0:
        print(proc.stdout)
        print(proc.stderr)
        raise SystemExit("   ERROR: el paquete no corre en carpeta limpia.")
    import json

    res = json.loads(proc.stdout.strip().splitlines()[-1])
    print(f"   media = {res['mean']:.2f}   mediana = {res['median']:.0f}   max = {res['max']}")
    if res["mean"] < 450:
        raise SystemExit("   ERROR: el agente rinde por debajo de lo esperado.")
    print("   corre sin intervencion manual")


def zip_up(dest: str) -> None:
    print("3. armando el ZIP")
    if os.path.exists(OUT):
        os.remove(OUT)
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        for folder, _dirs, files in os.walk(dest):
            for name in sorted(files):
                if "__pycache__" in folder:
                    continue
                full = os.path.join(folder, name)
                rel = os.path.join(PACKAGE_NAME, os.path.relpath(full, dest))
                z.write(full, rel)
    size = os.path.getsize(OUT) / 1e6
    print(f"   {OUT}   ({size:.1f} MB)")


if __name__ == "__main__":
    check_pristine()
    tmp = tempfile.mkdtemp(prefix="golddice_")
    dest = os.path.join(tmp, PACKAGE_NAME)
    try:
        stage(dest)
        smoke(dest)
        zip_up(dest)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("\nlisto.")
