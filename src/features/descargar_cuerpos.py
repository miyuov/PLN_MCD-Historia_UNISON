"""Descarga del cuerpo de las notas del corpus analizable.

Descarga solo las notas de ``data/interim/corpus_analisis.parquet`` (notas
internas, 2003-2026, sin enlaces externos) y extrae el texto de
``div.entry-content``. Reutiliza cuerpos ya descargados y es reanudable.

Optimización de espacio
- Se guardan solo las columnas necesarias: Enlace, http_status, ok, chars,
  cuerpo, error, intentos y descargado_utc.
- El Parquet se comprime con zstd.

Uso:
    uv run python -X utf8 src/features/descargar_cuerpos.py \
        --input data/interim/corpus_analisis.parquet \
        --salida data/interim/cuerpos_full.parquet \
        --previos data/interim/cuerpos_noticias.parquet
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
import re
import time

from bs4 import BeautifulSoup
import pandas as pd
import requests
from tqdm import tqdm

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    )
}

# Etiquetas que nunca forman parte del cuerpo de la nota.
RUIDO = ["script", "style", "nav", "footer", "aside", "form", "noscript"]


def decodificar_html(contenido: bytes) -> str:
    """El portal declara UTF-8, pero las notas antiguas están en cp1252."""
    try:
        return contenido.decode("utf-8")
    except UnicodeDecodeError:
        return contenido.decode("cp1252", errors="replace")


def extraer_texto(html: str) -> str:
    """Devuelve el texto del cuerpo de la nota, sin navegación ni scripts."""
    soup = BeautifulSoup(html, "html.parser")

    contenedor = soup.find(class_="entry-content") or soup.find("article")
    if contenedor is None:
        contenedor = soup.body

    if contenedor is None:
        return ""

    for etiqueta in contenedor(RUIDO):
        etiqueta.decompose()

    texto = contenedor.get_text(" ", strip=True)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def descargar_nota(fila: dict, timeout: int, reintentos: int) -> dict:
    """Descarga una nota y devuelve su registro de resultado."""
    url = fila["Enlace"]
    registro = {
        "Enlace": url,
        "http_status": None,
        "ok": False,
        "chars": 0,
        "cuerpo": "",
        "error": "",
        "intentos": 0,
        "descargado_utc": "",
    }

    for intento in range(1, reintentos + 1):
        registro["intentos"] = intento
        try:
            respuesta = requests.get(url, headers=HEADERS, timeout=timeout)
            registro["http_status"] = respuesta.status_code

            if respuesta.status_code != 200:
                raise requests.HTTPError(f"HTTP {respuesta.status_code}")

            respuesta.encoding = "utf-8"
            cuerpo = extraer_texto(decodificar_html(respuesta.content))
            registro["cuerpo"] = cuerpo
            registro["chars"] = len(cuerpo)
            registro["ok"] = len(cuerpo) > 0
            registro["error"] = "" if registro["ok"] else "cuerpo vacío"
            registro["descargado_utc"] = datetime.now(UTC).isoformat()
            return registro

        except Exception as exc:  # noqa: BLE001
            registro["error"] = f"{type(exc).__name__}: {exc}"
            if intento < reintentos:
                time.sleep(2**intento)

    return registro


def guardar_atomico(df: pd.DataFrame, destino: Path) -> None:
    """Escribe el parquet comprimido en un temporal y luego lo reemplaza."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporal = destino.with_suffix(".tmp.parquet")
    df.to_parquet(temporal, index=False, compression="zstd")
    for _ in range(30):
        try:
            temporal.replace(destino)
            return
        except PermissionError:
            time.sleep(2)
    raise RuntimeError(f"No se pudo reemplazar el archivo temporal: {temporal}")


COLUMNAS = [
    "Enlace",
    "http_status",
    "ok",
    "chars",
    "cuerpo",
    "error",
    "intentos",
    "descargado_utc",
]


