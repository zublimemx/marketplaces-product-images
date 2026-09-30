# Pendientes y próximas tareas

Última actualización: 2026-09-29, traspaso para continuar con otra IA (Codex o Claude). Empieza por `AGENTS.md`.

## Estado

| Concepto | Productos |
|---|---|
| Productos a publicar | 1,163 |
| Completos (ficha verificada + fotos) | 1,061 (91.2 %) |
| Verificados sin fotos | 26 |
| Sin verificar (confianza baja) | 11 |
| Pendientes de investigar | 65 |
| Sesiones realizadas | 6 |
| Sesiones que faltan | 1 (76 productos a investigar + 26 verificados sin fotos) |

El detalle vivo está en `PROGRESO.md`.

## Pendientes abiertos

| # | Pendiente | Quién | Notas |
|---|---|---|---|
| 1 | Sesión 7: 65 `pendiente` + 11 `sin_verificar` (76 búsquedas) y fotos de 26 verificados sin fotos (sin búsquedas) | Agente | `python scripts/seleccionar_lote.py --sesion 7 --fotos`; sobran ~124 búsquedas para reintentar fotos de baja resolución |
| 2 | Productos con datos dudosos a confirmar en empaque | Dueño | P. ej. B-Tracet (GTIN 1306881052251 asociado a tramadol en distribuidores vs. nombre con lidocaína), Colgate Total 2x25 m sin foto |
| 3 | Precios de competencia: "Precio Meli promedio otros vendedores" y "Precio mejor vendedor" | Dueño + agente | Script listo sin probar: `scripts/meli_precios.py` (ver `docs/MERCADOLIBRE_API.md`). Faltan credenciales de una aplicación de vendedor en `.env` y red hacia `api.mercadolibre.com`. Primera corrida con `--muestra 3 --limite 3` para ajustar campos. "Mejor vendedor": mayor `sold_quantity` si la API lo da; si no, ganador del catálogo |
| 4 | Costo real de envío a cargo del vendedor para productos ≥ $299 | Dueño | Hoy es 0 en `config/mercadolibre.json` (`precios.costo_envio_vendedor_estimado`) |
| 5 | Revisar productos con `receta_mx` = "Sí" o "Revisar" | Dueño | El dueño indicó que todo es de venta libre; Mercado Libre podría rechazar algunos (antibióticos, misoprostol como Cytotec y Cyrux, solución IV PiSA). Lista en la hoja Revisión |
| 6 | Revisar presentaciones dudosas contra el producto físico | Dueño | P. ej. Motrin Pediátrico (15 ml vs 150 ml), Nexcare "C24", Nivea exhibidor 10+2; ver `investigacion.notas` y la hoja Revisión |
| 7 | Mejorar fotos: 125 con producto < 500 px, 39 con posible fondo gris y algunas con bandas gráficas de tienda (p. ej. "800 gr Etapa 2") | Agente | `python scripts/revisar_fotos.py` genera la lista; opciones: nueva fuente con `scripts/imagenes.py` o fotos de catálogo con `scripts/meli_precios.py --fotos-catalogo` |
| 8 | Verificar comisiones por categoría con el simulador de Mercado Libre | Dueño o agente | Las de `config/mercadolibre.json` son aproximadas (fuentes 2026) |
| 9 | Entrega en Google Sheets | Dueño | En claude.ai solo estaba el conector de Google Drive (sin Google Sheets); el layout se entrega como .xlsx |
| 10 | Pasar el repositorio a privado cuando termine la importación | Dueño | Las URLs de fotos solo funcionan mientras es público |

## Próximas tareas (en orden)

1. Correr la sesión 7 para cerrar la investigación (76 productos) y completar fotos de los 26 verificados sin fotos (`docs/PROCEDIMIENTO_SESION.md`).
2. Precios de competencia con la API de Mercado Libre en cuanto haya credenciales (`docs/MERCADOLIBRE_API.md`); de paso, fotos de catálogo para productos sin fotos o de baja resolución.
3. Mejorar fotos marcadas por `scripts/revisar_fotos.py`.
4. Regenerar el layout de Mercado Libre y entregarlo; si el dueño comparte las plantillas oficiales del Publicador masivo, llenarlas directamente.
5. Layout de importación de **Odoo** (product.template: nombre, código de barras, referencia interna, precio, categoría, descripción de venta, imagen).
6. Layout de **Shopify** (CSV de productos: Handle, Title, Body (HTML), Vendor, Product Type, Variant SKU, Variant Barcode, Variant Price, Image Src…).
7. Layout de **Amazon** (plantilla de categoría de Seller Central México).

## Para retomar en otra IA

- Insumos que el dueño debe entregar de nuevo al agente (no están en git): los Excel de ventas y catálogos (en `insumos/originales/`) y, para la API, las credenciales en `.env`.
- Todo lo demás (fichas, fotos, reglas, contratos, procedimiento, scripts e historial) está en el repositorio.
