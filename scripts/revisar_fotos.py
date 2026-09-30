#!/usr/bin/env python3
"""Revisión automática de fotos (complementa la revisión visual; útil si el agente no puede ver imágenes).

Uso: python scripts/revisar_fotos.py [--gtin G ...] [--salida trabajo/revision_fotos.csv]

Marca por foto:
- baja_resolucion: el producto ocupa menos de 500 px (lado_util).
- posible_fondo_gris: el borde del área del producto es un gris claro uniforme (fondo gris o empaque blanco; confirmar a la vista).
- sin_fotos: producto verificado sin ninguna foto.
Escribe un CSV con gtin, archivo, lado_util, motivo, y un resumen en pantalla.
"""
import argparse
import csv
import glob
import json
import os

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def fondo_no_blanco(path):
    """Detecta fondo gris o de color: el borde del área del producto es un tono claro, neutro y uniforme."""
    im = Image.open(path).convert("RGB")
    box = im.convert("L").point(lambda v: 255 if v < 245 else 0).getbbox()
    if not box:
        return False
    x0, y0, x1, y1 = box
    k = max(3, min(x1 - x0, y1 - y0) // 60)
    tiras = [im.crop((x0, y0, x1, y0 + k)), im.crop((x0, y1 - k, x1, y1)), im.crop((x0, y0, x0 + k, y1)), im.crop((x1 - k, y0, x1, y1))]
    px = []
    for t in tiras:
        t = t.resize((max(1, t.width // 4), max(1, t.height // 4)))
        px += list(t.get_flattened_data() if hasattr(t, "get_flattened_data") else t.getdata())
    if not px:
        return False
    medias = [sum(p[c] for p in px) / len(px) for c in range(3)]
    media = sum(medias) / 3
    neutro = max(medias) - min(medias) < 12
    var = sum((sum(p) / 3 - media) ** 2 for p in px) / len(px)
    return 170 < media < 244 and neutro and var ** 0.5 < 10


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gtin", nargs="*")
    ap.add_argument("--salida", default=os.path.join(ROOT, "trabajo", "revision_fotos.csv"))
    a = ap.parse_args()
    files = glob.glob(os.path.join(ROOT, "products", "*", "product.json"))
    if a.gtin:
        files = [f for f in files if os.path.basename(os.path.dirname(f)) in set(a.gtin)]
    rows = []
    for pf in files:
        p = json.load(open(pf, encoding="utf-8"))
        g = p["gtin"]
        ims = p.get("imagenes", [])
        if not ims and p["investigacion"]["estado"] == "verificado":
            rows.append({"gtin": g, "archivo": "", "lado_util": "", "motivo": "sin_fotos"})
        for im in ims:
            f = os.path.join(ROOT, "products", g, "images", im["archivo"])
            if not os.path.exists(f):
                rows.append({"gtin": g, "archivo": im["archivo"], "lado_util": "", "motivo": "archivo_faltante"})
                continue
            motivos = []
            if im.get("lado_util", 9999) < 500:
                motivos.append("baja_resolucion")
            if fondo_no_blanco(f):
                motivos.append("posible_fondo_gris")
            if motivos:
                rows.append({"gtin": g, "archivo": im["archivo"], "lado_util": im.get("lado_util", ""), "motivo": ",".join(motivos)})
    os.makedirs(os.path.dirname(a.salida), exist_ok=True)
    with open(a.salida, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["gtin", "archivo", "lado_util", "motivo"])
        w.writeheader()
        w.writerows(sorted(rows, key=lambda r: (r["gtin"], r["archivo"])))
    cuenta = {}
    for r in rows:
        for m in r["motivo"].split(","):
            cuenta[m] = cuenta.get(m, 0) + 1
    print(f"{len(rows)} observaciones -> {a.salida}: {cuenta}")


if __name__ == "__main__":
    main()
