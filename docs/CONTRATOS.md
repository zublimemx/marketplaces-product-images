# Contratos de datos

Todo archivo JSON va en UTF-8 con `ensure_ascii=False`. Los GTIN siempre son texto (conservan ceros a la izquierda).

## 1. `products/<GTIN>/product.json` (fuente de verdad)

Esquema formal: `schema/product.schema.json`.

| Campo | Tipo | Regla |
|---|---|---|
| `gtin` | texto | Código de barras; igual al nombre de la carpeta |
| `sku` | texto | Igual al GTIN |
| `linea` | texto | `Farma`, `Mark` o `Farma + Mark` |
| `nombre_sistema` | texto | Nombre en el ERP |
| `nombres_sistema_alternos` | lista de texto | Otros nombres del mismo GTIN |
| `titulo` | texto ≤ 60 | Título comercial; vacío si está pendiente |
| `descripcion` | texto | Ver `docs/REGLAS_NEGOCIO.md` |
| `ficha` | objeto | Llaves permitidas: `marca`, `fabricante`, `linea`, `variante`, `presentacion`, `contenido_neto` (número), `unidad_contenido`, `unidades_por_envase` (número), `principio_activo`, `concentracion`, `via_administracion`, `edad_etapa`, `talla`, `sabor_aroma`, `genero`, `tipo_piel_cabello`, `registro_sanitario`, `otros` ("Atributo: valor; …") |
| `receta_mx` | texto | `Sí`, `No`, `Revisar`, `No aplica` o vacío (pendiente) |
| `marketplaces.mercadolibre` | objeto | `categoria_id` (hoja publicable MLM), `categoria_ruta`, `categoria_rx_sugerida` (ID de `reference/mercadolibre/categorias_con_receta.csv` o vacío), `catalogo_id` (MLM… o vacío); `descartado` {`motivo`, `fecha`} solo si el producto se sacó del catálogo de importación a Mercado Libre (`scripts/descartar.py`); `paquete` {`peso_g`, `largo_cm`, `ancho_cm`, `alto_cm`} opcional (medidas reales, p. ej. de la API; `scripts/envios.py` lo prefiere a su estimación) |
| `marketplaces.amazon`, `.shopify`, `.odoo` | objeto | Reservado; hoy vacío |
| `imagenes` | lista | Lo escribe solo `scripts/imagenes.py`: `archivo`, `origen` (`fabricante`/`catalogo_ml`/`tienda`), `fuente_url`, `pagina`, `ancho_original`, `alto_original`, `lado_final`, `lado_util` (px que ocupa el producto), `fecha` |
| `url_oficial` | texto | Página del fabricante o vacío |
| `fuentes` | lista de URL | Páginas usadas para la ficha |
| `investigacion` | objeto | `estado` (`pendiente`, `sin_verificar`, `verificado`), `confianza` (`alta`, `media`, `baja`), `encontrado_por` (`gtin`, `nombre`, `no_encontrado`), `notas`, `notas_imagenes`, `fecha`, `sesion` |

Reglas de estado: `verificado` = confianza alta o media; `sin_verificar` = confianza baja (datos deducidos del nombre); `pendiente` = sin investigar. "Completo" = verificado y con al menos una foto.

## 2. Lotes de trabajo (`trabajo/sesion_NN/lotes/*.json`, no versionados)

Arreglo de objetos `{id, gtin, nombre, linea, estado}`; `id` es el `orden` de `data/prioridad.csv`. Los crea `scripts/seleccionar_lote.py`. Prefijo `inv_` = investigación completa; `img_` = solo fotos y ficha.

## 3. Resultados de subagentes (`trabajo/sesion_NN/resultados/*.json`, no versionados)

Mismo nombre que su lote y mismo orden de GTIN.

- `inv_XX.json` (esquema `schema/resultado_investigacion.schema.json`): `id`, `gtin`, `titulo`, `descripcion`, `categoria_id`, `categoria_ruta`, `ficha`, `receta_mx`, `categoria_rx_sugerida`, `catalogo_ml`, `url_oficial`, `fuentes`, `encontrado_por`, `confianza`, `notas`, `notas_imagenes`.
- `img_XX.json` (esquema `schema/resultado_fotos.schema.json`): `id`, `gtin`, `ficha`, `fuentes_nuevas`, `notas_imagenes`.

Los integra `scripts/integrar_resultados.py`.

## 4. Insumos de precio (`insumos/precios_existencias.csv`, no versionado)

Columnas `gtin,precio,stock,linea,nombre,nota_cruce`, en el orden de `data/prioridad.csv`. `precio` con IVA incluido; `stock` ≥ 0. Lo genera `scripts/preparar_insumos.py` desde los Excel del ERP, que el dueño entrega y se colocan en `insumos/originales/`.

