"""Ejecuta las libretas del proyecto en orden y actualiza sus salidas.

Las libretas usan rutas relativas (``../data``, ``../reports``), por lo que deben
ejecutarse con el directorio de trabajo en ``notebooks/``. Este script se encarga
de eso y de detenerse si alguna celda falla.

Uso:
    uv run python -X utf8 src/features/ejecutar_libretas.py

    # Solo algunas libretas
    uv run python -X utf8 src/features/ejecutar_libretas.py --libretas 04_cobertura_y_brecha.ipynb
"""

from __future__ import annotations

import argparse
from pathlib import Path

from nbclient import NotebookClient
import nbformat

RAIZ = Path(__file__).resolve().parents[2]
LIBRETAS = [
    "04_cobertura_y_brecha.ipynb",
    "05_topicos.ipynb",
    "06_auditoria_datos.ipynb",
    "07_historia.ipynb",
]


def ejecutar(ruta: Path, timeout: int, kernel: str) -> None:
    nb = nbformat.read(ruta, as_version=4)
    cliente = NotebookClient(nb=nb, timeout=timeout, kernel_name=kernel)
    cliente.resources = {"metadata": {"path": str(ruta.parent)}}
    cliente.execute()
    nbformat.write(nb, ruta)
    print(f"[ok] {ruta.relative_to(RAIZ)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Ejecuta las libretas del proyecto")
    parser.add_argument(
        "--libretas",
        nargs="+",
        default=LIBRETAS,
        help="Nombres o rutas de las libretas a ejecutar (por defecto, todas).",
    )
    parser.add_argument("--timeout", type=int, default=1800, help="Timeout por celda (s).")
    parser.add_argument("--kernel", default="python3", help="Nombre del kernel de Jupyter.")
    args = parser.parse_args()

    for nombre in args.libretas:
        ruta = Path(nombre)
        if not ruta.is_absolute():
            ruta = RAIZ / "notebooks" / nombre
        if not ruta.exists():
            raise FileNotFoundError(f"No existe la libreta: {ruta}")
        ejecutar(ruta, args.timeout, args.kernel)

    print("\nLibretas ejecutadas y salidas actualizadas.")


if __name__ == "__main__":
    main()
