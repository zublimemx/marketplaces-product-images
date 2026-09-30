#!/usr/bin/env python3
"""Precios de competencia en Mercado Libre México con la API oficial (y, opcionalmente, fotos de catálogo).

Llena data/competencia_meli.csv (versionado), que scripts/build_mercadolibre.py y scripts/build_visor.py usan para las columnas
"Precio Meli promedio otros vendedores" y "Precio mejor vendedor".

IMPORTANTE: se escribió sin poder probarlo contra la API real (no había credenciales). Corre primero
con --muestra 3 para guardar las respuestas crudas en trabajo/meli_muestras/ y ajusta los campos si difieren.
Detalles y supuestos en docs/MERCADOLIBRE_API.md.

Credenciales (variables de entorno o archivo .env en la raíz, nunca en git):
  insumos/ml_token.json                de scripts/meli_auth.py (código de autorización); se renueva solo, o bien
  ML_ACCESS_TOKEN                      token vigente (dura unas 6 horas), o bien
  ML_CLIENT_ID, ML_CLIENT_SECRET, ML_REFRESH_TOKEN   para renovarlo solo. Mercado Libre entrega un refresh token
                                       nuevo en cada renovación: se guarda en insumos/ml_token.json y se usa en la siguiente corrida.
  ML_SELLER_ID                         (opcional) tu seller_id, para excluir tus propias publicaciones; si falta se consulta /users/me.

Uso:
  python scripts/meli_precios.py [--gtin 7501... ...] [--limite N] [--muestra N]
                                 [--guardar-catalogo] [--fotos-catalogo] [--salida data/competencia_meli.csv]

Por cada GTIN (en el orden de data/prioridad.csv):
 1. Busca el producto de catálogo: GET /products/search?status=active&site_id=MLM&product_identifier=<GTIN>
    (si no hay, usa marketplaces.mercadolibre.catalogo_id de product.json).
 2. Con catálogo: GET /products/<id> (buy_box_winner, fotos) y GET /products/<id>/items (publicaciones que compiten).
    Sin catálogo: GET /sites/MLM/search?q=<GTIN>.
 3. Promedio = media de precios de publicaciones de otros vendedores (condición nueva).
    Mejor vendedor = publicación con mayor sold_quantity si la API lo entrega (GET /items?ids=…); si no, el ganador
    de la compra del catálogo (buy_box_winner); si tampoco, la primera por relevancia de la búsqueda. La columna
    metodo_mejor_vendedor dice cuál se usó.
--guardar-catalogo escribe el ID de catálogo en product.json. --fotos-catalogo descarga las fotos del catálogo
(origen catalogo_ml) para productos sin fotos o con todas sus fotos de baja resolución, usando scripts/imagenes.py.
"""
import argparse
import csv
import datetime
import json
import os
import statistics
import subprocess
import sys
import time

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API = "https://api.mercadolibre.com"
SITE = "MLM"
TOKEN_FILE = os.path.join(ROOT, "insumos", "ml_token.json")
FIELDS = ["gtin", "producto_catalogo", "publicaciones_otros", "precio_promedio_otros", "precio_min_otros", "precio_max_otros",
          "precio_mejor_vendedor", "item_mejor_vendedor", "metodo_mejor_vendedor", "fecha", "nota"]


def load_env():
    path = os.path.join(ROOT, ".env")
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


