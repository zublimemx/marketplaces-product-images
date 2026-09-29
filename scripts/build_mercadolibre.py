#!/usr/bin/env python3
"""Genera el layout de importación masiva de Mercado Libre a partir de la base de productos.

Uso:
    python scripts/build_mercadolibre.py --precios precios_existencias.csv --salida layout_mercadolibre.xlsx

precios_existencias.csv: gtin,precio,stock,linea,nombre,nota_cruce (precio con impuestos incluidos).
El orden de las filas del layout sigue el orden del CSV.
"""
import argparse
import csv
import json
import os

from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FONT = "Arial"
HDR_FILL = PatternFill("solid", fgColor="1F3864")
HDR_AUX_FILL = PatternFill("solid", fgColor="595959")
HDR_FONT = Font(name=FONT, bold=True, color="FFFFFF", size=10)
BASE_FONT = Font(name=FONT, size=10)
INPUT_FONT = Font(name=FONT, size=10, color="0000FF")
LINK_FONT = Font(name=FONT, size=10, color="008000")
TITLE_FONT = Font(name=FONT, size=12, bold=True)
YELLOW = PatternFill("solid", fgColor="FFFF00")
PESOS = '"$"#,##0.00'
PCT = "0.0%"

FICHA_COLS = [
    ("marca", "Marca"),
    ("fabricante", "Fabricante / Laboratorio"),
    ("linea", "Línea"),
    ("variante", "Variante / Modelo"),
    ("presentacion", "Presentación"),
    ("contenido_neto", "Contenido neto"),
    ("unidad_contenido", "Unidad de contenido"),
    ("unidades_por_envase", "Unidades por envase"),
    ("principio_activo", "Principio activo"),
    ("concentracion", "Concentración"),
    ("via_administracion", "Vía de administración"),
    ("edad_etapa", "Edad / Etapa"),
    ("talla", "Talla"),
    ("sabor_aroma", "Sabor / Aroma"),
    ("genero", "Género"),
    ("tipo_piel_cabello", "Tipo de piel / cabello"),
    ("registro_sanitario", "Registro sanitario"),
    ("otros", "Otros atributos"),
]
N_IMG = 6
IMG0 = get_column_letter(16 + 18)
IMG1 = get_column_letter(16 + 18 + N_IMG - 1)
ESTADOS = {"verificado": "Verificado", "sin_verificar": "Sin verificar", "pendiente": "Pendiente de investigar"}


def load_products():
    prods = {}
    base = os.path.join(ROOT, "products")
    for g in os.listdir(base):
        p = os.path.join(base, g, "product.json")
        if os.path.exists(p):
            with open(p, encoding="utf-8") as fh:
                prods[g] = json.load(fh)
    return prods


