# Pendientes y próximas tareas

Última actualización: 2026-09-29, al sumar el costo de envío ($75–$150 por peso) al Precio Meli calculado de los productos de $299 o más y hacer editables en el visor todos los parámetros de precio (`docs/VISOR.md`, `docs/REGLAS_NEGOCIO.md`). Para continuar con otra IA, empieza por `AGENTS.md`.

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

Pendientes por producto (sección Pendientes del visor; reglas en `config/pendientes.json`): 43 productos con errores, 1,163 con pendientes y 829 con mejoras. Los más frecuentes: falta el precio del mejor vendedor (1,163), una sola foto (556), podría requerir receta (462), foto principal chica (221), precio en Meli muy arriba del de tienda (159), dato por confirmar en el empaque (146), sin existencia (146). Productos descartados de Meli: 0.

Layout vigente: `layouts/mercadolibre/layout_mercadolibre.xlsx` (versionado, recalculado; hoja Precios con parámetros por producto). Costos de envío: 1,012 productos $75, 80 $90, 21 $105, 43 $125 y 7 $150 (`data/envios.csv`); se aplican a los 475 productos de $299 o más. Ajustes de precio versionados: 0 (`data/ajustes_precios.json`). El visor exporta el mismo layout para cualquier selección de productos («Exportar layout Meli»). Precio Meli Final = mejor vendedor − $1 si no queda abajo del calculado; mientras no haya precios de competencia, todos se publican al calculado.

## Pendientes abiertos

| # | Pendiente | Quién | Notas |
|---|---|---|---|
| 1 | 8 productos sin verificar y 25 verificados sin fotos (lista: `python scripts/revisar_fotos.py` y la hoja Revisión) | Dueño + agente | Ya se intentaron por GTIN y nombre en 2 sesiones. Opciones: el dueño confirma el producto o toma fotos propias; o un agente prueba fotos de catálogo con la API (`scripts/meli_precios.py --fotos-catalogo`) |
| 2 | Productos con datos dudosos a confirmar en empaque (146 con «Dato por confirmar en el empaque» en el visor) | Dueño | P. ej. B-Tracet (GTIN 1306881052251 asociado a tramadol en distribuidores vs. nombre con lidocaína), Colgate Total 2x25 m sin foto. Exportarlos desde la sección Pendientes con la acción «Revisar con el dueño» |
| 3 | Precios de competencia ("Precio mejor vendedor", que define el Precio Meli Final y completa el indicador Precios, y "Precio Meli promedio otros vendedores"), fotos de otros vendedores para productos sin fotos o con fotos malas, y descripciones de otros vendedores como fuente para las cortas | Dueño + agente | Credenciales de la aplicación en `.env` (29 sep 2026). **Bloqueado:** el access token entregado venció y la aplicación no acepta `client_credentials`. Falta que el dueño entregue un código de autorización (`code=TG-…`) y su URL de redirección → `python scripts/meli_auth.py --code … --redirect-uri …`, o un access token nuevo. Luego: `scripts/meli_precios.py --muestra 3 --limite 3` para ajustar campos y corrida completa (ver `docs/MERCADOLIBRE_API.md`) |
| 4 | Confirmar el costo de envío estimado ($75–$150 por peso) en los 475 productos de $299 o más | Dueño | Estimado con `scripts/envios.py` (`data/envios.csv`); se corrige producto por producto en el visor y se versiona con «Exportar ajustes de precio». Con la API se pueden tomar medidas reales del catálogo (`marketplaces.mercadolibre.paquete`) |
| 5 | Revisar productos con `receta_mx` = "Sí" o "Revisar" | Dueño | El dueño indicó que todo es de venta libre; Mercado Libre podría rechazar algunos (antibióticos, misoprostol como Cytotec y Cyrux, solución IV PiSA). Lista en la hoja Revisión |
| 6 | Revisar presentaciones dudosas contra el producto físico | Dueño | P. ej. Motrin Pediátrico (15 ml vs 150 ml), Nexcare "C24", Nivea exhibidor 10+2; ver `investigacion.notas` y la hoja Revisión |
| 7 | Mejorar fotos: 77 con producto < 500 px (en la sesión 7 se mejoraron 38 de 47 productos que solo tenían fotos chicas), 45 con posible fondo gris y algunas con bandas gráficas de tienda. Para subir de «regular» a «buena» en el visor: 556 productos con una sola foto y 221 con la principal < 800 px | Agente | `python scripts/revisar_fotos.py` genera la lista; fuentes útiles en `docs/agentes/fotos.md` (YZA, Walmart, Farmacias del Ahorro) o fotos de catálogo con `scripts/meli_precios.py --fotos-catalogo` |
| 8 | Verificar comisiones por categoría con el simulador de Mercado Libre | Dueño o agente | Las de `config/mercadolibre.json` son aproximadas (fuentes 2026); el dueño confirmó que incluyen IVA. Se pueden ajustar por producto en el visor |
| 9 | Entrega en Google Sheets | Dueño | En claude.ai solo estaba el conector de Google Drive (sin Google Sheets); el layout se entrega como .xlsx y está versionado en `layouts/mercadolibre/` |
| 10 | Pasar el repositorio a privado cuando termine la importación | Dueño | Las URLs de fotos solo funcionan mientras es público. Desde que se versionan el layout y el visor, mientras el repositorio es público también quedan visibles precios y existencias |
| 11 | Revisar en el visor las 140 descripciones «regular» (sobre todo confianza media) | Dueño o agente | Filtro Descripción = Regular; confirmar presentación o completar secciones |
| 12 | Decidir qué productos se descartan de Meli (p. ej. los 159 cuyo precio en Meli queda al doble o más del de tienda, o los que requieren receta) | Dueño | Sección Pendientes → seleccionar → acción «Descartar de Meli» → exportar y adjuntar el Excel |

