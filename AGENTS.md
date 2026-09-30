# AGENTS.md — guía para cualquier agente de IA (Codex, Claude u otro)

Este repositorio es la **base de datos de productos** de una farmacia mexicana (líneas Farma y Mark) para publicarlos en marketplaces. Guarda por producto (por GTIN): ficha, descripción, ficha técnica, categorías por marketplace y fotos. A partir de aquí se generan los layouts de importación de **Mercado Libre** (hecho), **Odoo**, **Shopify** y **Amazon** (pendientes). Todo el trabajo y la documentación van en español de México.

## Empieza aquí

1. `bash scripts/setup.sh` (instala dependencias, crea `insumos/` y `trabajo/`, valida el repositorio).
2. Lee `PENDIENTES.md`: estado, pendientes abiertos y próximas tareas. **Actualízalo en cada PR.**
3. Lee según la tarea:
   - `docs/CONTEXTO.md`: antecedentes, decisiones del dueño y hallazgos.
   - `docs/REGLAS_NEGOCIO.md`: reglas de publicación, contenido, fotos y precio (no las cambies sin instrucción del dueño).
   - `docs/CONTRATOS.md` y `schema/`: formato de `product.json`, lotes, resultados, insumos y layout.
   - `docs/PROCEDIMIENTO_SESION.md`: cómo correr una sesión de investigación y publicar cambios por PR.
   - `docs/MERCADOLIBRE_API.md`: precios de competencia y fotos de catálogo con la API de Mercado Libre.
   - `docs/VISOR.md`: visor web para revisar calidad y cantidad de productos (indicadores de descripción, fotos y precios).
   - `docs/agentes/investigacion.md` y `docs/agentes/fotos.md`: instrucciones para investigar un lote de productos.

## Tareas pendientes y cómo continuarlas

| Tarea | Cómo |
|---|---|
| Productos que faltan (8 sin verificar, 25 sin fotos; la investigación automática terminó en la sesión 7) | Con datos del dueño o nuevas fuentes: `python scripts/seleccionar_lote.py --sesion 8 --fotos`; cada lote con `docs/agentes/investigacion.md` o `docs/agentes/fotos.md`; integrar con `scripts/integrar_resultados.py` |
| Precio de la publicación más vendida y promedio de competencia | `docs/MERCADOLIBRE_API.md` + `scripts/meli_precios.py` (necesita credenciales de la API) |
| Mejorar fotos de baja resolución o con fondo gris | `python scripts/revisar_fotos.py` lista los casos; reemplazar con `scripts/imagenes.py` (`rm` y `fetch`) o con `scripts/meli_precios.py --fotos-catalogo` |
| Regenerar el layout de Mercado Libre | `python scripts/preparar_insumos.py …` (Excel del ERP) y `python scripts/build_mercadolibre.py … --salida layouts/mercadolibre/layout_mercadolibre.xlsx`, recalculado antes de versionar (`docs/PROCEDIMIENTO_SESION.md` §4) |
| Revisar calidad de productos | `python scripts/build_visor.py` y abrir `visor/index.html`; sección Pendientes o filtro por indicador «mala» (`docs/VISOR.md`) |
| **Procesar un Excel de pendientes que adjunta el dueño** | `python scripts/solicitudes.py <archivo.xlsx>` agrupa por «Acción solicitada»; `--aplicar-descartes` descarta; el resto según `docs/VISOR.md` («Pedir acciones con el Excel»). Luego regenerar layout y visor y abrir PR |
| Entregar el layout de Meli de un subconjunto de productos | Visor → seleccionar (o «Seleccionar los N filtrados») → «Exportar layout Meli». Mismo contenido que el layout versionado (`docs/VISOR.md`) |
| Descartar o reactivar productos de Mercado Libre | `python scripts/descartar.py --gtin … --motivo …` / `--reactivar` / `--lista` |
| Layouts de Odoo, Shopify y Amazon | Nuevos `scripts/build_<canal>.py` que lean `product.json` + `insumos/`; reglas en `config/<canal>.json`; ver `docs/CONTRATOS.md` §7 |

## Reglas de trabajo