## 4 bis. Competencia (`data/competencia_meli.csv`, versionado)

Salida de `scripts/meli_precios.py` (antes en `insumos/`; los scripts aún leen esa ruta si falta la nueva): `gtin, producto_catalogo, nombre_catalogo, publicaciones_otros, precio_promedio_otros, precio_mediana_otros, precio_min_otros, precio_max_otros, publicaciones_atipicas, precio_mejor_vendedor, item_mejor_vendedor, vendedor_mejor, ventas_vendedor_mejor, metodo_mejor_vendedor, fecha, nota`. `metodo_mejor_vendedor`: `vendedor_con_mas_ventas` (la API ya no da ventas por publicación). `nota` explica las filas sin precios. Layout y visor leen solo `precio_promedio_otros`, `precio_mejor_vendedor` y `metodo_mejor_vendedor`. Reglas en `docs/MERCADOLIBRE_API.md`.

**Catálogos rechazados (`data/catalogo_ml_rechazados.csv`, versionado):** `gtin, producto_catalogo, nombre_catalogo, tipo, motivo, fecha`, con `tipo` = `otro_producto` u `otra_presentacion`. El catálogo de Mercado Libre que corresponde al GTIN no es el producto: `meli_precios.py` no lo usa (la fila de competencia queda sin precios, con `nota` = `catálogo rechazado (…): <motivo>`), `aplicar_revision_ml.py` quita el `catalogo_id` de `product.json` y, si es otro producto, sus fotos `catalogo_ml`, y el visor marca el pendiente `catalogo_ml_rechazado`.

## 4 ter. Revisión de fotos (`trabajo/revision_fotos.csv`, no versionado)

Salida de `scripts/revisar_fotos.py`: `gtin, archivo, lado_util, motivo` con motivos `baja_resolucion`, `posible_fondo_gris`, `sin_fotos`, `archivo_faltante`.

## 5. `data/prioridad.csv` (versionado)

`orden,gtin,linea,nombre_sistema,nota_cruce`. `orden` 1 = producto con más venta en pesos. Sin montos ni precios.

## 6. Layout de Mercado Libre (`layouts/mercadolibre/layout_mercadolibre.xlsx`, versionado)

Salida de `scripts/build_mercadolibre.py`. Libro .xlsx con fórmulas; la copia versionada se guarda recalculada (con valores) para que se lea sin abrir Excel. Por decisión del dueño se versiona completo, con precios y existencias. Hojas:

- **Avance**: conteos (productos, verificados, con fotos, completos, pendientes), sesiones realizadas y faltantes, historial.
- **Layout Mercado Libre**: SKU; Código universal de producto; Título; Categoría (ID); Categoría (ruta); Precio [$] (= Precio Meli Final); Cantidad; Condición; Tipo de publicación; Descripción; Forma de envío; Costo de envío; Retiro en persona; Tipo de garantía; ID de catálogo ML; Marca; Fabricante / Laboratorio; Línea; Variante / Modelo; Presentación; Contenido neto; Unidad de contenido; Unidades por envase; Principio activo; Concentración; Vía de administración; Edad / Etapa; Talla; Sabor / Aroma; Género; Tipo de piel / cabello; Registro sanitario; Otros atributos; Imagen 1 a 6 (URLs); y columnas de control: Línea de origen, Nombre en sistema, Estado de investigación.
- **Precios** (A–AA): SKU; Título; Categoría raíz; Precio de venta (D); Costo de empaque y logística (E); Precio de venta Marketplaces (F); Comisión Meli (G, IVA incluido); Peso cobrable estimado (H); Costo de envío si el precio queda en $299 o más (I); precio por tramo (J–M: < $99, $99–$149, $149–$299, ≥ $299 con envío); Precio Meli promedio otros vendedores (N); Precio mejor vendedor (O); Descuento contra mejor vendedor (P); Precio Meli calculado (Q); Precio Meli Final (R); Diferencia contra mejor vendedor (S); Costo fijo aplicado (T); Envío a cargo del vendedor (U); Ingreso neto estimado (V); Margen (W); Base del costo de envío (X); Ajustes manuales (Y); Precio de venta en otros marketplaces (Z, el más bajo encontrado, referencia); Otros marketplaces (AA, tienda de ese precio y cuántas se compararon). Los parámetros ajustados (D, E, G, I, N, O, P) llevan valor y fondo naranja claro; si no, E, G y P son fórmulas a Parámetros.
- **Parámetros**: entradas de `config/mercadolibre.json` con su fuente.
- **Revisión**: estado, confianza, receta, categoría con receta sugerida, notas, nota de cruce, existencia, fuentes, número y origen de fotos, fotos de baja resolución.
- **Categorías usadas**: ID, ruta, productos y comisión.
- **Descartados**: SKU, título, nombre en sistema, motivo, fecha, precio de venta y existencia de los productos con `descartado` (no están en las demás hojas).

