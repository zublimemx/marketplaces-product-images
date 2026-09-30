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
- **Filtros** multiselección con autocompletado por nombre, código (GTIN o ID de catálogo) y categoría de Mercado Libre; cada filtro acepta varios valores (se combinan con «o») y «Contiene «texto»» para buscar por fragmento. Además: línea, con o sin existencia, los tres indicadores, publicación en Meli (se publica o descartado), tipo de pendiente y pendiente. Filtros distintos se combinan con «y». Los números junto a cada opción cuentan los productos que quedarían al marcarla.
- **Resumen** arriba: conteo por indicador y por tipo de pendiente (clic para filtrar), piezas en inventario, productos sin existencia y descartados.
- **Detalle** (clic en un producto): indicadores con el motivo, botón «Seleccionar para exportar», fotos con miniaturas y datos de cada foto (origen, tamaño útil, fuente), precios e inventario, categoría y catálogo de Mercado Libre, pendientes, errores y mejoras, descripción, ficha técnica, investigación (estado, confianza, notas, fuentes) y hasta 12 productos similares de la misma categoría hoja (si hay pocos, se completa con categorías hermanas).
- **Selección**: casilla en cada renglón de la lista, en cada tarjeta y en cada renglón de Pendientes; la casilla del encabezado de la lista selecciona o deselecciona todos los filtrados (queda a medias si solo hay algunos). La barra de selección tiene «Seleccionar los N filtrados», «Deseleccionar los N filtrados», «Seleccionar esta página», «Quitar toda la selección» y «Ver solo seleccionados». La selección se conserva al cambiar filtros, vista o sección.
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

## Exportar el layout de Mercado Libre

Selecciona productos (por ejemplo, filtra y usa «Seleccionar los N filtrados», o todos con los filtros limpios) y pulsa **Exportar layout Meli**. El archivo trae:

- **Layout Mercado Libre**: las mismas columnas y valores que `layouts/mercadolibre/layout_mercadolibre.xlsx` (SKU, código universal, título, categoría, Precio [$] = Precio Meli Final, cantidad, valores fijos de publicación, descripción, ficha técnica e Imagen 1 a 6), con valores en lugar de fórmulas, más las columnas grises de control (línea de origen, nombre en sistema, estado de investigación y «Errores a revisar»).
- **Precios**: desglose de cada precio (venta, marketplaces, comisión, calculado, promedio, mejor vendedor, final, costo fijo, envío, ingreso neto y margen).
- **Instrucciones**: productos exportados, descartados omitidos, productos con errores, filtros aplicados y notas de importación.

Las URLs de las fotos apuntan al repositorio: `https://raw.githubusercontent.com/zublimemx/marketplaces-product-images/main/products/<GTIN>/images/<GTIN>_<n>.jpg`. Mercado Libre solo puede descargarlas mientras el repositorio es público. Los productos descartados no se exportan. La exportación de los 1,163 productos se comparó celda por celda con el layout versionado (0 diferencias). Las constantes del layout (encabezados, ficha, número de fotos, URL base, valores fijos) salen de `scripts/build_mercadolibre.py` y viajan en `visor/data/productos.js`, así que el visor y el script siempre coinciden.

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

Reglas y umbrales en `config/pendientes.json`; el cálculo está en `pendientes()` de `scripts/build_visor.py`. Los productos descartados no tienen pendientes.

### Pedir acciones con el Excel

1. Filtra (por ejemplo, Pendiente = «Sin fotos») y selecciona productos: casilla por renglón, «Seleccionar esta página», «Seleccionar los N filtrados» o desde el detalle. La selección es la misma que en el catálogo; «Ver solo seleccionados» la revisa.
2. Elige la **acción a solicitar** (Completar información, Buscar más imágenes, Completar precios, Revisar con el dueño o Descartar de Meli) o déjala vacía para elegirla por renglón en Excel.
3. **Exportar pendientes** descarga `pendientes_meli_AAAA-MM-DD_HHMM.xlsx` con tres hojas: **Productos** (un renglón por producto, con detalle de pendientes, acciones sugeridas, «Acción solicitada» con lista desplegable y «Comentarios»), **Detalle** (un renglón por pendiente) e **Instrucciones** (filtros aplicados y qué hace cada acción).
4. El dueño ajusta «Acción solicitada» y «Comentarios» y adjunta el archivo en el chat.
5. El agente lo procesa: `python scripts/solicitudes.py <archivo.xlsx>` agrupa los productos por acción; `--aplicar-descartes` descarta los marcados con «Descartar de Meli». Las demás acciones se trabajan con `docs/agentes/` (información e imágenes), `docs/MERCADOLIBRE_API.md` (precios) o con el dato que el dueño escribió en Comentarios. Al terminar: regenerar layout y visor y abrir PR.

### Descartar productos de Mercado Libre

`python scripts/descartar.py --gtin <GTIN…> --motivo "…"` marca `marketplaces.mercadolibre.descartado` en `product.json`. El producto se queda en el repositorio (sirve para otros marketplaces), pero sale del layout (queda en la hoja Descartados) y el visor lo muestra como «Descartado de Meli». `--reactivar` lo regresa y `--lista` muestra los descartados.

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
