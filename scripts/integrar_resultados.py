#!/usr/bin/env python3
"""Integra a products/<GTIN>/product.json los resultados de una sesión y actualiza el historial de avance.

Uso: python scripts/integrar_resultados.py --sesion 7 [--fecha 2026-09-30]

Lee trabajo/sesion_NN/lotes/*.json y trabajo/sesion_NN/resultados/*.json (contrato en docs/CONTRATOS.md):
- inv_XX.json: reemplaza titulo, descripcion, ficha, receta_mx, url_oficial, fuentes, categorías de Mercado Libre
  e investigacion. confianza alta o media => estado "verificado"; baja => "sin_verificar".
- img_XX.json: reemplaza ficha y agrega fuentes nuevas y notas de fotos.
Las fotos ya quedaron registradas por scripts/imagenes.py; aquí solo se mide su lado útil.
Valida títulos de 60 caracteres o menos y que cada categoria_id exista en el árbol de categorías.
Actualiza config/mercadolibre.json (avance.sesiones_realizadas e historial).
"""
import argparse
import csv
import datetime
import glob
import json
import os

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sesion", type=int, required=True)
    ap.add_argument("--fecha", default=datetime.date.today().isoformat())
    a = ap.parse_args()
    base = os.path.join(ROOT, "trabajo", f"sesion_{a.sesion:02d}")
    with open(os.path.join(ROOT, "reference", "mercadolibre", "categorias_mlm_hojas_publicables.csv"), encoding="utf-8") as fh:
        cats = {r["ID"] for r in csv.DictReader(fh)}
    probs, inv_g, img_g = [], [], []
    for f in sorted(glob.glob(os.path.join(base, "resultados", "*.json"))):
        kind = "inv" if os.path.basename(f).startswith("inv_") else "img"
        d = json.load(open(f, encoding="utf-8"))
        lote = json.load(open(os.path.join(base, "lotes", os.path.basename(f)), encoding="utf-8"))
        if [x["gtin"] for x in lote] != [str(x["gtin"]) for x in d]:
            probs.append((os.path.basename(f), "los GTIN no coinciden con el lote"))
        for x in d:
            g = str(x["gtin"])
            pf = os.path.join(ROOT, "products", g, "product.json")
            p = json.load(open(pf, encoding="utf-8"))
            if kind == "inv":
                if len(x["titulo"]) > 60:
                    probs.append((g, "título de más de 60 caracteres"))
                if x["categoria_id"] not in cats:
                    probs.append((g, f"categoría inexistente {x['categoria_id']}"))
                p.update(titulo=x["titulo"], descripcion=x["descripcion"], ficha=x["ficha"], receta_mx=x["receta_mx"],
                         url_oficial=x.get("url_oficial", ""), fuentes=x.get("fuentes", []))
                p["marketplaces"]["mercadolibre"].update(categoria_id=x["categoria_id"], categoria_ruta=x["categoria_ruta"],
                                                         categoria_rx_sugerida=x.get("categoria_rx_sugerida", ""),
                                                         catalogo_id=x.get("catalogo_ml", ""))
                p["investigacion"] = dict(estado="verificado" if x["confianza"] in ("alta", "media") else "sin_verificar",
                                          confianza=x["confianza"], encontrado_por=x["encontrado_por"], notas=x.get("notas", ""),
                                          notas_imagenes=x.get("notas_imagenes", ""), fecha=a.fecha, sesion=a.sesion)
                inv_g.append(g)
            else:
                p["ficha"] = x.get("ficha") or p["ficha"]
                p["fuentes"] = p.get("fuentes", []) + [u for u in x.get("fuentes_nuevas", []) if u not in p.get("fuentes", [])]
                p["investigacion"]["notas_imagenes"] = x.get("notas_imagenes", "")
                img_g.append(g)
            for im in p.get("imagenes", []):
                fp = os.path.join(ROOT, "products", g, "images", im["archivo"])
                if os.path.exists(fp) and "lado_util" not in im:
                    b = Image.open(fp).convert("L").point(lambda v: 255 if v < 245 else 0).getbbox()
                    im["lado_util"] = max(b[2] - b[0], b[3] - b[1]) if b else 0
            json.dump(p, open(pf, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    def load(g):
        return json.load(open(os.path.join(ROOT, "products", g, "product.json"), encoding="utf-8"))

    ver = sum(1 for g in inv_g if load(g)["investigacion"]["estado"] == "verificado")
    fot = sum(1 for g in inv_g + img_g if load(g).get("imagenes"))
    cfg_path = os.path.join(ROOT, "config", "mercadolibre.json")
    cfg = json.load(open(cfg_path, encoding="utf-8"))
    av = cfg.setdefault("avance", {})
    av["sesiones_realizadas"] = max(av.get("sesiones_realizadas", 0), a.sesion)
    hist = [h for h in av.get("historial", []) if h["sesion"] != a.sesion]
    hist.append({"sesion": a.sesion, "fecha": a.fecha, "investigados": len(inv_g), "verificados": ver, "con_fotos": fot})
    av["historial"] = sorted(hist, key=lambda h: h["sesion"])
    json.dump(cfg, open(cfg_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"problemas: {probs}")
    print(f"sesión {a.sesion}: investigados {len(inv_g)}, verificados {ver}, productos con fotos {fot}, solo fotos {len(img_g)}")


if __name__ == "__main__":
    main()
