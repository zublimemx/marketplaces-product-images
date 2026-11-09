#!/usr/bin/env python3
"""Catálogo Ecatepec, fase 1: categoría (árbol de Farmacias del Ahorro, dentro de «Farmacia» o «Perfumería» de Odoo)
y laboratorio o fabricante de cada producto nuevo del Excel del ERP. Ver docs/PROCEDIMIENTO_SESION.md §4 quinquies.

Pasos (desde la raíz del repositorio; los intermedios van a trabajo/ecatepec/, que no se versiona):
  python scripts/ecatepec_categorias.py candidatos insumos/originales/Catalogo_Ecatepec.xlsx
        -> candidatos.csv (GTIN válido, vendible, que no esté ya en products/) y data/ecatepec/excluidos.csv
  python scripts/ecatepec_categorias.py ahorro       -> fahorro.jsonl y fahorro_arbol.json (GraphQL de fahorro.com,
        lotes de 50 GTIN con 4 s de pausa; se puede reanudar)
  python scripts/ecatepec_categorias.py rutas        -> rutas_ahorro.csv (ruta canónica por GTIN) y rutas_permitidas.txt
  (subagente) laboratorios del ERP normalizados      -> data/ecatepec/laboratorios.json
  python scripts/ecatepec_categorias.py lotes        -> base.csv, rutas_odoo.txt y lotes/cat_XX.json
  (subagentes con docs/agentes/categorias.md)        -> resultados/cat_XX.json
  python scripts/ecatepec_categorias.py excel        -> data/ecatepec/catalogo.csv y
        layouts/odoo/categorias_laboratorios_ecatepec.xlsx
"""
import collections
import csv
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T = os.path.join(ROOT, "trabajo", "ecatepec")
LABS = os.path.join(ROOT, "data", "ecatepec", "laboratorios.json")

# Departamentos reales de fahorro.com, en orden de preferencia, y la categoría principal de Odoo donde quedan.
DEPTOS = {
    "farmacia": "Farmacia", "equipo-medico": "Farmacia", "vitaminas": "Farmacia", "diabetes": "Farmacia",
    "bienestar-sexual": "Farmacia", "control-de-peso": "Farmacia", "optica": "Farmacia",
    "nutricion-y-deporte": "Farmacia", "hidratacion-bebidas": "Farmacia",
    "bebes": "Perfumería", "cuidado-personal": "Perfumería", "derma": "Perfumería", "belleza": "Perfumería",
    "perfumes": "Perfumería", "electrobelleza": "Perfumería", "mascotas": "Perfumería", "hogar": "Perfumería",
    "conveniencia": "Perfumería", "deportes": "Perfumería", "juguetes": "Perfumería", "electronica": "Perfumería",
}
ORDEN = list(DEPTOS)
# Segmentos de ruta que son vitrinas o promociones, no categorías del producto.
EXCLUIR = ("marcas", "promocion", "lo-mas-vendido", "mi-rutina-diaria", "travel", "tipo-de-piel", "ver-todo",
           "ofertas", "novedades", "kits", "sets-kits", "landing", "campana", "temporada", "regalos", "exclusivo")


def valida(path):
    seg = path.split("/")
    if seg[0] not in DEPTOS:
        return False
    return not any(any(x in s for x in EXCLUIR) for s in seg[1:])


def nombres():
    n = {}
    def walk(c):
        n[c["url_path"]] = c["name"]
        for ch in c.get("children") or []:
            walk(ch)
    for c in json.load(open(os.path.join(T, "fahorro_arbol.json")))["data"]["categoryList"]:
        walk(c)
    for l in open(os.path.join(T, "fahorro.jsonl")):
        for it in json.loads(l)["items"]:
            for k in it["categories"]:
                n.setdefault(k["url_path"], k["name"])
    return n


def ruta_nombres(path, n):
    seg = path.split("/")
    out = []
    for i in range(1, len(seg) + 1):
        out.append(n.get("/".join(seg[:i]), seg[i - 1].replace("-", " ").capitalize()).strip())
    return out


