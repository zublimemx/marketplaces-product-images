# Pendientes y próximas tareas

Última actualización: 2026-09-29, al obtener con la API de Mercado Libre los precios de competencia (mejor vendedor y promedio), completar fotos con las del catálogo y reescribir o confirmar descripciones (`docs/MERCADOLIBRE_API.md`). Para continuar con otra IA, empieza por `AGENTS.md`.

## Estado

| Concepto | Productos |
|---|---|
| Productos a publicar | 1,163 |
| Completos (ficha verificada + fotos) | 1,138 (97.8 %) |
| Verificados sin fotos | 18 |
| Sin verificar (confianza baja, sin fotos; ya se intentaron 2 veces) | 7 |
| Pendientes de investigar | 0 |
| Sesiones realizadas | 7 |
| Faltan | 25 productos que necesitan ayuda del dueño (fotos propias o confirmar el producto) o una fuente distinta |

El detalle vivo está en `PROGRESO.md`.

Indicadores de calidad del visor (`visor/index.html`; reglas en `config/indicadores.json`):

| Indicador | Buena / completos | Regular | Mala / incompletos |
|---|---|---|---|
| Descripción | 1,101 | 55 (54 por confianza media) | 7 (sin verificar) |
| Fotos | 898 | 237 (193 con una sola foto; 56 con la principal < 800 px) | 28 (25 sin fotos, 3 solo con fotos chicas) |
| Precios | 1,024 | — | 139 (sin precio del mejor vendedor: 83 sin catálogo en Meli, 44 sin otros vendedores, 12 con catálogo rechazado) |

Pendientes por producto (sección Pendientes del visor; reglas en `config/pendientes.json`): 28 productos con errores, 688 con pendientes y 835 con mejoras. Los más frecuentes: podría requerir receta (462), precio calculado arriba del mejor vendedor (386), precio en Meli muy arriba del de tienda (363), una sola foto (193), dato por confirmar en el empaque (173), sin existencia (146), falta el precio del mejor vendedor (139), el GTIN apunta a otro producto en Mercado Libre (12). Productos descartados de Meli: 0.

Layout vigente: `layouts/mercadolibre/layout_mercadolibre.xlsx` (versionado, recalculado; hoja Precios con parámetros por producto). Costos de envío: 1,012 productos $75, 80 $90, 21 $105, 43 $125 y 7 $150 (`data/envios.csv`); se aplican a los 546 productos de $299 o más. Ajustes de precio versionados: 0 (`data/ajustes_precios.json`). El visor exporta el mismo layout para cualquier selección de productos («Exportar layout Meli»). Precio Meli Final = mejor vendedor − $1 si no queda abajo del calculado: 638 productos se publican a mejor vendedor − $1 y 525 al calculado. Competencia del 29 sep 2026 en `data/competencia_meli.csv`; catálogos rechazados en `data/catalogo_ml_rechazados.csv`.

## Pendientes abiertos