class Meli:
    def __init__(self, muestra=0):
        self.s = requests.Session()
        self.muestra = muestra
        self.n_muestra = 0
        self.ultimo_status = None
        self.token = os.environ.get("ML_ACCESS_TOKEN")
        if os.path.exists(TOKEN_FILE):  # token de scripts/meli_auth.py o de una renovación anterior
            t = json.load(open(TOKEN_FILE))
            if t.get("access_token") and t.get("vence", "") > datetime.datetime.now().isoformat():
                self.token = t["access_token"]
            elif t.get("refresh_token"):
                self.token = None
        if not self.token:
            self.refresh()
        self.s.headers["Authorization"] = f"Bearer {self.token}"

    def refresh(self):
        rt = os.environ.get("ML_REFRESH_TOKEN")
        if os.path.exists(TOKEN_FILE):
            rt = json.load(open(TOKEN_FILE)).get("refresh_token") or rt
        cid, sec = os.environ.get("ML_CLIENT_ID"), os.environ.get("ML_CLIENT_SECRET")
        if not (cid and sec and rt):
            sys.exit("Faltan credenciales: define ML_ACCESS_TOKEN o ML_CLIENT_ID, ML_CLIENT_SECRET y ML_REFRESH_TOKEN (ver .env.example)")
        r = requests.post(f"{API}/oauth/token", data={"grant_type": "refresh_token", "client_id": cid, "client_secret": sec, "refresh_token": rt},
                          headers={"Accept": "application/json"}, timeout=30)
        if r.status_code != 200:
            sys.exit(f"No se pudo renovar el token: {r.status_code} {r.text[:300]}")
        data = r.json()
        vence = datetime.datetime.now() + datetime.timedelta(seconds=int(data.get("expires_in", 21600)) - 300)
        os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
        json.dump({"access_token": data["access_token"], "refresh_token": data.get("refresh_token"), "vence": vence.isoformat(timespec="seconds"),
                   "obtenido": datetime.datetime.now().isoformat(timespec="seconds")}, open(TOKEN_FILE, "w"), indent=2)
        self.token = data["access_token"]
        self.s.headers["Authorization"] = f"Bearer {self.token}"

    def get(self, path, params=None, etiqueta=""):
        for intento in range(5):
            r = self.s.get(f"{API}{path}", params=params, timeout=30)
            if r.status_code == 401 and intento == 0 and (os.environ.get("ML_REFRESH_TOKEN") or os.path.exists(TOKEN_FILE)):
                self.refresh()
                continue
            if r.status_code == 429:
                time.sleep(2 ** intento)
                continue
            break
        if self.muestra and self.n_muestra < self.muestra * 6:
            d = os.path.join(ROOT, "trabajo", "meli_muestras")
            os.makedirs(d, exist_ok=True)
            self.n_muestra += 1
            with open(os.path.join(d, f"{self.n_muestra:03d}_{etiqueta}.json"), "w", encoding="utf-8") as fh:
                json.dump({"url": r.url, "status": r.status_code, "body": r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text[:2000]},
                          fh, ensure_ascii=False, indent=2)
        time.sleep(0.15)
        self.ultimo_status = r.status_code
        if r.status_code != 200:
            return None
        return r.json()


def precios_de(items, own):
    return [it for it in items if it.get("price") and str(it.get("seller_id")) != str(own) and it.get("condition", "new") in ("new", None)]


