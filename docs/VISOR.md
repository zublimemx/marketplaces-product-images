# Visor de productos

Página para revisar a ojo la calidad y la cantidad de los productos antes de importarlos: fotos, descripción, ficha técnica, categoría, inventario y precios, con indicadores de calidad por producto.

Archivos (HTML, CSS y JS por separado, sin dependencias ni compilación):

```
visor/index.html          Estructura de la página
visor/styles.css          Estilos (tema claro y oscuro según el sistema)
visor/app.js              Filtros, cuadrícula, tabla, paginación y detalle
visor/data/productos.js   Datos (window.CATALOGO = …), generado por scripts/build_visor.py
config/indicadores.json   Reglas de los indicadores
scripts/build_visor.py    Genera visor/data/productos.js
scripts/precios.py        Mismas fórmulas de precio que la hoja Precios del layout
```

## Abrir

Necesita el repositorio completo, porque las fotos se leen de `../products/<GTIN>/images/`.

- Doble clic en `visor/index.html` (funciona sin servidor porque los datos son un archivo `.js`).
- O con servidor local desde la raíz del repositorio: `python -m http.server 8000` y abrir `http://localhost:8000/visor/`.

Enlace directo a un producto: `visor/index.html#p<GTIN>` (por ejemplo `#p7501058623300`).

## Qué hace

- **Vistas**: cuadrícula y lista (tabla). En ambas, cada producto trae su carrusel de fotos (flechas y contador).
- **Tabla**: columnas Fotos, Código, Producto, Categoría, Línea, Inventario, Precio venta, Precio marketplaces, Precio Meli calculado, Promedio otros vendedores, Precio mejor vendedor, Precio Meli final e indicadores. Clic en el encabezado ordena (otro clic invierte el sentido). El botón «Columnas» muestra u oculta columnas.
- **Orden** también desde el selector «Ordenar por» (incluye «Prioridad por ventas», el orden de `data/prioridad.csv`).
- **Paginación** de 24, 48 o 96 productos.
- **Filtros** multiselección con autocompletado por nombre, código (GTIN o ID de catálogo) y categoría de Mercado Libre; cada filtro acepta varios valores (se combinan con «o») y «Contiene «texto»» para buscar por fragmento. Además: línea, con o sin existencia, y los tres indicadores. Filtros distintos se combinan con «y». Los números junto a cada opción cuentan los productos que quedarían al marcarla.
- **Resumen** arriba: conteo por indicador (clic para filtrar), piezas en inventario y productos sin existencia.
- **Detalle** (clic en un producto): indicadores con el motivo, fotos con miniaturas y datos de cada foto (origen, tamaño útil, fuente), precios e inventario, categoría y catálogo de Mercado Libre, descripción, ficha técnica, investigación (estado, confianza, notas, fuentes) y hasta 12 productos similares de la misma categoría hoja (si hay pocos, se completa con categorías hermanas).
- Recuerda en el navegador la vista, los productos por página y las columnas ocultas.

## Indicadores

Reglas en `config/indicadores.json` (cámbialas ahí y regenera los datos):

| Indicador | Valores | Regla |
|---|---|---|
| Descripción | buena / regular / mala | Buena: investigación verificada con confianza alta, 800 caracteres o más y 3 secciones reconocidas o más. Regular: verificada con 500 caracteres o más. Mala: sin verificar o más corta. |
| Fotos | buena / regular / mala | Buena: 2 fotos o más y la principal con el producto de 800 px o más, sin fondo gris. Regular: alguna foto con el producto de 500 px o más. Mala: sin fotos o todas más chicas. |
| Precios | completos / incompletos | Completos cuando se conocen el precio de venta al público, el precio de la publicación más vendida en Mercado Libre y el precio Meli calculado (con comisión y costo de empaque y logística). |

Mientras no se corra `scripts/meli_precios.py` con credenciales de la API, todos los productos salen con precios incompletos (falta el precio del mejor vendedor).

## Regenerar los datos

Después de integrar una sesión, cambiar fotos o precios:

```bash
python scripts/build_visor.py
```

- Precios y existencias: `insumos/precios_existencias.csv` si existe; si no, las hojas Precios y Layout del layout versionado `layouts/mercadolibre/layout_mercadolibre.xlsx`.
- Competencia: `insumos/competencia_meli.csv` si existe (salida de `scripts/meli_precios.py`).
- La detección de fondo gris (`scripts/revisar_fotos.py`) se guarda en caché en `trabajo/cache_fondo_fotos.json`; la primera corrida tarda más.
- `--base-imagenes` cambia la ruta de las fotos vista desde `visor/index.html` (por omisión `../products`); sirve, por ejemplo, para apuntar a `https://raw.githubusercontent.com/zublimemx/marketplaces-product-images/main/products` si se publica el visor fuera del repositorio.

Formato de `visor/data/productos.js` en `docs/CONTRATOS.md` §8.
