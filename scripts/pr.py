#!/usr/bin/env python3
"""Crea un PR en GitHub y, opcionalmente, lo fusiona. Útil cuando no hay `gh` instalado.

Uso:
  python scripts/pr.py --rama sesion-07 --titulo "Sesión 7: ..." --cuerpo archivo.md [--fusionar] [--metodo merge|squash|rebase]

Requiere GH_TOKEN o GITHUB_TOKEN con permiso de escritura en el repositorio y la rama ya empujada.
"""
import argparse
import json
import os
import subprocess
import sys

REPO = "zublimemx/marketplaces-product-images"


def api(method, path, data=None):
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        sys.exit("Falta GH_TOKEN o GITHUB_TOKEN")
    cmd = ["curl", "-sS", "-X", method, "-H", f"Authorization: Bearer {token}", "-H", "Accept: application/vnd.github+json",
           "-H", "X-GitHub-Api-Version: 2022-11-28", f"https://api.github.com/repos/{REPO}{path}"]
    if data is not None:
        cmd += ["-d", json.dumps(data)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        sys.exit(f"Respuesta inesperada: {r.stdout[:300]} {r.stderr[:300]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rama", required=True)
    ap.add_argument("--titulo", required=True)
    ap.add_argument("--cuerpo", required=True, help="archivo Markdown con la descripción del PR")
    ap.add_argument("--base", default="main")
    ap.add_argument("--fusionar", action="store_true")
    ap.add_argument("--metodo", default="merge", choices=["merge", "squash", "rebase"])
    a = ap.parse_args()
    body = open(a.cuerpo, encoding="utf-8").read()
    pr = api("POST", "/pulls", {"title": a.titulo, "head": a.rama, "base": a.base, "body": body})
    if "number" not in pr:
        sys.exit(f"No se creó el PR: {pr.get('message')} {pr.get('errors', '')}")
    print(f"PR #{pr['number']} {pr['html_url']}")
    if a.fusionar:
        m = api("PUT", f"/pulls/{pr['number']}/merge", {"merge_method": a.metodo, "commit_title": f"{a.titulo} (#{pr['number']})"})
        if not m.get("merged"):
            sys.exit(f"No se fusionó: {m.get('message')}")
        print(f"Fusionado: {m.get('sha')}")


if __name__ == "__main__":
    main()
