#!/usr/bin/env python3
"""Genera los datos del visor de productos (visor/data/productos.js).

Uso:
  python scripts/build_visor.py [--precios insumos/precios_existencias.csv] [--competencia insumos/competencia_meli.csv]
                                [--base-imagenes ../products] [--salida visor/data/productos.js]

Une product.json, precios y existencias, competencia de Mercado Libre y los precios calculados con las mismas
fórmulas del layout (scripts/precios.py), y califica cada producto con los indicadores de config/indicadores.json.
Si falta el CSV de precios, usa la hoja Precios del layout versionado (layouts/mercadolibre/layout_mercadolibre.xlsx).
El archivo es JavaScript (window.CATALOGO = …) para que el visor abra también con doble clic, sin servidor.
"""
import argparse
import csv
import datetime
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import precios  # noqa: E402
from revisar_fotos import fondo_no_blanco  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, "trabajo", "cache_fondo_fotos.json")


def num(v):
    try:
        return float(v) if v not in ("", None) else None
    except (TypeError, ValueError):
        return None


def leer_precios(path):
    datos = {}
    if path and os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                datos[r["gtin"]] = {"precio": float(r["precio"]), "stock": int(float(r["stock"])), "orden": len(datos) + 1}
        return datos
    xlsx = os.path.join(ROOT, "layouts", "mercadolibre", "layout_mercadolibre.xlsx")
    if not os.path.exists(xlsx):
        sys.exit("No hay insumos/precios_existencias.csv ni layout versionado para tomar precios y existencias")
    import openpyxl
    wb = openpyxl.load_workbook(xlsx, read_only=True)
    pre = list(wb["Precios"].iter_rows(min_row=2, values_only=True))
    lay = list(wb["Layout Mercado Libre"].iter_rows(min_row=2, values_only=True))
    for i, (rp, rl) in enumerate(zip(pre, lay), 1):
        datos[str(rp[0])] = {"precio": float(rp[3]), "stock": int(rl[6] or 0), "orden": i}
    return datos


def leer_competencia(path):
    comp = {}
    if path and os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                comp[r["gtin"]] = (num(r.get("precio_promedio_otros")), num(r.get("precio_mejor_vendedor")), r.get("metodo_mejor_vendedor", ""))
    return comp


def fondo_gris(path, cache):
    st = os.stat(path)
    clave = f"{os.path.relpath(path, ROOT)}|{st.st_size}|{int(st.st_mtime)}"
    if clave not in cache:
        cache[clave] = fondo_no_blanco(path)
    return cache[clave]


def ind_descripcion(p, reglas):
    d = p.get("descripcion") or ""
    inv = p["investigacion"]
    secs = sum(1 for s in reglas["secciones_reconocidas"] if re.search(rf"(^|\n){re.escape(s)}:", d))
    n = len(d)
    base = f"{n:,} caracteres, {secs} secciones"
    if inv["estado"] != reglas["regular"]["estado"]:
        return "mala", ("Sin verificar: datos deducidos del nombre" if inv["estado"] == "sin_verificar" else "Pendiente de investigar")
    if n < reglas["regular"]["min_caracteres"]:
        return "mala", f"Muy corta: {base}"
    b = reglas["buena"]
    if inv.get("confianza") in b["confianza"] and n >= b["min_caracteres"] and secs >= b["min_secciones"]:
        return "buena", f"Verificada con confianza {inv.get('confianza')}; {base}"
    faltas = []
    if inv.get("confianza") not in b["confianza"]:
        faltas.append(f"confianza {inv.get('confianza') or 'sin dato'}")
    if n < b["min_caracteres"]:
        faltas.append(f"menos de {b['min_caracteres']} caracteres")
    if secs < b["min_secciones"]:
        faltas.append(f"menos de {b['min_secciones']} secciones")
    return "regular", f"{base}; " + ", ".join(faltas)


def ind_fotos(imgs, reglas):
    if not imgs:
        return "mala", "Sin fotos"
    utiles = [im["u"] for im in imgs]
    if max(utiles) < reglas["regular"]["min_lado_util"]:
        return "mala", f"{len(imgs)} foto(s), producto de {max(utiles)} px como máximo (mínimo {reglas['regular']['min_lado_util']})"
    b = reglas["buena"]
    principal = imgs[0]
    faltas = []
    if len(imgs) < b["min_fotos"]:
        faltas.append(f"solo {len(imgs)} foto")
    if principal["u"] < b["min_lado_util_principal"]:
        faltas.append(f"principal de {principal['u']} px")
    if b.get("principal_sin_fondo_gris") and principal.get("gris"):
        faltas.append("principal con posible fondo gris")
    if not faltas:
        return "buena", f"{len(imgs)} fotos; principal de {principal['u']} px"
    return "regular", f"{len(imgs)} foto(s); " + ", ".join(faltas)