def main():
    load_env()
    ap = argparse.ArgumentParser()
    ap.add_argument("--gtin", nargs="*")
    ap.add_argument("--limite", type=int)
    ap.add_argument("--muestra", type=int, default=0, help="guarda respuestas crudas de los primeros N productos")
    ap.add_argument("--guardar-catalogo", action="store_true")
    ap.add_argument("--fotos-catalogo", action="store_true")
    ap.add_argument("--salida", default=os.path.join(ROOT, "data", "competencia_meli.csv"))
    a = ap.parse_args()

    with open(os.path.join(ROOT, "data", "prioridad.csv"), encoding="utf-8") as fh:
        gtins = [r["gtin"] for r in csv.DictReader(fh)]
    if a.gtin:
        gtins = [g for g in gtins if g in set(a.gtin)]
    if a.limite:
        gtins = gtins[: a.limite]

    ml = Meli(muestra=a.muestra)
    own = os.environ.get("ML_SELLER_ID")
    if not own:
        me = ml.get("/users/me", etiqueta="users_me") or {}
        own = str(me.get("id", ""))

    previos = {}
    if os.path.exists(a.salida):
        with open(a.salida, encoding="utf-8") as fh:
            previos = {r["gtin"]: r for r in csv.DictReader(fh)}

    hoy = datetime.date.today().isoformat()
    for n, g in enumerate(gtins, 1):
        pj = os.path.join(ROOT, "products", g, "product.json")
        prod = json.load(open(pj, encoding="utf-8"))
        row = {k: "" for k in FIELDS}
        row.update(gtin=g, fecha=hoy)
        pid = ""
        res = ml.get("/products/search", {"status": "active", "site_id": SITE, "product_identifier": g}, etiqueta=f"{g}_products_search") or {}
        if ml.ultimo_status in (401, 403):
            sys.exit(f"La API respondió {ml.ultimo_status} en /products/search: revisa el token, los permisos de la aplicación "
                     "y que la red del entorno permita api.mercadolibre.com")
        results = res.get("results") or []
        if results:
            pid = results[0].get("id", "")
        if not pid:
            pid = prod["marketplaces"]["mercadolibre"].get("catalogo_id", "")
        items, bbw, metodo = [], None, ""
        if pid:
            row["producto_catalogo"] = pid
            p = ml.get(f"/products/{pid}", etiqueta=f"{g}_product") or {}
            bbw = p.get("buy_box_winner")
            its = ml.get(f"/products/{pid}/items", etiqueta=f"{g}_product_items") or {}
            items = [{"id": it.get("item_id"), "price": it.get("price"), "seller_id": it.get("seller_id"), "condition": it.get("condition", "new")}
                     for it in its.get("results", [])]
            if a.guardar_catalogo and prod["marketplaces"]["mercadolibre"].get("catalogo_id") != pid:
                prod["marketplaces"]["mercadolibre"]["catalogo_id"] = pid
                json.dump(prod, open(pj, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
            if a.fotos_catalogo:
                bajas = [im for im in prod.get("imagenes", []) if im.get("lado_util", 9999) < 500]
                if not prod.get("imagenes") or len(bajas) == len(prod["imagenes"]):
                    urls = [pic.get("url") for pic in p.get("pictures", []) if pic.get("url")][:4]
                    if urls:
                        subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "imagenes.py"), "fetch", g, "--origen", "catalogo_ml",
                                        "--pagina", f"https://www.mercadolibre.com.mx/p/{pid}", *urls])
        else:
            s = ml.get(f"/sites/{SITE}/search", {"q": g, "limit": 50}, etiqueta=f"{g}_site_search") or {}
            items = [{"id": it.get("id"), "price": it.get("price"), "seller_id": (it.get("seller") or {}).get("id"),
                      "condition": it.get("condition", "new"), "sold_quantity": it.get("sold_quantity")} for it in s.get("results", [])]
            metodo = "busqueda_relevancia" if items else ""

        otros = precios_de(items, own)
        if otros:
            ids = [it["id"] for it in otros if it.get("id")]
            if ids and not any(it.get("sold_quantity") for it in otros):
                for i in range(0, len(ids), 20):
                    det = ml.get("/items", {"ids": ",".join(ids[i:i + 20]), "attributes": "id,price,sold_quantity,seller_id"}, etiqueta=f"{g}_items") or []
                    sold = {d["body"]["id"]: d["body"].get("sold_quantity") for d in det if isinstance(d, dict) and d.get("code") == 200}
                    for it in otros:
                        if it.get("id") in sold:
                            it["sold_quantity"] = sold[it["id"]]
            precios = [float(it["price"]) for it in otros]
            row.update(publicaciones_otros=len(otros), precio_promedio_otros=round(statistics.mean(precios), 2),
                       precio_min_otros=min(precios), precio_max_otros=max(precios))
            con_ventas = [it for it in otros if it.get("sold_quantity")]
            if con_ventas:
                best = max(con_ventas, key=lambda it: it["sold_quantity"])
                row.update(precio_mejor_vendedor=best["price"], item_mejor_vendedor=best["id"], metodo_mejor_vendedor="mayor_sold_quantity")
            elif bbw and str(bbw.get("seller_id")) != str(own):
                row.update(precio_mejor_vendedor=bbw.get("price"), item_mejor_vendedor=bbw.get("item_id"), metodo_mejor_vendedor="ganador_catalogo")
            elif metodo:
                row.update(precio_mejor_vendedor=otros[0]["price"], item_mejor_vendedor=otros[0]["id"], metodo_mejor_vendedor=metodo)
        else:
            row["nota"] = "sin publicaciones de otros vendedores" if (pid or items) else "sin resultados en la API"
        previos[g] = row
        if n % 25 == 0 or n == len(gtins):
            os.makedirs(os.path.dirname(a.salida), exist_ok=True)
            with open(a.salida, "w", encoding="utf-8", newline="") as fh:
                w = csv.DictWriter(fh, fieldnames=FIELDS)
                w.writeheader()
                for r in previos.values():
                    w.writerow({k: r.get(k, "") for k in FIELDS})
            print(f"{n}/{len(gtins)} productos consultados -> {a.salida}")


if __name__ == "__main__":
    main()
