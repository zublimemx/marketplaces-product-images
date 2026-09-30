#!/usr/bin/env python3
"""Cálculo de precios de Mercado Libre, idéntico a las fórmulas de la hoja Precios del layout.

Lo usan scripts/build_visor.py y cualquier generador que necesite los mismos precios sin abrir Excel.
Reglas en docs/REGLAS_NEGOCIO.md; parámetros en config/mercadolibre.json.
"""
import json
import math
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def cargar_config():
    return json.load(open(os.path.join(ROOT, "config", "mercadolibre.json"), encoding="utf-8"))["precios"]


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


def calcular(precio_venta, ruta_categoria, cfg, promedio_otros=None, mejor_vendedor=None):
    """Devuelve un dict con las columnas de la hoja Precios para un producto."""
    tramos = cfg["costos_fijos_clasica"]
    marketplaces = precio_venta + cfg["costo_empaque_logistica_por_pieza"]
    c = comision(ruta_categoria, cfg)
    envio = cfg["costo_envio_vendedor_estimado"]
    umbral = cfg["umbral_envio_gratis_obligatorio"]
    calculado = None
    for t in tramos[:-1]:
        p = _roundup((marketplaces + t["costo_fijo"]) / (1 - c))
        if p < t["hasta"]:
            calculado = p
            break
    if calculado is None:
        calculado = max(_roundup((marketplaces + envio) / (1 - c)), umbral)
    final = calculado
    if promedio_otros is not None and promedio_otros - cfg["descuento_vs_promedio_competencia"] >= calculado:
        final = round(promedio_otros - cfg["descuento_vs_promedio_competencia"], 2)
    fijo = costo_fijo(final, cfg)
    envio_vendedor = envio if final >= umbral else 0
    neto = final * (1 - c) - fijo - envio_vendedor
    return {
        "precio_venta": precio_venta,
        "precio_marketplaces": round(marketplaces, 2),
        "comision": c,
        "precio_meli_calculado": calculado,
        "precio_promedio_otros": promedio_otros,
        "precio_mejor_vendedor": mejor_vendedor,
        "precio_meli_final": final,
        "diferencia_mejor_vendedor": (final / mejor_vendedor - 1) if mejor_vendedor else None,
        "costo_fijo": fijo,
        "envio_vendedor": envio_vendedor,
        "ingreso_neto": round(neto, 2),
        "margen": round(neto - marketplaces, 2),
    }
