#!/usr/bin/env python3
"""Precios de competencia en Mercado Libre México con la API oficial.

Escribe data/competencia_meli.csv (versionado), que scripts/build_mercadolibre.py y scripts/build_visor.py usan para
"Precio Meli promedio otros vendedores" y "Precio mejor vendedor". Guarda la respuesta cruda de cada producto en
trabajo/meli/<GTIN>.json (producto de catálogo con atributos y fotos, publicaciones que compiten y, con
--descripciones, descripciones de otros vendedores) para completar fotos y descripciones sin volver a consultar.

Credenciales (.env o insumos/ml_token.json, nunca en git): ver docs/MERCADOLIBRE_API.md y scripts/meli_auth.py.

Uso:
  python scripts/meli_precios.py [--gtin 7501... ...] [--limite N] [--hilos 4] [--descripciones] [--forzar]
                                 [--guardar-catalogo] [--salida data/competencia_meli.csv]
  python scripts/meli_precios.py --solo-csv      # recalcula el CSV desde trabajo/meli/ sin llamar a la API

Qué permite la API (probado el 29 sep 2026 con la cuenta del vendedor):
  - GET /products/search?product_identifier=<GTIN>, /products/<id> y /products/<id>/items: sí.
  - GET /items/<id> e /items?ids= de otros vendedores: 403 (no hay ventas por publicación ni sus fotos).
  - GET /items/<id>/description: sí (muchas vienen vacías porque usan imágenes).
  - GET /users/<id>: sí (reputación y ventas históricas del vendedor).
  - GET /sites/MLM/search: 403.
Reglas:
  - Promedio de otros vendedores: media de las publicaciones nuevas de otros vendedores del producto de catálogo, sin
    atípicas (más del doble de la mediana, casi siempre paquetes de varias piezas).
  - Mejor vendedor: como la API ya no da ventas por publicación, se toma la publicación del vendedor con más ventas
    históricas (seller_reputation.transactions.total); en empate, la más barata. metodo = vendedor_con_mas_ventas.
  - Catálogos rechazados en revisión (data/catalogo_ml_rechazados.csv: el GTIN apunta a otro producto o a otra
    presentación): no se usan ni para precios ni para fotos; la fila queda sin precios y con la nota del motivo.
"""
import argparse
import concurrent.futures
import csv
import datetime
import json
import os
import statistics
import sys
import threading
import time

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API = "https://api.mercadolibre.com"
SITE = "MLM"
TOKEN_FILE = os.path.join(ROOT, "insumos", "ml_token.json")
CRUDO = os.path.join(ROOT, "trabajo", "meli")
VENDEDORES = os.path.join(CRUDO, "_vendedores.json")
RECHAZADOS = os.path.join(ROOT, "data", "catalogo_ml_rechazados.csv")
FIELDS = ["gtin", "producto_catalogo", "nombre_catalogo", "publicaciones_otros", "precio_promedio_otros", "precio_mediana_otros",
          "precio_min_otros", "precio_max_otros", "publicaciones_atipicas", "precio_mejor_vendedor", "item_mejor_vendedor",
          "vendedor_mejor", "ventas_vendedor_mejor", "metodo_mejor_vendedor", "fecha", "nota"]


def rechazados():
    """{gtin: {producto_catalogo, tipo, motivo, ...}} de data/catalogo_ml_rechazados.csv."""
    if not os.path.exists(RECHAZADOS):
        return {}
    return {r["gtin"]: r for r in csv.DictReader(open(RECHAZADOS, encoding="utf-8"))}


RECH = rechazados()


def load_env():
    path = os.path.join(ROOT, ".env")
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


