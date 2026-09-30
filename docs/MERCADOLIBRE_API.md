# Precios de competencia con la API de Mercado Libre

Objetivo: llenar en el layout "Precio Meli promedio otros vendedores" y "Precio mejor vendedor" (reglas en `docs/REGLAS_NEGOCIO.md`). Script: `scripts/meli_precios.py`. Salida: `insumos/competencia_meli.csv` (no versionada), que `scripts/build_mercadolibre.py` lee sola.

> **Estado:** el script se escribió sin credenciales, así que no se ha probado contra la API real. Antes de la corrida completa, prueba con `--muestra 3 --limite 3`, revisa las respuestas guardadas en `trabajo/meli_muestras/` y ajusta los nombres de campos si difieren.

## Requisitos

1. Una aplicación en [developers.mercadolibre.com.mx](https://developers.mercadolibre.com.mx) ligada a la cuenta de vendedor, con permisos de lectura.
2. Un `refresh_token` obtenido con el flujo OAuth (autorización del vendedor → `code` → `POST /oauth/token` con `grant_type=authorization_code`). Mercado Libre devuelve un `refresh_token` nuevo en cada renovación; el script guarda el último en `insumos/ml_token.json`.
3. Variables en `.env` (ver `.env.example`): `ML_CLIENT_ID`, `ML_CLIENT_SECRET`, `ML_REFRESH_TOKEN` (o `ML_ACCESS_TOKEN` temporal) y opcionalmente `ML_SELLER_ID`.
4. Salida de red a `api.mercadolibre.com` (en Codex, habilitar acceso a internet en el entorno o en el sandbox; en Claude, que el administrador lo permita).

Sin token, la API responde 403 incluso a búsquedas públicas (comprobado el 2026-09-29). Los listados web (`listado.mercadolibre.com.mx`) redirigen a verificación de cuenta: **no** se deben raspar.

## Flujo por producto

1. `GET /products/search?status=active&site_id=MLM&product_identifier=<GTIN>` → producto de catálogo. Si no aparece, usa `marketplaces.mercadolibre.catalogo_id` de `product.json` (la investigación dejó IDs en varios productos).
2. Con catálogo:
   - `GET /products/<id>` → `buy_box_winner` (precio y publicación ganadora) y `pictures` (fotos de catálogo).
   - `GET /products/<id>/items` → publicaciones que compiten (precio y vendedor).
3. Sin catálogo: `GET /sites/MLM/search?q=<GTIN>`.
4. Se excluyen las publicaciones del propio vendedor y las usadas. Promedio, mínimo y máximo de precio de las demás.
5. "Mejor vendedor" (publicación con más ventas):
   - si `GET /items?ids=…&attributes=id,price,sold_quantity,seller_id` devuelve `sold_quantity`, la de mayor valor (`mayor_sold_quantity`);
   - si no, el ganador de la compra del catálogo (`ganador_catalogo`), que es la publicación que Mercado Libre muestra primero y la que concentra las ventas del catálogo;
   - si no hay catálogo, la primera por relevancia de la búsqueda (`busqueda_relevancia`).
   La columna `metodo_mejor_vendedor` del CSV dice cuál se usó. Si Mercado Libre ya no expone `sold_quantity` de otros vendedores, `ganador_catalogo` es el criterio acordado como propuesta (ver `PENDIENTES.md`).

## Opciones útiles

- `--guardar-catalogo`: guarda en `product.json` el ID de catálogo encontrado (dato público, sí se versiona).
- `--fotos-catalogo`: para productos sin fotos o con todas sus fotos de baja resolución, descarga las fotos del catálogo con `scripts/imagenes.py` (origen `catalogo_ml`). Revisa después con `scripts/revisar_fotos.py` y a la vista.
- `--gtin …` y `--limite N` para corridas parciales; el CSV se va acumulando y se reescribe cada 25 productos.

## Contrato de `insumos/competencia_meli.csv`

`gtin, producto_catalogo, publicaciones_otros, precio_promedio_otros, precio_min_otros, precio_max_otros, precio_mejor_vendedor, item_mejor_vendedor, metodo_mejor_vendedor, fecha, nota`

Después de correrlo:

```bash
python scripts/build_mercadolibre.py --precios insumos/precios_existencias.csv --salida trabajo/layout_mercadolibre.xlsx
```

El layout toma el CSV automáticamente (`--competencia` para otra ruta) y la fórmula de "Precio Meli Final" aplica la regla del promedio − $1.