Precio Meli Final (hoja Precios, columna R) = Precio mejor vendedor − descuento (columna P) si no queda abajo del Precio Meli calculado (Q); si no, Q. Q incluye el costo de envío (I) cuando el precio queda en $299 o más. El promedio de otros vendedores es solo referencia. Mismas reglas en `scripts/precios.py` y `visor/precios.js`.

## 7. Futuros layouts (Odoo, Shopify, Amazon)

Deben leerse de `product.json` y de `insumos/precios_existencias.csv` (o, si no está, de las hojas Precios y Layout del layout versionado), sin copiar contenido a otro lado. Para precios de Mercado Libre usa `scripts/precios.py`, que replica las fórmulas de la hoja Precios. Cada layout se versiona en `layouts/<canal>/`. Los datos propios de cada canal (categoría, tipo de producto, etc.) se guardan en `marketplaces.<canal>` del `product.json`, y sus reglas en `config/<canal>.json`.

## 8. Datos del visor (`visor/data/productos.js`, versionado)

Salida de `scripts/build_visor.py` (ver `docs/VISOR.md`). Es JavaScript para abrir el visor sin servidor: `window.CATALOGO = {generado, total, reglas, productos: [...]}`.

- `reglas`: copia de `config/indicadores.json`.
- `pendientes`: `acciones` (nombre y descripción), `tipos` y el catálogo `pendientes` de `config/pendientes.json` (código → `tipo`, `titulo`, `accion`).
- Cada producto: `orden` (prioridad por ventas), `gtin`, `titulo`, `nombre_sistema`, `linea`, `categoria_id`, `categoria_ruta`, `categoria` (hoja), `catalogo_id`, `categoria_rx_sugerida`, `stock`, `precios` (salida de `calcular_parametros()` de `scripts/precios.py`: `precio_venta`, `costo_empaque`, `precio_marketplaces`, `comision`, `costo_envio`, `precio_meli_calculado`, `precio_promedio_otros`, `precio_mejor_vendedor`, `descuento_mejor_vendedor`, `precio_meli_final`, `diferencia_mejor_vendedor`, `costo_fijo`, `envio_vendedor`, `ingreso_neto`, `margen`; `null` = sin dato), `param` (los siete parámetros efectivos), `param_origen` (`{campo: "ajuste"}` para los versionados en `data/ajustes_precios.json`), `envio` (`peso`, `tamano`, `base`, `estimado`), `ajuste_nota`, `metodo_mejor_vendedor`, `imagenes` (`src` relativo a `visor/`, `u` = lado útil en px, `o` = origen, `gris` = posible fondo gris, `fuente`), `descripcion`, `ficha`, `receta_mx`, `url_oficial`, `fuentes`, `investigacion` (`estado`, `confianza`, `encontrado_por`, `notas`, `notas_imagenes`, `fecha`, `sesion`), `ind` (`descripcion`, `fotos`, `precios` y su `*_motivo`), `pend` (lista de `{c: código de config/pendientes.json, d: detalle}`; se calcula aunque esté descartado y el visor la oculta en ese caso), `descartado` (`{motivo, fecha}` o `null`), `sin_titulo` y `otros` (precios en otros marketplaces: `{m: tienda, p: precio, pl: precio de lista, u: URL, f: fecha, n: nota}`, ordenados de menor a mayor). Arriba, `marketplaces` lista las tiendas con precio, de la más a la menos frecuente. En `imagenes`, `a` es el nombre del archivo. Arriba, `meli` trae las constantes del layout (§10) y `calculo` las del precio (`costos_fijos`, `umbral`, `envio`, `campos`).

No se edita a mano: se regenera después de cada cambio en `product.json`, fotos, precios o reglas.

## 9. Excel de pendientes (exportado desde el visor; lo adjunta el dueño)

`pendientes_meli_AAAA-MM-DD_HHMM.xlsx`, generado por `visor/xlsx.js`:

