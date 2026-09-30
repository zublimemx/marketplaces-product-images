#!/usr/bin/env python3
"""Aplica a products/<GTIN>/product.json la revisión de fotos, descripciones y catálogo de Mercado Libre hecha por
subagentes (contrato en docs/CONTRATOS.md §13).

Uso:
  python scripts/aplicar_revision_ml.py [--fotos trabajo/revision_fotos_ml] [--descripciones trabajo/descripciones_ml]
                                        [--fecha 2026-09-29] [--seco]

- Fotos (resultado_NN.json: {"quitar": [{gtin, archivo, motivo}], "principal": [{gtin, archivo}]}): borra del disco y de
  imagenes las fotos a quitar y pone al frente la principal indicada.
- Descripciones y confirmación (resultado_dN.json y resultado_cN.json: [{gtin, confirmado, diferencias?, descripcion?,
  ficha?, titulo?, notas}]): reemplaza descripcion y titulo si vienen; actualiza las claves de ficha que vengan (otros se
  reemplaza completo). confirmado = true deja la investigación verificada con confianza alta.
- Catálogos rechazados (data/catalogo_ml_rechazados.csv): quita catalogo_id de product.json y las fotos de origen
  catalogo_ml de los catálogos que son otro producto. scripts/meli_precios.py ya no usa esos catálogos para precios.
Después: python scripts/meli_precios.py --solo-csv, scripts/revisar_fotos.py y regenerar layout y visor.
"""
import argparse
import csv
import datetime
import glob
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RECHAZADOS = os.path.join(ROOT, "data", "catalogo_ml_rechazados.csv")


def ficha_keys():
    import sys
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    import build_mercadolibre as bml  # noqa: E402
    return {k for k, _ in bml.FICHA_COLS}


def cargar_rechazados():
    if not os.path.exists(RECHAZADOS):
        return {}
    return {r["gtin"]: r for r in csv.DictReader(open(RECHAZADOS, encoding="utf-8"))}


def pj(g):
    return os.path.join(ROOT, "products", g, "product.json")


def leer(g):
    return json.load(open(pj(g), encoding="utf-8"))


def escribir(g, p):
    tmp = pj(g) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(p, fh, ensure_ascii=False, indent=2)
    os.replace(tmp, pj(g))


def quitar_foto(g, p, archivo, seco):
    antes = len(p.get("imagenes", []))
    p["imagenes"] = [im for im in p.get("imagenes", []) if im["archivo"] != archivo]
    f = os.path.join(ROOT, "products", g, "images", archivo)
    if not seco and os.path.exists(f):
        os.remove(f)
    return antes != len(p["imagenes"])


def fotos(carpeta, seco, probs):
    quitar, principal = {}, {}
    for f in sorted(glob.glob(os.path.join(carpeta, "resultado_*.json"))):
        r = json.load(open(f, encoding="utf-8"))
        for x in r.get("quitar", []):
            quitar.setdefault(str(x["gtin"]), []).append(x["archivo"])
        for x in r.get("principal", []):
            principal[str(x["gtin"])] = x["archivo"]
    n_q = n_p = 0
    sin_fotos = []
    for g in sorted(set(quitar) | set(principal)):
        if not os.path.exists(pj(g)):
            probs.append((g, "no existe product.json"))
            continue
        p = leer(g)
        for a in quitar.get(g, []):
            if quitar_foto(g, p, a, seco):
                n_q += 1
            else:
                probs.append((g, f"foto a quitar no registrada: {a}"))
        if g in principal:
            imgs = p.get("imagenes", [])
            i = next((k for k, im in enumerate(imgs) if im["archivo"] == principal[g]), None)
            if i is None:
                probs.append((g, f"principal no registrada o quitada: {principal[g]}"))
            elif i > 0:
                imgs.insert(0, imgs.pop(i))
                n_p += 1
        if not p.get("imagenes"):
            sin_fotos.append(g)
        if not seco:
            escribir(g, p)
    return n_q, n_p, sin_fotos


