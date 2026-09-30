#!/usr/bin/env python3
"""Genera MANUAL.pdf (raíz del repositorio) a partir de docs/manual/manual.html.

Uso:
  python scripts/build_manual.py              # solo el PDF, con las capturas existentes
  python scripts/build_manual.py --capturas   # vuelve a tomar las capturas del visor y luego genera el PDF

Necesita Playwright con Chromium (pip install playwright; en Claude ya está preinstalado). Si el visor cambia,
actualiza docs/manual/manual.html y corre con --capturas.
"""
import argparse
import os

from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANUAL = os.path.join(ROOT, "docs", "manual")
IMG = os.path.join(MANUAL, "img")
VISOR = "file://" + os.path.join(ROOT, "visor", "index.html")
SALIDA = os.path.join(ROOT, "MANUAL.pdf")


def lanzar(p):
    try:
        return p.chromium.launch()
    except Exception:
        return p.chromium.launch(executable_path="/opt/pw-browsers/chromium")


def capturas(p):
    os.makedirs(IMG, exist_ok=True)
    b = lanzar(p)
    ctx = b.new_context(viewport={"width": 1360, "height": 860}, device_scale_factor=2, color_scheme="light")
    pg = ctx.new_page()
    pg.goto(VISOR)
    pg.wait_for_timeout(1500)

    # 1. Catálogo en cuadrícula
    pg.screenshot(path=os.path.join(IMG, "01_catalogo.png"), clip={"x": 0, "y": 0, "width": 1360, "height": 600})

    # 2. Filtros: autocompletado de categoría y filtro de fotos
    pg.locator("#f-ind-fotos label.toggle").nth(1).click()
    pg.fill("#in-categoria", "leche")
    pg.wait_for_timeout(400)
    pg.screenshot(path=os.path.join(IMG, "02_filtros.png"), clip={"x": 0, "y": 150, "width": 1360, "height": 560})
    pg.keyboard.press("Enter")
    pg.wait_for_timeout(300)
    pg.click("#limpiar")

    # 3. Lista con precios editables y selección
    pg.click("#vista-lista")
    pg.wait_for_timeout(500)
    fila = pg.locator("#tabla-body tr").first
    fila.locator("td[data-col=costo_envio] input").fill("110")
    fila.locator("td[data-col=costo_envio] input").press("Enter")
    for n in (0, 1, 2):
        pg.locator("#tabla-body tr").nth(n).locator(".tsel input").check()
    pg.wait_for_timeout(300)
    pg.evaluate("document.getElementById('tabla-body').closest('.tabla-wrap').scrollLeft = 260")
    top = pg.locator("#barra-sel").bounding_box()["y"] - 10
    pg.screenshot(path=os.path.join(IMG, "03_lista.png"), clip={"x": 320, "y": top, "width": 1040, "height": 600})

    # 4. Detalle con el formulario de precios
    pg.locator("#tabla-body tr").nth(1).locator("td[data-col=titulo]").click()
    pg.wait_for_timeout(600)
    sec = pg.locator("#det-precios")
    sec.scroll_into_view_if_needed()
    bb = sec.bounding_box()
    pg.screenshot(path=os.path.join(IMG, "04_detalle_precios.png"), clip={"x": bb["x"] - 8, "y": max(bb["y"] - 8, 0), "width": bb["width"] + 16, "height": min(bb["height"] + 16, 860)})
    pg.click("#det-cerrar")

    # 5. Tarjeta con «Editar precios»
    pg.click("#vista-cuadricula")
    pg.wait_for_timeout(400)
    card = pg.locator("#vista-grid .card").nth(1)
    card.scroll_into_view_if_needed()
    bb = card.bounding_box()
    pg.screenshot(path=os.path.join(IMG, "05_tarjeta.png"), clip={"x": bb["x"] - 6, "y": bb["y"] - 6, "width": bb["width"] + 12, "height": bb["height"] + 12})

    # 6. Sección Pendientes
    pg.evaluate("window.scrollTo(0, 0)")
    pg.click("#sel-quitar")
    pg.click("#sec-pendientes")
    pg.wait_for_timeout(500)
    pg.locator("#f-pend label.toggle", has_text="Sin fotos").click()
    pg.wait_for_timeout(400)
    pg.screenshot(path=os.path.join(IMG, "06_pendientes.png"), clip={"x": 320, "y": 190, "width": 1040, "height": 560})
    b.close()


def pdf(p):
    b = lanzar(p)
    pg = b.new_page()
    pg.goto("file://" + os.path.join(MANUAL, "manual.html"))
    pg.wait_for_load_state("networkidle")
    pg.wait_for_timeout(800)
    pie = ('<div style="width:100%;font:8px Helvetica,Arial,sans-serif;color:#6b7684;padding:0 17mm;display:flex;justify-content:space-between">'
           '<span>Manual del visor y del repositorio · marketplaces-product-images</span>'
           '<span><span class="pageNumber"></span> / <span class="totalPages"></span></span></div>')
    pg.pdf(path=SALIDA, format="Letter", print_background=True, display_header_footer=True,
           header_template="<div></div>", footer_template=pie,
           margin={"top": "16mm", "bottom": "18mm", "left": "17mm", "right": "17mm"})
    b.close()
    print(f"{os.path.relpath(SALIDA, ROOT)} ({os.path.getsize(SALIDA) / 1e6:.1f} MB)")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--capturas", action="store_true")
    a = ap.parse_args()
    with sync_playwright() as p:
        if a.capturas:
            capturas(p)
        pdf(p)


if __name__ == "__main__":
    main()