- Fuente de verdad: `products/<GTIN>/product.json`. Las fotos solo se agregan o quitan con `scripts/imagenes.py`, que también las registra en `product.json`.
- **Qué se versiona y qué no.** Por decisión del dueño se versionan el layout completo (`layouts/mercadolibre/layout_mercadolibre.xlsx`) y los datos del visor (`visor/data/productos.js`), que traen precios y existencias; al hacer público el repositorio durante una importación, esos datos quedan visibles. **No se versionan** los Excel del ERP ni los CSV de `insumos/` (ignorado por git; se generan con `scripts/preparar_insumos.py` a partir de los Excel que entrega el dueño en `insumos/originales/`), las cifras de venta ni las credenciales (`.env`, ignorado; plantilla en `.env.example`). Solo los `.xlsx` bajo `layouts/` están exentos del `*.xlsx` de `.gitignore`.
- El repositorio **nunca se borra**. Normalmente es privado; el dueño lo hace público solo durante importaciones (las URLs de fotos `raw.githubusercontent.com` solo funcionan entonces).
- Fotos: siempre de internet (nunca llegan en ZIP), descargadas y versionadas aquí. Preferencia: fabricante > catálogo de Mercado Libre > tienda. Nada de marcas de agua, logos de tienda, texto promocional ni precios.
- Investigación: **1 búsqueda web por producto**; abrir páginas concretas no cuenta como búsqueda. No uses buscadores generales vía fetch/curl para esquivar límites. No raspes Mercado Libre ni Amazon: usa la API oficial de Mercado Libre.
- Nunca inventes datos de ficha técnica ni afirmaciones de salud. Si no se confirma el producto, confianza "baja".
- Cada cambio va en una rama y un PR; se fusiona con `PENDIENTES.md` y `PROGRESO.md` al día (y el layout y `visor/data/productos.js` regenerados si cambiaron fichas, fotos o precios). `python scripts/validar.py` debe pasar antes de fusionar.

## Notas para Codex

- **Red:** el trabajo necesita internet (páginas de fabricantes y farmacias, descarga de fotos, API de Mercado Libre y GitHub). En Codex CLI, el sandbox bloquea la red por defecto: habilítala (por ejemplo, con `sandbox_workspace_write.network_access = true` en la configuración o con el modo de acceso completo). En Codex cloud, activa el acceso a internet del entorno y pon `bash scripts/setup.sh` como script de preparación.
- **Búsqueda web:** activa la herramienta de búsqueda web de Codex (por ejemplo, `codex --search`). Respeta 1 búsqueda por producto.
- **Sin subagentes:** procesa los lotes uno tras otro con las mismas instrucciones de `docs/agentes/`. Un lote de 25 productos es una unidad de trabajo razonable; guarda el resultado de cada lote antes de pasar al siguiente.
- **Revisión de fotos:** si puedes ver imágenes, abre las hojas de contacto `trabajo/contactos/<gtin>.jpg`. Si no, corre `python scripts/revisar_fotos.py --gtin …` y deja anotado en `notas_imagenes` que la revisión visual está pendiente.
- **PRs:** usa `gh` o `python scripts/pr.py --rama … --titulo … --cuerpo … --fusionar` con `GH_TOKEN` en `.env` o en el entorno.

## Mapa del repositorio

```
AGENTS.md / CLAUDE.md            Guías para agentes (Codex lee AGENTS.md; Claude Code lee CLAUDE.md)
PENDIENTES.md                    Pendientes abiertos y próximas tareas
PROGRESO.md                      Avance de fichas y fotos (lo genera scripts/progreso.py)
docs/                            Contexto, reglas, contratos, procedimiento, API de Mercado Libre, instrucciones de subagentes
schema/                          JSON Schema de product.json y de los resultados de investigación
config/mercadolibre.json         Valores fijos de publicación, parámetros de precio y avance por sesión
config/indicadores.json          Reglas de los indicadores de calidad del visor
config/pendientes.json           Catálogo de pendientes por producto, umbrales y acciones que el dueño puede pedir
data/prioridad.csv               Orden de trabajo por ventas (sin montos)
products/<GTIN>/product.json     Ficha del producto
products/<GTIN>/images/          Fotos <GTIN>_<n>.jpg
reference/mercadolibre/          Árbol de categorías MLM (todas las hojas, relevantes y con receta)
layouts/mercadolibre/            Layout de importación de Mercado Libre (.xlsx recalculado, versionado)
visor/                           Visor web de productos (index.html, styles.css, app.js, xlsx.js, data/productos.js)
scripts/                         Herramientas (ver README.md)
requirements.txt, .env.example   Dependencias y plantilla de credenciales
insumos/, trabajo/, .env         Locales, ignorados por git
```
