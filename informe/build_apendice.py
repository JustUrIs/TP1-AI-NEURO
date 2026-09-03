"""
Arma el apendice juntando los documentos de docs/ y lo pasa a PDF.

El informe tiene un tope de tres paginas. Todo lo que no entra ahi vive en
docs/, y esto lo empaqueta para poder entregarlo junto.

    python build_apendice.py
"""

import io
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DOCS = os.path.join(HERE, "..", "docs")

PARTES = [
    ("01_REGLAS_OCULTAS.md", "El ambiente leído línea por línea"),
    ("02_RESULTADOS.md", "Todos los resultados y ablaciones"),
]

PORTADA = """# Apéndice técnico

**Gold Dice RL — Trabajo Práctico 1 — Aprendizaje por Refuerzos**

El informe tiene un tope de tres páginas. Acá está el material que no entra: el análisis del
ambiente línea por línea, y la tabla completa de resultados con sus intervalos de confianza.

Nada de esto hace falta para leer el informe, y todo es reproducible con los scripts del paquete.

---

"""

if __name__ == "__main__":
    partes = [PORTADA]
    for nombre, _titulo in PARTES:
        partes.append(io.open(os.path.join(DOCS, nombre), encoding="utf-8").read())
        partes.append("\n\n---\n\n")

    destino = os.path.join(HERE, "apendice.md")
    io.open(destino, "w", encoding="utf-8").write("\n".join(partes))
    print(f"apendice.md armado con {len(PARTES)} documentos")

    subprocess.run([sys.executable, os.path.join(HERE, "build_pdf.py"), destino,
                    os.path.join(HERE, "apendice.pdf")], check=True)
