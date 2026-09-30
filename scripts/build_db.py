#!/usr/bin/env python3
"""Base de datos SQLite del catálogo: data/catalogo.db (versionada). Reúne en tablas todo lo que hay en el repositorio:
fichas (products/<GTIN>/product.json), fotos (registro; los archivos siguen en products/<GTIN>/images/), precios
calculados, competencia de Mercado Libre, precios en otros marketplaces, costos de envío, ajustes, descartes,
indicadores y pendientes. Se abre con cualquier cliente SQLite (DB Browser for SQLite, DBeaver, Excel vía ODBC, Python).

Uso:
  python scripts/build_db.py               # reconstruye data/catalogo.db (después de scripts/build_visor.py)
  python scripts/build_db.py --verificar   # falla si data/catalogo.db no corresponde a los datos actuales (lo usa CI)

La base se genera desde los archivos del repositorio (fuente de verdad: product.json y los CSV/JSON de data/); los
cambios se hacen con los scripts de siempre y luego se regenera. Tablas y columnas se documentan en la tabla
«diccionario» y en docs/CONTRATOS.md §14. Consultas de ejemplo en docs/BASE_DE_DATOS.md.
"""
import argparse
import csv
import glob
import json
import os
import sqlite3
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import build_mercadolibre as bml  # noqa: E402
import otros_marketplaces as otros_mk  # noqa: E402

SALIDA = os.path.join(ROOT, "data", "catalogo.db")
VISOR = os.path.join(ROOT, "visor", "data", "productos.js")
FICHA = [k for k, _ in bml.FICHA_COLS]
PRECIO_CAMPOS = ["precio_venta", "costo_empaque", "precio_marketplaces", "comision", "costo_envio", "precio_meli_calculado",
                 "precio_promedio_otros", "precio_mejor_vendedor", "descuento_mejor_vendedor", "precio_meli_final",
                 "diferencia_mejor_vendedor", "costo_fijo", "envio_vendedor", "ingreso_neto", "margen"]

