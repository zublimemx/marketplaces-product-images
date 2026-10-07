#!/usr/bin/env python3
"""Calcula el avance de fichas y fotos y escribe PROGRESO.md.

Uso: python scripts/progreso.py
"""
import json
import math
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    cfg = json.load(open(os.path.join(ROOT, "config", "mercadolibre.json"), encoding="utf-8"))
    av = cfg.get("avance", {})
    por_sesion = av.get("productos_por_sesion", 200)
    base = os.path.join(ROOT, "products")
    tot = ver = sinv = pend = fotos = comp = nfotos = 0
    for g in os.listdir(base):
        pj = os.path.join(base, g, "product.json")
        if not os.path.exists(pj):
            continue
        p = json.load(open(pj, encoding="utf-8"))
        tot += 1
        e = p["investigacion"]["estado"]
        ims = [im for im in p.get("imagenes", []) if os.path.exists(os.path.join(base, g, "images", im["archivo"]))]
        nfotos += len(ims)
        ver += e == "verificado"
        sinv += e == "sin_verificar"
        pend += e == "pendiente"
        fotos += bool(ims)
        comp += bool(ims) and e == "verificado"
    faltan = sinv + pend
    ses_faltan = math.ceil(faltan / por_sesion) if por_sesion else 0
    hechas = av.get("sesiones_realizadas", 0)
    lines = [
        "# Avance de fichas y fotos",
        "",
        "Completo = ficha verificada en internet y al menos una foto.",
        "",
        "| Concepto | Productos |",
        "|---|---|",
        f"| Productos a publicar | {tot} |",
        f"| Con ficha verificada | {ver} |",
        f"| Con al menos una foto | {fotos} |",
        f"| Completos | {comp} ({comp / tot:.1%}) |",
        f"| Sin verificar | {sinv} |",
        f"| Pendientes de investigar | {pend} |",
        f"| Por investigar | {faltan} |",
        "",
        f"Fotos guardadas: {nfotos}.",
        "",
        (f"Con {por_sesion} productos por sesión falta 1 sesión" if ses_faltan == 1 else f"Con {por_sesion} productos por sesión faltan {ses_faltan} sesiones")
        + f"; con las {hechas} ya hechas, el total estimado es de {hechas + ses_faltan} sesiones.",
        "",
        "## Exportación de Mercado Libre",
        "",
        "El visor modifica una copia de la planilla operativa fresca que carga el usuario. Las plantillas de referencia por categoría se listan y administran desde Configuración del visor; el parser conserva sus esquemas en caché con invalidación por archivo, checksum, fecha de modificación y estado activo. Nginx debe reenviar `/api/meli/` al backend local (ver `docs/nginx-visor.conf`).",
        "",
        "## Historial",
        "",
        "| Sesión | Fecha | Productos investigados | Fichas verificadas | Productos con fotos nuevas |",
        "|---|---|---|---|---|",
    ]
    for h in av.get("historial", []):
        lines.append(f"| {h['sesion']} | {h['fecha']} | {h['investigados']} | {h['verificados']} | {h['con_fotos']} |")
    open(os.path.join(ROOT, "PROGRESO.md"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