def load_cat_paths():
    paths = {}
    with open(os.path.join(ROOT, "reference", "mercadolibre", "categorias_mlm_hojas_publicables.csv"), encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            paths[r["ID"]] = r["Ruta completa"]
    return paths


def style_header(ws, row, ncols, fill=HDR_FILL, start=1):
    for c in range(start, start + ncols):
        cell = ws.cell(row=row, column=c)
        cell.font = HDR_FONT
        cell.fill = fill
        cell.alignment = Alignment(vertical="center", wrap_text=True)


def build(precios_csv, salida):
    cfg = json.load(open(os.path.join(ROOT, "config", "mercadolibre.json"), encoding="utf-8"))
    prods = load_products()
    cat_paths = load_cat_paths()
    with open(precios_csv, encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        if r["gtin"] not in prods:
            raise SystemExit(f"GTIN {r['gtin']} sin product.json")

    wb = Workbook()
    lay = wb.active
    lay.title = "Layout Mercado Libre"
    pre = wb.create_sheet("Precios")
    par = wb.create_sheet("Parámetros")
    rev = wb.create_sheet("Revisión")
    cats = wb.create_sheet("Categorías usadas")
    ava = wb.create_sheet("Avance", 0)

    # ---------------- Parámetros ----------------
    P = cfg["precios"]
    pub = cfg["publicacion"]
    par["A1"] = "Parámetros de publicación y precio para Mercado Libre"
    par["A1"].font = TITLE_FONT
    par["A2"] = "Texto azul: dato de entrada que puedes cambiar. Fondo amarillo: dato por confirmar. Las demás cifras del libro son fórmulas."
    par["A4"], par["B4"], par["C4"] = "Parámetro", "Valor", "Fuente"
    style_header(par, 4, 3)
    fuentes = P["fuentes"]
    params = [
        (5, "Costo de empaque y logística interna por pieza ($)", P["costo_empaque_logistica_por_pieza"], "Indicado por el usuario, 29 sep 2026", PESOS),
        (6, "Descuento contra el promedio de otros vendedores ($)", P["descuento_vs_promedio_competencia"], "Indicado por el usuario, 29 sep 2026", PESOS),
        (7, "Precio desde el que Mercado Libre obliga el envío gratis ($)", P["umbral_envio_gratis_obligatorio"], fuentes[2], PESOS),
        (8, "Costo de envío estimado a cargo del vendedor en productos con envío gratis ($)", P["costo_envio_vendedor_estimado"], "Por confirmar: depende del peso del paquete y de la reputación; con 0 el precio no lo cubre", PESOS),
        (9, "Comisión Clásica para categorías no listadas abajo", P["comision_clasica_otras_categorias"], fuentes[3], PCT),
    ]
    for r, label, val, src, fmt in params:
        par.cell(row=r, column=1, value=label).font = BASE_FONT
        c = par.cell(row=r, column=2, value=val)
        c.font = INPUT_FONT
        c.number_format = fmt
        par.cell(row=r, column=3, value=src).font = BASE_FONT
    par["B8"].fill = YELLOW

    par["A11"] = "Costo fijo por unidad vendida en publicación Clásica"
    par["A11"].font = Font(name=FONT, bold=True, size=10)
    par["A12"], par["B12"], par["C12"] = "Precio desde ($)", "Precio menor a ($)", "Costo fijo ($)"
    style_header(par, 12, 3)
    for i, t in enumerate(P["costos_fijos_clasica"]):
        r = 13 + i
        for col, v in ((1, t["desde"]), (2, t["hasta"]), (3, t["costo_fijo"])):
            c = par.cell(row=r, column=col, value=v)
            c.font = INPUT_FONT
            c.number_format = PESOS
    par["D13"] = fuentes[0]
    par["D14"] = fuentes[1]

    par["A18"] = "Comisión por venta en publicación Clásica, por categoría raíz"
    par["A18"].font = Font(name=FONT, bold=True, size=10)
    par["A19"], par["B19"], par["C19"] = "Categoría raíz", "Comisión", "Fuente"
    style_header(par, 19, 3)
    com = list(P["comision_clasica_por_categoria_raiz"].items())
    for i, (k, v) in enumerate(com):
        r = 20 + i
        par.cell(row=r, column=1, value=k).font = BASE_FONT
        c = par.cell(row=r, column=2, value=v)
        c.font = INPUT_FONT
        c.number_format = PCT
        par.cell(row=r, column=3, value=fuentes[0]).font = BASE_FONT
    com_last = 20 + len(com) - 1
    com_rng = f"Parámetros!$A$20:$B${com_last}"

    par["A26"] = "Valores fijos de cada publicación"
    par["A26"].font = Font(name=FONT, bold=True, size=10)
    par["A27"], par["B27"], par["C27"] = "Campo", "Valor", "Fuente"
    style_header(par, 27, 3)
    fixed = [
        (28, "Condición", pub["condicion"]),
        (29, "Tipo de publicación", pub["tipo_publicacion"]),
        (30, "Forma de envío", pub["forma_envio"]),
        (31, "Costo de envío", pub["costo_envio"]),
        (32, "Retiro en persona", pub["retiro_en_persona"]),
        (33, "Tipo de garantía", pub["tipo_garantia"]),
    ]
    for r, k, v in fixed:
        par.cell(row=r, column=1, value=k).font = BASE_FONT
        par.cell(row=r, column=2, value=v).font = INPUT_FONT
        par.cell(row=r, column=3, value="Indicado por el usuario, 29 sep 2026").font = BASE_FONT
    par.column_dimensions["A"].width = 70
    par.column_dimensions["B"].width = 22
    par.column_dimensions["C"].width = 90
    par.column_dimensions["D"].width = 90

    # ---------------- Layout ----------------
    lay_hdr = (["SKU", "Código universal de producto", "Título", "Categoría (ID)", "Categoría (ruta)", "Precio [$]", "Cantidad",
                "Condición", "Tipo de publicación", "Descripción", "Forma de envío", "Costo de envío", "Retiro en persona",
                "Tipo de garantía", "ID de catálogo ML"]
               + [h for _, h in FICHA_COLS]
               + [f"Imagen {i}" for i in range(1, N_IMG + 1)])
    aux_hdr = ["Línea de origen", "Nombre en sistema", "Estado de investigación"]
    for j, h in enumerate(lay_hdr + aux_hdr, start=1):
        lay.cell(row=1, column=j, value=h)
    style_header(lay, 1, len(lay_hdr))
    style_header(lay, 1, len(aux_hdr), fill=HDR_AUX_FILL, start=len(lay_hdr) + 1)
    lay["A1"].comment = Comment("SKU = código universal de producto, por indicación del usuario.", "Claude")
    lay["G1"].comment = Comment("Fuente: catalogo_productos_farma.xlsx y catalogo_productos_mark.xlsx, columna Cantidades disponibles, subidos 2026-09-29. Existencias negativas o en cero se publican en 0.", "Claude")
    lay["F1"].comment = Comment("Precio Meli Final de la hoja Precios.", "Claude")

    # ---------------- Precios ----------------
    pre_hdr = ["SKU", "Título", "Categoría raíz", "Precio de venta", "Precio de venta Marketplaces", "Comisión Meli",
               "Precio si queda debajo de $99", "Precio si queda entre $99 y $149", "Precio si queda entre $149 y $299",
               "Precio si queda en $299 o más", "Precio Meli calculado", "Precio Meli promedio otros vendedores",
               "Precio mejor vendedor", "Precio Meli Final", "Diferencia contra mejor vendedor", "Costo fijo aplicado",
               "Envío a cargo del vendedor", "Ingreso neto estimado", "Margen contra Precio de venta Marketplaces"]
    for j, h in enumerate(pre_hdr, start=1):
        pre.cell(row=1, column=j, value=h)
    style_header(pre, 1, len(pre_hdr))
    pre["D1"].comment = Comment("Fuente: catalogo_productos_farma.xlsx y catalogo_productos_mark.xlsx, columna Precio de venta (impuestos incluidos, según el usuario), subidos 2026-09-29.", "Claude")
    pre["L1"].comment = Comment("Dato de entrada: precio promedio de otras publicaciones del mismo producto en Mercado Libre.", "Claude")
    pre["M1"].comment = Comment("Dato de entrada: precio de la publicación del mismo producto con más ventas.", "Claude")

    # ---------------- Revisión ----------------
    rev_hdr = ["SKU", "Título", "Estado de investigación", "Confianza", "Encontrado por",
               "Receta en México según principio activo", "Categoría con receta sugerida (ID)",
               "Categoría con receta sugerida (ruta)", "Notas de investigación", "Nota de cruce de datos",
               "Existencia en catálogo", "Página oficial", "Fuentes", "Fotos", "Origen de fotos",
               "Fotos con producto menor a 500 px", "Notas de fotos"]
    for j, h in enumerate(rev_hdr, start=1):
        rev.cell(row=1, column=j, value=h)
    style_header(rev, 1, len(rev_hdr))

    img_base = "https://raw.githubusercontent.com/zublimemx/marketplaces-product-images/main/products/{g}/images/{f}"
    used_cats = {}
    for i, r in enumerate(rows, start=2):
        g = r["gtin"]
        p = prods[g]
        ml = p["marketplaces"]["mercadolibre"]
        inv = p["investigacion"]
        estado = ESTADOS.get(inv["estado"], inv["estado"])
        titulo = p["titulo"] or f"PENDIENTE: {p['nombre_sistema']}"
        ficha = p.get("ficha") or {}
        imgs = [img_base.format(g=g, f=im["archivo"]) for im in p.get("imagenes", [])][:N_IMG]

        vals = [g, g, titulo, ml["categoria_id"], ml["categoria_ruta"],
                f"=Precios!N{i}", int(float(r["stock"])),
                "=Parámetros!$B$28", "=Parámetros!$B$29", p["descripcion"], "=Parámetros!$B$30",
                f'=IF(F{i}>=Parámetros!$B$7,"Envío gratis (obligatorio en Mercado Libre)",Parámetros!$B$31)',
                "=Parámetros!$B$32", "=Parámetros!$B$33", ml.get("catalogo_id", "")]
        for k, _ in FICHA_COLS:
            v = ficha.get(k, "")
            if isinstance(v, (dict, list)):
                v = json.dumps(v, ensure_ascii=False)
            vals.append(v)
        vals += imgs + [""] * (N_IMG - len(imgs))
        vals += [p["linea"], p["nombre_sistema"], estado]
        for j, v in enumerate(vals, start=1):
            c = lay.cell(row=i, column=j, value=(v if v != "" else None))
            c.font = BASE_FONT
        for j in (1, 2):
            lay.cell(row=i, column=j).number_format = "@"
        lay.cell(row=i, column=6).number_format = PESOS
        lay.cell(row=i, column=6).font = LINK_FONT
        for j in (8, 9, 11, 13, 14):
            lay.cell(row=i, column=j).font = LINK_FONT

        # Precios
        pv = [g, f"='Layout Mercado Libre'!C{i}",
              f"=IFERROR(LEFT('Layout Mercado Libre'!E{i},FIND(\" > \",'Layout Mercado Libre'!E{i})-1),\"\")",
              float(r["precio"]),
              f"=D{i}+Parámetros!$B$5",
              f"=IF(C{i}=\"\",Parámetros!$B$9,IFERROR(VLOOKUP(C{i},{com_rng},2,FALSE),Parámetros!$B$9))",
              f"=ROUNDUP((E{i}+Parámetros!$C$13)/(1-F{i}),0)",
              f"=ROUNDUP((E{i}+Parámetros!$C$14)/(1-F{i}),0)",
              f"=ROUNDUP((E{i}+Parámetros!$C$15)/(1-F{i}),0)",
              f"=MAX(ROUNDUP((E{i}+Parámetros!$B$8)/(1-F{i}),0),Parámetros!$B$7)",
              f"=IF(G{i}<Parámetros!$B$13,G{i},IF(H{i}<Parámetros!$B$14,H{i},IF(I{i}<Parámetros!$B$15,I{i},J{i})))",
              None, None,
              f"=IF(AND(ISNUMBER(L{i}),L{i}-Parámetros!$B$6>=K{i}),L{i}-Parámetros!$B$6,K{i})",
              f"=IF(ISNUMBER(M{i}),N{i}/M{i}-1,\"\")",
              f"=VLOOKUP(N{i},Parámetros!$A$13:$C$16,3,TRUE)",
              f"=IF(N{i}>=Parámetros!$B$7,Parámetros!$B$8,0)",
              f"=N{i}*(1-F{i})-P{i}-Q{i}",
              f"=R{i}-E{i}"]
        for j, v in enumerate(pv, start=1):
            c = pre.cell(row=i, column=j, value=v)
            c.font = BASE_FONT
        pre.cell(row=i, column=1).number_format = "@"
        for j in (2, 3):
            pre.cell(row=i, column=j).font = LINK_FONT
        for j in (4, 12, 13):
            pre.cell(row=i, column=j).font = INPUT_FONT
        for j in (4, 5, 7, 8, 9, 10, 11, 12, 13, 14, 16, 17, 18, 19):
            pre.cell(row=i, column=j).number_format = PESOS
        pre.cell(row=i, column=6).number_format = PCT
        pre.cell(row=i, column=15).number_format = PCT

        # Revisión
        rx = ml.get("categoria_rx_sugerida", "")
        all_imgs = p.get("imagenes", [])
        origenes = ", ".join(sorted({im["origen"] for im in all_imgs}))
        bajas = sum(1 for im in all_imgs if im.get("lado_util", 9999) < 500)
        rvals = [g, f"='Layout Mercado Libre'!C{i}", estado, inv.get("confianza", ""), inv.get("encontrado_por", ""),
                 p.get("receta_mx", ""), rx, cat_paths.get(rx, "") if rx else "", inv.get("notas", ""),
                 r.get("nota_cruce", ""), int(float(r["stock"])), p.get("url_oficial", ""),
                 " | ".join(p.get("fuentes", [])), f"=COUNTA('Layout Mercado Libre'!{IMG0}{i}:{IMG1}{i})",
                 origenes, bajas, inv.get("notas_imagenes", "")]
        for j, v in enumerate(rvals, start=1):
            c = rev.cell(row=i, column=j, value=(v if v != "" or j == 16 else None))
            c.font = BASE_FONT
        rev.cell(row=i, column=1).number_format = "@"
        rev.cell(row=i, column=2).font = LINK_FONT

        if ml["categoria_id"]:
            used_cats.setdefault(ml["categoria_id"], ml["categoria_ruta"])

    last = len(rows) + 1

    # ---------------- Categorías usadas ----------------
    cat_hdr = ["Categoría (ID)", "Categoría (ruta)", "Productos", "Comisión Meli"]
    for j, h in enumerate(cat_hdr, start=1):
        cats.cell(row=1, column=j, value=h)
    style_header(cats, 1, len(cat_hdr))
    for i, (cid, ruta) in enumerate(sorted(used_cats.items(), key=lambda x: x[1]), start=2):
        cats.cell(row=i, column=1, value=cid).font = BASE_FONT
        cats.cell(row=i, column=2, value=ruta).font = BASE_FONT
        cats.cell(row=i, column=3, value=f"=COUNTIF('Layout Mercado Libre'!$D$2:$D${last},A{i})").font = BASE_FONT
        c = cats.cell(row=i, column=4, value=f"=IFERROR(VLOOKUP(LEFT(B{i},FIND(\" > \",B{i})-1),{com_rng},2,FALSE),Parámetros!$B$9)")
        c.font = BASE_FONT
        c.number_format = PCT
    nc = len(used_cats) + 2
    cats.cell(row=nc, column=2, value="Total con categoría").font = Font(name=FONT, bold=True, size=10)
    cats.cell(row=nc, column=3, value=f"=SUM(C2:C{nc - 1})").font = Font(name=FONT, bold=True, size=10)
    cats.cell(row=nc + 1, column=2, value="Productos sin categoría (pendientes de investigar)").font = BASE_FONT
    cats.cell(row=nc + 1, column=3, value=f"=COUNTBLANK('Layout Mercado Libre'!$D$2:$D${last})").font = BASE_FONT
    cats.column_dimensions["A"].width = 14
    cats.column_dimensions["B"].width = 110
    cats.column_dimensions["C"].width = 12
    cats.column_dimensions["D"].width = 14
    cats.freeze_panes = "A2"

    # ---------------- Avance ----------------
    ava["A1"] = "Avance de fichas y fotos para Mercado Libre"
    ava["A1"].font = TITLE_FONT
    ava["A2"] = "Completo = ficha verificada en internet y al menos una foto. Texto azul: dato de entrada."
    ava["A2"].font = BASE_FONT
    rng_e = f"Revisión!$C$2:$C${last}"
    rng_f = f"Revisión!$N$2:$N${last}"
    items = [
        (4, "Productos a publicar", f"=COUNTA(Revisión!$A$2:$A${last})", None),
        (5, "Con ficha verificada", f"=COUNTIF({rng_e},\"Verificado\")", None),
        (6, "Con al menos una foto", f"=COUNTIF({rng_f},\">0\")", None),
        (7, "Completos (ficha verificada y fotos)", f"=COUNTIFS({rng_e},\"Verificado\",{rng_f},\">0\")", None),
        (8, "Verificados sin fotos", "=B5-B7", None),
        (9, "Sin verificar (datos deducidos del nombre)", f"=COUNTIF({rng_e},\"Sin verificar\")", None),
        (10, "Pendientes de investigar", f"=COUNTIF({rng_e},\"Pendiente de investigar\")", None),
        (11, "Por investigar (sin verificar + pendientes)", "=B9+B10", None),
        (12, "Avance (completos / total)", "=IF(B4=0,0,B7/B4)", PCT),
        (14, "Productos por sesión", cfg.get("avance", {}).get("productos_por_sesion", 200), "input"),
        (15, "Sesiones realizadas", cfg.get("avance", {}).get("sesiones_realizadas", 0), "input"),
        (16, "Sesiones que faltan", "=ROUNDUP(B11/B14,0)", None),
        (17, "Total de sesiones estimadas", "=B15+B16", None),
    ]
    for r, label, val, kind in items:
        ava.cell(row=r, column=1, value=label).font = BASE_FONT
        c = ava.cell(row=r, column=2, value=val)
        c.font = INPUT_FONT if kind == "input" else BASE_FONT
        if kind == PCT:
            c.number_format = PCT
    ava["C14"] = "Límite de búsquedas web por sesión: 200 (1 búsqueda por producto)"
    ava["C14"].font = BASE_FONT
    hist = cfg.get("avance", {}).get("historial", [])
    if hist:
        ava["A19"] = "Historial de sesiones"
        ava["A19"].font = Font(name=FONT, bold=True, size=10)
        for j, h in enumerate(["Sesión", "Fecha", "Productos investigados", "Fichas verificadas", "Productos con fotos nuevas"], start=1):
            ava.cell(row=20, column=j, value=h)
        style_header(ava, 20, 5)
        for k, h in enumerate(hist, start=21):
            for j, key in enumerate(["sesion", "fecha", "investigados", "verificados", "con_fotos"], start=1):
                ava.cell(row=k, column=j, value=h.get(key)).font = INPUT_FONT
    ava.column_dimensions["A"].width = 46
    ava.column_dimensions["B"].width = 14
    ava.column_dimensions["C"].width = 22
    ava.column_dimensions["D"].width = 20
    ava.column_dimensions["E"].width = 26

    # ---------------- Formato general ----------------
    widths_lay = {"A": 16, "B": 16, "C": 58, "D": 12, "E": 60, "F": 12, "G": 10, "H": 10, "I": 12, "J": 60,
                  "K": 16, "L": 22, "M": 12, "N": 14, "O": 16}
    for col, w in widths_lay.items():
        lay.column_dimensions[col].width = w
    for j in range(16, 16 + len(FICHA_COLS)):
        lay.column_dimensions[get_column_letter(j)].width = 18
    for j in range(16 + len(FICHA_COLS), 16 + len(FICHA_COLS) + N_IMG):
        lay.column_dimensions[get_column_letter(j)].width = 24
    aux0 = len(lay_hdr) + 1
    lay.column_dimensions[get_column_letter(aux0)].width = 14
    lay.column_dimensions[get_column_letter(aux0 + 1)].width = 40
    lay.column_dimensions[get_column_letter(aux0 + 2)].width = 22
    lay.freeze_panes = "D2"
    lay.auto_filter.ref = f"A1:{get_column_letter(len(lay_hdr) + len(aux_hdr))}{last}"
    lay.row_dimensions[1].height = 30

    for j, w in enumerate([16, 50, 26, 12, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 14, 14, 14, 16], start=1):
        pre.column_dimensions[get_column_letter(j)].width = w
    pre.freeze_panes = "C2"
    pre.auto_filter.ref = f"A1:S{last}"
    pre.row_dimensions[1].height = 42

    for j, w in enumerate([16, 50, 20, 11, 14, 16, 16, 60, 70, 50, 12, 40, 80, 8, 18, 14, 60], start=1):
        rev.column_dimensions[get_column_letter(j)].width = w
    rev.freeze_panes = "C2"
    rev.auto_filter.ref = f"A1:Q{last}"
    rev.row_dimensions[1].height = 30

    dv = DataValidation(type="decimal", operator="greaterThanOrEqual", formula1="0", allow_blank=True)
    pre.add_data_validation(dv)
    dv.add(f"L2:M{last}")

    wb.save(salida)
    print(f"{len(rows)} productos -> {salida}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--precios", required=True)
    ap.add_argument("--salida", required=True)
    a = ap.parse_args()
    build(a.precios, a.salida)