- **Productos** (un renglón por producto seleccionado): Código, Producto, Nombre en sistema, Línea, Categoría, Inventario, Precio de venta, Precio Meli calculado, Precio mejor vendedor, Precio Meli final, Descripción, Fotos, Precios (indicadores), Errores, Pendientes, Mejoras (conteos), Detalle de pendientes (`[Tipo] Título: detalle`, uno por línea), Acciones sugeridas, Publicación en Meli, **Acción solicitada** (lista: Completar información, Buscar más imágenes, Completar precios, Revisar con el dueño, Descartar de Meli) y **Comentarios** (texto libre del dueño).
- **Detalle** (un renglón por pendiente): Código, Producto, Tipo, Pendiente, Detalle, Acción sugerida, Clave (código de `config/pendientes.json`).
- **Instrucciones**: fecha, filtros aplicados, acción precargada y qué hace cada acción.

`scripts/solicitudes.py` lee la hoja Productos por nombre de columna (Código, Producto, Acción solicitada, Acciones sugeridas, Comentarios), así que tolera columnas movidas o agregadas.

## 10. Plantilla oficial de Mercado Libre exportada desde el visor

`layout_meli_AAAA-MM-DD_HHMM.xlsx`, generado por `visor/app.js` y `scripts/visor_server.py`, parte exclusivamente del XLSX operativo cargado por el usuario. El parser detecta dinámicamente hojas por ruta en A1, nombre visible en A2, encabezados en fila 3 y obligatoriedad en fila 4. Los datos empiezan en la fila 8. El ID y ruta se contrastan con `reference/mercadolibre/categorias_mlm_hojas_publicables.csv`.

El flujo separa **planilla operativa** (archivo fresco cargado y base del XLSX de salida) de **plantilla de referencia** (archivo por categoría usado solo para compatibilidad). El visor envía los productos seleccionados en el formato intermedio descrito en §8. El exportador agrupa por `Categoría (ID)`, mapea por encabezados y transforma atributos desde `config/mercadolibre_plantilla.json`. No modifica celdas con fórmulas o estilo gris, ni agrega hojas o columnas. Categorías sin referencia o con esquema incompatible y campos obligatorios faltantes se muestran en el visor y se omiten; si no queda ningún producto válido, no se descarga un XLSX.

La salida conserva las partes del XLSX operativo, incluidas hojas auxiliares/ocultas, relaciones, dibujos, estilos, fórmulas y validaciones. La administración de referencias está en `scripts/meli_referencias.py`; el registro inicial `reference/mercadolibre/templates/registry.json` está vacío. Las referencias individuales serán entregadas posteriormente y no se generaron en esta tarea.

La cache de esquemas referencia archivo, checksum del manifiesto y contenido, `mtime`, tamaño y estado. La planilla operativa no se cachea: `POST /api/meli/layout` comparte el objeto parseado con la inspección previa dentro de esa misma petición. `GET /api/meli/references` lista metadata; `POST` al mismo recurso valida e incorpora/reemplaza una referencia. La interfaz de Configuración consume ambas operaciones. El manifiesto puede definir `templates` o `categories`, con rutas `file`/`filename`/`path` y campos equivalentes para ID, checksum, fecha y estado.

## 11. Ajustes de precio (`data/ajustes_precios.json`, versionado)

`{"<GTIN>": {"costo_envio": 120, "precio_mejor_vendedor": 349, "nota": "…", "fecha": "AAAA-MM-DD"}}`. Campos permitidos: `precio_venta`, `costo_empaque`, `comision` (fracción, 0.14), `costo_envio`, `precio_promedio_otros`, `precio_mejor_vendedor`, `descuento_mejor_vendedor`. Un campo ausente usa el valor del sistema, el estimado o el de la API. Lo escribe `scripts/ajustes_precios.py` a partir del Excel «Exportar ajustes de precio» del visor (hoja Ajustes: Código, Producto, una columna por parámetro con el encabezado del visor, Precio Meli calculado, Precio Meli final, Origen, Nota); cada renglón reemplaza los ajustes de ese producto. En el navegador, los ajustes que aún no se versionan viven en `localStorage` (`visor:ajustes`).

## 11 bis. Descartes exportados desde el visor

`descartes_AAAA-MM-DD_HHMM.xlsx`, generado por `exportarDescartes()` de `visor/app.js` con los cambios hechos en el navegador (`localStorage`, `visor:descartes` = `{gtin: {motivo, fecha}}` o `{gtin: {reactivar: true, fecha}}`). Hoja **Descartes**: Código, Producto, Acción (`Descartar` o `Reactivar`), Motivo, Fecha; hoja **Instrucciones**. Se aplica con `python scripts/descartar.py --excel <archivo.xlsx>` (motivo vacío = «Descartado desde el visor»).

## 12. Costos de envío estimados (`data/envios.csv`, versionado)