def descripciones(carpeta, fecha, rech, seco, probs):
    keys = ficha_keys()
    n = {"descripcion": 0, "titulo": 0, "ficha": 0, "confirmados": 0, "no_confirmados": 0}
    for f in sorted(glob.glob(os.path.join(carpeta, "resultado_*.json"))):
        for x in json.load(open(f, encoding="utf-8")):
            g = str(x["gtin"])
            p = leer(g)
            ml = p["marketplaces"]["mercadolibre"]
            cat = ml.get("catalogo_id") or (rech.get(g) or {}).get("producto_catalogo", "")
            if x.get("descripcion"):
                p["descripcion"] = x["descripcion"].strip()
                n["descripcion"] += 1
            if x.get("titulo"):
                if len(x["titulo"]) > 60:
                    probs.append((g, "título de más de 60 caracteres; no se aplicó"))
                else:
                    p["titulo"] = x["titulo"]
                    n["titulo"] += 1
            ficha = {k: v for k, v in (x.get("ficha") or {}).items() if k in keys}
            fuera = set(x.get("ficha") or {}) - keys
            if fuera:
                probs.append((g, f"claves de ficha ignoradas: {sorted(fuera)}"))
            if ficha:
                p.setdefault("ficha", {}).update(ficha)
                n["ficha"] += 1
            inv = p["investigacion"]
            notas_nuevas = (x.get("notas") or "").strip()
            if x.get("confirmado"):
                inv.update(estado="verificado", confianza="alta", encontrado_por="gtin")
                inv["notas"] = f"GTIN confirmado en el catálogo de Mercado Libre ({cat}, {fecha}). {notas_nuevas}".strip()
                n["confirmados"] += 1
            else:
                dif = (x.get("diferencias") or "").strip()
                extra = f"Catálogo de Mercado Libre {cat} no coincide: {dif}" if dif else ""
                if x.get("descripcion"):
                    extra = (extra + " " if extra else "") + f"Descripción reescrita el {fecha} con el catálogo y otros vendedores de Mercado Libre."
                inv["notas"] = " ".join(s for s in ((inv.get("notas") or "").strip(), extra, notas_nuevas) if s)
                n["no_confirmados"] += 1
            inv["fecha"] = fecha
            if not seco:
                escribir(g, p)
    return n


def catalogos_rechazados(rech, seco):
    n_cat = n_fotos = 0
    for g, r in rech.items():
        p = leer(g)
        ml = p["marketplaces"]["mercadolibre"]
        if ml.get("catalogo_id") == r["producto_catalogo"]:
            ml["catalogo_id"] = ""
            n_cat += 1
        if r["tipo"] == "otro_producto":
            for im in [im for im in p.get("imagenes", []) if im.get("origen") == "catalogo_ml"]:
                quitar_foto(g, p, im["archivo"], seco)
                n_fotos += 1
        if not seco:
            escribir(g, p)
    return n_cat, n_fotos


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fotos", default=os.path.join(ROOT, "trabajo", "revision_fotos_ml"))
    ap.add_argument("--descripciones", default=os.path.join(ROOT, "trabajo", "descripciones_ml"))
    ap.add_argument("--fecha", default=datetime.date.today().isoformat())
    ap.add_argument("--seco", action="store_true", help="no escribe nada; solo reporta")
    a = ap.parse_args()
    probs = []
    rech = cargar_rechazados()
    n_q, n_p, sin = fotos(a.fotos, a.seco, probs) if os.path.isdir(a.fotos) else (0, 0, [])
    print(f"fotos quitadas: {n_q} · principal cambiada: {n_p} · productos sin fotos tras la revisión: {sin or 'ninguno'}")
    if os.path.isdir(a.descripciones):
        print("descripciones y confirmación:", descripciones(a.descripciones, a.fecha, rech, a.seco, probs))
    n_cat, n_fot = catalogos_rechazados(rech, a.seco)
    print(f"catálogos rechazados: {len(rech)} ({n_cat} catalogo_id quitados, {n_fot} fotos de catálogo de otro producto quitadas)")
    for g, m in probs:
        print(f"  aviso {g}: {m}")


if __name__ == "__main__":
    main()
