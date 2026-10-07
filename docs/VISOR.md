# Visor de productos

Página para revisar a ojo la calidad y la cantidad de los productos antes de importarlos: fotos, descripción, ficha técnica, categoría, inventario y precios, con indicadores de calidad por producto. La sección **Pendientes** lista lo que le falta o conviene mejorar a cada producto y exporta a Excel los que selecciones, para pedir acciones concretas. Desde cualquier vista se exporta el **layout de Mercado Libre** listo para importar, con las URLs de las fotos en GitHub.

Archivos (HTML, CSS y JS por separado, sin dependencias ni compilación):

```
visor/index.html          Estructura de la página
visor/styles.css          Estilos (tema claro y oscuro según el sistema)
visor/app.js              Filtros, cuadrícula, tabla, paginación, detalle y sección Pendientes
visor/xlsx.js             Escritor de .xlsx sin dependencias (exportación del layout Meli, pendientes y ajustes)
visor/precios.js          Cálculo de precios en vivo, idéntico a scripts/precios.py
visor/data/productos.js   Datos (window.CATALOGO = …), generado por scripts/build_visor.py
config/indicadores.json   Reglas de los indicadores
config/pendientes.json    Catálogo de pendientes (tipo, título, acción sugerida), umbrales y acciones que se pueden pedir
scripts/build_visor.py    Genera visor/data/productos.js
scripts/precios.py        Mismas fórmulas de precio que la hoja Precios del layout
```

## Abrir

Necesita el repositorio completo, porque las fotos se leen de `../products/<GTIN>/images/`.

- Doble clic en `visor/index.html` (funciona sin servidor porque los datos son un archivo `.js`).
- O con servidor local desde la raíz del repositorio: `python -m http.server 8000` y abrir `http://localhost:8000/visor/`.

Enlace directo a un producto: `visor/index.html#p<GTIN>` (por ejemplo `#p7501058623300`).

## Qué hace

- **Secciones**: «Catálogo» (cuadrícula o lista) y «Pendientes» (ver abajo). Los filtros de la izquierda aplican a las dos.
- **Vistas del catálogo**: cuadrícula y lista (tabla). En ambas, cada producto trae su carrusel de fotos (flechas y contador).
- **Tabla**: columnas Fotos, Código, Producto, Categoría, Línea, Inventario, Precio venta, Precio marketplaces, Precio Meli calculado, Promedio otros vendedores, Precio mejor vendedor, Precio Meli final, indicadores y conteo de pendientes. Clic en el encabezado ordena (otro clic invierte el sentido). El botón «Columnas» muestra u oculta columnas.
- **Orden** también desde el selector «Ordenar por» (incluye «Prioridad por ventas», el orden de `data/prioridad.csv`).
- **Paginación** de 24, 48 o 96 productos.
- **Filtros** multiselección con autocompletado por nombre, código (GTIN o ID de catálogo) y categoría de Mercado Libre; cada filtro acepta varios valores (se combinan con «o») y «Contiene «texto»» para buscar por fragmento. Además: línea, con o sin existencia, los tres indicadores, elegibilidad en Meli (se publica o descartado), estado de publicación en MeLi (Todos, No publicados o Publicados), tipo de pendiente y pendiente. Filtros distintos se combinan con «y». Los números junto a cada opción cuentan los productos que quedarían al marcarla.
- **Resumen** arriba: conteo por indicador y por tipo de pendiente (clic para filtrar), piezas en inventario, productos sin existencia y descartados.
- **Detalle** (clic en un producto): indicadores con el motivo, botón «Seleccionar para exportar», fotos con miniaturas y datos de cada foto (origen, tamaño útil, fuente), precios e inventario, categoría y catálogo de Mercado Libre, pendientes, errores y mejoras, descripción, ficha técnica, investigación (estado, confianza, notas, fuentes) y hasta 12 productos similares de la misma categoría hoja (si hay pocos, se completa con categorías hermanas).
- **Selección**: casilla en cada renglón de la lista, en cada tarjeta y en cada renglón de Pendientes; la casilla del encabezado de la lista selecciona o deselecciona todos los filtrados (queda a medias si solo hay algunos). La barra de selección tiene «Seleccionar los N filtrados», «Deseleccionar los N filtrados», «Seleccionar esta página», «Quitar toda la selección» y «Ver solo seleccionados». También permite marcar como publicados en MeLi todos los seleccionados que aún no lo estén. La selección se conserva al cambiar filtros, vista o sección.
- **Edición de precios**: los parámetros de precio de cada producto (precio de venta, costo de empaque y logística, comisión, costo de envío, promedio de otros vendedores, precio del mejor vendedor y descuento) se editan en la **lista** (celdas editables; «Columnas» muestra empaque, comisión y descuento), en la **cuadrícula** (botón «Editar precios» de cada tarjeta) y en el **detalle** (bloque Precios e inventario). El precio calculado, el final, el ingreso neto y el margen se recalculan al salir del campo. Ver «Editar precios» abajo.
- **Exportar layout Meli**: descarga `layout_meli_AAAA-MM-DD_HHMM.xlsx` con los productos seleccionados (ver abajo).
- Recuerda en el navegador la sección, la vista, los productos por página, las columnas ocultas, la selección y la acción elegida.

