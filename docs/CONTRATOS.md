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
| `marketplaces.mercadolibre` | objeto | `categoria_id` (hoja publicable MLM), `categoria_ruta`, `categoria_rx_sugerida` (ID de `reference/mercadolibre/categorias_con_receta.csv` o vacío), `catalogo_id` (MLM… o vacío) |
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

Columnas `gtin,precio,stock,linea,nombre,nota_cruce`, en el orden de `data/prioridad.csv`. `precio` con IVA incluido; `stock` ≥ 0. Lo genera `scripts/preparar_insumos.py` desde los Excel del ERP.

## 5. `data/prioridad.csv` (versionado)

`orden,gtin,linea,nombre_sistema,nota_cruce`. `orden` 1 = producto con más venta en pesos. Sin montos ni precios.

## 6. Layout de Mercado Libre (salida de `scripts/build_mercadolibre.py`)

Libro .xlsx con fórmulas (recalcular con LibreOffice o abrir en Excel/Sheets):

- **Avance**: conteos (productos, verificados, con fotos, completos, pendientes), sesiones realizadas y faltantes, historial.
- **Layout Mercado Libre**: SKU; Código universal de producto; Título; Categoría (ID); Categoría (ruta); Precio [$] (= Precio Meli Final); Cantidad; Condición; Tipo de publicación; Descripción; Forma de envío; Costo de envío; Retiro en persona; Tipo de garantía; ID de catálogo ML; Marca; Fabricante / Laboratorio; Línea; Variante / Modelo; Presentación; Contenido neto; Unidad de contenido; Unidades por envase; Principio activo; Concentración; Vía de administración; Edad / Etapa; Talla; Sabor / Aroma; Género; Tipo de piel / cabello; Registro sanitario; Otros atributos; Imagen 1 a 6 (URLs); y columnas de control: Línea de origen, Nombre en sistema, Estado de investigación.
- **Precios**: SKU; Título; Categoría raíz; Precio de venta; Precio de venta Marketplaces; Comisión Meli; precio por tramo (< $99, $99–$149, $149–$299, ≥ $299); Precio Meli calculado; Precio Meli promedio otros vendedores (entrada); Precio mejor vendedor (entrada); Precio Meli Final; Diferencia contra mejor vendedor; Costo fijo aplicado; Envío a cargo del vendedor; Ingreso neto estimado; Margen contra Precio de venta Marketplaces.
- **Parámetros**: entradas de `config/mercadolibre.json` con su fuente.
- **Revisión**: estado, confianza, receta, categoría con receta sugerida, notas, nota de cruce, existencia, fuentes, número y origen de fotos, fotos de baja resolución.
- **Categorías usadas**: ID, ruta, productos y comisión.

## 7. Futuros layouts (Odoo, Shopify, Amazon)

Deben leerse de `product.json` y de `insumos/precios_existencias.csv`, sin copiar contenido a otro lado. Los datos propios de cada canal (categoría, tipo de producto, etc.) se guardan en `marketplaces.<canal>` del `product.json`, y sus reglas en `config/<canal>.json`.