# (tabla, descripción, [(columna, tipo, descripción)])
ESQUEMA = [
    ("productos", "Un renglón por producto (GTIN). Datos generales, investigación, indicadores y resumen de precios en otros marketplaces.", [
        ("gtin", "TEXT PRIMARY KEY", "Código de barras (GTIN/EAN); también es el SKU"),
        ("sku", "TEXT", "SKU (igual al GTIN)"),
        ("orden", "INTEGER", "Prioridad por ventas (1 = el más vendido)"),
        ("linea", "TEXT", "Línea de origen: Farma, Mark o Farma + Mark"),
        ("nombre_sistema", "TEXT", "Nombre abreviado en el sistema (ERP)"),
        ("titulo", "TEXT", "Título para marketplaces (máx. 60 caracteres)"),
        ("descripcion", "TEXT", "Descripción en texto plano con secciones"),
        ("receta_mx", "TEXT", "Receta en México según principio activo: No, Sí, No aplica, Revisar"),
        ("url_oficial", "TEXT", "Página oficial del producto o marca"),
        ("stock", "INTEGER", "Existencia en el sistema"),
        ("estado_investigacion", "TEXT", "pendiente, sin_verificar o verificado"),
        ("confianza", "TEXT", "alta, media o baja"),
        ("encontrado_por", "TEXT", "gtin, nombre o no_encontrado"),
        ("notas_investigacion", "TEXT", "Notas y dudas de la investigación"),
        ("notas_imagenes", "TEXT", "Notas de las fotos"),
        ("fecha_investigacion", "TEXT", "Fecha de la última investigación (AAAA-MM-DD)"),
        ("sesion", "INTEGER", "Sesión de investigación"),
        ("ind_descripcion", "TEXT", "Indicador de descripción: buena, regular, mala"),
        ("ind_fotos", "TEXT", "Indicador de fotos: buena, regular, mala"),
        ("ind_precios", "TEXT", "Indicador de precios: completos, incompletos"),
        ("num_fotos", "INTEGER", "Fotos registradas"),
        ("precio_otros_marketplaces", "REAL", "Precio de venta en otros marketplaces: el más bajo encontrado (detalle en precios_otros_marketplaces)"),
        ("otros_marketplaces", "TEXT", "Marketplace o tienda de ese precio"),
        ("num_otros_marketplaces", "INTEGER", "Marketplaces con precio para este producto"),
    ]),
    ("fichas", "Ficha técnica, una columna por atributo (vacía si no aplica).", [("gtin", "TEXT PRIMARY KEY REFERENCES productos(gtin)", "GTIN")]
     + [(k, "TEXT", h) for k, h in bml.FICHA_COLS]),
    ("imagenes", "Fotos del producto en orden (la 1 es la principal). El archivo está en products/<GTIN>/images/.", [
        ("gtin", "TEXT REFERENCES productos(gtin)", "GTIN"),
        ("posicion", "INTEGER", "Orden de la foto (1 = principal)"),
        ("archivo", "TEXT", "Nombre del archivo"),
        ("ruta", "TEXT", "Ruta en el repositorio"),
        ("url_github", "TEXT", "URL pública (funciona mientras el repositorio es público)"),
        ("origen", "TEXT", "fabricante, catalogo_ml o tienda"),
        ("fuente_url", "TEXT", "URL de la imagen original"),
        ("pagina", "TEXT", "Página de donde se tomó"),
        ("ancho_original", "INTEGER", "Ancho original en px"),
        ("alto_original", "INTEGER", "Alto original en px"),
        ("lado_final", "INTEGER", "Lado del JPG guardado en px"),
        ("lado_util", "INTEGER", "Lado del producto dentro de la foto en px"),
        ("fecha", "TEXT", "Fecha de descarga"),
    ]),
    ("fuentes", "Páginas consultadas en la investigación.", [
        ("gtin", "TEXT REFERENCES productos(gtin)", "GTIN"), ("posicion", "INTEGER", "Orden"), ("url", "TEXT", "URL")]),
    ("mercadolibre", "Datos de publicación en Mercado Libre.", [
        ("gtin", "TEXT PRIMARY KEY REFERENCES productos(gtin)", "GTIN"),
        ("categoria_id", "TEXT", "Categoría hoja (MLM…)"),
        ("categoria_ruta", "TEXT", "Ruta de la categoría"),
        ("categoria_rx_sugerida", "TEXT", "Categoría con receta sugerida para revisión"),
        ("catalogo_id", "TEXT", "Producto de catálogo de Mercado Libre (MLM…)"),
        ("descartado", "INTEGER", "1 si no entra al layout de importación"),
        ("descartado_motivo", "TEXT", "Motivo del descarte"),
        ("descartado_fecha", "TEXT", "Fecha del descarte"),
        ("catalogo_rechazado", "TEXT", "Catálogo del GTIN que no corresponde al producto (no se usa)"),
        ("catalogo_rechazado_motivo", "TEXT", "Por qué se rechazó"),
    ]),
    ("precios_meli", "Precio de publicación en Mercado Libre calculado con las reglas del repositorio (docs/REGLAS_NEGOCIO.md).", [
        ("gtin", "TEXT PRIMARY KEY REFERENCES productos(gtin)", "GTIN"),
        ("precio_venta", "REAL", "Precio de venta en tienda (sistema, IVA incluido)"),
        ("costo_empaque", "REAL", "Costo de empaque y logística por pieza"),
        ("precio_marketplaces", "REAL", "Precio de venta + empaque"),
        ("comision", "REAL", "Comisión Meli (fracción, IVA incluido)"),
        ("costo_envio", "REAL", "Costo de envío si el precio queda en $299 o más"),
        ("precio_meli_calculado", "REAL", "Precio Meli calculado"),
        ("precio_promedio_otros", "REAL", "Promedio de otros vendedores en Meli"),
        ("precio_mejor_vendedor", "REAL", "Precio del mejor vendedor en Meli"),
        ("descuento_mejor_vendedor", "REAL", "Descuento contra el mejor vendedor"),
        ("precio_meli_final", "REAL", "Precio con el que se publica"),
        ("diferencia_mejor_vendedor", "REAL", "Precio final / mejor vendedor − 1"),
        ("costo_fijo", "REAL", "Costo fijo de Meli aplicado"),
        ("envio_vendedor", "REAL", "Envío a cargo del vendedor"),
        ("ingreso_neto", "REAL", "Ingreso neto estimado"),
        ("margen", "REAL", "Ingreso neto − precio de venta marketplaces"),
        ("metodo_mejor_vendedor", "TEXT", "Cómo se eligió el mejor vendedor"),
        ("parametros_ajustados", "TEXT", "Parámetros con ajuste manual (data/ajustes_precios.json)"),
        ("envio_peso_kg", "REAL", "Peso cobrable estimado (kg)"),
        ("envio_tamano", "TEXT", "chico, mediano o grande"),
        ("envio_base", "TEXT", "De qué dato sale el peso"),
    ]),
    ("competencia_meli", "Competencia en Mercado Libre obtenida con la API (data/competencia_meli.csv).", [
        ("gtin", "TEXT PRIMARY KEY REFERENCES productos(gtin)", "GTIN")] + [(c, "TEXT" if c in ("producto_catalogo", "nombre_catalogo", "item_mejor_vendedor", "vendedor_mejor", "metodo_mejor_vendedor", "fecha", "nota") else "REAL", c.replace("_", " ")) for c in (
            "producto_catalogo", "nombre_catalogo", "publicaciones_otros", "precio_promedio_otros", "precio_mediana_otros", "precio_min_otros",
            "precio_max_otros", "publicaciones_atipicas", "precio_mejor_vendedor", "item_mejor_vendedor", "vendedor_mejor",
            "ventas_vendedor_mejor", "metodo_mejor_vendedor", "fecha", "nota")]),
    ("precios_otros_marketplaces", "Precio de venta del mismo producto en otras tiendas en línea (data/precios_otros_marketplaces.csv).", [
        ("gtin", "TEXT REFERENCES productos(gtin)", "GTIN"),
        ("marketplace", "TEXT", "Otros marketplaces: nombre de la tienda (Farmacias del Ahorro, Walmart, Amazon…)"),
        ("precio", "REAL", "Precio de venta en otros marketplaces (IVA incluido; el de oferta si hay)"),
        ("precio_lista", "REAL", "Precio normal cuando el anterior es de oferta"),
        ("url", "TEXT", "Página del producto en esa tienda"),
        ("fecha", "TEXT", "Fecha en que se tomó el precio"),
        ("nota", "TEXT", "Observaciones"),
        ("origen", "TEXT", "Quién lo capturó (agente, dueño)"),
    ]),
    ("comparacion_precios", "Quién tiene el precio más alto y más bajo por producto: nosotros (Precio Meli final y precio de tienda), el mejor vendedor de Meli y otros marketplaces.", [
        ("gtin", "TEXT PRIMARY KEY REFERENCES productos(gtin)", "GTIN"),
        ("nuestro_precio_meli", "REAL", "Nuestro Precio Meli final"),
        ("nuestro_precio_tienda", "REAL", "Nuestro precio de venta en tienda"),
        ("precio_mas_alto", "REAL", "Precio más alto entre los competidores (Meli mejor vendedor y otros marketplaces)"),
        ("quien_mas_alto", "TEXT", "Quién tiene el precio más alto, incluyéndonos (Nosotros = Precio Meli final)"),
        ("precio_mas_bajo", "REAL", "Precio más bajo entre los competidores"),
        ("quien_mas_bajo", "TEXT", "Quién tiene el precio más bajo, incluyéndonos"),
        ("competidores", "INTEGER", "Competidores con precio"),
        ("posicion_meli", "TEXT", "Nuestro Precio Meli final: mas_caro, mas_barato, intermedio o sin_comparacion"),
        ("posicion_tienda", "TEXT", "Nuestro precio de tienda: mas_caro, mas_barato, intermedio o sin_comparacion"),
        ("diferencia_vs_mas_bajo", "REAL", "Precio Meli final / precio más bajo de competidores − 1"),
    ]),
    ("envios", "Costo de envío estimado por peso (data/envios.csv).", [
        ("gtin", "TEXT PRIMARY KEY REFERENCES productos(gtin)", "GTIN"), ("peso_real_kg", "REAL", "Peso estimado"),
        ("peso_volumetrico_kg", "REAL", "Peso volumétrico"), ("peso_cobrable_kg", "REAL", "Mayor de los dos"),
        ("tamano", "TEXT", "chico, mediano o grande"), ("costo_envio", "REAL", "Costo estimado ($75 a $150)"), ("base", "TEXT", "Dato usado")]),
    ("ajustes_precios", "Parámetros de precio ajustados a mano (data/ajustes_precios.json).", [
        ("gtin", "TEXT REFERENCES productos(gtin)", "GTIN"), ("campo", "TEXT", "Parámetro"), ("valor", "REAL", "Valor"),
        ("nota", "TEXT", "Nota"), ("fecha", "TEXT", "Fecha")]),
    ("catalogos_rechazados", "Catálogos de Meli que no corresponden al GTIN (data/catalogo_ml_rechazados.csv).", [
        ("gtin", "TEXT PRIMARY KEY REFERENCES productos(gtin)", "GTIN"), ("producto_catalogo", "TEXT", "Catálogo rechazado"),
        ("nombre_catalogo", "TEXT", "Nombre en Meli"), ("tipo", "TEXT", "otro_producto u otra_presentacion"), ("motivo", "TEXT", "Motivo"), ("fecha", "TEXT", "Fecha")]),
    ("pendientes", "Errores, pendientes y mejoras por producto (config/pendientes.json); los descartados se incluyen con descartado = 1.", [
        ("gtin", "TEXT REFERENCES productos(gtin)", "GTIN"), ("codigo", "TEXT", "Código del pendiente"), ("tipo", "TEXT", "error, pendiente o mejora"),
        ("titulo", "TEXT", "Título"), ("detalle", "TEXT", "Detalle"), ("accion", "TEXT", "Acción sugerida"), ("descartado", "INTEGER", "1 si el producto está descartado")]),
    ("diccionario", "Descripción de cada tabla y columna.", [("tabla", "TEXT", "Tabla"), ("columna", "TEXT", "Columna (vacía = la tabla)"), ("descripcion", "TEXT", "Descripción")]),
    ("meta", "Datos de la generación.", [("clave", "TEXT PRIMARY KEY", "Clave"), ("valor", "TEXT", "Valor")]),
]