| # | Pendiente | Quién | Notas |
|---|---|---|---|
| 1 | 7 productos sin verificar y 18 verificados sin fotos (lista: `python scripts/revisar_fotos.py` y la hoja Revisión) | Dueño | Ya se intentaron por GTIN, nombre y catálogo de Mercado Libre. El dueño confirma el producto o toma fotos propias. Nuevo: Head & Shoulders 650 ml (7500435162241) quedó sin fotos porque las 4 tenían bandas o eran de otra presentación |
| 2 | Productos con datos dudosos a confirmar en empaque (146 con «Dato por confirmar en el empaque» en el visor) | Dueño | P. ej. B-Tracet (GTIN 1306881052251 asociado a tramadol en distribuidores vs. nombre con lidocaína), Colgate Total 2x25 m sin foto. Exportarlos desde la sección Pendientes con la acción «Revisar con el dueño» |
| 3 | Revisar lo que dejó la API de Mercado Libre (sección Pendientes del visor) | Dueño | 12 GTIN cuyo catálogo en Meli es otro producto u otra presentación (pendiente «El GTIN apunta a otro producto»; sus precios no se usan): confirmar el GTIN en el empaque. Inhibitron Dual (7501299302668): ¿14 o 28 cápsulas? Oxímetro 7502256732016: confirmar modelo INH01. Precios de competencia sospechosos: A.M.K. Amikacina (mejor vendedor $505 contra $19.90 en tienda) y Nediclon (tienda $7.53); corregir en el visor si hace falta. Fotos a completar: Brillantina Palmolive 75001872 (solo reverso), Stefano Play 7509546064697 (solo costado), Freska-ra 7501035911062 (foto de 132 g), Evenflo 7501027515230 (¿Minnie o Mickey?) |
| 4 | Confirmar el costo de envío estimado ($75–$150 por peso) en los 546 productos de $299 o más | Dueño | Estimado con `scripts/envios.py` (`data/envios.csv`); se corrige producto por producto en el visor y se versiona con «Exportar ajustes de precio». Con la API se pueden tomar medidas reales del catálogo (`marketplaces.mercadolibre.paquete`) |
| 5 | Revisar productos con `receta_mx` = "Sí" o "Revisar" | Dueño | El dueño indicó que todo es de venta libre; Mercado Libre podría rechazar algunos (antibióticos, misoprostol como Cytotec y Cyrux, solución IV PiSA). Lista en la hoja Revisión |
| 6 | Revisar presentaciones dudosas contra el producto físico | Dueño | P. ej. Motrin Pediátrico (15 ml vs 150 ml), Nexcare "C24", Nivea exhibidor 10+2; ver `investigacion.notas` y la hoja Revisión |
| 7 | Mejorar fotos: 63 con producto < 500 px, 54 con posible fondo gris. Para subir de «regular» a «buena» en el visor: 193 productos con una sola foto y 56 con la principal < 800 px (las fotos de catálogo de Meli ya se usaron y revisaron a la vista) | Agente | `python scripts/revisar_fotos.py` genera la lista; fuentes útiles en `docs/agentes/fotos.md` (YZA, Walmart, Farmacias del Ahorro) |
| 8 | Verificar comisiones por categoría con el simulador de Mercado Libre | Dueño o agente | Las de `config/mercadolibre.json` son aproximadas (fuentes 2026); el dueño confirmó que incluyen IVA. Se pueden ajustar por producto en el visor |
| 9 | Entrega en Google Sheets | Dueño | En claude.ai solo estaba el conector de Google Drive (sin Google Sheets); el layout se entrega como .xlsx y está versionado en `layouts/mercadolibre/` |
| 10 | Pasar el repositorio a privado cuando termine la importación | Dueño | Las URLs de fotos solo funcionan mientras es público. Desde que se versionan el layout y el visor, mientras el repositorio es público también quedan visibles precios y existencias |
| 13 | Rotar el secreto de la aplicación de Mercado Libre | Dueño | Se compartió por chat; al rotarlo, actualizar `.env` (nunca se versiona) |
| 11 | Revisar en el visor las 55 descripciones «regular» (54 por confianza media) | Dueño o agente | Filtro Descripción = Regular; confirmar presentación o completar secciones |
| 12 | Decidir qué productos se descartan de Meli (p. ej. los 363 cuyo precio en Meli queda al doble o más del de tienda, o los que requieren receta) y revisar los 386 cuyo calculado queda arriba del mejor vendedor | Dueño | Sección Pendientes → seleccionar → acción «Descartar de Meli» → exportar y adjuntar el Excel |

## Próximas tareas (en orden)

1. Procesar el Excel de pendientes que adjunte el dueño (`python scripts/solicitudes.py <archivo.xlsx>`; ver `docs/PROCEDIMIENTO_SESION.md` §4 ter).
2. Actualizar precios de competencia antes de publicar (cambian a diario): token nuevo del dueño y `docs/PROCEDIMIENTO_SESION.md` §4 bis. Para renovar solo, conviene el flujo de código de autorización (`scripts/meli_auth.py`).
3. Resolver con el dueño los 25 productos pendientes (7 sin verificar, 18 sin fotos) y los 12 catálogos rechazados.
4. Mejorar fotos marcadas por `scripts/revisar_fotos.py`.
5. Regenerar el layout de Mercado Libre y el visor después de cada cambio (`docs/PROCEDIMIENTO_SESION.md` §4) y entregarlo; si el dueño comparte las plantillas oficiales del Publicador masivo, llenarlas directamente.
6. Layout de importación de **Odoo** (product.template: nombre, código de barras, referencia interna, precio, categoría, descripción de venta, imagen).
7. Layout de **Shopify** (CSV de productos: Handle, Title, Body (HTML), Vendor, Product Type, Variant SKU, Variant Barcode, Variant Price, Image Src…).
8. Layout de **Amazon** (plantilla de categoría de Seller Central México).

## Para retomar en otra IA

- Insumos que el dueño debe entregar de nuevo al agente (no están en git): los Excel de ventas y catálogos (en `insumos/originales/`) y, para la API, las credenciales en `.env` (ML_CLIENT_ID, ML_CLIENT_SECRET) y un token vigente (`ML_ACCESS_TOKEN`, dura 6 horas) o un código de autorización (`insumos/ml_token.json`). Las respuestas crudas de la API (`trabajo/meli/`) no se versionan: una sesión nueva repite la consulta.
- Todo lo demás (fichas, fotos, reglas, contratos, procedimiento, scripts, historial, el layout vigente y el visor) está en el repositorio. Sin los Excel, `scripts/build_visor.py` toma precios y existencias del layout versionado.
