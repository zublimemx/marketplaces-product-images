#!/usr/bin/env python3
"""Estima el costo del envío gratis que Mercado Libre cobra al vendedor (precios de $299 o más).

Uso:
  python scripts/envios.py                 # escribe data/envios.csv y muestra el resumen
  python scripts/envios.py --gtin 7501...  # muestra el cálculo de un producto

El costo sale de config/mercadolibre.json → precios.envio (rango $75–$150, IVA incluido) según el peso cobrable:
el mayor entre el peso real estimado y el peso volumétrico estimado (largo × ancho × alto / divisor).
Si product.json trae marketplaces.mercadolibre.paquete {peso_g, largo_cm, ancho_cm, alto_cm} (por ejemplo, de la
API de Mercado Libre), se usa ese dato. Si no, se estima con la ficha técnica (contenido neto, unidad, unidades por
envase) y el título. Es un supuesto: cada producto se puede corregir en el visor (costo de envío) y versionarse en
data/ajustes_precios.json.
"""
import argparse
import csv
import glob
import json
import os
import re
import unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SALIDA = os.path.join(ROOT, "data", "envios.csv")
CAMPOS = ["gtin", "peso_real_kg", "peso_volumetrico_kg", "peso_cobrable_kg", "tamano", "costo_envio", "base"]

MEDICAMENTO = {"tabletas", "tableta", "capsulas", "capsula", "comprimidos", "comprimido", "grageas", "pastillas", "supositorios",
               "ovulos", "dosis", "sobres", "sobre", "ampolletas", "ampolleta", "carteras", "tabletas efervescentes", "paletas",
               "frasco ampula", "frascos", "sticks", "parches", "tiras", "lancetas", "gasas", "pads", "tampones", "condones"}
PESO_UNIDAD = {"sobres": 0.006, "sobre": 0.006, "ampolletas": 0.012, "ampolleta": 0.012, "frascos": 0.02, "sticks": 0.012,
               "jeringas": 0.008, "tiras": 0.002, "lancetas": 0.001, "gasas": 0.004, "pads": 0.002, "tampones": 0.006,
               "condones": 0.004, "paletas": 0.008, "rollos": 0.03, "carteras": 0.02}


