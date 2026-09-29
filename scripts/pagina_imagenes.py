#!/usr/bin/env python3
"""Lista las URLs de imágenes de producto que aparecen en una página web.

Uso: python scripts/pagina_imagenes.py <URL de la página> [palabra_clave ...]

Busca en og:image, twitter:image, JSON-LD (campo image), atributos data-zoom/data-large y <img>.
Imprime primero las candidatas más probables (las que contienen el GTIN o las palabras clave, o
vienen de metadatos del producto). No descarga nada: para guardar usa scripts/imagenes.py fetch.
"""
import html
import json
import re
import subprocess
import sys
from urllib.parse import urljoin

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
SKIP = re.compile(r"(logo|icon|sprite|banner|placeholder|pixel|tracking|facebook|payment|pago|visa|mastercard|flag|avatar|loader|blank|\.svg|\.gif)", re.I)


def get(url):
    r = subprocess.run(["curl", "-sSL", "-m", "40", "-A", UA, "-H", "Accept-Language: es-MX,es;q=0.9", url], capture_output=True)
    if r.returncode != 0:
        sys.exit(f"ERROR al abrir la página: {r.stderr.decode(errors='ignore')[:200]}")
    return r.stdout.decode("utf-8", errors="ignore")


def jsonld_images(doc):
    out = []
    for m in re.finditer(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', doc, re.S | re.I):
        try:
            data = json.loads(m.group(1).strip())
        except Exception:
            continue
        stack = [data]
        while stack:
            x = stack.pop()
            if isinstance(x, dict):
                if "image" in x:
                    v = x["image"]
                    if isinstance(v, str):
                        out.append(v)
                    elif isinstance(v, list):
                        out += [i if isinstance(i, str) else i.get("url", "") for i in v if i]
                    elif isinstance(v, dict):
                        out.append(v.get("url", ""))
                stack += list(x.values())
            elif isinstance(x, list):
                stack += x
    return out


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    url = sys.argv[1]
    keys = [k.lower() for k in sys.argv[2:]]
    doc = get(url)
    cands = []
    for pat in [r'<meta[^>]+(?:property|name)=["\'](?:og:image(?::secure_url)?|twitter:image)["\'][^>]+content=["\']([^"\']+)',
                r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\'](?:og:image|twitter:image)']:
        cands += [("meta", u) for u in re.findall(pat, doc, re.I)]
    cands += [("jsonld", u) for u in jsonld_images(doc)]
    for attr in ["data-zoom-image", "data-zoom", "data-large", "data-full", "data-src", "data-original", "src", "href"]:
        for u in re.findall(attr + r'=["\']([^"\']+\.(?:jpe?g|png|webp)(?:\?[^"\']*)?)["\']', doc, re.I):
            cands.append(("html", u))
    for u in re.findall(r'srcset=["\']([^"\']+)["\']', doc, re.I):
        parts = [p.strip().split(" ")[0] for p in u.split(",") if p.strip()]
        if parts:
            cands.append(("srcset", parts[-1]))
    seen, ranked = set(), []
    for src, u in cands:
        u = html.unescape(u.strip())
        if not u or u.startswith("data:"):
            continue
        u = urljoin(url, u)
        if u in seen or SKIP.search(u):
            continue
        seen.add(u)
        low = u.lower()
        score = {"meta": 3, "jsonld": 3, "html": 1, "srcset": 1}[src]
        score += sum(2 for k in keys if k and k in low)
        ranked.append((score, src, u))
    ranked.sort(key=lambda x: -x[0])
    for score, src, u in ranked[:25]:
        print(f"{score}\t{src}\t{u}")
    if not ranked:
        print("SIN_IMAGENES")


if __name__ == "__main__":
    main()
