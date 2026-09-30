#!/usr/bin/env python3
"""Obtiene tokens de la API de Mercado Libre a partir de un código de autorización (flujo OAuth del vendedor).

1. El dueño abre en su navegador (con la cuenta de vendedor):
   https://auth.mercadolibre.com.mx/authorization?response_type=code&client_id=<ML_CLIENT_ID>&redirect_uri=<REDIRECT_URI>
2. Autoriza y copia el `code=TG-...` de la URL a la que lo redirige (vence en minutos).
3. python scripts/meli_auth.py --code TG-... --redirect-uri <REDIRECT_URI>

Guarda access_token, refresh_token y vencimiento en insumos/ml_token.json (ignorado por git). scripts/meli_precios.py
lo usa y lo renueva solo con el refresh token (la aplicación necesita el permiso offline_access).
Credenciales de la aplicación en .env: ML_CLIENT_ID y ML_CLIENT_SECRET.
"""
import argparse
import datetime
import json
import os
import sys

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOKEN_FILE = os.path.join(ROOT, "insumos", "ml_token.json")


def load_env():
    path = os.path.join(ROOT, ".env")
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def guardar(data):
    os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
    vence = datetime.datetime.now() + datetime.timedelta(seconds=int(data.get("expires_in", 21600)) - 300)
    json.dump({"access_token": data["access_token"], "refresh_token": data.get("refresh_token"), "user_id": data.get("user_id"),
               "scope": data.get("scope"), "vence": vence.isoformat(timespec="seconds"),
               "obtenido": datetime.datetime.now().isoformat(timespec="seconds")}, open(TOKEN_FILE, "w"), indent=2)


def main():
    load_env()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--code", required=True)
    ap.add_argument("--redirect-uri", required=True)
    a = ap.parse_args()
    cid, sec = os.environ.get("ML_CLIENT_ID"), os.environ.get("ML_CLIENT_SECRET")
    if not (cid and sec):
        sys.exit("Faltan ML_CLIENT_ID y ML_CLIENT_SECRET en .env")
    r = requests.post("https://api.mercadolibre.com/oauth/token", timeout=30, headers={"Accept": "application/json"},
                      data={"grant_type": "authorization_code", "client_id": cid, "client_secret": sec, "code": a.code.strip(),
                            "redirect_uri": a.redirect_uri.strip()})
    if r.status_code != 200:
        sys.exit(f"Mercado Libre respondió {r.status_code}: {r.text[:300]}")
    data = r.json()
    guardar(data)
    print(f"Token guardado en {os.path.relpath(TOKEN_FILE, ROOT)} · usuario {data.get('user_id')} · permisos: {data.get('scope')}"
          + ("" if data.get("refresh_token") else " · SIN refresh token: activa offline_access en la aplicación"))


if __name__ == "__main__":
    main()
