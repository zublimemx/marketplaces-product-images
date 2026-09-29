# AGENTS.md — guía para cualquier agente de IA (Claude, Codex u otro)

Este repositorio es la **base de datos de productos** de una farmacia mexicana (líneas Farma y Mark) para publicarlos en marketplaces. Guarda por producto (por GTIN): ficha, descripción, ficha técnica, categorías por marketplace y fotos. A partir de aquí se generan los layouts de importación de **Mercado Libre** (hecho), **Odoo**, **Shopify** y **Amazon** (pendientes).

Antes de trabajar, lee en este orden:

1. `PENDIENTES.md`: estado actual, pendientes abiertos y próximas tareas. **Actualízalo en cada PR.**
2. `docs/CONTEXTO.md`: antecedentes, decisiones del dueño y historial.
3. `docs/REGLAS_NEGOCIO.md`: reglas de publicación y de precio (no las cambies sin instrucción del dueño).
4. `docs/CONTRATOS.md`: formato de `product.json`, de los resultados de investigación, de los insumos y del layout.
5. `docs/PROCEDIMIENTO_SESION.md`: cómo correr una sesión de investigación y cómo publicar cambios (rama, PR, fusión).

## Reglas de trabajo

- Idioma: todo el contenido (títulos, descripciones, documentación, commits, PRs) en español de México.
- Fuente de verdad: `products/<GTIN>/product.json`. No edites a mano la carpeta `images/`: usa `scripts/imagenes.py`.
- **No versiones precios, existencias ni cifras de venta**: el repositorio se hace público durante las importaciones. Esos datos viven en `insumos/` (ignorado por git) y se generan con `scripts/preparar_insumos.py` desde los Excel del ERP.
- El repositorio **nunca se borra**. Normalmente es privado; el dueño lo hace público solo durante importaciones o actualizaciones en marketplaces (las URLs de fotos `raw.githubusercontent.com` solo funcionan mientras es público).
- Fotos: siempre se obtienen de internet (nunca llegan en ZIP), se descargan y se versionan aquí. Orden de preferencia: fabricante, catálogo de Mercado Libre, tienda. Nada de marcas de agua, logos de tienda, texto promocional ni precios.
- Investigación: **1 búsqueda web por producto** (el entorno de Claude tiene un límite de 200 búsquedas por sesión, de ahí los lotes de 200). Abrir páginas concretas no cuenta como búsqueda. No uses buscadores generales vía fetch/curl para saltarte ese límite.
- Cada cambio va en una rama y un PR con descripción clara; al fusionarlo, `PENDIENTES.md` debe quedar actualizado.
- Commits con el pie de coautoría que indique tu entorno.

## Mapa del repositorio

```
AGENTS.md / CLAUDE.md            Guías para agentes (Codex lee AGENTS.md; Claude Code lee CLAUDE.md)
PENDIENTES.md                    Pendientes abiertos y próximas tareas
PROGRESO.md                      Avance de fichas y fotos (lo genera scripts/progreso.py)
docs/                            Contexto, reglas, contratos, procedimiento e instrucciones para subagentes
schema/                          JSON Schema de product.json y de los resultados de investigación
config/mercadolibre.json         Valores fijos de publicación, parámetros de precio y avance por sesión
data/prioridad.csv               Orden de trabajo por ventas (sin montos): orden, gtin, linea, nombre_sistema, nota_cruce
products/<GTIN>/product.json     Ficha del producto
products/<GTIN>/images/          Fotos <GTIN>_<n>.jpg
reference/mercadolibre/          Árbol de categorías MLM (todas las hojas, relevantes y con receta)
scripts/                         Herramientas (ver docs/PROCEDIMIENTO_SESION.md)
insumos/, trabajo/               Locales, ignorados por git (precios y lotes de trabajo)
```

## Requisitos del entorno

Python 3.10+ con `pandas`, `openpyxl` y `Pillow`; `curl`; acceso de red a los sitios de fabricantes y farmacias; LibreOffice opcional para recalcular fórmulas del layout. Para PRs: `gh` o la API REST de GitHub con un token con permiso de escritura en `zublimemx/marketplaces-product-images`.