## Editar precios

- Cada parámetro muestra su valor efectivo. Fondo **naranja** = editado en este navegador; fondo **azul** = ajustado en el repositorio (`data/ajustes_precios.json`). Borrar el campo regresa al valor del sistema o al estimado. Valores inválidos se marcan en rojo y no se guardan.
- **Costo de envío**: lo que cobra Mercado Libre por el envío gratis cuando el precio queda en $299 o más (IVA incluido). Viene estimado de $75 a $150 por peso cobrable (`scripts/envios.py`); la tarjeta y la columna muestran el peso estimado y si aplica.
- La comisión se escribe en porcentaje (14 = 14 %) y ya incluye IVA.
- Lo editado se guarda en este navegador (`localStorage`) y ya se usa en todo: indicadores, pendientes, exportación del layout y de pendientes. La barra naranja muestra cuántos productos llevan ajustes y permite **Exportar ajustes de precio** (Excel), **Ver solo editados** y **Deshacer lo editado aquí**. El filtro «Ajustes de precio» separa editados aquí, ajustados en el repositorio y sin ajustes.
- Para que los ajustes queden en el repositorio (y en el layout versionado), adjunta el Excel de ajustes en el chat: `python scripts/ajustes_precios.py <archivo.xlsx>` los guarda en `data/ajustes_precios.json`; luego se regeneran layout y visor. Al abrir el visor regenerado, los ajustes locales iguales a los versionados se limpian solos.
- El cálculo en el navegador (`visor/precios.js`) es el mismo que `scripts/precios.py` y la hoja Precios: se comprobó con los 1,163 productos y 400 casos con mejor vendedor y ajustes al azar (0 diferencias).

## Exportar la planilla operativa de Mercado Libre

El usuario debe descargar una planilla fresca del Publicador masivo de Mercado Libre antes de cada carga. En el visor selecciona productos, elige **Seleccionar planilla oficial de Mercado Libre**, pulsa **Validar planilla** y después **Generar copia completada**. El backend procesa temporalmente el archivo cargado y devuelve una copia del mismo XLSX; no lo conserva como referencia ni sustituye la metadata de lote, vigencia o UUID. Si la vigencia se reconoce y ya venció, la exportación se bloquea. Si no se reconoce, el visor lo informa y permite continuar.

La primera fila de productos se detecta en cada hoja desde el inicio de los rangos de validación. Así se conservan avisos informativos que Mercado Libre agrega antes de los datos, y los defaults, validaciones, fórmulas internas y escritura usan la misma fila detectada. La metadata de publicación se guarda en `marketplaces.mercadolibre` dentro de `products/<GTIN>/product.json`; los productos antiguos sin estado se leen como `not_published`. Desde el detalle se pueden marcar como **Publicado en MeLi** o **No publicado**; la barra de selección permite marcar varios como publicados en una acción. Se conserva la fecha histórica al desmarcar. El visor muestra el badge y ofrece filtros por estado; los publicados quedan fuera de la selección y del XLSX hasta activar **Incluir publicados en la planilla**. `meli_item_id` identifica la publicación del vendedor y no cambia `catalogo_id`, que identifica el producto del catálogo.

