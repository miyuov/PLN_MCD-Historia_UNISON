"""Crea un snapshot verificable del estado actual del pipeline."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import zipfile

RAIZ = Path(".")
FECHA = "2026-11-03"
NOMBRE = f"checkpoint_{FECHA}_v2_fase4"


def _archivos(carpeta: str, patron: str) -> list[str]:
    """Lista rutas relativas ordenadas de una carpeta."""
    return [p.as_posix() for p in sorted(Path(carpeta).glob(patron)) if p.is_file()]


ARCHIVOS = [
    "README.md",
    "Makefile",
    "pyproject.toml",
    "uv.lock",
    "docs/README.md",
    "docs/prompts/instrucciones_flujo_principal.md",
    "docs/prompts/skill_1_limpieza.md",
    "docs/prompts/skill_2_analista.md",
    "reports/fase4_narrativa.md",
    "notebooks/Historia_UNISON.ipynb",
    "notebooks/04_cobertura_y_brecha.ipynb",
    "notebooks/05_topicos.ipynb",
    "notebooks/06_auditoria_datos.ipynb",
    "notebooks/07_historia.ipynb",
    *_archivos("src/data", "*.py"),
    *_archivos("src/features", "*.py"),
    *_archivos("tests", "*.py"),
    *_archivos("data/raw", "*.parquet"),
    *_archivos("data/interim", "*.parquet"),
    *_archivos("data/processed", "*.parquet"),
    *_archivos("reports/figures", "*.png"),
]


def sha256(ruta: Path) -> str:
    digest = hashlib.sha256()
    with ruta.open("rb") as archivo:
        for bloque in iter(lambda: archivo.read(1024 * 1024), b""):
            digest.update(bloque)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="Snapshot verificable del pipeline")
    parser.add_argument("--nombre", default=NOMBRE)
    parser.add_argument(
        "--descripcion",
        default="Pipeline v2 - Fases 1-4: entidades, cobertura/brecha, topicos y narrativa.",
    )
    args = parser.parse_args()

    destino = RAIZ / "snapshots" / f"{args.nombre}.zip"
    destino.parent.mkdir(parents=True, exist_ok=True)

    manifiesto = {
        "nombre": args.nombre,
        "creado_utc": datetime.now(UTC).isoformat(),
        "descripcion": args.descripcion,
        "archivos": [],
    }

    with zipfile.ZipFile(destino, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for relativo in ARCHIVOS:
            ruta = RAIZ / relativo
            if not ruta.exists():
                print(f"[omitido] no existe: {relativo}")
                continue
            zf.write(ruta, arcname=relativo)
            manifiesto["archivos"].append(
                {
                    "ruta": relativo,
                    "bytes": ruta.stat().st_size,
                    "sha256": sha256(ruta),
                }
            )
            print(f"[ok] {relativo} ({ruta.stat().st_size:,} bytes)")

        zf.writestr(
            "MANIFEST.json",
            json.dumps(manifiesto, ensure_ascii=False, indent=2),
        )

    with zipfile.ZipFile(destino) as zf:
        corrupto = zf.testzip()

    copia_manifiesto = destino.with_suffix(".json")
    copia_manifiesto.write_text(
        json.dumps(manifiesto, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"\nSnapshot : {destino}")
    print(f"Tamaño   : {destino.stat().st_size:,} bytes")
    print(f"Integridad: {'OK' if corrupto is None else f'CORRUPTO: {corrupto}'}")
    print(f"Manifiesto: {copia_manifiesto}")


if __name__ == "__main__":
    main()
