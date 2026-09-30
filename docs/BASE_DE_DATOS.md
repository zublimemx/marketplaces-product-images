# Base de datos del catálogo (`data/catalogo.db`)

Archivo SQLite versionado con **todos los datos** del catálogo en tablas: fichas, fotos (su registro; los archivos siguen en `products/<GTIN>/images/`), precios calculados, competencia de Mercado Libre, precios en otros marketplaces, comparación de precios, envíos, ajustes, descartes, indicadores y pendientes. Es un solo archivo: se copia, se versiona en GitHub y se abre con cualquier cliente SQLite.

## Cómo abrirla

- **DB Browser for SQLite** (gratis, Windows/Mac): Abrir base de datos → `data/catalogo.db` → pestaña «Hojear datos» o «Ejecutar SQL».
- **DBeaver**, **TablePlus**, **DataGrip**: conexión SQLite al archivo.
- **Excel**: con el controlador ODBC de SQLite, o exportando una tabla a CSV desde DB Browser.
- **Python**: `sqlite3.connect("data/catalogo.db")`; **terminal**: `sqlite3 data/catalogo.db`.

## Cómo se mantiene

La base se **genera** desde los archivos del repositorio, que siguen siendo la fuente de verdad (así cada cambio queda revisable en el PR y las IA siguen usando los mismos scripts):

| Dato | Fuente | Se cambia con |
|---|---|---|
| Ficha, descripción, investigación, fotos | `products/<GTIN>/product.json` | scripts de investigación y fotos (`AGENTS.md`) |
| Descartes de Meli | `product.json` → `marketplaces.mercadolibre.descartado` | visor («Descartar de Meli») + `scripts/descartar.py` |
| Competencia de Mercado Libre | `data/competencia_meli.csv` | `scripts/meli_precios.py` |
| Precios en otros marketplaces | `data/precios_otros_marketplaces.csv` | `scripts/otros_marketplaces.py` (subagentes o Excel del visor) |
| Ajustes de precio | `data/ajustes_precios.json` | visor + `scripts/ajustes_precios.py` |
| Envíos, catálogos rechazados | `data/envios.csv`, `data/catalogo_ml_rechazados.csv` | `scripts/envios.py`, revisión de catálogo |
| Precios calculados, indicadores, pendientes | `visor/data/productos.js` | `scripts/build_visor.py` |

Después de cualquier cambio: `python scripts/build_visor.py && python scripts/build_db.py`. El CI corre `python scripts/build_db.py --verificar` y falla si la base quedó atrasada. No edites la base a mano: el siguiente `build_db.py` la reemplaza.

## Tablas

La tabla `diccionario` describe cada tabla y columna (`SELECT * FROM diccionario`). Resumen:

| Tabla | Llave | Contenido |
|---|---|---|
| `productos` | `gtin` | Datos generales, investigación, indicadores, **precio_otros_marketplaces** (el más bajo encontrado) y **otros_marketplaces** (tienda de ese precio) |
| `fichas` | `gtin` | Ficha técnica, una columna por atributo |
| `imagenes` | `gtin`, `posicion` | Fotos en orden (1 = principal), ruta y URL de GitHub, origen, resolución |
| `fuentes` | `gtin`, `posicion` | Páginas consultadas |
| `mercadolibre` | `gtin` | Categoría, catálogo, descarte, catálogo rechazado |
| `precios_meli` | `gtin` | Parámetros y Precio Meli final (mismas reglas que el layout) |
| `competencia_meli` | `gtin` | Promedio, mediana, mínimo, máximo y mejor vendedor en Meli |
| `precios_otros_marketplaces` | `gtin`, `marketplace` | Precio de venta en cada tienda en línea, precio de lista, URL, fecha, nota, quién lo capturó |
| `comparacion_precios` | `gtin` | Quién tiene el precio más alto y más bajo, nuestra posición con el Precio Meli final y con el precio de tienda |
| `envios`, `ajustes_precios`, `catalogos_rechazados`, `pendientes` | | Lo que dice su nombre |
| `v_productos`, `v_comparacion_precios` | | Vistas listas para consultar |

## Consultas útiles

```sql
-- Productos donde somos el más caro en Meli, con la diferencia contra el más barato
SELECT titulo, nuestro_precio_meli, precio_mas_bajo, quien_mas_bajo, diferencia_vs_mas_bajo
FROM v_comparacion_precios WHERE posicion_meli = 'mas_caro' AND descartado = 0
ORDER BY diferencia_vs_mas_bajo DESC;

-- Precio promedio por tienda de los productos que también vendemos
SELECT marketplace, COUNT(*) productos, ROUND(AVG(precio), 2) promedio FROM precios_otros_marketplaces GROUP BY 1 ORDER BY 2 DESC;

-- Productos que se publican, sin precio en otros marketplaces, por prioridad de ventas
SELECT p.orden, p.gtin, p.titulo FROM productos p JOIN mercadolibre m USING (gtin)
WHERE m.descartado = 0 AND p.num_otros_marketplaces = 0 ORDER BY p.orden;

-- Fotos de un producto con su URL pública
SELECT posicion, url_github, origen, lado_util FROM imagenes WHERE gtin = '7501123013302' ORDER BY posicion;
```