Las referencias técnicas viven separadas en `reference/mercadolibre/templates/`; el visor tiene una sección **Configuración · referencias de categorías de Mercado Libre** para listarlas, cargar un XLSX individual o reemplazar la referencia existente. Muestra ID, nombre, ruta, checksum, fecha y estado. La carga valida que el archivo sea XLSX con una hoja de categoría identificable por ID/ruta, compara contra la anterior y muestra encabezados, obligatoriedad, fórmulas, campos internos y validaciones que cambiaron. Estas referencias sirven solo para comparar esquemas y habilitar categorías; nunca son la base de publicación. El loader admite `registry.json` y `manifest.json` (`templates` o `categories`), de modo que pueda consumir el manifiesto junto con referencias añadidas al repositorio. La carpeta de referencias aún no contiene los 35 archivos; no deben generarse aquí. También se conserva `python3 scripts/meli_referencia.py --lista` y `python3 scripts/meli_referencia.py <categoria.xlsx> [--categoria MLM…]` para administrarlas por CLI.

El esquema de cada referencia se cachea. Una consulta revisa ruta de archivo, checksum declarado y real, `mtime`, tamaño y estado activo; cualquier cambio provoca una nueva lectura OOXML. La planilla operativa no se cachea. Cada petición `/api/meli/layout` construye una instancia y comparte ese mismo `OfficialTemplate` entre inspección y escritura, evitando parsear el archivo dos veces.

El escritor OOXML conserva las partes del archivo operativo y solo modifica celdas editables de producto; las hojas auxiliares, relaciones, dibujos, fórmulas, validaciones, estilos, metadata y hojas ocultas se mantienen.

Los valores de precios, existencia, ficha y fotos parten del layout intermedio del visor. `Cantidad` se convierte en `Stock`, `Precio [$]` en `Precio`, `ID de catálogo ML` en `Código de catálogo ML`, `Fabricante / Laboratorio` en `Fabricante` y las imágenes se unen con coma cuando la planilla operativa ofrece una celda editable. Las transformaciones por categoría se configuran en `config/mercadolibre_plantilla.json`.

Para usar el servidor local directamente abre `http://127.0.0.1:8765/visor/`. Detrás de Nginx, el frontend llama rutas relativas `/api/meli/...`; configura un reverse proxy hacia el backend de loopback, como en `docs/nginx-visor.conf`. `GET /api/meli/` devuelve estado y rutas disponibles; la lista usa `GET /api/meli/references`; la carga/reemplazo usa `POST /api/meli/references`; el visor sincroniza estados con `GET /api/meli/publication-status` y guarda cambios con `POST /api/meli/publication-status`; validación y exportación usan `/api/meli/inspect` y `/api/meli/layout`.

## Sección Pendientes

Lista los productos que tienen algo por resolver, cada uno con su foto, datos básicos y sus pendientes ordenados por gravedad, con el detalle y la acción sugerida. Si filtras por tipo o por pendiente, cada renglón muestra solo los que coinciden (y cuántos más tiene fuera del filtro).

Tipos:

- **Error**: impide o pone en riesgo la publicación (sin fotos, todas las fotos chicas, sin categoría, descripción vacía o muy corta, título largo, sin precio).
- **Pendiente**: falta un dato o una confirmación (producto sin verificar, dato por confirmar en el empaque, podría requerir receta, sin existencia, falta el precio del mejor vendedor, falta el costo de envío en productos de $299 o más).
- **Mejora**: se puede publicar, pero conviene mejorarlo (confianza media, descripción corta, ficha incompleta, una sola foto, foto principal chica o con fondo gris, precio calculado arriba del mejor vendedor, precio en Meli muy arriba del de tienda).

