"""Descarga el archivo completo de Noticias Anteriores de la UNISON.

El formulario del portal topa en 200 resultados cuando se consulta un mes.
Con `mes="-"` (opción "Selecciona mes") devuelve el año completo sin ese tope.
"""

from __future__ import annotations

import argparse
import re
import time

from bs4 import BeautifulSoup
import pandas as pd
import requests

URL = "https://www.unison.mx/noticias-anteriores/"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    )
}

MESES = {
    "enero": "01",
    "febrero": "02",
    "marzo": "03",
    "abril": "04",
    "mayo": "05",
    "junio": "06",
    "julio": "07",
    "agosto": "08",
    "septiembre": "09",
    "octubre": "10",
    "noviembre": "11",
    "diciembre": "12",
}
PATRON_FECHA = re.compile(r"^(\d{1,2})\s+de\s+([a-zA-ZáéíóúÁÉÍÓÚ]+)\s+de\s+(\d{4})$")


def fecha_iso(texto: str) -> str | None:
    match = PATRON_FECHA.match(texto.strip())
    if not match:
        return None
    dia, mes, anio = match.groups()
    mes_num = MESES.get(mes.lower())
    if not mes_num:
        return None
    return f"{anio}-{mes_num}-{int(dia):02d}"


def descargar_anio(anio: int) -> list[dict]:
    payload = {
        "anio": str(anio),
        "mes": "-",
        "pclave": "",
        "opc": "historialnoti",
        "submit": "BUSCAR",
    }
    response = requests.post(URL, data=payload, headers=HEADERS, timeout=120)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    lista = soup.find("ul", class_="list-unstyled")
    if lista is None:
        return []

    registros = []
    for li in lista.find_all("li", recursive=False):
        enlace = li.find("a", href=True)
        if enlace is None:
            continue
        fecha_tag = enlace.find("span")
        fecha_txt = fecha_tag.get_text(" ", strip=True) if fecha_tag else ""
        iso = fecha_iso(fecha_txt)
        if iso is None:
            continue
        titulo = "".join(enlace.find_all(string=True, recursive=False))
        titulo = re.sub(r"\s+", " ", titulo).strip(" ,;:")
        registros.append(
            {
                "Título": titulo,
                "Fecha Original": fecha_txt,
                "Fecha_ISO": iso,
                "Enlace": enlace["href"],
                "Año": int(iso[:4]),
            }
        )
    return registros


def main() -> None:
    parser = argparse.ArgumentParser(description="Descarga completa de Noticias Anteriores UNISON")
    parser.add_argument("--desde", type=int, default=2003)
    parser.add_argument("--hasta", type=int, default=2026)
    parser.add_argument("--salida", default="data/raw/noticias_raw_full.parquet")
    parser.add_argument("--pausa", type=float, default=0.5)
    args = parser.parse_args()

    registros: list[dict] = []
    for anio in range(args.desde, args.hasta + 1):
        notas = descargar_anio(anio)
        registros.extend(notas)
        print(f"{anio}: {len(notas)} notas")
        time.sleep(args.pausa)

    df = pd.DataFrame(registros)
    df["_informativo"] = ~df["Título"].fillna("").astype(str).str.fullmatch(r"[.\s]*")
    df = df.sort_values(
        ["Enlace", "_informativo", "Fecha_ISO"], ascending=[True, False, True]
    )
    df = df.drop_duplicates(subset=["Enlace"], keep="first")
    df = (
        df.drop(columns="_informativo")
        .sort_values(["Fecha_ISO", "Título"])
        .reset_index(drop=True)
    )
    df.to_parquet(args.salida, index=False)

    print(f"\nTotal: {len(df)} notas | rango: {df['Fecha_ISO'].min()} -> {df['Fecha_ISO'].max()}")
    print(f"Guardado en {args.salida}")


if __name__ == "__main__":
    main()
