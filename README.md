# marketplaces-product-images

Base de datos de productos para publicar en marketplaces (Mercado Libre, Amazon, Shopify y Odoo). Guarda imágenes, descripciones y fichas técnicas; los precios y existencias no se guardan aquí porque cambian a diario y este repositorio se hace público durante las importaciones.

## Estructura

```
products/<GTIN>/product.json     Ficha del producto (título, descripción, ficha técnica, categorías por marketplace, fuentes)
products/<GTIN>/images/          Fotos del producto: <GTIN>_1.jpg, <GTIN>_2.jpg, ...
config/mercadolibre.json         Valores fijos de publicación y reglas de precio de Mercado Libre
reference/mercadolibre/          Árbol de categorías hoja publicables de Mercado Libre México
scripts/build_mercadolibre.py    Genera el layout de importación de Mercado Libre
scripts/imagenes.py              Descarga, valida (mínimo 500 px), recorta y guarda fotos; las registra en product.json
scripts/pagina_imagenes.py       Lista las fotos de producto que aparecen en una página web
scripts/progreso.py              Calcula el avance y escribe PROGRESO.md
PROGRESO.md                      Avance de fichas y fotos por sesión
schema/product.md                Descripción de cada campo de product.json
```

## URL de una imagen

`https://raw.githubusercontent.com/zublimemx/marketplaces-product-images/main/products/<GTIN>/images/<GTIN>_1.jpg`

Solo funciona mientras el repositorio es público.

## Generar el layout de Mercado Libre

```
python scripts/build_mercadolibre.py --precios precios_existencias.csv --salida layout_mercadolibre.xlsx
```

`precios_existencias.csv` lleva las columnas `gtin,precio,stock,linea,nombre,nota_cruce` (precio con impuestos incluidos) y se genera desde el ERP; no se versiona.

## Estado de investigación

`investigacion.estado` en cada producto:

- `verificado`: producto confirmado en internet (por código de barras o por nombre y presentación).
- `sin_verificar`: datos deducidos del nombre; hay que investigarlo antes de publicar.
- `pendiente`: aún sin investigar.