| Pendiente | Tipo | Acción sugerida |
|---|---|---|
| Sin título | error | Completar información |
| Título de más de 60 caracteres | error | Completar información |
| Sin categoría de Mercado Libre | error | Completar información |
| Descripción vacía o muy corta | error | Completar información |
| Sin fotos | error | Buscar más imágenes |
| Todas las fotos son chicas | error | Buscar más imágenes |
| Sin precio de venta | error | Revisar con el dueño |
| Producto sin verificar | pendiente | Completar información |
| Dato por confirmar en el empaque | pendiente | Revisar con el dueño |
| Podría requerir receta | pendiente | Revisar con el dueño |
| Sin existencia | pendiente | Revisar con el dueño |
| Falta el precio del mejor vendedor | pendiente | Completar precios |
| Falta el costo de envío (precio de $299 o más) | pendiente | Completar precios |
| Investigación con confianza media | mejora | Completar información |
| Descripción corta | mejora | Completar información |
| Descripción con pocas secciones | mejora | Completar información |
| Ficha técnica incompleta | mejora | Completar información |
| Una sola foto | mejora | Buscar más imágenes |
| Foto principal chica | mejora | Buscar más imágenes |
| Foto principal con posible fondo gris | mejora | Buscar más imágenes |
| Precio calculado arriba del mejor vendedor | mejora | Revisar con el dueño |
| Precio en Meli muy arriba del de tienda | mejora | Revisar con el dueño |

Reglas y umbrales en `config/pendientes.json`; el cálculo está en `pendientes()` de `scripts/build_visor.py`. Los pendientes de un producto descartado se calculan igual (por si se reactiva), pero no se muestran ni se cuentan.

### Pedir acciones con el Excel

1. Filtra (por ejemplo, Pendiente = «Sin fotos») y selecciona productos: casilla por renglón, «Seleccionar esta página», «Seleccionar los N filtrados» o desde el detalle. La selección es la misma que en el catálogo; «Ver solo seleccionados» la revisa.
2. Elige la **acción a solicitar** (Completar información, Buscar más imágenes, Completar precios, Revisar con el dueño o Descartar de Meli) o déjala vacía para elegirla por renglón en Excel.
3. **Exportar pendientes** descarga `pendientes_meli_AAAA-MM-DD_HHMM.xlsx` con tres hojas: **Productos** (un renglón por producto, con detalle de pendientes, acciones sugeridas, «Acción solicitada» con lista desplegable y «Comentarios»), **Detalle** (un renglón por pendiente) e **Instrucciones** (filtros aplicados y qué hace cada acción).
4. El dueño ajusta «Acción solicitada» y «Comentarios» y adjunta el archivo en el chat.
5. El agente lo procesa: `python scripts/solicitudes.py <archivo.xlsx>` agrupa los productos por acción; `--aplicar-descartes` descarta los marcados con «Descartar de Meli». Las demás acciones se trabajan con `docs/agentes/` (información e imágenes), `docs/MERCADOLIBRE_API.md` (precios) o con el dato que el dueño escribió en Comentarios. Al terminar: regenerar layout y visor y abrir PR.

### Descartar productos de Mercado Libre

Desde el visor, en cualquier vista:

- **Tarjeta** (cuadrícula) y columna **Meli** (lista): botón «Descartar de Meli» o «Reactivar en Meli».
- **Detalle**: botón «Descartar de Meli», que pide el motivo (por omisión «Indicación del dueño desde el visor»), o «Reactivar en Meli».
- **Selección**: «Descartar de Meli (N)» (pide confirmar con un segundo clic) y «Reactivar en Meli (N)» para todos los seleccionados.

El cambio se aplica al momento en este navegador (`localStorage`, `visor:descartes`): el producto sale de «Exportar layout Meli», de los conteos y de la sección Pendientes. La barra roja muestra cuántos hay descartados y cuántos cambios faltan por versionar, y permite **Exportar descartes** (Excel `descartes_AAAA-MM-DD_HHMM.xlsx`, hoja Descartes: Código, Producto, Acción = Descartar o Reactivar, Motivo, Fecha), **Ver solo descartados** y **Deshacer lo hecho aquí**. Para que quede en el repositorio (y en el layout versionado), el dueño adjunta ese Excel y pide «Versiona estos descartes»; el agente corre `python scripts/descartar.py --excel <archivo.xlsx>` y regenera layout y visor.

En la terminal: `python scripts/descartar.py --gtin <GTIN…> --motivo "…"` marca `marketplaces.mercadolibre.descartado` en `product.json`. El producto se queda en el repositorio (sirve para otros marketplaces), pero sale del layout (queda en la hoja Descartados) y el visor lo muestra como «Descartado de Meli». `--reactivar` lo regresa y `--lista` muestra los descartados.

