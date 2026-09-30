# Competencia, fotos y descripciones con la API de Mercado Libre

Objetivo: llenar "Precio mejor vendedor" (define el Precio Meli Final) y "Precio Meli promedio otros vendedores" (referencia) con la API oficial (reglas en `docs/REGLAS_NEGOCIO.md`), y usar el catálogo de Mercado Libre para completar fotos y descripciones malas o cortas y confirmar el GTIN. Primera corrida completa: 29 sep 2026 (1,163 productos).

| Paso | Script | Salida |
|---|---|---|
| 1. Token | `scripts/meli_auth.py` | `insumos/ml_token.json` (ignorado por git) |
| 2. Precios de competencia y datos de catálogo | `scripts/meli_precios.py` | `data/competencia_meli.csv` (versionado) y `trabajo/meli/<GTIN>.json` (crudo, no versionado) |
| 3. Fotos de catálogo | `scripts/meli_fotos.py` | fotos `catalogo_ml` en `products/<GTIN>/images/` |
| 4. Revisión con subagentes | `scripts/preparar_revision_ml.py` + `docs/agentes/revision_ml.md` | `trabajo/revision_fotos_ml/`, `trabajo/descripciones_ml/` |
| 5. Aplicar la revisión | `scripts/aplicar_revision_ml.py` | `product.json`, fotos, `data/catalogo_ml_rechazados.csv` |
| 6. Regenerar | `envios.py`, `build_mercadolibre.py` (recalculado), `build_visor.py`, `validar.py` | layout y visor |

## Requisitos

