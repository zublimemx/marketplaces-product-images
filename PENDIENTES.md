# Pendientes y próximas tareas

Última actualización: 2026-09-29, al agregar al visor la selección múltiple en la lista y la exportación del layout de Mercado Libre con las URLs de fotos de GitHub (`docs/VISOR.md`). Para continuar con otra IA, empieza por `AGENTS.md`.

## Estado

| Concepto | Productos |
|---|---|
| Productos a publicar | 1,163 |
| Completos (ficha verificada + fotos) | 1,130 (97.2 %) |
| Verificados sin fotos | 25 |
| Sin verificar (confianza baja, ya se intentaron 2 veces) | 8 |
| Pendientes de investigar | 0 |
| Sesiones realizadas | 7 |
| Faltan | 33 productos que necesitan ayuda del dueño (fotos propias o confirmar el producto) o una fuente distinta |

El detalle vivo está en `PROGRESO.md`.

Indicadores de calidad del visor (`visor/index.html`; reglas en `config/indicadores.json`):

| Indicador | Buena / completos | Regular | Mala / incompletos |
|---|---|---|---|
| Descripción | 1,015 | 140 (≈110 por confianza media, el resto con menos de 800 caracteres) | 8 (sin verificar) |
| Fotos | 429 | 691 (556 con una sola foto; 221 con la principal < 800 px) | 43 (33 sin fotos, 10 solo con fotos chicas) |
| Precios | 0 | — | 1,163 (falta el precio del mejor vendedor en Meli) |

Pendientes por producto (sección Pendientes del visor; reglas en `config/pendientes.json`): 43 productos con errores, 1,163 con pendientes y 829 con mejoras. Los más frecuentes: falta el precio del mejor vendedor (1,163), una sola foto (556), falta el costo de envío en productos de $299 o más (475), podría requerir receta (462), foto principal chica (221), precio en Meli muy arriba del de tienda (159), dato por confirmar en el empaque (146), sin existencia (146). Productos descartados de Meli: 0.

Layout vigente: `layouts/mercadolibre/layout_mercadolibre.xlsx` (versionado, recalculado). El visor exporta el mismo layout para cualquier selección de productos («Exportar layout Meli»). Precio Meli Final = mejor vendedor − $1 si no queda abajo del calculado; mientras no haya precios de competencia, todos se publican al calculado.

## Pendientes abiertos

