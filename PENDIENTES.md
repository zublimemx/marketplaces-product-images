# Pendientes y próximas tareas

Última actualización: 2026-09-29, al integrar la sesión 7 (investigación automática terminada). Para continuar con otra IA, empieza por `AGENTS.md`.

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

## Pendientes abiertos

| # | Pendiente | Quién | Notas |
|---|---|---|---|
| 1 | 8 productos sin verificar y 25 verificados sin fotos (lista: `python scripts/revisar_fotos.py` y la hoja Revisión) | Dueño + agente | Ya se intentaron por GTIN y nombre en 2 sesiones. Opciones: el dueño confirma el producto o toma fotos propias; o un agente prueba fotos de catálogo con la API (`scripts/meli_precios.py --fotos-catalogo`) |
| 2 | Productos con datos dudosos a confirmar en empaque | Dueño | P. ej. B-Tracet (GTIN 1306881052251 asociado a tramadol en distribuidores vs. nombre con lidocaína), Colgate Total 2x25 m sin foto |
| 3 | Precios de competencia: "Precio Meli promedio otros vendedores" y "Precio mejor vendedor" | Dueño + agente | Script listo sin probar: `scripts/meli_precios.py` (ver `docs/MERCADOLIBRE_API.md`). Faltan credenciales de una aplicación de vendedor en `.env` y red hacia `api.mercadolibre.com`. Primera corrida con `--muestra 3 --limite 3` para ajustar campos. "Mejor vendedor": mayor `sold_quantity` si la API lo da; si no, ganador del catálogo |
| 4 | Costo real de envío a cargo del vendedor para productos ≥ $299 | Dueño | Hoy es 0 en `config/mercadolibre.json` (`precios.costo_envio_vendedor_estimado`) |
| 5 | Revisar productos con `receta_mx` = "Sí" o "Revisar" | Dueño | El dueño indicó que todo es de venta libre; Mercado Libre podría rechazar algunos (antibióticos, misoprostol como Cytotec y Cyrux, solución IV PiSA). Lista en la hoja Revisión |
| 6 | Revisar presentaciones dudosas contra el producto físico | Dueño | P. ej. Motrin Pediátrico (15 ml vs 150 ml), Nexcare "C24", Nivea exhibidor 10+2; ver `investigacion.notas` y la hoja Revisión |
| 7 | Mejorar fotos: 77 con producto < 500 px (en la sesión 7 se mejoraron 38 de 47 productos que solo tenían fotos chicas), 45 con posible fondo gris y algunas con bandas gráficas de tienda | Agente | `python scripts/revisar_fotos.py` genera la lista; fuentes útiles en `docs/agentes/fotos.md` (YZA, Walmart, Farmacias del Ahorro) o fotos de catálogo con `scripts/meli_precios.py --fotos-catalogo` |
| 8 | Verificar comisiones por categoría con el simulador de Mercado Libre | Dueño o agente | Las de `config/mercadolibre.json` son aproximadas (fuentes 2026) |
| 9 | Entrega en Google Sheets | Dueño | En claude.ai solo estaba el conector de Google Drive (sin Google Sheets); el layout se entrega como .xlsx |
| 10 | Pasar el repositorio a privado cuando termine la importación | Dueño | Las URLs de fotos solo funcionan mientras es público |

## Próximas tareas (en orden)

1. Resolver con el dueño los 33 productos pendientes (8 sin verificar, 25 sin fotos).
2. Precios de competencia con la API de Mercado Libre en cuanto haya credenciales (`docs/MERCADOLIBRE_API.md`); de paso, fotos de catálogo para productos sin fotos o de baja resolución.
3. Mejorar fotos marcadas por `scripts/revisar_fotos.py`.
4. Regenerar el layout de Mercado Libre y entregarlo; si el dueño comparte las plantillas oficiales del Publicador masivo, llenarlas directamente.
5. Layout de importación de **Odoo** (product.template: nombre, código de barras, referencia interna, precio, categoría, descripción de venta, imagen).
6. Layout de **Shopify** (CSV de productos: Handle, Title, Body (HTML), Vendor, Product Type, Variant SKU, Variant Barcode, Variant Price, Image Src…).
7. Layout de **Amazon** (plantilla de categoría de Seller Central México).

## Para retomar en otra IA

- Insumos que el dueño debe entregar de nuevo al agente (no están en git): los Excel de ventas y catálogos (en `insumos/originales/`) y, para la API, las credenciales en `.env`.
- Todo lo demás (fichas, fotos, reglas, contratos, procedimiento, scripts e historial) está en el repositorio.