VISTAS = {
    "v_productos": """SELECT p.gtin, p.orden, p.linea, p.titulo, p.nombre_sistema, f.marca, f.presentacion, m.categoria_ruta, p.stock,
        pm.precio_venta, pm.precio_meli_final, pm.precio_mejor_vendedor, p.precio_otros_marketplaces, p.otros_marketplaces,
        p.ind_descripcion, p.ind_fotos, p.ind_precios, m.descartado
      FROM productos p JOIN fichas f USING (gtin) JOIN mercadolibre m USING (gtin) JOIN precios_meli pm USING (gtin)""",
    "v_comparacion_precios": """SELECT p.gtin, p.orden, p.titulo, c.nuestro_precio_tienda, c.nuestro_precio_meli, pm.precio_mejor_vendedor,
        pm.precio_promedio_otros, p.precio_otros_marketplaces, p.otros_marketplaces, c.precio_mas_alto, c.quien_mas_alto,
        c.precio_mas_bajo, c.quien_mas_bajo, c.posicion_meli, c.posicion_tienda, c.diferencia_vs_mas_bajo, m.descartado
      FROM productos p JOIN comparacion_precios c USING (gtin) JOIN precios_meli pm USING (gtin) JOIN mercadolibre m USING (gtin)""",
}


def num(v):
    if v in (None, ""):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def leer_visor():
    t = open(VISOR, encoding="utf-8").read()
    d = json.loads(t[t.index("{"):t.rstrip().rstrip(";").rindex("}") + 1])
    return d


