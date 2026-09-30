#!/usr/bin/env python3
"""Lee el Excel de pendientes exportado desde el visor y agrupa los productos por acción solicitada.

Uso:
  python scripts/solicitudes.py pendientes_meli_2026-09-29_2030.xlsx
  python scripts/solicitudes.py archivo.xlsx --csv trabajo/solicitudes.csv
  python scripts/solicitudes.py archivo.xlsx --aplicar-descartes

El dueño marca en la hoja «Productos» la columna «Acción solicitada» (lista desplegable) y, si quiere, «Comentarios».
Si la acción está vacía se toman las «Acciones sugeridas» del visor. Con --aplicar-descartes, los renglones con
«Descartar de Meli» se descartan con scripts/descartar.py (motivo = comentario del dueño). Las demás acciones
(completar información, buscar más imágenes, completar precios, revisar con el dueño) se trabajan con
docs/agentes/ y docs/MERCADOLIBRE_API.md; ver docs/VISOR.md.
"""
import argparse
import csv
import datetime
import os
import sys

import openpyxl

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import descartar as desc  # noqa: E402

DESCARTAR = "Descartar de Meli"


def leer(path):
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    ws = wb["Productos"] if "Productos" in wb.sheetnames else wb.worksheets[0]
    filas = ws.iter_rows(values_only=True)
    hdr = [str(h or "").strip() for h in next(filas)]
    idx = {h: i for i, h in enumerate(hdr)}
    for req in ("Código", "Acción solicitada"):
        if req not in idx:
            raise SystemExit(f"No encuentro la columna «{req}» en la hoja {ws.title}")
    out = []
    for r in filas:
        g = r[idx["Código"]]
        if g in (None, ""):
            continue
        g = str(g).strip()
        if g.endswith(".0"):
            g = g[:-2]
        get = lambda k: (str(r[idx[k]]).strip() if k in idx and r[idx[k]] not in (None, "") else "")
        out.append({"gtin": g, "producto": get("Producto"), "accion": get("Acción solicitada"),
                    "sugeridas": get("Acciones sugeridas"), "comentarios": get("Comentarios")})
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("archivo")
    ap.add_argument("--csv", help="guarda gtin, producto, acción y comentarios en un CSV")
    ap.add_argument("--aplicar-descartes", action="store_true")
    a = ap.parse_args()

    filas = leer(a.archivo)
    grupos = {}
    for f in filas:
        clave = f["accion"] or f"Sin acción solicitada (sugeridas: {f['sugeridas'] or '—'})"
        grupos.setdefault(clave, []).append(f)
    print(f"{len(filas)} productos en {os.path.basename(a.archivo)}\n")
    for clave, lista in sorted(grupos.items(), key=lambda kv: -len(kv[1])):
        print(f"## {clave}: {len(lista)}")
        for f in lista:
            print(f"  {f['gtin']}  {f['producto'][:60]}" + (f"  — {f['comentarios']}" if f["comentarios"] else ""))
        print()

    if a.csv:
        os.makedirs(os.path.dirname(os.path.abspath(a.csv)), exist_ok=True)
        with open(a.csv, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=["gtin", "producto", "accion", "sugeridas", "comentarios"])
            w.writeheader()
            w.writerows(filas)
        print(f"CSV: {a.csv}")

    if a.aplicar_descartes:
        hoy = datetime.date.today().isoformat()
        n = 0
        for f in filas:
            if f["accion"] == DESCARTAR:
                motivo = f"Solicitud del dueño ({os.path.basename(a.archivo)})" + (f": {f['comentarios']}" if f["comentarios"] else "")
                desc.descartar([f["gtin"]], motivo, hoy)
                n += 1
        print(f"Descartados: {n}. Regenera el layout y el visor (docs/PROCEDIMIENTO_SESION.md §4).")


if __name__ == "__main__":
    main()