def _norm(s):
    s = unicodedata.normalize("NFD", (s or "").lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn").strip()


def _num(v):
    try:
        return float(str(v).replace(",", "."))
    except (TypeError, ValueError):
        return None


def cargar_config():
    return json.load(open(os.path.join(ROOT, "config", "mercadolibre.json"), encoding="utf-8"))["precios"]["envio"]


def costo_por_peso(kg, cfg):
    for t in cfg["tramos"]:
        if t["hasta_kg"] is None or kg <= t["hasta_kg"]:
            return t["costo"]
    return cfg["maximo"]


def _contenido_titulo(titulo):
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(kg|g|gr|ml|l|lt|litros?|oz)\b", _norm(titulo))
    if not m:
        return None, None
    u = {"gr": "g", "lt": "l", "litro": "l", "litros": "l"}.get(m.group(2), m.group(2))
    return _num(m.group(1)), u


def _piezas_titulo(titulo):
    m = re.search(r"(\d+)\s*(piezas|pzas|panales|unidades|toallitas)", _norm(titulo))
    return int(m.group(1)) if m else None


def _en_titulo(valor, t):
    """¿Aparece la cantidad en el título (normalizado)? 250 → «250 ml», 0.5 → «0.5 l»."""
    if not valor:
        return False
    txt = f"{valor:g}"
    return re.search(rf"(?<![\d.]){re.escape(txt)}\s*(kg|g|gr|ml|l|lt|litros?|oz)\b", t) is not None


def estimar(p, cfg=None):
    """Devuelve dict con peso_real_kg, peso_volumetrico_kg, peso_cobrable_kg, tamano, costo_envio y base (explicación)."""
    cfg = cfg or cargar_config()
    div = cfg.get("divisor_volumetrico", 5000)
    paq = (p.get("marketplaces", {}).get("mercadolibre", {}) or {}).get("paquete") or {}
    if paq.get("peso_g"):
        real = paq["peso_g"] / 1000
        vol = (paq.get("largo_cm", 0) * paq.get("ancho_cm", 0) * paq.get("alto_cm", 0)) / div
        base = f"Paquete de Mercado Libre: {paq['peso_g']:.0f} g"
        return _resultado(real, vol, base, cfg)

    f = p.get("ficha") or {}
    titulo = p.get("titulo") or p.get("nombre_sistema") or ""
    t = _norm(titulo)
    unidad = _norm(f.get("unidad_contenido"))
    cont = _num(f.get("contenido_neto"))
    uds = _num(f.get("unidades_por_envase")) or 1

    if re.search(r"\bpanales\b", t):
        n = (cont if unidad in ("piezas", "pieza") and cont else None) or _piezas_titulo(titulo) or 40
        extra = 0.4 if "toallita" in t else 0
        return _resultado(n * 0.035 + 0.1 + extra, n * 0.08 + extra, f"Pañales: {n:.0f} piezas (bulto voluminoso)", cfg)
    if "toallita" in t:
        n = (cont if cont and unidad in ("piezas", "toallitas", "pieza") else None) or _piezas_titulo(titulo) or 80
        return _resultado(n * 0.0065 + 0.05, n * 0.006, f"Toallitas: {n:.0f} piezas", cfg)
    if "vitrolero" in t:
        return _resultado(0.8, 0.6, "Vitrolero de 100 piezas", cfg)
    if "jeringa" in t and unidad in ("ml", "piezas", "jeringas", ""):
        n = _piezas_titulo(titulo) or (uds if uds > 1 else 1)
        kg = 0.05 + n * 0.008
        return _resultado(kg, kg * 1.5, f"Jeringas: {n:g} piezas", cfg)
    if re.search(r"biberon|calentador|termometro|baumanometro|glucometro|oximetro|nebulizador|tensiometro", t):
        return _resultado(0.5, 0.5, "Aparato o accesorio: peso supuesto de 500 g", cfg)

    if unidad in ("g", "kg", "ml", "l", "oz") or (not unidad and _contenido_titulo(titulo)[0]):
        if not unidad or not cont:
            cont, unidad = _contenido_titulo(titulo)
        kg = {"g": cont / 1000, "kg": cont, "ml": cont / 1000 * 1.05, "l": cont * 1.05, "oz": cont * 0.03}[unidad]
        por_pieza = uds > 1 and _en_titulo(cont, t) and not _en_titulo(cont / uds, t)
        if por_pieza:  # «250 ml Caja con 36 piezas»: el contenido es por pieza
            kg *= uds
        real = kg * 1.15 + 0.05
        vol = kg * 1.3 * 1000 / div * 1.2
        return _resultado(real, vol, f"Contenido {cont:g} {unidad}" + (f" × {uds:g} piezas" if por_pieza else ""), cfg)

    if unidad in PESO_UNIDAD or unidad in MEDICAMENTO or unidad == "jeringas":
        n = cont or uds or 1
        kg = 0.08 + n * PESO_UNIDAD.get(unidad, 0.0015)
        vol = kg * 1.5
        return _resultado(kg, vol, f"Caja con {n:g} {unidad}", cfg)

    if unidad == "m":
        return _resultado(0.08, 0.05, "Rollo o carrete", cfg)
    if unidad in ("piezas", "pieza", "panuelos"):
        n = cont or 1
        kg = 0.1 + n * 0.004
        return _resultado(kg, kg * 1.5, f"{n:g} piezas", cfg)
    if re.search(r"ampolleta|tableta|capsula|ovulo|frasco|aplicacion|comprimido|inyectable|prueba", t):
        return _resultado(0.15, 0.15, "Medicamento o prueba en caja: peso supuesto de 150 g", cfg)
    return _resultado(0.4, 0.4, "Sin datos de contenido: peso supuesto de 400 g", cfg)


def _resultado(real, vol, base, cfg):
    cobrable = max(real, vol)
    tam = "chico" if cobrable <= 0.5 else "mediano" if cobrable <= 2 else "grande"
    costo = min(max(costo_por_peso(cobrable, cfg), cfg["minimo"]), cfg["maximo"])
    return {"peso_real_kg": round(real, 2), "peso_volumetrico_kg": round(vol, 2), "peso_cobrable_kg": round(cobrable, 2),
            "tamano": tam, "costo_envio": costo, "base": base}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--gtin")
    a = ap.parse_args()
    cfg = cargar_config()
    if a.gtin:
        p = json.load(open(os.path.join(ROOT, "products", a.gtin, "product.json"), encoding="utf-8"))
        print(json.dumps(estimar(p, cfg), ensure_ascii=False, indent=2))
        return
    filas = []
    for fn in sorted(glob.glob(os.path.join(ROOT, "products", "*", "product.json"))):
        p = json.load(open(fn, encoding="utf-8"))
        filas.append({"gtin": p["gtin"], **estimar(p, cfg)})
    os.makedirs(os.path.dirname(SALIDA), exist_ok=True)
    with open(SALIDA, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=CAMPOS)
        w.writeheader()
        w.writerows(filas)
    cuenta = {}
    for f in filas:
        cuenta[f["costo_envio"]] = cuenta.get(f["costo_envio"], 0) + 1
    print(f"{len(filas)} productos -> {os.path.relpath(SALIDA, ROOT)}")
    print("productos por costo:", dict(sorted(cuenta.items())))


if __name__ == "__main__":
    main()