class Meli:
    def __init__(self):
        self.local = threading.local()
        self.lock = threading.Lock()
        self.token = None
        if os.path.exists(TOKEN_FILE):  # de scripts/meli_auth.py o de una renovación anterior
            t = json.load(open(TOKEN_FILE))
            if t.get("access_token") and t.get("vence", "") > datetime.datetime.now().isoformat():
                self.token = t["access_token"]
        self.token = self.token or os.environ.get("ML_ACCESS_TOKEN")
        if not self.token:
            self.refresh()

    def sesion(self):
        if not hasattr(self.local, "s"):
            self.local.s = requests.Session()
        return self.local.s

    def refresh(self):
        with self.lock:
            rt = os.environ.get("ML_REFRESH_TOKEN")
            if os.path.exists(TOKEN_FILE):
                rt = json.load(open(TOKEN_FILE)).get("refresh_token") or rt
            cid, sec = os.environ.get("ML_CLIENT_ID"), os.environ.get("ML_CLIENT_SECRET")
            if not (cid and sec and rt):
                sys.exit("El token venció y no hay refresh token: pide al dueño un código de autorización (scripts/meli_auth.py) o un token nuevo")
            r = requests.post(f"{API}/oauth/token", timeout=30, headers={"Accept": "application/json"},
                              data={"grant_type": "refresh_token", "client_id": cid, "client_secret": sec, "refresh_token": rt})
            if r.status_code != 200:
                sys.exit(f"No se pudo renovar el token: {r.status_code} {r.text[:300]}")
            data = r.json()
            vence = datetime.datetime.now() + datetime.timedelta(seconds=int(data.get("expires_in", 21600)) - 300)
            os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
            json.dump({"access_token": data["access_token"], "refresh_token": data.get("refresh_token"),
                       "vence": vence.isoformat(timespec="seconds"), "obtenido": datetime.datetime.now().isoformat(timespec="seconds")},
                      open(TOKEN_FILE, "w"), indent=2)
            self.token = data["access_token"]

    def get(self, path, params=None):
        """(status, json o None)."""
        r = None
        for intento in range(6):
            try:
                r = self.sesion().get(f"{API}{path}", params=params, timeout=30, headers={"Authorization": f"Bearer {self.token}"})
            except requests.RequestException:
                time.sleep(2 ** intento)
                continue
            if r.status_code == 401 and intento == 0:
                self.refresh()
                continue
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(min(2 ** intento, 20))
                continue
            break
        if r is None:
            return 0, None
        try:
            return r.status_code, r.json()
        except ValueError:
            return r.status_code, None


class Vendedores:
    def __init__(self, ml):
        self.ml = ml
        self.lock = threading.Lock()
        self.d = json.load(open(VENDEDORES)) if os.path.exists(VENDEDORES) else {}

    def get(self, sid):
        sid = str(sid)
        with self.lock:
            if sid in self.d:
                return self.d[sid]
        st, u = self.ml.get(f"/users/{sid}")
        rep = (u or {}).get("seller_reputation") or {}
        v = {"nickname": (u or {}).get("nickname", ""), "ventas": ((rep.get("transactions") or {}).get("total") or 0),
             "nivel": rep.get("level_id"), "power_seller": rep.get("power_seller_status"), "status": st}
        with self.lock:
            self.d[sid] = v
        return v

    def guardar(self):
        with self.lock:
            os.makedirs(CRUDO, exist_ok=True)
            json.dump(self.d, open(VENDEDORES, "w"), ensure_ascii=False)


