#!/usr/bin/env python3
"""Prepara la revisión con subagentes de lo que se obtuvo del catálogo de Mercado Libre (docs/agentes/revision_ml.md).

Uso:
  python scripts/preparar_revision_ml.py fotos [--por-hoja 5] [--gtin ...]
  python scripts/preparar_revision_ml.py descripciones [--por-lote 25] [--gtin ...]

fotos: hojas de contacto numeradas de los productos con fotos de origen catalogo_ml en
  trabajo/revision_fotos_ml/hoja_NNN.jpg y su índice trabajo/revision_fotos_ml/indice.json
  ({gtin: {hoja, titulo, presentacion, imagenes: [{n, archivo, origen}]}}).
descripciones: lotes en trabajo/descripciones_ml/ con los datos del catálogo guardados por scripts/meli_precios.py
  (trabajo/meli/<GTIN>.json; conviene correrlo con --descripciones):
  - lote_dN.json: descripción no «buena» o de menos de 800 caracteres → reescribir descripción y confirmar el GTIN;
  - lote_cN.json: el resto con confianza distinta de alta y catálogo encontrado por GTIN → solo confirmar el GTIN.
Los subagentes escriben resultado_NN.json, resultado_dN.json y resultado_cN.json (docs/CONTRATOS.md §13) y luego se
aplican con scripts/aplicar_revision_ml.py.
"""
import argparse
import csv
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
CRUDO = os.path.join(ROOT, "trabajo", "meli")
RECHAZADOS = os.path.join(ROOT, "data", "catalogo_ml_rechazados.csv")


def gtins(filtro):
    orden = [r["gtin"] for r in csv.DictReader(open(os.path.join(ROOT, "data", "prioridad.csv"), encoding="utf-8"))]
    return [g for g in orden if not filtro or g in set(filtro)]


def leer(g):
    return json.load(open(os.path.join(ROOT, "products", g, "product.json"), encoding="utf-8"))


def fuente(tam):
    for f in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/Library/Fonts/Arial.ttf", "C:/Windows/Fonts/arial.ttf"):
        if os.path.exists(f):
            return ImageFont.truetype(f, tam)
    return ImageFont.load_default()


def hojas(lista, por_hoja):
    out = os.path.join(ROOT, "trabajo", "revision_fotos_ml")
    os.makedirs(out, exist_ok=True)
    prods = []
    for g in lista:
        p = leer(g)
        if any(im.get("origen") == "catalogo_ml" for im in p.get("imagenes", [])):
            prods.append((g, p))
    T, C, F = 240, 5, fuente(15)
    indice = {}
    for h in range(0, len(prods), por_hoja):
        grupo = prods[h:h + por_hoja]
        filas = sum((len(p["imagenes"]) + C - 1) // C for _, p in grupo)
        hoja = Image.new("RGB", (T * C + 8, filas * (T + 24) + len(grupo) * 26 + 8), "white")
        d = ImageDraw.Draw(hoja)
        nombre = f"hoja_{h // por_hoja + 1:03d}.jpg"
        y = 4
        for g, p in grupo:
            d.text((6, y), f"{g} · {p.get('titulo') or p['nombre_sistema']}"[:120], fill="black", font=F)
            y += 26
            indice[g] = {"hoja": nombre, "titulo": p.get("titulo", ""), "presentacion": (p.get("ficha") or {}).get("presentacion", ""),
                         "imagenes": []}
            for i, im in enumerate(p["imagenes"]):
                x, yy = 4 + (i % C) * T, y + (i // C) * (T + 24)
                try:
                    th = Image.open(os.path.join(ROOT, "products", g, "images", im["archivo"])).convert("RGB")
                    th.thumbnail((T - 12, T - 12))
                    hoja.paste(th, (x + 4, yy))
                except OSError:
                    pass
                n = str(i + 1)
                d.text((x + 4, yy + T - 8), f"#{n} {im.get('origen', '')} {im.get('lado_util', '')} px", fill="red", font=F)
                indice[g]["imagenes"].append({"n": n, "archivo": im["archivo"], "origen": im.get("origen", "")})
            y += ((len(p["imagenes"]) + C - 1) // C) * (T + 24)
        hoja.save(os.path.join(out, nombre), quality=82)
    json.dump(indice, open(os.path.join(out, "indice.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{len(prods)} productos en {(len(prods) + por_hoja - 1) // por_hoja} hojas -> {os.path.relpath(out, ROOT)}/")


def catalogo(crudo):
    p = crudo.get("producto") or {}
    atr = [f"{a.get('name')}: {a.get('value_name')}" for a in (p.get("attributes") or []) if a.get("value_name")]
    sd = p.get("short_description") or {}
    return {"id": crudo.get("producto_catalogo", ""), "origen": crudo.get("origen_catalogo", ""), "nombre": p.get("name", ""),
            "caracteristicas": [f.get("text") for f in (p.get("main_features") or []) if f.get("text")],
            "descripcion_corta": sd.get("content", "") if isinstance(sd, dict) else str(sd or ""), "atributos": atr}


def lotes(lista, por_lote):
    from build_visor import ind_descripcion  # noqa: E402
    reglas = json.load(open(os.path.join(ROOT, "config", "indicadores.json"), encoding="utf-8"))["descripcion"]
    rech = {r["gtin"] for r in csv.DictReader(open(RECHAZADOS, encoding="utf-8"))} if os.path.exists(RECHAZADOS) else set()
    out = os.path.join(ROOT, "trabajo", "descripciones_ml")
    os.makedirs(out, exist_ok=True)
    d_, c_ = [], []
    for g in lista:
        f = os.path.join(CRUDO, f"{g}.json")
        if g in rech or not os.path.exists(f):
            continue
        crudo = json.load(open(f, encoding="utf-8"))
        if not crudo.get("producto"):
            continue
        p = leer(g)
        inv = p["investigacion"]
        x = {"gtin": g, "titulo": p.get("titulo", ""), "nombre_sistema": p["nombre_sistema"], "receta_mx": p.get("receta_mx", ""),
             "categoria": p["marketplaces"]["mercadolibre"].get("categoria_ruta", ""),
             "investigacion": {k: inv.get(k, "") for k in ("estado", "confianza", "notas")}, "catalogo_ml": catalogo(crudo),
             "descripciones_otros_vendedores": [d["texto"] for d in crudo.get("descripciones", [])]}
        desc = p.get("descripcion") or ""
        if ind_descripcion(p, reglas)[0] != "buena" or len(desc) < 800:
            d_.append(x | {"descripcion_actual": desc, "ficha_actual": p.get("ficha", {})})
        elif (inv.get("confianza") != "alta" or inv.get("estado") != "verificado") and crudo.get("origen_catalogo") == "gtin":
            c_.append(x | {"ficha_actual": p.get("ficha", {})})
    for pref, grupo in (("d", d_), ("c", c_)):
        for i in range(0, len(grupo), por_lote):
            nombre = os.path.join(out, f"lote_{pref}{i // por_lote + 1}.json")
            json.dump(grupo[i:i + por_lote], open(nombre, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"descripciones: {len(d_)} productos · solo confirmación: {len(c_)} -> {os.path.relpath(out, ROOT)}/lote_*.json")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("que", choices=["fotos", "descripciones"])
    ap.add_argument("--gtin", nargs="*")
    ap.add_argument("--por-hoja", type=int, default=5)
    ap.add_argument("--por-lote", type=int, default=25)
    a = ap.parse_args()
    if a.que == "fotos":
        hojas(gtins(a.gtin), a.por_hoja)
    else:
        lotes(gtins(a.gtin), a.por_lote)


if __name__ == "__main__":
    main()