## Comparar precios

Botón **Comparar precios** (arriba, junto a Catálogo y Pendientes): lista tipo Excel, un renglón por producto (respeta los filtros de la izquierda), para ver quién tiene el precio más alto y más bajo.

- Columnas: código, producto, nuestro precio en tienda, **Nosotros: Precio Meli final**, Mercado Libre (mejor vendedor y promedio de referencia), una columna por tienda con precio (Farmacias Benavides, YZA, del Ahorro, Chedraui…), **Precio de venta en otros marketplaces** (el más bajo) y **Otros marketplaces** (tienda de ese precio), quién tiene el precio más alto, quién el más bajo, nuestra posición y nosotros contra el más bajo (%).
- En cada renglón el precio más alto va en rojo y el más bajo en verde; nuestra columna va resaltada. El precio de lista tachado aparece debajo cuando la tienda tiene oferta. Clic en un precio abre la página de la tienda; clic en el renglón abre el detalle (bloque «Precios en otros marketplaces»).
- **Nuestro precio**: compara con el Precio Meli final (el que publicamos) o con el precio de venta en tienda.
- Chips de posición (Somos el más caro, Intermedio, Somos el más barato, Sin comparación) para filtrar; «Solo con precio en otros marketplaces»; clic en un encabezado para ordenar.
- **Exportar comparación**: Excel con la hoja Comparación (lo filtrado), la hoja **Captura** (precios existentes y un renglón vacío por producto para agregar más) e Instrucciones. El dueño llena Captura, lo adjunta y pide «Versiona estos precios de otros marketplaces» → `python scripts/otros_marketplaces.py excel <archivo.xlsx>`.

La misma comparación está en la base de datos (`comparacion_precios`, `v_comparacion_precios`; `docs/BASE_DE_DATOS.md`).

## Indicadores

Reglas en `config/indicadores.json` (cámbialas ahí y regenera los datos):

| Indicador | Valores | Regla |
|---|---|---|
| Descripción | buena / regular / mala | Buena: investigación verificada con confianza alta, 800 caracteres o más y 3 secciones reconocidas o más. Regular: verificada con 500 caracteres o más. Mala: sin verificar o más corta. |
| Fotos | buena / regular / mala | Buena: 2 fotos o más y la principal con el producto de 800 px o más, sin fondo gris. Regular: alguna foto con el producto de 500 px o más. Mala: sin fotos o todas más chicas. |
| Precios | completos / incompletos | Completos cuando se conocen el precio de venta al público, el precio de la publicación más vendida en Mercado Libre y el precio Meli calculado (con comisión y costo de empaque y logística). |

El precio del mejor vendedor sale de `scripts/meli_precios.py` (`data/competencia_meli.csv`, 1,024 productos el 29 sep 2026). Sin él, el producto tiene precios incompletos y se publica al Precio Meli calculado; con él, el Precio Meli final = mejor vendedor − $1 si no queda abajo del calculado; si no, el calculado.

## Regenerar los datos

Después de integrar una sesión, cambiar fotos o precios:

```bash
python scripts/build_visor.py
```

- Precios y existencias: `insumos/precios_existencias.csv` si existe; si no, las hojas Precios y Layout del layout versionado `layouts/mercadolibre/layout_mercadolibre.xlsx`.
- Competencia: `data/competencia_meli.csv` (salida de `scripts/meli_precios.py`); catálogos rechazados: `data/catalogo_ml_rechazados.csv` (pendiente «El GTIN apunta a otro producto en Mercado Libre»).
- La detección de fondo gris (`scripts/revisar_fotos.py`) se guarda en caché en `trabajo/cache_fondo_fotos.json`; la primera corrida tarda más.
- `--base-imagenes` cambia la ruta de las fotos vista desde `visor/index.html` (por omisión `../products`); sirve, por ejemplo, para apuntar a `https://raw.githubusercontent.com/zublimemx/marketplaces-product-images/main/products` si se publica el visor fuera del repositorio.

Formato de `visor/data/productos.js` en `docs/CONTRATOS.md` §8.
