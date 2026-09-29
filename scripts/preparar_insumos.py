#!/usr/bin/env python3
"""Genera insumos/precios_existencias.csv (precio con IVA y existencia por GTIN) a partir de los Excel del ERP.

Uso:
  python scripts/preparar_insumos.py --ventas "Productos más vendidos ... .xlsx" \
      --farma catalogo_productos_farma.xlsx --mark catalogo_productos_mark.xlsx

Reglas (ver docs/REGLAS_NEGOCIO.md):
- Productos a publicar = los del Excel de más vendidos (hoja 1 = Farma, hoja 2 = Mark), cruzados por nombre
  normalizado (mayúsculas, espacios colapsados) contra el catálogo de su línea.
- Se ignora el renglón genérico "Todo / Perfumería" y se quita el sufijo " (2)" antes de cruzar.
- Si un nombre tiene varios códigos en el catálogo, se usa el de mayor existencia.
- Si un mismo GTIN aparece en Farma y Mark se publica una sola vez: existencia sumada y precio mayor.
- Existencia negativa se publica como 0. Los productos sin existencia sí se incluyen.
- El orden sigue data/prioridad.csv; los GTIN nuevos se agregan al final por monto vendido.

Salida (no se versiona: contiene precios): insumos/precios_existencias.csv con gtin,precio,stock,linea,nombre,nota_cruce.
Si aparecen GTIN nuevos, también los agrega a data/prioridad.csv y crea su products/<GTIN>/product.json en estado pendiente.
"""
import argparse
import json
import os
import re

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def norm(s):
    return re.sub(r"\s+", " ", str(s)).strip().upper()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ventas", required=True)
    ap.add_argument("--farma", required=True)
    ap.add_argument("--mark", required=True)
    a = ap.parse_args()

    rows = []
    for sheet, linea, cat_path in [(0, "Farma", a.farma), (1, "Mark", a.mark)]:
        ventas = pd.read_excel(a.ventas, sheet_name=sheet)
        cat = pd.read_excel(cat_path, dtype={"Código de barras": str})
        cat["key"] = cat["Nombre"].map(norm)
        for _, r in ventas.iterrows():
            key = norm(r["Producto"])
            if key == "TODO / PERFUMERÍA":
                continue
            k2 = re.sub(r"\s*\(2\)$", "", key)
            m = cat[cat["key"] == k2]
            if m.empty:
                print(f"SIN CRUCE: {r['Producto']!r}")
                continue
            nota = ""
            if len(m) > 1:
                m = m.sort_values("Cantidades disponibles", ascending=False)
                nota = "Nombre con %d códigos en catálogo (%s); se usó el de mayor existencia" % (len(m), ", ".join(m["Código de barras"]))
            if k2 != key:
                nota = "Nombre en ventas con sufijo (2); se cruzó sin el sufijo"
            b = m.iloc[0]
            rows.append(dict(gtin=str(b["Código de barras"]).strip(), linea=linea,
                             nombre=re.sub(r"\s+", " ", str(b["Nombre"])).strip(),
                             precio=float(b["Precio de venta"]), stock=max(int(b["Cantidades disponibles"]), 0),
                             mxn=float(r["Total MXN"]), nota_cruce=nota))
    df = pd.DataFrame(rows)
    out = []
    for g, grp in df.groupby("gtin", sort=False):
        r = grp.sort_values("linea").iloc[0].to_dict()
        if len(grp) > 1:
            r["linea"] = "Farma + Mark"
            r["stock"] = int(grp["stock"].sum())
            r["precio"] = float(grp["precio"].max())
            r["mxn"] = float(grp["mxn"].sum())
            r["nota_cruce"] = "Mismo código de barras en Farma y Mark; se unió en una publicación con la existencia sumada" + (
                " y el precio mayor" if grp["precio"].nunique() > 1 else "")
        out.append(r)
    df = pd.DataFrame(out)

    pri_path = os.path.join(ROOT, "data", "prioridad.csv")
    pri = pd.read_csv(pri_path, dtype={"gtin": str}, keep_default_na=False)
    orden = dict(zip(pri.gtin, pri.orden))
    nuevos = df[~df.gtin.isin(orden)].sort_values("mxn", ascending=False)
    nxt = int(pri.orden.max()) + 1
    add = []
    for _, r in nuevos.iterrows():
        orden[r.gtin] = nxt
        add.append(dict(orden=nxt, gtin=r.gtin, linea=r.linea, nombre_sistema=r.nombre, nota_cruce=r.nota_cruce))
        pdir = os.path.join(ROOT, "products", r.gtin)
        os.makedirs(pdir, exist_ok=True)
        pj = os.path.join(pdir, "product.json")
        if not os.path.exists(pj):
            json.dump({"gtin": r.gtin, "sku": r.gtin, "linea": r.linea, "nombre_sistema": r.nombre,
                       "nombres_sistema_alternos": [], "titulo": "", "descripcion": "", "ficha": {}, "receta_mx": "",
                       "marketplaces": {"mercadolibre": {"categoria_id": "", "categoria_ruta": "", "categoria_rx_sugerida": "", "catalogo_id": ""},
                                        "amazon": {}, "shopify": {}, "odoo": {}},
                       "imagenes": [], "url_oficial": "", "fuentes": [],
                       "investigacion": {"estado": "pendiente", "confianza": "", "encontrado_por": "", "notas": "", "fecha": ""}},
                      open(pj, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        nxt += 1
    if add:
        pri = pd.concat([pri, pd.DataFrame(add)], ignore_index=True)
        pri.to_csv(pri_path, index=False)
        print(f"{len(add)} GTIN nuevos agregados a data/prioridad.csv")
    faltan = set(pri.gtin) - set(df.gtin)
    if faltan:
        print(f"AVISO: {len(faltan)} GTIN de data/prioridad.csv no vienen en los Excel de este corte; se omiten del layout")
    df["orden"] = df.gtin.map(orden)
    df = df.sort_values("orden")
    os.makedirs(os.path.join(ROOT, "insumos"), exist_ok=True)
    salida = os.path.join(ROOT, "insumos", "precios_existencias.csv")
    df[["gtin", "precio", "stock", "linea", "nombre", "nota_cruce"]].to_csv(salida, index=False)
    print(f"{len(df)} productos -> {salida}")


if __name__ == "__main__":
    main()