def cargar_previos(destino: Path, previos: Path | None) -> pd.DataFrame:
    """Lee cuerpos válidos del destino y de un archivo previo, sin duplicar."""
    marcos = []
    for ruta in (destino, previos):
        if ruta is None or not ruta.exists():
            continue
        df = pd.read_parquet(ruta)
        columnas = [col for col in COLUMNAS if col in df.columns]
        marcos.append(df.loc[df["ok"], columnas])

    if not marcos:
        return pd.DataFrame(columns=COLUMNAS)

    return (
        pd.concat(marcos, ignore_index=True)
        .drop_duplicates(subset=["Enlace"], keep="last")
        .reset_index(drop=True)
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Descarga de cuerpos de noticias")
    parser.add_argument("--input", default="data/interim/corpus_analisis.parquet")
    parser.add_argument("--salida", default="data/interim/cuerpos_full.parquet")
    parser.add_argument(
        "--previos",
        default="data/interim/cuerpos_noticias.parquet",
        help="Cuerpos ya descargados que se reutilizan. Cadena vacía para ignorar.",
    )
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--reintentos", type=int, default=3)
    parser.add_argument("--guardar-cada", type=int, default=500)
    parser.add_argument("--limite", type=int, default=0, help="0 = todas las del input")
    parser.add_argument(
        "--max-nuevas",
        type=int,
        default=0,
        help="Máximo de notas nuevas por corrida (0 = todas las pendientes).",
    )
    parser.add_argument("--pausa", type=float, default=0.15)
    args = parser.parse_args()

    destino = Path(args.salida)
    df = pd.read_parquet(args.input).drop_duplicates(subset=["Enlace"])
    if args.limite:
        df = df.head(args.limite)

    previos = cargar_previos(destino, Path(args.previos) if args.previos else None)
    previos = previos[previos["Enlace"].isin(set(df["Enlace"]))].reset_index(drop=True)
    ya_listas = set(previos["Enlace"])
    pendientes = df[~df["Enlace"].isin(ya_listas)].to_dict("records")
    if args.max_nuevas:
        pendientes = pendientes[: args.max_nuevas]

    print(f"Notas objetivo : {len(df):,}")
    print(f"Ya descargadas : {len(ya_listas):,}")
    print(f"Pendientes     : {len(pendientes):,}")
    print(f"Workers        : {args.workers}")
    print(f"Salida         : {destino}\n")

    if not pendientes:
        print("Nada por descargar.")
        return

    resultados = previos.to_dict("records")
    inicio = time.time()
    completadas = 0
    fallidas = 0

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futuros = {
            pool.submit(descargar_nota, fila, args.timeout, args.reintentos): fila
            for fila in pendientes
        }

        for futuro in tqdm(
            as_completed(futuros),
            total=len(futuros),
            desc="Descargando cuerpos",
            unit="nota",
            dynamic_ncols=True,
        ):
            registro = futuro.result()
            resultados.append(registro)
            completadas += 1

            if not registro["ok"]:
                fallidas += 1
                tqdm.write(f"[fallo] {registro['Enlace']} -> {registro['error']}")

            if completadas % args.guardar_cada == 0:
                guardar_atomico(pd.DataFrame(resultados), destino)
                transcurrido = time.time() - inicio
                ritmo = completadas / transcurrido if transcurrido else 0
                tqdm.write(
                    f"Guardado parcial: {completadas:,}/{len(pendientes):,} | "
                    f"{ritmo:.1f} notas/s | fallos {fallidas}"
                )

            time.sleep(args.pausa)

    final = pd.DataFrame(resultados)
    guardar_atomico(final, destino)

    ok = int(final["ok"].sum())
    total_chars = int(final["chars"].sum())
    tamano_mb = destino.stat().st_size / 1e6
    print(f"\nDescargadas OK : {ok:,}/{len(final):,}")
    print(f"Fallidas       : {int((~final['ok']).sum()):,}")
    print(f"Texto extraído : {total_chars / 1e6:.1f} millones de caracteres")
    print(f"Tamaño         : {tamano_mb:.1f} MB")
    print(f"Guardado en    : {destino}")


if __name__ == "__main__":
    main()
