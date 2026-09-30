#!/usr/bin/env python3
"""Descarga, valida y guarda fotos de producto en products/<GTIN>/images/.

Comandos:
  python scripts/imagenes.py fetch <GTIN> --origen fabricante|catalogo_ml|tienda --pagina <URL de la página> <URL imagen> [<URL imagen> ...]
      Descarga cada imagen, la convierte a JPG con fondo blanco, la hace cuadrada (relleno blanco),
      la limita a 2000 px por lado y la guarda como <GTIN>_<n>.jpg. Rechaza imágenes de menos de 500 px
      por lado o duplicadas. Registra cada foto en product.json["imagenes"] y genera una hoja de contacto
      para revisarla visualmente (ruta impresa al final).
  python scripts/imagenes.py rm <GTIN> <archivo>      Borra una foto equivocada y la quita de product.json.
  python scripts/imagenes.py list <GTIN>             Lista las fotos registradas.
  python scripts/imagenes.py contacto <GTIN>         Regenera la hoja de contacto.
  python scripts/imagenes.py reprocesar              Recorta el borde blanco sobrante y centra todas las fotos.
"""
import argparse
import datetime
import hashlib
import io
import json
import os
import subprocess
import sys

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MIN_SIDE = 500
MAX_SIDE = 2000
MARGIN = 0.04
MAX_IMGS = 6
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
CONTACT_DIR = os.environ.get("CONTACT_DIR", "/tmp/contactos")


def pdir(gtin):
    return os.path.join(ROOT, "products", gtin)


def load(gtin):
    p = os.path.join(pdir(gtin), "product.json")
    if not os.path.exists(p):
        sys.exit(f"No existe {p}")
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def save(gtin, data):
    p = os.path.join(pdir(gtin), "product.json")
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    os.replace(tmp, p)


def download(url):
    r = subprocess.run(["curl", "-sSL", "-m", "40", "--max-filesize", "20000000", "-A", UA,
                        "-H", "Accept: image/avif,image/webp,image/png,image/jpeg,*/*", url],
                       capture_output=True)
    if r.returncode != 0 or not r.stdout:
        raise RuntimeError(f"descarga fallida ({r.returncode}): {r.stderr.decode(errors='ignore')[:150]}")
    return r.stdout