1. Una aplicación en [developers.mercadolibre.com.mx](https://developers.mercadolibre.com.mx) ligada a la cuenta de vendedor (la del dueño ya existe; su ID está en `.env`).
2. Token: la aplicación **no** acepta `client_credentials` (responde `unsupported_grant_type`) y un access token dura 6 horas. Dos caminos:
   - El dueño genera un token de prueba en el portal de desarrolladores y lo entrega; se guarda en `.env` como `ML_ACCESS_TOKEN`. Sirve para una corrida, no se renueva.
   - Flujo de autorización (recomendado para renovar solo): el dueño abre `https://auth.mercadolibre.com.mx/authorization?response_type=code&client_id=<ML_CLIENT_ID>&redirect_uri=<REDIRECT_URI>`, autoriza y entrega el `code=TG-…` (vence en minutos); `python scripts/meli_auth.py --code TG-… --redirect-uri <REDIRECT_URI>` guarda access y refresh token en `insumos/ml_token.json`. `scripts/meli_precios.py` lo renueva solo (permiso `offline_access`).
3. Variables en `.env` (ver `.env.example`): `ML_CLIENT_ID`, `ML_CLIENT_SECRET`, `ML_ACCESS_TOKEN` o `ML_REFRESH_TOKEN`, y opcionalmente `ML_SELLER_ID` (si falta, se toma de `/users/me`). **Nunca** en git: antes de cada push, `git log -p | grep -cE 'APP_USR-[0-9]'` debe dar 0 (y lo mismo con el secreto de `.env`).
4. Salida de red a `api.mercadolibre.com` y `http2.mlstatic.com` (fotos).

No se raspan los listados web (`listado.mercadolibre.com.mx` redirige a verificación de cuenta).

## Qué permite la API (probado el 29 sep 2026 con la cuenta del vendedor)

| Endpoint | Resultado | Uso |
|---|---|---|
| `GET /products/search?status=active&site_id=MLM&product_identifier=<GTIN>` | Sí | Producto de catálogo por GTIN |
| `GET /products/<id>` | Sí | Nombre, atributos, fotos (`pictures`), `main_features`, `short_description` |
| `GET /products/<id>/items` | Sí | Publicaciones que compiten: precio, vendedor, condición, envío; **sin** `sold_quantity` |
| `GET /users/<id>` | Sí | `seller_reputation.transactions.total` (ventas históricas del vendedor) |
| `GET /items/<id>/description` | Sí | Descripción de otra publicación (muchas vienen vacías porque usan imágenes) |
| `GET /items/<id>` e `/items?ids=` de otros vendedores | **403** | No hay ventas por publicación ni sus fotos |
| `GET /sites/MLM/search` | **403** | No hay búsqueda por texto |

Consecuencias: las fotos de "otros vendedores" solo se pueden tomar del **producto de catálogo** (son las que Mercado Libre muestra en la ficha del catálogo); la "publicación más vendida" se aproxima con el vendedor con más ventas históricas.

## Reglas

- **Producto de catálogo:** el primero de `/products/search` por GTIN que no esté rechazado; si no hay, el `catalogo_id` de `product.json`. `--guardar-catalogo` escribe en `product.json` el encontrado por GTIN.
- **Publicaciones que cuentan:** nuevas, con precio, de vendedores distintos al propio.
- **Promedio de otros vendedores:** media sin atípicas (más del doble de la mediana; casi siempre paquetes de varias piezas). También se guardan mediana, mínimo, máximo y cuántas atípicas hubo.
- **Mejor vendedor** (`metodo_mejor_vendedor = vendedor_con_mas_ventas`): entre las publicaciones no atípicas, la del vendedor con más ventas históricas; en empate, la más barata.
- **Catálogos rechazados** (`data/catalogo_ml_rechazados.csv`): cuando la revisión encuentra que el GTIN apunta en Mercado Libre a otro producto (`otro_producto`) o a otra presentación (`otra_presentacion`), el catálogo no se usa ni para precios ni para fotos, se quita `catalogo_id` de `product.json` y el visor marca el pendiente «El GTIN apunta a otro producto en Mercado Libre». `meli_precios.py` lo respeta en corridas futuras.

## Comandos

```bash
python scripts/meli_precios.py --gtin 7501123013302 7501058623300      # prueba con 2 productos
python scripts/meli_precios.py --guardar-catalogo --descripciones --hilos 4   # corrida completa (≈20 min)
python scripts/meli_precios.py --solo-csv                               # recalcula el CSV desde trabajo/meli/ sin API
python scripts/meli_fotos.py [--seco]                                   # fotos de catálogo para fotos «mala» o «regular»
python scripts/preparar_revision_ml.py fotos                            # hojas de contacto para revisar a la vista
python scripts/preparar_revision_ml.py descripciones                    # lotes de descripciones y confirmación de GTIN
# … subagentes con docs/agentes/revision_ml.md …
python scripts/aplicar_revision_ml.py [--seco]
python scripts/meli_precios.py --solo-csv
```

Luego regenerar (`docs/PROCEDIMIENTO_SESION.md` §4): `scripts/envios.py`, `scripts/build_mercadolibre.py` (y recalcular), `scripts/build_visor.py`, `scripts/validar.py` y `scripts/revisar_fotos.py`.

`--forzar` vuelve a consultar productos que ya tienen `trabajo/meli/<GTIN>.json`. Como `trabajo/` no se versiona, en una sesión nueva la corrida completa se repite desde cero.

## `scripts/meli_fotos.py`

Para los productos con fotos «mala» o «regular» (reglas de `config/indicadores.json`) y producto de catálogo:

1. Descarga hasta 4 fotos del catálogo de 500 px o más con `scripts/imagenes.py fetch --origen catalogo_ml` (normaliza a fondo blanco y rechaza duplicados exactos).
2. Quita duplicados visuales (hash de diferencias ≤ 6), conservando la de más resolución útil.
3. Si todas las fotos anteriores eran chicas y hay de catálogo buenas, borra las chicas.
4. Si la principal era chica o con posible fondo gris, pone como principal la primera de catálogo buena.

Las fotos de catálogo suelen traer bandas, sellos o infografías añadidas, y a veces son de otra presentación o de otro producto (cuando el GTIN apunta mal): **siempre** se revisan a la vista después (paso 4).

## Contrato de `data/competencia_meli.csv`

`gtin, producto_catalogo, nombre_catalogo, publicaciones_otros, precio_promedio_otros, precio_mediana_otros, precio_min_otros, precio_max_otros, publicaciones_atipicas, precio_mejor_vendedor, item_mejor_vendedor, vendedor_mejor, ventas_vendedor_mejor, metodo_mejor_vendedor, fecha, nota`

`nota` explica las filas sin precios: `sin producto de catálogo para el GTIN`, `sin publicaciones de otros vendedores` o `catálogo rechazado (…): <motivo>`. `build_mercadolibre.py` y `build_visor.py` solo leen `precio_promedio_otros`, `precio_mejor_vendedor` y `metodo_mejor_vendedor`.

## Resultado de la corrida del 29 sep 2026

- 1,080 productos con producto de catálogo por GTIN; 83 sin catálogo; 44 con catálogo pero sin otros vendedores.
- 1,024 con precio del mejor vendedor (tras rechazar 12 catálogos). 638 se publican a mejor vendedor − $1 y 525 al Precio Meli calculado (386 porque el calculado queda arriba del mejor vendedor).
- Fotos: el indicador «buena» pasó de 429 a 898 productos (de 1,941 a 2,545 fotos) después de quitar 420 fotos con bandas, infografías, ambiente, otra presentación u otro producto.
- 47 descripciones reescritas y 83 productos confirmados por GTIN (confianza alta).