def ind_precios(pr, reglas):
    falta = [txt for k, txt in reglas["requeridos"].items() if pr.get(k) is None]
    if not falta:
        return "completos", "Se conocen los tres precios"
    return "incompletos", "Falta: " + "; ".join(falta)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--precios", default=os.path.join(ROOT, "insumos", "precios_existencias.csv"))
    ap.add_argument("--competencia", default=os.path.join(ROOT, "insumos", "competencia_meli.csv"))
    ap.add_argument("--base-imagenes", default="../products", help="ruta o URL base de las fotos, vista desde visor/index.html")
    ap.add_argument("--salida", default=os.path.join(ROOT, "visor", "data", "productos.js"))
    a = ap.parse_args()

    cfg = precios.cargar_config()
    reglas = json.load(open(os.path.join(ROOT, "config", "indicadores.json"), encoding="utf-8"))
    pv = leer_precios(a.precios)
    comp = leer_competencia(a.competencia)
    cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}

    productos = []
    for g, base in pv.items():
        p = json.load(open(os.path.join(ROOT, "products", g, "product.json"), encoding="utf-8"))
        ml = p["marketplaces"]["mercadolibre"]
        prom, mejor, metodo = comp.get(g, (None, None, ""))
        pr = precios.calcular(base["precio"], ml["categoria_ruta"], cfg, prom, mejor)
        imgs = []
        for im in p.get("imagenes", []):
            f = os.path.join(ROOT, "products", g, "images", im["archivo"])
            if not os.path.exists(f):
                continue
            imgs.append({"src": f"{a.base_imagenes.rstrip('/')}/{g}/images/{im['archivo']}", "u": im.get("lado_util", 0),
                         "o": im.get("origen", ""), "gris": fondo_gris(f, cache), "fuente": im.get("pagina") or im.get("fuente_url", "")})
        d_ind, d_mot = ind_descripcion(p, reglas["descripcion"])
        f_ind, f_mot = ind_fotos(imgs, reglas["fotos"])
        p_ind, p_mot = ind_precios(pr, reglas["precios"])
        ruta = ml["categoria_ruta"] or ""
        productos.append({
            "orden": base["orden"], "gtin": g, "titulo": p["titulo"] or p["nombre_sistema"], "nombre_sistema": p["nombre_sistema"],
            "linea": p["linea"], "categoria_id": ml["categoria_id"], "categoria_ruta": ruta,
            "categoria": ruta.split(" > ")[-1] if ruta else "Sin categoría",
            "catalogo_id": ml.get("catalogo_id", ""), "categoria_rx_sugerida": ml.get("categoria_rx_sugerida", ""),
            "stock": base["stock"], "precios": {k: pr[k] for k in ("precio_venta", "precio_marketplaces", "comision", "precio_meli_calculado",
                                                                  "precio_promedio_otros", "precio_mejor_vendedor", "precio_meli_final",
                                                                  "diferencia_mejor_vendedor", "costo_fijo", "envio_vendedor", "ingreso_neto", "margen")},
            "metodo_mejor_vendedor": metodo,
            "imagenes": imgs, "descripcion": p["descripcion"], "ficha": p.get("ficha", {}), "receta_mx": p.get("receta_mx", ""),
            "url_oficial": p.get("url_oficial", ""), "fuentes": p.get("fuentes", []),
            "investigacion": {k: p["investigacion"].get(k, "") for k in ("estado", "confianza", "encontrado_por", "notas", "notas_imagenes", "sesion")},
            "ind": {"descripcion": d_ind, "descripcion_motivo": d_mot, "fotos": f_ind, "fotos_motivo": f_mot, "precios": p_ind, "precios_motivo": p_mot},
        })
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    json.dump(cache, open(CACHE, "w"))
    datos = {"generado": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "total": len(productos),
             "reglas": reglas, "productos": productos}
    os.makedirs(os.path.dirname(a.salida), exist_ok=True)
    with open(a.salida, "w", encoding="utf-8") as fh:
        fh.write("// Generado por scripts/build_visor.py. No editar a mano.\nwindow.CATALOGO = ")
        json.dump(datos, fh, ensure_ascii=False, separators=(",", ":"))
        fh.write(";\n")
    cuenta = {}
    for pr_ in productos:
        for k in ("descripcion", "fotos", "precios"):
            cuenta.setdefault(k, {}).setdefault(pr_["ind"][k], 0)
            cuenta[k][pr_["ind"][k]] += 1
    print(f"{len(productos)} productos -> {os.path.relpath(a.salida, ROOT)} ({os.path.getsize(a.salida) / 1e6:.1f} MB)")
    print(json.dumps(cuenta, ensure_ascii=False))


if __name__ == "__main__":
    main()
