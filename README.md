# marketplaces-product-images

Base de datos de productos (farmacia, líneas Farma y Mark) para publicar en marketplaces: Mercado Libre (en curso), Odoo, Shopify y Amazon. Guarda por GTIN la ficha, la descripción, la ficha técnica, las categorías por marketplace y las fotos. Los precios, existencias y ventas no se guardan aquí porque el repositorio se hace público durante las importaciones.

**Si eres un agente de IA (Codex, Claude u otro), empieza por `AGENTS.md`.** Preparación: `bash scripts/setup.sh`.

## Documentación

| Archivo | Para qué |
|---|---|
| `AGENTS.md` / `CLAUDE.md` | Guía para agentes |
| `PENDIENTES.md` | Pendientes abiertos y próximas tareas |
| `PROGRESO.md` | Avance de fichas y fotos por sesión |
| `docs/CONTEXTO.md` | Antecedentes, decisiones del dueño e historial |
| `docs/REGLAS_NEGOCIO.md` | Reglas de publicación, contenido, fotos y precio |
| `docs/CONTRATOS.md` | Formato de product.json, lotes, resultados, insumos y layout |
| `docs/PROCEDIMIENTO_SESION.md` | Cómo correr una sesión y publicar cambios por PR |
| `docs/MERCADOLIBRE_API.md` | Precios de competencia y fotos de catálogo con la API de Mercado Libre |
| `docs/agentes/` | Instrucciones para subagentes de investigación y de fotos |
| `schema/` | JSON Schema de product.json y de resultados |

## Estructura

```
products/<GTIN>/product.json     Ficha del producto
products/<GTIN>/images/          Fotos <GTIN>_1.jpg, <GTIN>_2.jpg, ...
config/mercadolibre.json         Valores fijos de publicación, parámetros de precio y avance
data/prioridad.csv               Orden de trabajo por ventas (sin montos)
reference/mercadolibre/          Árbol de categorías MLM
scripts/preparar_insumos.py      Genera insumos/precios_existencias.csv desde los Excel del ERP
scripts/seleccionar_lote.py      Arma los lotes de una sesión
scripts/pagina_imagenes.py       Lista las fotos de producto de una página web
scripts/imagenes.py              Descarga, valida, recorta y registra fotos
scripts/integrar_resultados.py   Integra los resultados de una sesión a product.json
scripts/validar.py               Valida product.json y resultados contra los esquemas
scripts/progreso.py              Escribe PROGRESO.md
scripts/build_mercadolibre.py    Genera el layout de importación de Mercado Libre
scripts/revisar_fotos.py         Revisión automática de fotos (baja resolución, posible fondo gris, sin fotos)
scripts/meli_precios.py          Precios de competencia y fotos de catálogo con la API de Mercado Libre
scripts/pr.py                    Crea y fusiona PRs con la API de GitHub (si no hay gh)
scripts/setup.sh                 Prepara el entorno (dependencias, carpetas locales, validación)
```

## URL de una foto

`https://raw.githubusercontent.com/zublimemx/marketplaces-product-images/main/products/<GTIN>/images/<GTIN>_1.jpg` (solo mientras el repositorio es público).

## Generar el layout de Mercado Libre

```
python scripts/preparar_insumos.py --ventas <ventas.xlsx> --farma <catalogo_farma.xlsx> --mark <catalogo_mark.xlsx>
python scripts/build_mercadolibre.py --precios insumos/precios_existencias.csv --salida trabajo/layout_mercadolibre.xlsx
```
