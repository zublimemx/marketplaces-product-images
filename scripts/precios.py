#!/usr/bin/env python3
"""Cálculo de precios de Mercado Libre, idéntico a las fórmulas de la hoja Precios del layout y al visor (visor/app.js).

Parámetros por producto (se pueden ajustar uno por uno en el visor y versionarse en data/ajustes_precios.json):
  precio_venta               Precio de venta del catálogo, IVA incluido
  costo_empaque              Costo de empaque y logística interna por pieza (por omisión, config)
  comision                   Comisión de Mercado Libre, IVA incluido (por omisión, según la categoría raíz)
  costo_envio                Envío gratis que cobra Mercado Libre al vendedor si el precio queda en $299 o más
                             (por omisión, estimado por peso con scripts/envios.py, $75 a $150 IVA incluido)
  precio_promedio_otros      Promedio de otros vendedores (solo referencia)
  precio_mejor_vendedor      Precio de la publicación más vendida
  descuento_mejor_vendedor   Cuánto abajo del mejor vendedor se publica (por omisión, config)

Reglas (docs/REGLAS_NEGOCIO.md):
  Precio Marketplaces = precio_venta + costo_empaque
  Precio calculado por tramo = ROUNDUP((Marketplaces + costo fijo del tramo) / (1 − comisión)); el primero que cae en su tramo.
  Si ninguno cae, o si mejor vendedor − descuento ≥ $299 (el precio final quedará en $299 o más):
      calculado = MAX(ROUNDUP((Marketplaces + costo_envio) / (1 − comisión)), 299)
  Precio Meli Final = mejor vendedor − descuento si eso es ≥ calculado; si no, calculado.
"""
import json
import math
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AJUSTES = os.path.join(ROOT, "data", "ajustes_precios.json")
CAMPOS = ("precio_venta", "costo_empaque", "comision", "costo_envio", "precio_promedio_otros", "precio_mejor_vendedor",
          "descuento_mejor_vendedor")


def cargar_config():
    return json.load(open(os.path.join(ROOT, "config", "mercadolibre.json"), encoding="utf-8"))["precios"]


def cargar_ajustes():
    """{gtin: {campo: valor, "nota": ..., "fecha": ...}} de data/ajustes_precios.json (vacío si no existe)."""
    if not os.path.exists(AJUSTES):
        return {}
    return json.load(open(AJUSTES, encoding="utf-8"))


def _roundup(x):
    # ROUNDUP(x, 0) de Excel sin arrastrar errores de punto flotante
    return math.ceil(round(x, 6))


def categoria_raiz(ruta):
    return ruta.split(" > ")[0] if ruta and " > " in ruta else ""


def comision(ruta, cfg):
    raiz = categoria_raiz(ruta)
    return cfg["comision_clasica_por_categoria_raiz"].get(raiz, cfg["comision_clasica_otras_categorias"]) if raiz else cfg["comision_clasica_otras_categorias"]


def costo_fijo(precio, cfg):
    for t in cfg["costos_fijos_clasica"]:
        if precio >= t["desde"] and (t["hasta"] is None or precio < t["hasta"]):
            return t["costo_fijo"]
    return 0


def parametros(precio_venta, ruta, cfg, promedio_otros=None, mejor_vendedor=None, costo_envio=None, ajuste=None):
    """Parámetros efectivos del producto y de dónde sale cada uno ("base" o "ajuste")."""
    par = {
        "precio_venta": precio_venta,
        "costo_empaque": cfg["costo_empaque_logistica_por_pieza"],
        "comision": comision(ruta, cfg),
        "costo_envio": costo_envio if costo_envio is not None else cfg["envio"]["maximo"],
        "precio_promedio_otros": promedio_otros,
        "precio_mejor_vendedor": mejor_vendedor,
        "descuento_mejor_vendedor": cfg["descuento_vs_mejor_vendedor"],
    }
    origen = {}
    for k in CAMPOS:
        if ajuste and k in ajuste:
            par[k] = ajuste[k]
            origen[k] = "ajuste"
    return par, origen


def calcular_parametros(par, cfg):
    """Devuelve las columnas de la hoja Precios a partir de los parámetros efectivos."""
    tramos = cfg["costos_fijos_clasica"]
    umbral = cfg["umbral_envio_gratis_obligatorio"]
    pm = par["precio_venta"] + par["costo_empaque"]
    c = par["comision"]
    envio = par["costo_envio"]
    mejor = par["precio_mejor_vendedor"]
    desc = par["descuento_mejor_vendedor"]
    con_envio = max(_roundup((pm + envio) / (1 - c)), umbral)
    calculado = None
    for t in tramos[:-1]:
        p = _roundup((pm + t["costo_fijo"]) / (1 - c))
        if p < t["hasta"]:
            calculado = p
            break
    if calculado is None or (mejor is not None and mejor - desc >= umbral):
        calculado = con_envio
    final = calculado
    if mejor is not None and mejor - desc >= calculado:
        final = round(mejor - desc, 2)
    fijo = costo_fijo(final, cfg)
    envio_vendedor = envio if final >= umbral else 0
    neto = final * (1 - c) - fijo - envio_vendedor
    return {
        "precio_venta": par["precio_venta"],
        "costo_empaque": par["costo_empaque"],
        "precio_marketplaces": round(pm, 2),
        "comision": c,
        "costo_envio": envio,
        "precio_meli_calculado": calculado,
        "precio_promedio_otros": par["precio_promedio_otros"],
        "precio_mejor_vendedor": mejor,
        "descuento_mejor_vendedor": desc,
        "precio_meli_final": final,
        "diferencia_mejor_vendedor": (final / mejor - 1) if mejor else None,
        "costo_fijo": fijo,
        "envio_vendedor": envio_vendedor,
        "ingreso_neto": round(neto, 2),
        "margen": round(neto - pm, 2),
    }


def calcular(precio_venta, ruta_categoria, cfg, promedio_otros=None, mejor_vendedor=None, costo_envio=None, ajuste=None):
    par, _ = parametros(precio_venta, ruta_categoria, cfg, promedio_otros, mejor_vendedor, costo_envio, ajuste)
    return calcular_parametros(par, cfg)