def consultar(ml, vend, g, descripciones=False, guardar_catalogo=False):
    pj = os.path.join(ROOT, "products", g, "product.json")
    prod = json.load(open(pj, encoding="utf-8"))
    crudo = {"gtin": g, "fecha": datetime.date.today().isoformat(), "producto_catalogo": "", "origen_catalogo": "", "producto": None,
             "items": [], "vendedores": {}, "descripciones": []}
    st, res = ml.get("/products/search", {"status": "active", "site_id": SITE, "product_identifier": g})
    if st in (401, 403):
        raise SystemExit(f"La API respondió {st} en /products/search: revisa el token")
    results = (res or {}).get("results") or []
    malo = (RECH.get(g) or {}).get("producto_catalogo")
    pid = next((r.get("id", "") for r in results if r.get("id") and r.get("id") != malo), "")
    crudo["origen_catalogo"] = "gtin" if pid else ""
    if not pid and prod["marketplaces"]["mercadolibre"].get("catalogo_id") not in ("", None, malo):
        pid, crudo["origen_catalogo"] = prod["marketplaces"]["mercadolibre"]["catalogo_id"], "product.json"
    if pid:
        crudo["producto_catalogo"] = pid
        _, p = ml.get(f"/products/{pid}")
        if p:
            crudo["producto"] = {k: p.get(k) for k in ("id", "name", "domain_id", "permalink", "status", "attributes", "pictures",
                                                        "main_features", "short_description", "buy_box_winner", "parent_id")}
        items, offset = [], 0
        while True:
            _, its = ml.get(f"/products/{pid}/items", {"offset": offset, "limit": 100})
            lote = (its or {}).get("results") or []
            for it in lote:
                env = it.get("shipping") or {}
                items.append({k: it.get(k) for k in ("item_id", "seller_id", "price", "original_price", "condition", "listing_type_id",
                                                     "official_store_id", "tags")}
                             | {"logistic_type": env.get("logistic_type"), "free_shipping": env.get("free_shipping")})
            total = ((its or {}).get("paging") or {}).get("total", 0)
            offset += 100
            if not lote or offset >= total or offset >= 500:
                break
        crudo["items"] = items
        for it in items:
            if it.get("seller_id"):
                crudo["vendedores"][str(it["seller_id"])] = vend.get(it["seller_id"])
        if descripciones:
            for it in items[:10]:
                _, d = ml.get(f"/items/{it['item_id']}/description")
                txt = ((d or {}).get("plain_text") or "").strip()
                if txt:
                    crudo["descripciones"].append({"item_id": it["item_id"], "texto": txt})
                if len(crudo["descripciones"]) >= 3:
                    break
        if guardar_catalogo and crudo["origen_catalogo"] == "gtin" and prod["marketplaces"]["mercadolibre"].get("catalogo_id") != pid:
            prod["marketplaces"]["mercadolibre"]["catalogo_id"] = pid
            tmp = pj + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(prod, fh, ensure_ascii=False, indent=2)
            os.replace(tmp, pj)
    os.makedirs(CRUDO, exist_ok=True)
    with open(os.path.join(CRUDO, f"{g}.json"), "w", encoding="utf-8") as fh:
        json.dump(crudo, fh, ensure_ascii=False)
    return crudo


def resumen(crudo, propio):
    row = {k: "" for k in FIELDS}
    row.update(gtin=crudo["gtin"], fecha=crudo["fecha"], producto_catalogo=crudo.get("producto_catalogo", ""),
               nombre_catalogo=((crudo.get("producto") or {}).get("name") or ""))
    if not crudo.get("producto_catalogo"):
        row["nota"] = "sin producto de catálogo para el GTIN"
        return row
    r = RECH.get(crudo["gtin"])
    if r and r["producto_catalogo"] == crudo["producto_catalogo"]:
        row["nota"] = f"catálogo rechazado ({r['tipo'].replace('_', ' ')}): {r['motivo']}"
        return row
    otros = [it for it in crudo["items"] if it.get("price") and str(it.get("seller_id")) != str(propio)
             and (it.get("condition") or "new") == "new"]
    if not otros:
        row["nota"] = "sin publicaciones de otros vendedores"
        return row
    precios = sorted(float(it["price"]) for it in otros)
    med = statistics.median(precios)
    normales = [p for p in precios if p <= 2 * med]
    row.update(publicaciones_otros=len(otros), precio_promedio_otros=round(statistics.mean(normales), 2), precio_mediana_otros=round(med, 2),
               precio_min_otros=precios[0], precio_max_otros=precios[-1], publicaciones_atipicas=len(precios) - len(normales))
    vend = crudo.get("vendedores") or {}
    candidatos = [it for it in otros if float(it["price"]) <= 2 * med]
    best = max(candidatos, key=lambda it: ((vend.get(str(it["seller_id"])) or {}).get("ventas") or 0, -float(it["price"])))
    v = vend.get(str(best["seller_id"])) or {}
    row.update(precio_mejor_vendedor=float(best["price"]), item_mejor_vendedor=best["item_id"], vendedor_mejor=v.get("nickname", ""),
               ventas_vendedor_mejor=v.get("ventas", ""), metodo_mejor_vendedor="vendedor_con_mas_ventas")
    return row