def rutas():
    n = nombres()
    filas = []
    usadas = collections.Counter()
    for l in open(os.path.join(T, "fahorro.jsonl")):
        for it in json.loads(l)["items"]:
            ps = [k["url_path"] for k in it["categories"] if valida(k["url_path"])]
            if not ps:
                filas.append(dict(gtin=it["sku"], nombre_ahorro=it["name"], marca_ahorro=it.get("brand_label") or "", ruta_ahorro=""))
                continue
            ps.sort(key=lambda p: (-p.count("/"), ORDEN.index(p.split("/")[0])))
            p = ps[0]
            usadas[p] += 1
            filas.append(dict(gtin=it["sku"], nombre_ahorro=it["name"], marca_ahorro=(it.get("brand_label") or "").replace("0", "") if it.get("brand_label") == "0" else (it.get("brand_label") or ""),
                              ruta_ahorro=" > ".join(ruta_nombres(p, n)), url_path=p))
    with open(os.path.join(T, "rutas_ahorro.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["gtin", "nombre_ahorro", "marca_ahorro", "ruta_ahorro", "url_path"])
        w.writeheader()
        w.writerows(filas)
    # Rutas permitidas para inferir: hojas del árbol de los departamentos reales + las usadas por productos encontrados.
    perm = set(usadas)
    def walk(c):
        if valida(c["url_path"]) and not c.get("children"):
            perm.add(c["url_path"])
        for ch in c.get("children") or []:
            walk(ch)
    for c in json.load(open(os.path.join(T, "fahorro_arbol.json")))["data"]["categoryList"]:
        walk(c)
    with open(os.path.join(T, "rutas_permitidas.txt"), "w", encoding="utf-8") as f:
        for p in sorted(perm, key=lambda p: (ORDEN.index(p.split("/")[0]), p)):
            f.write(f"{DEPTOS[p.split('/')[0]]} | {' > '.join(ruta_nombres(p, n))} | {usadas.get(p, 0)}\n")
    print(len(filas), "encontrados;", sum(1 for x in filas if x["ruta_ahorro"]), "con ruta;", len(perm), "rutas permitidas")


def gtin_valido(s):
    if not re.fullmatch(r"\d{8}|\d{12,14}", s):
        return False
    d = [int(c) for c in s]
    t = sum(x * (3 if i % 2 == 0 else 1) for i, x in enumerate(d[:-1][::-1]))
    return (10 - t % 10) % 10 == d[-1]


def candidatos(xlsx):
    import pandas as pd
    norm = lambda s: re.sub(r"\s+", " ", str(s)).strip().upper()
    df = pd.read_excel(xlsx, dtype={"Código de barras": str})
    df["g"] = df["Código de barras"].fillna("").str.strip()
    df["n"] = df.Nombre.map(norm)
    pdir = os.path.join(ROOT, "products")
    exist = set(os.listdir(pdir))
    en = {e.lstrip("0") for e in exist}
    exn = {norm(json.load(open(os.path.join(pdir, d, "product.json")))["nombre_sistema"]) for d in exist}
    def motivo(r):
        if r.g.lstrip("0") in en:
            return "Ya está en el repositorio (mismo GTIN)"
        if r.n in exn:
            return "Ya está en el repositorio (mismo nombre)"
        if not gtin_valido(r.g):
            return "Código de barras no es GTIN válido (oferta o código interno)"
        if not r["Se puede vender"]:
            return "Marcado como no se puede vender"
        return ""
    df["motivo"] = df.apply(motivo, axis=1)
    c = df[df.motivo == ""].copy()
    c["descatalogado"] = c["Categoría de producto"].eq("DESCATALOGADO")
    c["orden"] = range(1, len(c) + 1)
    os.makedirs(T, exist_ok=True)
    c[["orden", "g", "Nombre", "Laboratorio", "Categoría de producto", "Categoría de producto UNSPSC", "descatalogado"]].rename(
        columns={"g": "gtin"}).to_csv(os.path.join(T, "candidatos.csv"), index=False)
    df[df.motivo != ""][["g", "Nombre", "motivo"]].rename(columns={"g": "gtin", "Nombre": "nombre_erp"}).to_csv(
        os.path.join(ROOT, "data", "ecatepec", "excluidos.csv"), index=False)
    print(len(c), "candidatos;", df.motivo.value_counts().to_dict())


def ahorro():
    import time
    import pandas as pd
    import requests
    url, H = "https://www.fahorro.com/graphql", {"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"}
    c = pd.read_csv(os.path.join(T, "candidatos.csv"), dtype={"gtin": str})
    out = os.path.join(T, "fahorro.jsonl")
    hechos = set()
    if os.path.exists(out):
        for l in open(out):
            hechos.update(json.loads(l)["consultados"])
    Q = ("{ products(filter: {sku: {in: %s}}, pageSize: 100) { items { sku name url_key brand "
         "categories { uid name url_path level } } aggregations { attribute_code options { label value } } } }")
    g = [x for x in c.gtin if x not in hechos]
    for i in range(0, len(g), 50):
        lote = g[i:i + 50]
        for intento in range(4):
            try:
                d = requests.post(url, json={"query": Q % json.dumps(lote)}, headers=H, timeout=90).json()["data"]["products"]
                break
            except Exception as e:
                print("error", i, e, flush=True)
                time.sleep(30 * (intento + 1))
        else:
            sys.exit("falló el lote %d; vuelve a correr para reanudar" % i)
        br = {o["value"]: o["label"] for a in d["aggregations"] if a["attribute_code"] == "brand" for o in a["options"]}
        items = [dict(it, brand_label=br.get(str(it["brand"]))) for it in d["items"]]
        with open(out, "a") as f:
            f.write(json.dumps({"consultados": lote, "items": items}, ensure_ascii=False) + "\n")
        time.sleep(4)
    Qa = ("{ categoryList(filters: {parent_id: {eq: \"2\"}}) { name url_path level product_count children { name url_path "
          "level product_count children { name url_path level product_count children { name url_path level product_count "
          "children { name url_path level product_count } } } } } }")
    arbol = requests.post(url, json={"query": Qa}, headers=H, timeout=90).json()
    json.dump(arbol, open(os.path.join(T, "fahorro_arbol.json"), "w"), ensure_ascii=False)
    print("listo:", sum(len(json.loads(l)["items"]) for l in open(out)), "productos encontrados")


MALOS = ("plan de lealtad", "foundayz", "mounjaro", "ozempic", "rybelsus", "saxenda", "trulicity", "wegovy",
         "nuevos lanzamientos", "lanzamientos", "invernal", "catálogo extendido", "nan", "nido")


def odoo(ruta_ahorro):
    """Ruta del Ahorro («Farmacia > Especialidades > Cardiología») -> nombre completo de Odoo
    («Farmacia / Especialidades / Cardiología»), dentro de las categorías principales Farmacia o Perfumería.
    Devuelve "" si la ruta pasa por un nodo comercial (marca, programa, temporada)."""
    if not ruta_ahorro:
        return ""
    seg = [re.sub(r"^\d+\.\s*", "", x).replace("/", "-").strip() for x in ruta_ahorro.split(" > ")]
    if any(x.lower() in MALOS for x in seg):
        return ""
    dep = seg[0]
    raiz = "Farmacia" if dep in DEPTOS_FARMACIA else "Perfumería"
    if dep.lower() == "farmacia":
        seg = seg[1:]
    elif dep.lower() == "bienestar sexual":
        seg = ["Bienestar sexual"] + seg[1:]
    seg = [CANON.get(x.lower(), x) for x in seg]
    return " / ".join([raiz] + seg)


# Nombres de departamento del Ahorro que van dentro de «Farmacia» (el resto, dentro de «Perfumería»).
DEPTOS_FARMACIA = {"Farmacia", "Equipo Médico & Ortopedia", "Vitaminas & Suplementos", "Diabetes", "Bienestar Sexual",
                   "Control de Peso", "Salud Visual", "Nutrición y Deporte", "Hidratación & Bebidas"}
# Unifica mayúsculas de nombres repetidos con distinta escritura.
CANON = {"accesorios sexualidad": "Accesorios sexualidad", "bienestar sexual": "Bienestar sexual"}


def lotes(n_lotes=15):
    import pandas as pd
    c = pd.read_csv(os.path.join(T, "candidatos.csv"), dtype={"gtin": str})
    r = pd.read_csv(os.path.join(T, "rutas_ahorro.csv"), dtype={"gtin": str}, keep_default_na=False)
    labs = {x["laboratorio_excel"].strip(): x for x in json.load(open(LABS))}
    x = c.merge(r, on="gtin", how="left").fillna("")
    x["Laboratorio"] = x.Laboratorio.str.strip().replace("", "(vacío)")
    x["odoo"] = x.ruta_ahorro.map(odoo)
    x["lab_tipo"] = x.Laboratorio.map(lambda l: labs[l]["tipo"])
    x["fabricante_lab"] = x.Laboratorio.map(lambda l: labs[l]["fabricante"])
    x.to_csv(os.path.join(T, "base.csv"), index=False)
    # Rutas permitidas (formato Odoo) con su número de productos confirmados en el Ahorro.
    usadas = collections.Counter(x.odoo[x.odoo != ""])
    perm = set(usadas)
    for l in open(os.path.join(T, "rutas_permitidas.txt"), encoding="utf-8"):
        o = odoo(l.split(" | ")[1])
        if o:
            perm.add(o)
    with open(os.path.join(T, "rutas_odoo.txt"), "w", encoding="utf-8") as f:
        for p in sorted(perm):
            f.write(f"{p}\t{usadas.get(p, 0)}\n")
    # Pistas: rutas más frecuentes entre productos confirmados con el mismo código UNSPSC y el mismo laboratorio.
    conf = x[x.odoo != ""]
    def top(col):
        return {k: "; ".join(f"{p} ({n})" for p, n in g.odoo.value_counts().head(3).items()) for k, g in conf.groupby(col)}
    pu, pl = top("Categoría de producto UNSPSC"), top("Laboratorio")
    falta = x[(x.odoo == "") | (x.lab_tipo == "distribuidor")]
    filas = []
    for _, f in falta.iterrows():
        filas.append({"gtin": f.gtin, "nombre_erp": str(f.Nombre).strip(), "laboratorio_erp": f.Laboratorio,
                      "categoria_erp": f["Categoría de producto"], "unspsc": f["Categoría de producto UNSPSC"],
                      "nombre_ahorro": f.nombre_ahorro, "marca_ahorro": f.marca_ahorro,
                      "necesita": ("categoria" if f.odoo == "" else "") + ("+fabricante" if f.lab_tipo == "distribuidor" else ""),
                      "categoria_confirmada": f.odoo,
                      "pista_unspsc": pu.get(f["Categoría de producto UNSPSC"], ""), "pista_laboratorio": pl.get(f.Laboratorio, "")})
    d = os.path.join(T, "lotes")
    os.makedirs(d, exist_ok=True)
    tam = -(-len(filas) // n_lotes)
    for i in range(n_lotes):
        json.dump(filas[i * tam:(i + 1) * tam], open(os.path.join(d, f"cat_{i + 1:02d}.json"), "w"), ensure_ascii=False, indent=0)
    print(len(x), "candidatos;", (x.odoo != "").sum(), "con categoría del Ahorro;", len(filas), "a lotes de", tam, ";", len(perm), "rutas Odoo")


def excel():
    """Une la categoría del Ahorro con las inferidas y escribe:
    - data/ecatepec/catalogo.csv (versionado, sin precios): una fila por producto con fuente y confianza.
    - layouts/odoo/categorias_laboratorios_ecatepec.xlsx: hojas Categorías (importación de product.category),
      Laboratorios, Productos (SKU, Nombre, Categoría, Laboratorio) y Rutas por nivel."""
    import glob
    import pandas as pd
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    b = pd.read_csv(os.path.join(T, "base.csv"), dtype={"gtin": str}, keep_default_na=False).drop_duplicates("gtin")
    rutas_ok = {l.split("\t")[0] for l in open(os.path.join(T, "rutas_odoo.txt"), encoding="utf-8")}
    inf = {}
    for f in sorted(glob.glob(os.path.join(T, "resultados", "cat_*.json"))):
        for x in json.load(open(f)):
            inf[x["gtin"]] = x
    labs = {x["laboratorio_excel"].strip(): x for x in json.load(open(LABS))}
    filas, malos = [], []
    for _, r in b.iterrows():
        i = inf.get(r.gtin, {})
        if r.odoo:
            cat, fuente, conf = r.odoo, "Farmacias del Ahorro", "alta"
        else:
            cat, fuente, conf = i.get("categoria", ""), "inferida", i.get("confianza", "")
            if cat not in rutas_ok:
                malos.append((r.gtin, cat))
                cat, conf = "", ""
        lab = labs.get(r.Laboratorio, {})
        if lab.get("tipo") == "distribuidor":
            fab, ffab = (i.get("fabricante") or "").strip(), "inferido por producto"
            if not fab:
                fab, ffab = lab.get("fabricante", ""), "laboratorio del ERP (distribuidor)"
        else:
            fab, ffab = lab.get("fabricante", ""), "laboratorio del ERP normalizado (%s)" % lab.get("confianza", "")
        filas.append({"gtin": r.gtin, "nombre_erp": str(r.Nombre).strip(), "laboratorio_erp": r.Laboratorio,
                      "categoria_erp": r["Categoría de producto"], "categoria_odoo": cat, "fuente_categoria": fuente,
                      "confianza_categoria": conf, "fabricante": fab, "fuente_fabricante": ffab,
                      "nombre_ahorro": r.nombre_ahorro, "marca_ahorro": r.marca_ahorro, "ruta_ahorro": r.ruta_ahorro})
    df = pd.DataFrame(filas)
    # Nodos comerciales o mal escritos del Ahorro que se ajustan en la ruta final.
    ajustes = {"Perfumería / Higiene y Cuidado Personal / Incontinencia / Compra Más, Ahorra Más": "Perfumería / Higiene y Cuidado Personal / Incontinencia",
               "Perfumería / Hogar / Ver Todo Hogar": "Perfumería / Hogar",
               "Farmacia / Articulos de medición": "Farmacia / Artículos de medición"}
    df["categoria_odoo"] = df.categoria_odoo.replace(ajustes)
    if malos:
        print("AVISO: %d categorías inferidas fuera de rutas_odoo.txt (quedan vacías): %s" % (len(malos), malos[:5]))
    df.to_csv(os.path.join(ROOT, "data", "ecatepec", "catalogo.csv"), index=False)

    # Categorías: todos los nodos intermedios de las rutas usadas, padres antes que hijos. Las raíces ya existen en Odoo.
    usadas = df.categoria_odoo[df.categoria_odoo != ""].value_counts()
    nodos = set()
    for c in usadas.index:
        seg = c.split(" / ")
        for k in range(2, len(seg) + 1):
            nodos.add(" / ".join(seg[:k]))
    nodos = sorted(nodos, key=lambda c: (c.count(" / "), c))
    wb = Workbook()
    neg = Font(bold=True)
    gris = PatternFill("solid", fgColor="DDDDDD")
    def hoja(ws, cab, filas_, anchos):
        ws.append(cab)
        for c in ws[1]:
            c.font, c.fill = neg, gris
        for f in filas_:
            ws.append(f)
        for i, w in enumerate(anchos):
            ws.column_dimensions[chr(65 + i)].width = w
        ws.freeze_panes = "A2"
    ws = wb.active
    ws.title = "Categorías"
    hoja(ws, ["Nombre", "Categoría padre"], [[n.split(" / ")[-1], " / ".join(n.split(" / ")[:-1])] for n in nodos], [45, 80])
    fabs = sorted(set(df.fabricante[df.fabricante != ""]), key=str.lower)
    hoja(wb.create_sheet("Laboratorios"), ["Nombre"], [[f] for f in fabs], [45])
    hoja(wb.create_sheet("Productos"), ["SKU", "Nombre", "Categoría", "Laboratorio"],
         df[["gtin", "nombre_erp", "categoria_odoo", "fabricante"]].values.tolist(), [16, 60, 80, 35])
    maxn = max(c.count(" / ") + 1 for c in usadas.index)
    hoja(wb.create_sheet("Rutas por nivel"), ["Categoría"] + ["Nivel %d" % (k + 1) for k in range(maxn)] + ["Productos"],
         [[c] + c.split(" / ") + [""] * (maxn - c.count(" / ") - 1) + [int(n)] for c, n in sorted(usadas.items())],
         [80] + [28] * maxn + [10])
    for c in wb["Productos"]["A"]:
        c.number_format = "@"
    out = os.path.join(ROOT, "layouts", "odoo", "categorias_laboratorios_ecatepec.xlsx")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    wb.save(out)
    print(len(df), "productos;", (df.categoria_odoo != "").sum(), "con categoría (%d del Ahorro, %d inferidas);"
          % ((df.fuente_categoria == "Farmacias del Ahorro").sum(), ((df.fuente_categoria == "inferida") & (df.categoria_odoo != "")).sum()),
          len(nodos), "categorías nuevas;", len(fabs), "laboratorios ->", out)


if __name__ == "__main__":
    acciones = {"candidatos": candidatos, "ahorro": ahorro, "rutas": rutas, "lotes": lotes, "excel": excel}
    if len(sys.argv) < 2 or sys.argv[1] not in acciones:
        sys.exit(__doc__)
    acciones[sys.argv[1]](*sys.argv[2:])
