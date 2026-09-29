#!/usr/bin/env python3
"""Valida products/*/product.json contra schema/product.schema.json y, opcionalmente, los resultados de una sesión.

Uso: python scripts/validar.py [--sesion NN]
Sale con código 1 si hay errores.
"""
import argparse
import glob
import json
import os
import sys

import jsonschema

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def check(schema_file, files):
    v = jsonschema.Draft202012Validator(json.load(open(os.path.join(ROOT, "schema", schema_file), encoding="utf-8")))
    bad = 0
    for f in files:
        errs = list(v.iter_errors(json.load(open(f, encoding="utf-8"))))
        if errs:
            bad += 1
            e = errs[0]
            print(f"{os.path.relpath(f, ROOT)}: {e.message} en {list(e.path)}")
    return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sesion", type=int)
    a = ap.parse_args()
    prods = glob.glob(os.path.join(ROOT, "products", "*", "product.json"))
    bad = check("product.schema.json", prods)
    for pf in prods:
        g = os.path.basename(os.path.dirname(pf))
        p = json.load(open(pf, encoding="utf-8"))
        if p["gtin"] != g:
            bad += 1
            print(f"{g}: el gtin del archivo no coincide con la carpeta")
        for im in p.get("imagenes", []):
            if not os.path.exists(os.path.join(ROOT, "products", g, "images", im["archivo"])):
                bad += 1
                print(f"{g}: falta la foto {im['archivo']}")
    print(f"product.json revisados: {len(prods)}")
    if a.sesion:
        base = os.path.join(ROOT, "trabajo", f"sesion_{a.sesion:02d}", "resultados")
        bad += check("resultado_investigacion.schema.json", glob.glob(os.path.join(base, "inv_*.json")))
        bad += check("resultado_fotos.schema.json", glob.glob(os.path.join(base, "img_*.json")))
    print("OK" if not bad else f"{bad} archivos con errores")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
