#!/usr/bin/env python3
"""Arma los lotes de una sesión de investigación.

Uso: python scripts/seleccionar_lote.py --sesion 7 [--tamano 200] [--por-lote 25] [--fotos]

Toma de data/prioridad.csv, en orden, los productos con investigacion.estado "pendiente" o "sin_verificar"
(hasta --tamano) y los reparte en trabajo/sesion_NN/lotes/inv_XX.json. Con --fotos también crea
trabajo/sesion_NN/lotes/img_XX.json con los productos verificados que no tienen fotos (no consumen búsquedas).
Cada elemento lleva: id (orden), gtin, nombre (nombre en sistema), linea, estado.
"""
import argparse
import csv
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sesion", type=int, required=True)
    ap.add_argument("--tamano", type=int, default=200)
    ap.add_argument("--por-lote", type=int, default=25)
    ap.add_argument("--fotos", action="store_true")
    a = ap.parse_args()
    base = os.path.join(ROOT, "trabajo", f"sesion_{a.sesion:02d}")
    os.makedirs(os.path.join(base, "lotes"), exist_ok=True)
    os.makedirs(os.path.join(base, "resultados"), exist_ok=True)
    inv, img = [], []
    with open(os.path.join(ROOT, "data", "prioridad.csv"), encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            p = json.load(open(os.path.join(ROOT, "products", r["gtin"], "product.json"), encoding="utf-8"))
            e = p["investigacion"]["estado"]
            item = {"id": int(r["orden"]), "gtin": r["gtin"], "nombre": r["nombre_sistema"], "linea": r["linea"], "estado": e}
            if e in ("pendiente", "sin_verificar"):
                inv.append(item)
            elif e == "verificado" and not p.get("imagenes"):
                img.append(item)
    inv = inv[: a.tamano]
    for i in range(0, len(inv), a.por_lote):
        json.dump(inv[i:i + a.por_lote], open(os.path.join(base, "lotes", f"inv_{i // a.por_lote + 1:02d}.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    n_img = 0
    if a.fotos:
        for i in range(0, len(img), a.por_lote):
            json.dump(img[i:i + a.por_lote], open(os.path.join(base, "lotes", f"img_{i // a.por_lote + 1:02d}.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=0)
        n_img = len(img)
    print(f"sesión {a.sesion}: {len(inv)} productos a investigar en {-(-len(inv) // a.por_lote)} lotes; {n_img} verificados sin fotos -> {base}/lotes")


if __name__ == "__main__":
    main()