def posicion(nuestro, precios):
    """precios: lista de precios de competidores."""
    if nuestro is None or not precios:
        return "sin_comparacion"
    if nuestro < min(precios) - 0.005:
        return "mas_barato"
    if nuestro > max(precios) + 0.005:
        return "mas_caro"
    if abs(nuestro - min(precios)) < 0.005:
        return "mas_barato"
    if abs(nuestro - max(precios)) < 0.005:
        return "mas_caro"
    return "intermedio"


def comparar(pr, otros):
    comp = []
    if pr.get("precio_mejor_vendedor") is not None:
        comp.append(("Mercado Libre (mejor vendedor)", pr["precio_mejor_vendedor"]))
    comp += [(r["marketplace"], r["precio"]) for r in otros]
    nos, tienda = pr.get("precio_meli_final"), pr.get("precio_venta")
    todos = ([("Nosotros (Meli)", nos)] if nos is not None else []) + comp  # en empate gana «Nosotros»
    precios = [p for _, p in comp]
    hi = max(todos, key=lambda x: x[1]) if comp else (None, None)
    lo = min(todos, key=lambda x: x[1]) if comp else (None, None)
    return {"nuestro_precio_meli": nos, "nuestro_precio_tienda": tienda,
            "precio_mas_alto": max(precios) if precios else None, "quien_mas_alto": hi[0] if comp else None,
            "precio_mas_bajo": min(precios) if precios else None, "quien_mas_bajo": lo[0] if comp else None,
            "competidores": len(comp), "posicion_meli": posicion(nos, precios), "posicion_tienda": posicion(tienda, precios),
            "diferencia_vs_mas_bajo": round(nos / min(precios) - 1, 4) if precios and nos else None}


