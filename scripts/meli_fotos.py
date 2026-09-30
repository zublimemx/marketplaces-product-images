#!/usr/bin/env python3
"""Completa fotos con las del catálogo de Mercado Libre (origen catalogo_ml) para productos con fotos malas o regulares.

Usa la respuesta guardada por scripts/meli_precios.py en trabajo/meli/<GTIN>.json (producto de catálogo encontrado por
GTIN o por el ID de catálogo de product.json). Las fotos de catálogo son públicas (http2.mlstatic.com); no hace falta token.
Las fotos de publicaciones de otros vendedores no se pueden obtener: la API responde 403 a /items de otros vendedores.

Uso:
  python scripts/meli_fotos.py [--gtin 7501... ...] [--max 4] [--hilos 8] [--seco]

Por producto con fotos «mala» o «regular» (reglas de config/indicadores.json):
  1. Descarga hasta --max fotos de catálogo con scripts/imagenes.py fetch (normaliza, rechaza < 500 px y duplicados exactos).
  2. Quita duplicados visuales (misma foto de otra fuente): se queda la de más resolución útil.
  3. Si todas las fotos anteriores eran chicas (< 500 px útiles) y hay fotos de catálogo buenas, borra las chicas.
  4. Si la foto principal es chica (< 800 px útiles) o con posible fondo gris, pone como principal la primera foto de
     catálogo buena.
Escribe un resumen en trabajo/meli_fotos.csv. Después: python scripts/revisar_fotos.py y regenerar layout y visor.
"""
import argparse
import concurrent.futures
import csv
import json
import os
import subprocess
import sys

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from revisar_fotos import fondo_no_blanco  # noqa: E402

CRUDO = os.path.join(ROOT, "trabajo", "meli")
REGLAS = json.load(open(os.path.join(ROOT, "config", "indicadores.json"), encoding="utf-8"))["fotos"]


def ruta_img(g, archivo):
    return os.path.join(ROOT, "products", g, "images", archivo)


def dhash(path, n=8):
    im = Image.open(path).convert("L").resize((n + 1, n), Image.LANCZOS)
    px = list(im.getdata())
    bits = 0
    for y in range(n):
        for x in range(n):
            bits = (bits << 1) | (px[y * (n + 1) + x] > px[y * (n + 1) + x + 1])
    return bits


def calidad(imgs, g):
    """'buena', 'regular' o 'mala' con las mismas reglas del visor."""
    if not imgs:
        return "mala"
    utiles = [im.get("lado_util", 0) for im in imgs]
    if max(utiles) < REGLAS["regular"]["min_lado_util"]:
        return "mala"
    b = REGLAS["buena"]
    principal = imgs[0]
    gris = fondo_no_blanco(ruta_img(g, principal["archivo"])) if os.path.exists(ruta_img(g, principal["archivo"])) else False
    if len(imgs) >= b["min_fotos"] and principal.get("lado_util", 0) >= b["min_lado_util_principal"] and not gris:
        return "buena"
    return "regular"


