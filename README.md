# marketplaces-product-images

Base de datos de productos (farmacia, líneas Farma y Mark) para publicar en marketplaces: Mercado Libre (en curso), Odoo, Shopify y Amazon. Guarda por GTIN la ficha, la descripción, la ficha técnica, las categorías por marketplace y las fotos, además del layout de importación de Mercado Libre (con precios y existencias, por decisión del dueño) y un visor web para revisar la calidad de los productos. Las cifras de venta, los Excel del ERP y las credenciales no se guardan aquí.

**Manual para el usuario: [`MANUAL.pdf`](MANUAL.pdf)** (visor, edición de precios, layout de Mercado Libre y cómo seguir con Claude o Codex).

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
| `docs/BASE_DE_DATOS.md` | Base de datos SQLite `data/catalogo.db`: tablas, cómo se regenera y consultas |
| `docs/MERCADOLIBRE_API.md` | Precios de competencia, fotos y descripciones del catálogo con la API de Mercado Libre |
| `docs/VISOR.md` | Visor de productos: cómo abrirlo, regenerarlo e indicadores |
| `docs/agentes/` | Instrucciones para subagentes de investigación y de fotos |
| `schema/` | JSON Schema de product.json y de resultados |

## Estructura

```
products/<GTIN>/product.json     Ficha del producto
products/<GTIN>/images/          Fotos <GTIN>_1.jpg, <GTIN>_2.jpg, ...
config/mercadolibre.json         Valores fijos de publicación, parámetros de precio y avance
config/indicadores.json          Reglas de los indicadores del visor
config/pendientes.json           Pendientes por producto y acciones que se pueden pedir
layouts/mercadolibre/            Layout de importación de Mercado Libre (versionado)
visor/                           Visor web de productos (abrir visor/index.html)
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
scripts/precios.py               Fórmulas de precio de Mercado Libre (idénticas a la hoja Precios)
scripts/build_visor.py           Genera los datos del visor (visor/data/productos.js), con indicadores y pendientes
scripts/descartar.py             Descarta o reactiva productos del layout de Mercado Libre
scripts/envios.py                Estima el costo de envío por producto ($75–$150 por peso y tamaño)
scripts/ajustes_precios.py       Versiona los ajustes de precio exportados desde el visor
scripts/meli_auth.py             Obtiene el token de la API de Mercado Libre con un código de autorización
scripts/build_manual.py          Genera MANUAL.pdf desde docs/manual/manual.html (--capturas retoma las capturas del visor)
scripts/solicitudes.py           Lee el Excel de pendientes que devuelve el dueño y agrupa por acción
scripts/revisar_fotos.py         Revisión automática de fotos (baja resolución, posible fondo gris, sin fotos)
scripts/meli_precios.py          Precios de competencia y datos de catálogo con la API de Mercado Libre
scripts/meli_fotos.py            Completa fotos malas o regulares con las del catálogo de Mercado Libre
scripts/preparar_revision_ml.py  Hojas de fotos y lotes de descripciones para revisar con subagentes
scripts/aplicar_revision_ml.py   Aplica la revisión (fotos, descripciones, GTIN confirmados, catálogos rechazados)
scripts/otros_marketplaces.py    Precios en otros marketplaces (integra subagentes o el Excel del visor)
scripts/build_db.py              Base de datos SQLite data/catalogo.db con todos los datos (--verificar en CI)
scripts/pr.py                    Crea y fusiona PRs con la API de GitHub (si no hay gh)
scripts/setup.sh                 Prepara el entorno (dependencias, carpetas locales, validación)
```

## URL de una foto

`https://raw.githubusercontent.com/zublimemx/marketplaces-product-images/main/products/<GTIN>/images/<GTIN>_1.jpg` (solo mientras el repositorio es público).

## Layout de Mercado Libre

La versión vigente está en `layouts/mercadolibre/layout_mercadolibre.xlsx` (hojas Layout Mercado Libre, Precios, Parámetros, Revisión, Categorías usadas y Avance). Para regenerarlo:

```
python scripts/preparar_insumos.py --ventas <ventas.xlsx> --farma <catalogo_farma.xlsx> --mark <catalogo_mark.xlsx>
python scripts/build_mercadolibre.py --precios insumos/precios_existencias.csv --salida layouts/mercadolibre/layout_mercadolibre.xlsx
```

y recalcularlo antes de versionarlo (ver `docs/PROCEDIMIENTO_SESION.md` §4).

## Visor de productos

Abre `visor/index.html` con doble clic (o `python -m http.server 8000` desde la raíz y `http://localhost:8000/visor/`). Muestra los 1,163 productos en cuadrícula o tabla, con carrusel de fotos, filtros con autocompletado, orden por columna, paginación, detalle con productos similares e indicadores de descripción, fotos y precios. Permite **editar los parámetros de precio** de cada producto (precio de venta, empaque, comisión, costo de envío, competencia y descuento) desde la cuadrícula, la lista o el detalle, seleccionar productos (uno a uno o todos los filtrados) y **exportar el layout de Mercado Libre** listo para importar, con las URLs de las fotos en GitHub. La sección **Pendientes** lista errores, pendientes y mejoras de cada producto y exporta a Excel los seleccionados para pedir acciones (completar información, buscar imágenes, completar precios, revisar o descartar). Para actualizar sus datos: `python scripts/build_visor.py`. Detalle en `docs/VISOR.md`.