| # | Pendiente | Quién | Notas |
|---|---|---|---|
| 1 | 8 productos sin verificar y 25 verificados sin fotos (lista: `python scripts/revisar_fotos.py` y la hoja Revisión) | Dueño + agente | Ya se intentaron por GTIN y nombre en 2 sesiones. Opciones: el dueño confirma el producto o toma fotos propias; o un agente prueba fotos de catálogo con la API (`scripts/meli_precios.py --fotos-catalogo`) |
| 2 | Productos con datos dudosos a confirmar en empaque (146 con «Dato por confirmar en el empaque» en el visor) | Dueño | P. ej. B-Tracet (GTIN 1306881052251 asociado a tramadol en distribuidores vs. nombre con lidocaína), Colgate Total 2x25 m sin foto. Exportarlos desde la sección Pendientes con la acción «Revisar con el dueño» |
| 3 | Precios de competencia: "Precio mejor vendedor" (define el Precio Meli Final y completa el indicador Precios) y "Precio Meli promedio otros vendedores" (referencia) | Dueño + agente | Script listo sin probar: `scripts/meli_precios.py` (ver `docs/MERCADOLIBRE_API.md`). Faltan credenciales de una aplicación de vendedor en `.env` y red hacia `api.mercadolibre.com`. Primera corrida con `--muestra 3 --limite 3` para ajustar campos. "Mejor vendedor": mayor `sold_quantity` si la API lo da; si no, ganador del catálogo |
| 4 | Costo real de envío a cargo del vendedor para productos ≥ $299 | Dueño | Hoy es 0 en `config/mercadolibre.json` (`precios.costo_envio_vendedor_estimado`) |
| 5 | Revisar productos con `receta_mx` = "Sí" o "Revisar" | Dueño | El dueño indicó que todo es de venta libre; Mercado Libre podría rechazar algunos (antibióticos, misoprostol como Cytotec y Cyrux, solución IV PiSA). Lista en la hoja Revisión |
| 6 | Revisar presentaciones dudosas contra el producto físico | Dueño | P. ej. Motrin Pediátrico (15 ml vs 150 ml), Nexcare "C24", Nivea exhibidor 10+2; ver `investigacion.notas` y la hoja Revisión |
| 7 | Mejorar fotos: 77 con producto < 500 px (en la sesión 7 se mejoraron 38 de 47 productos que solo tenían fotos chicas), 45 con posible fondo gris y algunas con bandas gráficas de tienda. Para subir de «regular» a «buena» en el visor: 556 productos con una sola foto y 221 con la principal < 800 px | Agente | `python scripts/revisar_fotos.py` genera la lista; fuentes útiles en `docs/agentes/fotos.md` (YZA, Walmart, Farmacias del Ahorro) o fotos de catálogo con `scripts/meli_precios.py --fotos-catalogo` |
| 8 | Verificar comisiones por categoría con el simulador de Mercado Libre | Dueño o agente | Las de `config/mercadolibre.json` son aproximadas (fuentes 2026) |
| 9 | Entrega en Google Sheets | Dueño | En claude.ai solo estaba el conector de Google Drive (sin Google Sheets); el layout se entrega como .xlsx y está versionado en `layouts/mercadolibre/` |
| 10 | Pasar el repositorio a privado cuando termine la importación | Dueño | Las URLs de fotos solo funcionan mientras es público. Desde que se versionan el layout y el visor, mientras el repositorio es público también quedan visibles precios y existencias |
| 11 | Revisar en el visor las 140 descripciones «regular» (sobre todo confianza media) | Dueño o agente | Filtro Descripción = Regular; confirmar presentación o completar secciones |
| 12 | Decidir qué productos se descartan de Meli (p. ej. los 159 cuyo precio en Meli queda al doble o más del de tienda, o los que requieren receta) | Dueño | Sección Pendientes → seleccionar → acción «Descartar de Meli» → exportar y adjuntar el Excel |

## Próximas tareas (en orden)

1. Procesar el Excel de pendientes que adjunte el dueño (`python scripts/solicitudes.py <archivo.xlsx>`; ver `docs/PROCEDIMIENTO_SESION.md` §4 ter).
2. Resolver con el dueño los 33 productos pendientes (8 sin verificar, 25 sin fotos).
3. Precios de competencia con la API de Mercado Libre en cuanto haya credenciales (`docs/MERCADOLIBRE_API.md`); de paso, fotos de catálogo para productos sin fotos o de baja resolución.
4. Mejorar fotos marcadas por `scripts/revisar_fotos.py`.
5. Regenerar el layout de Mercado Libre y el visor después de cada cambio (`docs/PROCEDIMIENTO_SESION.md` §4) y entregarlo; si el dueño comparte las plantillas oficiales del Publicador masivo, llenarlas directamente.
6. Layout de importación de **Odoo** (product.template: nombre, código de barras, referencia interna, precio, categoría, descripción de venta, imagen).
7. Layout de **Shopify** (CSV de productos: Handle, Title, Body (HTML), Vendor, Product Type, Variant SKU, Variant Barcode, Variant Price, Image Src…).
8. Layout de **Amazon** (plantilla de categoría de Seller Central México).

## Para retomar en otra IA

- Insumos que el dueño debe entregar de nuevo al agente (no están en git): los Excel de ventas y catálogos (en `insumos/originales/`) y, para la API, las credenciales en `.env`.
- Todo lo demás (fichas, fotos, reglas, contratos, procedimiento, scripts, historial, el layout vigente y el visor) está en el repositorio. Sin los Excel, `scripts/build_visor.py` toma precios y existencias del layout versionado.