def procesar(g, maximo, seco):
    pj = os.path.join(ROOT, "products", g, "product.json")
    prod = json.load(open(pj, encoding="utf-8"))
    antes = calidad(prod.get("imagenes", []), g)
    fila = {"gtin": g, "antes": antes, "despues": antes, "descargadas": 0, "quitadas": 0, "principal_cambiada": "", "nota": ""}
    if antes == "buena":
        fila["nota"] = "ya estaba buena"
        return fila
    f = os.path.join(CRUDO, f"{g}.json")
    crudo = json.load(open(f, encoding="utf-8")) if os.path.exists(f) else {}
    pics = ((crudo.get("producto") or {}).get("pictures")) or []
    urls = [p["url"] for p in pics if p.get("url") and max(p.get("max_width") or 0, p.get("max_height") or 0) >= 500][:maximo]
    if not urls:
        fila["nota"] = "sin fotos de catálogo" if crudo.get("producto") else "sin producto de catálogo"
        return fila
    if seco:
        fila["nota"] = f"{len(urls)} fotos de catálogo disponibles"
        return fila
    previas = {im["archivo"] for im in prod.get("imagenes", [])}
    r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "imagenes.py"), "fetch", g, "--origen", "catalogo_ml",
                        "--pagina", f"https://www.mercadolibre.com.mx/p/{crudo['producto_catalogo']}", *urls],
                       capture_output=True, text=True, env={**os.environ, "CONTACT_DIR": os.path.join(ROOT, "trabajo", "contactos")})
    prod = json.load(open(pj, encoding="utf-8"))
    imgs = prod.get("imagenes", [])
    nuevas = [im for im in imgs if im["archivo"] not in previas]
    fila["descargadas"] = len(nuevas)
    if not nuevas:
        fila["nota"] = "no se pudo descargar: " + (r.stdout.strip().splitlines() or [""])[-1][:120]
        return fila
    # 2. duplicados visuales
    hashes = {im["archivo"]: dhash(ruta_img(g, im["archivo"])) for im in imgs if os.path.exists(ruta_img(g, im["archivo"]))}
    quitar = set()
    for i, a in enumerate(imgs):
        for b in imgs[i + 1:]:
            if a["archivo"] in quitar or b["archivo"] in quitar or a["archivo"] not in hashes or b["archivo"] not in hashes:
                continue
            if bin(hashes[a["archivo"]] ^ hashes[b["archivo"]]).count("1") <= 6:
                quitar.add(b["archivo"] if a.get("lado_util", 0) >= b.get("lado_util", 0) else a["archivo"])
    # 3. fotos chicas cuando hay de catálogo buenas
    buenas_cat = [im for im in nuevas if im["archivo"] not in quitar and im.get("lado_util", 0) >= REGLAS["regular"]["min_lado_util"]]
    if buenas_cat and all(im.get("lado_util", 0) < REGLAS["regular"]["min_lado_util"] for im in imgs if im["archivo"] in previas):
        quitar |= {im["archivo"] for im in imgs if im["archivo"] in previas}
    for arch in quitar:
        if os.path.exists(ruta_img(g, arch)):
            os.remove(ruta_img(g, arch))
    imgs = [im for im in imgs if im["archivo"] not in quitar]
    fila["quitadas"] = len(quitar)
    # 4. principal
    if imgs:
        p0 = imgs[0]
        mala_principal = p0.get("lado_util", 0) < REGLAS["buena"]["min_lado_util_principal"] or fondo_no_blanco(ruta_img(g, p0["archivo"]))
        cand = [im for im in imgs if im["origen"] == "catalogo_ml" and im["archivo"] not in previas
                and im.get("lado_util", 0) >= REGLAS["buena"]["min_lado_util_principal"]]
        if mala_principal and cand and cand[0] is not p0:
            imgs.remove(cand[0])
            imgs.insert(0, cand[0])
            fila["principal_cambiada"] = cand[0]["archivo"]
    prod["imagenes"] = imgs
    tmp = pj + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(prod, fh, ensure_ascii=False, indent=2)
    os.replace(tmp, pj)
    fila["despues"] = calidad(imgs, g)
    return fila


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--gtin", nargs="*")
    ap.add_argument("--max", type=int, default=4)
    ap.add_argument("--hilos", type=int, default=8)
    ap.add_argument("--seco", action="store_true", help="solo cuenta lo que haría")
    a = ap.parse_args()
    gtins = [r["gtin"] for r in csv.DictReader(open(os.path.join(ROOT, "data", "prioridad.csv"), encoding="utf-8"))]
    if a.gtin:
        gtins = [g for g in gtins if g in set(a.gtin)]
    filas = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=a.hilos) as ex:
        for fila in ex.map(lambda g: procesar(g, a.max, a.seco), gtins):
            filas.append(fila)
    out = os.path.join(ROOT, "trabajo", "meli_fotos.csv")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(filas[0].keys()))
        w.writeheader()
        w.writerows(filas)
    cambio = {}
    for f in filas:
        cambio[(f["antes"], f["despues"])] = cambio.get((f["antes"], f["despues"]), 0) + 1
    print("antes → después:", {f"{k[0]}→{k[1]}": v for k, v in sorted(cambio.items())})
    print("fotos descargadas:", sum(f["descargadas"] for f in filas), "· quitadas:", sum(f["quitadas"] for f in filas),
          "· principal cambiada:", sum(1 for f in filas if f["principal_cambiada"]), f"· detalle en {os.path.relpath(out, ROOT)}")


if __name__ == "__main__":
    main()