def escribir(salida, filas):
    os.makedirs(os.path.dirname(salida), exist_ok=True)
    orden = [r["gtin"] for r in csv.DictReader(open(os.path.join(ROOT, "data", "prioridad.csv"), encoding="utf-8"))]
    pos = {g: i for i, g in enumerate(orden)}
    with open(salida, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        for r in sorted(filas.values(), key=lambda r: pos.get(r["gtin"], 10 ** 6)):
            w.writerow({k: r.get(k, "") for k in FIELDS})


def main():
    load_env()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--gtin", nargs="*")
    ap.add_argument("--limite", type=int)
    ap.add_argument("--hilos", type=int, default=4)
    ap.add_argument("--descripciones", action="store_true", help="guarda hasta 3 descripciones de otros vendedores por producto")
    ap.add_argument("--forzar", action="store_true", help="vuelve a consultar aunque exista trabajo/meli/<GTIN>.json")
    ap.add_argument("--guardar-catalogo", action="store_true", help="escribe el ID de catálogo encontrado por GTIN en product.json")
    ap.add_argument("--solo-csv", action="store_true")
    ap.add_argument("--salida", default=os.path.join(ROOT, "data", "competencia_meli.csv"))
    a = ap.parse_args()

    gtins = [r["gtin"] for r in csv.DictReader(open(os.path.join(ROOT, "data", "prioridad.csv"), encoding="utf-8"))]
    if a.gtin:
        gtins = [g for g in gtins if g in set(a.gtin)]
    if a.limite:
        gtins = gtins[: a.limite]
    propio = os.environ.get("ML_SELLER_ID", "")

    filas = {}
    if os.path.exists(a.salida):
        filas = {r["gtin"]: r for r in csv.DictReader(open(a.salida, encoding="utf-8"))}

    if a.solo_csv:
        for g in gtins:
            f = os.path.join(CRUDO, f"{g}.json")
            if os.path.exists(f):
                filas[g] = resumen(json.load(open(f, encoding="utf-8")), propio)
        escribir(a.salida, filas)
        print(f"{len(filas)} productos -> {os.path.relpath(a.salida, ROOT)}")
        return

    ml = Meli()
    if not propio:
        _, me = ml.get("/users/me")
        propio = str((me or {}).get("id", ""))
    vend = Vendedores(ml)
    pendientes = [g for g in gtins if a.forzar or not os.path.exists(os.path.join(CRUDO, f"{g}.json"))]
    for g in gtins:
        f = os.path.join(CRUDO, f"{g}.json")
        if g not in pendientes and os.path.exists(f):
            filas[g] = resumen(json.load(open(f, encoding="utf-8")), propio)
    print(f"{len(pendientes)} productos por consultar ({len(gtins) - len(pendientes)} ya estaban en {os.path.relpath(CRUDO, ROOT)}/)")
    hechos = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=a.hilos) as ex:
        futuros = {ex.submit(consultar, ml, vend, g, a.descripciones, a.guardar_catalogo): g for g in pendientes}
        for fu in concurrent.futures.as_completed(futuros):
            g = futuros[fu]
            try:
                filas[g] = resumen(fu.result(), propio)
            except SystemExit:
                raise
            except Exception as e:  # noqa: BLE001
                print(f"{g}: error {e}")
            hechos += 1
            if hechos % 50 == 0 or hechos == len(pendientes):
                escribir(a.salida, filas)
                vend.guardar()
                print(f"{hechos}/{len(pendientes)} consultados", flush=True)
    escribir(a.salida, filas)
    vend.guardar()
    con = sum(1 for r in filas.values() if r.get("precio_mejor_vendedor") not in ("", None))
    print(f"{len(filas)} productos en {os.path.relpath(a.salida, ROOT)}; {con} con precio de mejor vendedor")


if __name__ == "__main__":
    main()