def normalize(raw):
    im = Image.open(io.BytesIO(raw))
    im.load()
    if im.mode in ("P", "LA", "RGBA") or (im.mode == "P" and "transparency" in im.info):
        im = im.convert("RGBA")
        bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
        bg.alpha_composite(im)
        im = bg.convert("RGB")
    else:
        im = im.convert("RGB")
    w, h = im.size
    side = max(w, h)
    if side < MIN_SIDE:
        raise ValueError(f"muy pequeña ({w}x{h})")
    im = trim(im)
    w2, h2 = im.size
    side = max(w2, h2)
    side = int(side * (1 + 2 * MARGIN))
    canvas = Image.new("RGB", (side, side), (255, 255, 255))
    canvas.paste(im, ((side - w2) // 2, (side - h2) // 2))
    if side > MAX_SIDE:
        canvas = canvas.resize((MAX_SIDE, MAX_SIDE), Image.LANCZOS)
    out = io.BytesIO()
    canvas.save(out, "JPEG", quality=90, optimize=True)
    return out.getvalue(), (w, h), canvas.size[0]


def trim(im):
    """Recorta el borde blanco sobrante; si el recorte deja la foto por debajo de 500 px, no recorta."""
    gray = im.convert("L").point(lambda v: 255 if v < 245 else 0)
    box = gray.getbbox()
    if not box:
        return im
    cropped = im.crop(box)
    if max(cropped.size) * (1 + 2 * MARGIN) < MIN_SIDE:
        return im
    return cropped


def reprocess(path):
    """Vuelve a recortar y centrar una foto ya guardada."""
    im = Image.open(path).convert("RGB")
    raw = io.BytesIO()
    im.save(raw, "PNG")
    jpg, _, side = normalize(raw.getvalue())
    with open(path, "wb") as fh:
        fh.write(jpg)
    return side


def lado_util(path):
    """Pixeles que ocupa el producto (lado mayor de su recuadro sin el fondo blanco)."""
    b = Image.open(path).convert("L").point(lambda v: 255 if v < 245 else 0).getbbox()
    return max(b[2] - b[0], b[3] - b[1]) if b else 0


def contact_sheet(gtin):
    data = load(gtin)
    imgs = data.get("imagenes", [])
    os.makedirs(CONTACT_DIR, exist_ok=True)
    path = os.path.join(CONTACT_DIR, f"{gtin}.jpg")
    if not imgs:
        return None
    t = 260
    sheet = Image.new("RGB", (t * len(imgs), t + 24), (235, 235, 235))
    d = ImageDraw.Draw(sheet)
    for i, im in enumerate(imgs):
        f = os.path.join(pdir(gtin), "images", im["archivo"])
        try:
            x = Image.open(f).convert("RGB")
            x.thumbnail((t - 6, t - 6))
            sheet.paste(x, (i * t + 3, 3))
        except Exception:
            pass
        d.text((i * t + 6, t + 4), im["archivo"], fill=(0, 0, 0))
    sheet.save(path, "JPEG", quality=80)
    return path


def cmd_fetch(a):
    data = load(a.gtin)
    imgs = data.setdefault("imagenes", [])
    idir = os.path.join(pdir(a.gtin), "images")
    os.makedirs(idir, exist_ok=True)
    hashes = set()
    for im in imgs:
        f = os.path.join(idir, im["archivo"])
        if os.path.exists(f):
            hashes.add(hashlib.md5(open(f, "rb").read()).hexdigest())
    used = {im["archivo"] for im in imgs}
    for url in a.urls:
        if len(imgs) >= MAX_IMGS:
            print(f"OMITIDA {url}: ya hay {MAX_IMGS} fotos")
            continue
        try:
            jpg, orig, side = normalize(download(url))
        except Exception as e:
            print(f"RECHAZADA {url}: {e}")
            continue
        h = hashlib.md5(jpg).hexdigest()
        if h in hashes:
            print(f"DUPLICADA {url}")
            continue
        n = 1
        while f"{a.gtin}_{n}.jpg" in used:
            n += 1
        name = f"{a.gtin}_{n}.jpg"
        with open(os.path.join(idir, name), "wb") as fh:
            fh.write(jpg)
        used.add(name)
        hashes.add(h)
        imgs.append({"archivo": name, "origen": a.origen, "fuente_url": url, "pagina": a.pagina,
                     "ancho_original": orig[0], "alto_original": orig[1], "lado_final": side,
                     "lado_util": lado_util(os.path.join(idir, name)), "fecha": datetime.date.today().isoformat()})
        print(f"GUARDADA {name} ({orig[0]}x{orig[1]} -> {side}x{side}) desde {url}")
    save(a.gtin, data)
    p = contact_sheet(a.gtin)
    if p:
        print(f"HOJA_DE_CONTACTO {p}")


def cmd_rm(a):
    data = load(a.gtin)
    data["imagenes"] = [im for im in data.get("imagenes", []) if im["archivo"] != a.archivo]
    f = os.path.join(pdir(a.gtin), "images", a.archivo)
    if os.path.exists(f):
        os.remove(f)
    save(a.gtin, data)
    print(f"BORRADA {a.archivo}")
    p = contact_sheet(a.gtin)
    if p:
        print(f"HOJA_DE_CONTACTO {p}")


def cmd_list(a):
    for im in load(a.gtin).get("imagenes", []):
        print(im["archivo"], im["origen"], im["lado_final"], im["fuente_url"])


def cmd_reprocesar():
    """Recorta y centra de nuevo todas las fotos guardadas."""
    base = os.path.join(ROOT, "products")
    n = 0
    for g in sorted(os.listdir(base)):
        pj = os.path.join(base, g, "product.json")
        if not os.path.exists(pj):
            continue
        data = load(g)
        for im in data.get("imagenes", []):
            f = os.path.join(base, g, "images", im["archivo"])
            if os.path.exists(f):
                im["lado_final"] = reprocess(f)
                im["lado_util"] = lado_util(f)
                n += 1
        save(g, data)
    print(f"{n} fotos reprocesadas")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fetch")
    f.add_argument("gtin")
    f.add_argument("--origen", required=True, choices=["fabricante", "catalogo_ml", "tienda"])
    f.add_argument("--pagina", default="")
    f.add_argument("urls", nargs="+")
    r = sub.add_parser("rm")
    r.add_argument("gtin")
    r.add_argument("archivo")
    l = sub.add_parser("list")
    l.add_argument("gtin")
    c = sub.add_parser("contacto")
    c.add_argument("gtin")
    sub.add_parser("reprocesar")
    a = ap.parse_args()
    if a.cmd == "fetch":
        cmd_fetch(a)
    elif a.cmd == "rm":
        cmd_rm(a)
    elif a.cmd == "list":
        cmd_list(a)
    elif a.cmd == "reprocesar":
        cmd_reprocesar()
    else:
        print(contact_sheet(a.gtin))


if __name__ == "__main__":
    main()