`gtin, peso_real_kg, peso_volumetrico_kg, peso_cobrable_kg, tamano (chico/mediano/grande), costo_envio, base`. Lo escribe `python scripts/envios.py` (para revisión); el layout y el visor calculan lo mismo con `envios.estimar()`.

## 13. Revisión del catálogo de Mercado Libre (`trabajo/revision_fotos_ml/`, `trabajo/descripciones_ml/`, no versionados)

Los prepara `scripts/preparar_revision_ml.py`, los llenan subagentes con `docs/agentes/revision_ml.md` y los aplica `scripts/aplicar_revision_ml.py`.

- `revision_fotos_ml/indice.json`: `{gtin: {hoja, titulo, presentacion, imagenes: [{n, archivo, origen}]}}`; hojas `hoja_NNN.jpg`.
- `revision_fotos_ml/resultado_XX.json`: `{"revisadas": [hojas], "quitar": [{gtin, archivo, motivo}], "principal": [{gtin, archivo}]}`. Se borra cada foto de `quitar` (archivo y registro en `imagenes`) y la `principal` pasa al frente.
- `descripciones_ml/lote_dXX.json` (reescribir descripción) y `lote_cXX.json` (solo confirmar): `gtin, titulo, nombre_sistema, receta_mx, categoria, investigacion {estado, confianza, notas}, catalogo_ml {id, origen, nombre, caracteristicas, descripcion_corta, atributos}, descripciones_otros_vendedores, [descripcion_actual], ficha_actual`.
- `descripciones_ml/resultado_dXX.json` y `resultado_cXX.json`: arreglo en el orden del lote con `gtin, confirmado, diferencias, notas` y opcionales `descripcion`, `ficha` (solo claves que cambian; `otros` completo), `titulo` (≤ 60). Al aplicar: `confirmado` = true deja `investigacion` en `verificado`, confianza `alta`, `encontrado_por` `gtin` y `notas` = "GTIN confirmado en el catálogo de Mercado Libre (<ID>, <fecha>). <notas>"; si es false, agrega a las notas anteriores "Catálogo de Mercado Libre <ID> no coincide: <diferencias>" y las notas nuevas.

## 14. Base de datos (`data/catalogo.db`, versionada)

SQLite generada por `scripts/build_db.py` desde `products/*/product.json`, `data/` y `visor/data/productos.js` (no se edita a mano; el CI verifica que esté al día con `--verificar`). Tablas: `productos` (con `precio_otros_marketplaces` = precio más bajo en otros marketplaces y `otros_marketplaces` = tienda de ese precio), `fichas`, `imagenes`, `fuentes`, `mercadolibre`, `precios_meli`, `competencia_meli`, `precios_otros_marketplaces`, `comparacion_precios`, `envios`, `ajustes_precios`, `catalogos_rechazados`, `pendientes`, `diccionario` (descripción de cada columna) y `meta`; vistas `v_productos` y `v_comparacion_precios`. Detalle y consultas en `docs/BASE_DE_DATOS.md`.

**Comparación de precios** (misma regla en `build_db.py` y en `visor/app.js`): competidores = mejor vendedor de Mercado Libre + cada tienda de `precios_otros_marketplaces`; «nosotros» = Precio Meli final (o precio de tienda). Posición: `mas_barato` si nuestro precio es menor o igual al más bajo de los competidores, `mas_caro` si es mayor o igual al más alto, `intermedio` en otro caso, `sin_comparacion` sin competidores. En empate, «quién tiene el más alto/bajo» es «Nosotros».

## 15. Precios en otros marketplaces (`data/precios_otros_marketplaces.csv`, versionado)

`gtin, marketplace, precio, precio_lista, url, fecha, nota, origen`: un renglón por producto y tienda. `precio` con IVA incluido (el de oferta si hay; `precio_lista` = precio normal). `marketplace` con nombre canónico (`ALIAS` de `scripts/otros_marketplaces.py`: «Farmacias del Ahorro», «Farmacias Benavides», «Farmacias YZA», «Farmacias San Pablo», «Walmart», «Amazon»…). `origen`: `agente sesión N` o `dueño (Excel)`. Se escribe con `scripts/otros_marketplaces.py`:
- `integrar --sesion N`: resultados `trabajo/sesion_NN/resultados/precios_XX.json` (`[{gtin, precios: [{marketplace, precio, precio_lista?, url, nota}], notas}]`, ver `docs/agentes/precios_otros.md`).
- `excel <archivo>`: hoja **Captura** del Excel «Exportar comparación» del visor (Código, Producto, Marketplace, Precio, Precio lista, URL, Nota, Fecha); cada renglón reemplaza el precio de ese producto y tienda, y precio vacío lo borra.