def construir(salida):
    visor = leer_visor()
    vis = {p["gtin"]: p for p in visor["productos"]}
    otros = otros_mk.leer()
    comp = {r["gtin"]: r for r in csv.DictReader(open(bml.COMPETENCIA, encoding="utf-8"))} if os.path.exists(bml.COMPETENCIA) else {}
    rech_f = os.path.join(ROOT, "data", "catalogo_ml_rechazados.csv")
    rech = {r["gtin"]: r for r in csv.DictReader(open(rech_f, encoding="utf-8"))} if os.path.exists(rech_f) else {}
    env_f = os.path.join(ROOT, "data", "envios.csv")
    env = {r["gtin"]: r for r in csv.DictReader(open(env_f, encoding="utf-8"))} if os.path.exists(env_f) else {}
    ajustes = json.load(open(os.path.join(ROOT, "data", "ajustes_precios.json"), encoding="utf-8")) if os.path.exists(os.path.join(ROOT, "data", "ajustes_precios.json")) else {}
    cat_pend = json.load(open(os.path.join(ROOT, "config", "pendientes.json"), encoding="utf-8"))["pendientes"]

    if os.path.exists(salida):
        os.remove(salida)
    db = sqlite3.connect(salida)
    db.execute("PRAGMA foreign_keys = ON")
    for t, _, cols in ESQUEMA:
        db.execute(f"CREATE TABLE {t} ({', '.join(f'{c} {tipo}' for c, tipo, _ in cols)})")
    ins = lambda t, row: db.execute(f"INSERT INTO {t} ({', '.join(row)}) VALUES ({', '.join('?' * len(row))})", list(row.values()))  # noqa: E731

    gtins = sorted(vis, key=lambda g: vis[g]["orden"])
    for g in gtins:
        v = vis[g]
        p = json.load(open(os.path.join(ROOT, "products", g, "product.json"), encoding="utf-8"))
        inv, ml, pr = p["investigacion"], p["marketplaces"]["mercadolibre"], v["precios"]
        o = otros.get(g, [])
        o_min, o_m, _, _, o_n = otros_mk.resumen(o)
        ins("productos", {"gtin": g, "sku": p.get("sku", g), "orden": v["orden"], "linea": p["linea"], "nombre_sistema": p["nombre_sistema"],
                          "titulo": p.get("titulo", ""), "descripcion": p.get("descripcion", ""), "receta_mx": p.get("receta_mx", ""),
                          "url_oficial": p.get("url_oficial", ""), "stock": v["stock"], "estado_investigacion": inv.get("estado"),
                          "confianza": inv.get("confianza"), "encontrado_por": inv.get("encontrado_por"), "notas_investigacion": inv.get("notas"),
                          "notas_imagenes": inv.get("notas_imagenes"), "fecha_investigacion": inv.get("fecha"), "sesion": inv.get("sesion"),
                          "ind_descripcion": v["ind"]["descripcion"], "ind_fotos": v["ind"]["fotos"], "ind_precios": v["ind"]["precios"],
                          "num_fotos": len(p.get("imagenes", [])), "precio_otros_marketplaces": o_min, "otros_marketplaces": o_m or None,
                          "num_otros_marketplaces": o_n})
        ficha = p.get("ficha") or {}
        ins("fichas", {"gtin": g, **{k: (json.dumps(ficha[k], ensure_ascii=False) if isinstance(ficha.get(k), (dict, list)) else
                                          (None if ficha.get(k) in (None, "") else str(ficha[k]))) for k in FICHA}})
        for i, im in enumerate(p.get("imagenes", []), start=1):
            ins("imagenes", {"gtin": g, "posicion": i, "archivo": im["archivo"], "ruta": f"products/{g}/images/{im['archivo']}",
                             "url_github": f"{bml.IMG_BASE}/{g}/images/{im['archivo']}", "origen": im.get("origen"),
                             "fuente_url": im.get("fuente_url"), "pagina": im.get("pagina"), "ancho_original": im.get("ancho_original"),
                             "alto_original": im.get("alto_original"), "lado_final": im.get("lado_final"), "lado_util": im.get("lado_util"),
                             "fecha": im.get("fecha")})
        for i, u in enumerate(p.get("fuentes", []), start=1):
            ins("fuentes", {"gtin": g, "posicion": i, "url": u})
        d, r = ml.get("descartado") or {}, rech.get(g) or {}
        ins("mercadolibre", {"gtin": g, "categoria_id": ml.get("categoria_id"), "categoria_ruta": ml.get("categoria_ruta"),
                             "categoria_rx_sugerida": ml.get("categoria_rx_sugerida"), "catalogo_id": ml.get("catalogo_id") or None,
                             "descartado": 1 if d else 0, "descartado_motivo": d.get("motivo"), "descartado_fecha": d.get("fecha"),
                             "catalogo_rechazado": r.get("producto_catalogo"), "catalogo_rechazado_motivo": r.get("motivo")})
        ins("precios_meli", {"gtin": g, **{k: pr.get(k) for k in PRECIO_CAMPOS}, "metodo_mejor_vendedor": v.get("metodo_mejor_vendedor") or None,
                             "parametros_ajustados": ", ".join(sorted(v.get("param_origen") or {})) or None,
                             "envio_peso_kg": v["envio"]["peso"], "envio_tamano": v["envio"]["tamano"], "envio_base": v["envio"]["base"]})
        if g in comp:
            c = comp[g]
            ins("competencia_meli", {"gtin": g, **{k: (c.get(k) or None) if k in ("producto_catalogo", "nombre_catalogo", "item_mejor_vendedor", "vendedor_mejor", "metodo_mejor_vendedor", "fecha", "nota") else num(c.get(k))
                                                   for k in [x for x, _, _ in ESQUEMA[6][2][1:]]}})
        for x in o:
            ins("precios_otros_marketplaces", {k: x.get(k) or None for k in ("gtin", "marketplace", "precio", "precio_lista", "url", "fecha", "nota", "origen")})
        ins("comparacion_precios", {"gtin": g, **comparar(pr, o)})
        if g in env:
            e = env[g]
            ins("envios", {"gtin": g, "peso_real_kg": num(e["peso_real_kg"]), "peso_volumetrico_kg": num(e["peso_volumetrico_kg"]),
                           "peso_cobrable_kg": num(e["peso_cobrable_kg"]), "tamano": e["tamano"], "costo_envio": num(e["costo_envio"]), "base": e["base"]})
        for campo, valor in (ajustes.get(g) or {}).items():
            if campo not in ("nota", "fecha"):
                ins("ajustes_precios", {"gtin": g, "campo": campo, "valor": valor, "nota": ajustes[g].get("nota"), "fecha": ajustes[g].get("fecha")})
        if r:
            ins("catalogos_rechazados", {k: r.get(k) for k in ("gtin", "producto_catalogo", "nombre_catalogo", "tipo", "motivo", "fecha")})
        for x in v.get("pend", []):
            c = cat_pend.get(x["c"], {})
            ins("pendientes", {"gtin": g, "codigo": x["c"], "tipo": c.get("tipo"), "titulo": c.get("titulo"), "detalle": x["d"],
                               "accion": c.get("accion"), "descartado": 1 if d else 0})
    for t, desc, cols in ESQUEMA:
        ins("diccionario", {"tabla": t, "columna": "", "descripcion": desc})
        for c, _, dc in cols:
            ins("diccionario", {"tabla": t, "columna": c, "descripcion": dc})
    for nombre, sql in VISTAS.items():
        db.execute(f"CREATE VIEW {nombre} AS {sql}")
        ins("diccionario", {"tabla": nombre, "columna": "", "descripcion": "Vista de consulta"})
    for k, v in (("esquema", "1"), ("productos", str(len(gtins))), ("datos_visor", visor.get("generado", "")),
                 ("fuente", "Generada por scripts/build_db.py desde products/*/product.json, data/ y visor/data/productos.js")):
        ins("meta", {"clave": k, "valor": v})
    for t in ("imagenes", "fuentes", "precios_otros_marketplaces", "ajustes_precios", "pendientes"):
        db.execute(f"CREATE INDEX idx_{t}_gtin ON {t}(gtin)")
    db.commit()
    db.execute("VACUUM")
    db.close()
    return len(gtins)


def volcado(path):
    db = sqlite3.connect(path)
    out = [l for l in db.iterdump() if "'datos_visor'" not in l]
    db.close()
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--salida", default=SALIDA)
    ap.add_argument("--verificar", action="store_true")
    a = ap.parse_args()
    if a.verificar:
        if not os.path.exists(a.salida):
            raise SystemExit(f"Falta {os.path.relpath(a.salida, ROOT)}: corre python scripts/build_db.py")
        tmp = os.path.join(tempfile.mkdtemp(), "catalogo.db")
        construir(tmp)
        if volcado(tmp) != volcado(a.salida):
            raise SystemExit("data/catalogo.db no corresponde a los datos actuales: corre python scripts/build_visor.py y python scripts/build_db.py")
        print("data/catalogo.db al día")
        return
    n = construir(a.salida)
    db = sqlite3.connect(a.salida)
    cuenta = {t: db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t, _, _ in ESQUEMA}
    db.close()
    print(f"{n} productos -> {os.path.relpath(a.salida, ROOT)} ({os.path.getsize(a.salida) / 1e6:.1f} MB)")
    print(json.dumps(cuenta, ensure_ascii=False))


if __name__ == "__main__":
    main()