## Próximas tareas (en orden)

1. En cuanto el dueño entregue el código de autorización de Mercado Libre: `scripts/meli_auth.py`, prueba de `scripts/meli_precios.py` con 3 productos y corrida completa; fotos de catálogo y de otros vendedores para productos sin fotos o con fotos malas; descripciones de otros vendedores como fuente para reescribir las cortas o de baja calidad.
2. Procesar el Excel de pendientes que adjunte el dueño (`python scripts/solicitudes.py <archivo.xlsx>`; ver `docs/PROCEDIMIENTO_SESION.md` §4 ter).
3. Resolver con el dueño los 33 productos pendientes (8 sin verificar, 25 sin fotos).
4. Mejorar fotos marcadas por `scripts/revisar_fotos.py`.
5. Regenerar el layout de Mercado Libre y el visor después de cada cambio (`docs/PROCEDIMIENTO_SESION.md` §4) y entregarlo; si el dueño comparte las plantillas oficiales del Publicador masivo, llenarlas directamente.
6. Layout de importación de **Odoo** (product.template: nombre, código de barras, referencia interna, precio, categoría, descripción de venta, imagen).
7. Layout de **Shopify** (CSV de productos: Handle, Title, Body (HTML), Vendor, Product Type, Variant SKU, Variant Barcode, Variant Price, Image Src…).
8. Layout de **Amazon** (plantilla de categoría de Seller Central México).

## Para retomar en otra IA

- Insumos que el dueño debe entregar de nuevo al agente (no están en git): los Excel de ventas y catálogos (en `insumos/originales/`) y, para la API, las credenciales en `.env` (ML_CLIENT_ID, ML_CLIENT_SECRET) y un código de autorización o token (`insumos/ml_token.json`).
- Todo lo demás (fichas, fotos, reglas, contratos, procedimiento, scripts, historial, el layout vigente y el visor) está en el repositorio. Sin los Excel, `scripts/build_visor.py` toma precios y existencias del layout versionado.
