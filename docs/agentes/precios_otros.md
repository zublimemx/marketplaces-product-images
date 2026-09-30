# Instrucciones para el agente de precios en otros marketplaces

Todas las rutas son relativas a la raíz del repositorio. `NN` es el número de sesión con dos dígitos y `XX` el número de lote.

Trabajas un lote de productos de una farmacia mexicana. Para cada producto busca su **precio de venta al público actual** en tiendas en línea de México, para compararlo con el nuestro. No modifiques el repositorio: escribe solo tu archivo de resultado y deja temporales en tu carpeta de trabajo con prefijo `precios_XX_`.

## Entrada
`trabajo/sesion_NN/lotes/precios_XX.json`: `orden`, `gtin`, `titulo`, `nombre_sistema`, `presentacion`, `contenido`, `fuentes` (páginas ya usadas en la investigación; muchas son fichas de farmacias con precio).

## Dónde buscar
- Tiendas válidas: Farmacias San Pablo, Farmacias del Ahorro, Farmacias Guadalajara, Farmacias Benavides, Farmacias Similares, Farmacias YZA, Walmart, Bodega Aurrera, Soriana, Chedraui, HEB, La Comer, Sanborns, Farmalisto, Costco, Sam's Club, sitios oficiales de la marca con tienda.
- **No** consultes Mercado Libre (su precio ya viene de su API) ni Amazon (no se raspa).
- Primero las `fuentes` del producto que sean de tiendas: ábrelas con WebFetch (o `curl`) y lee el precio.
- Luego el buscador **del propio sitio** por GTIN o nombre, por ejemplo `https://www.farmaciasanpablo.com.mx/search/?text=<GTIN>`, `https://www.fahorro.com/catalogsearch/result/?q=<GTIN>`, `https://www.farmaciasguadalajara.com/…`. No uses buscadores generales vía fetch/curl.
- Búsqueda web (WebSearch): **máximo 1 por producto**, solo si lo anterior no dio 2 precios. Si responde que se agotó el presupuesto, deja de buscar.
- Si una página da 403/404/429 o pide verificación, pasa a otra; no insistas.
- **Nunca** hagas barridos de URLs adivinadas ni cientos de peticiones seguidas a una tienda (en la sesión 9 eso hizo que Farmacias del Ahorro bloqueara el acceso). Una o dos consultas por producto y tienda.

### Accesos que funcionaron (sesión 9, 30 sep 2026)
- **Farmacias YZA:** `https://www.yza.mx/x/MXYZ_<GTIN>.html`; el precio está en el JSON-LD. Casi todo sale «agotado» porque no hay sucursal elegida: el precio de ficha sí vale (anótalo en `nota`).
- **Farmacias del Ahorro:** GraphQL `https://www.fahorro.com/graphql` con `products(search: "<GTIN>")` (precio final y regular). Su buscador HTML se llena con JavaScript.
- **Farmacias Benavides:** `https://www.benavides.com.mx/catalogsearch/result/?q=<GTIN>` redirige a la ficha; también GraphQL en `/graphql` (por nombre).
- **Chedraui:** `https://www.chedraui.com.mx/api/catalog_system/pub/products/search?ft=<nombre>` (por nombre; filtra por EAN).
- Bloqueados: Farmacias San Pablo (403), Guadalajara, Walmart, Bodega Aurrera, Soriana, Sam's, La Comer, HEB (casi siempre) y Farmalisto (captcha).

## Qué cuenta como precio válido
- Mismo producto y **misma presentación** (contenido, piezas, concentración, etapa). Si la tienda vende otra presentación, no lo anotes.
- Precio en pesos con IVA incluido, el que paga cualquier cliente. Si hay precio de oferta y precio normal, anota el de oferta en `precio` y el normal en `precio_lista`.
- Objetivo: 2 o 3 tiendas por producto. Si no encuentras ninguno, deja `precios` vacío y explica en `notas`.

## Salida
`trabajo/sesion_NN/resultados/precios_XX.json`: arreglo en el mismo orden del lote, un objeto por producto:

```json
{"gtin": "…", "precios": [{"marketplace": "Farmacias San Pablo", "precio": 189.5, "precio_lista": 215.0, "url": "https://…", "nota": ""}], "notas": ""}
```

`marketplace` con el nombre comercial de la tienda (usa siempre el mismo: «Farmacias San Pablo», «Farmacias del Ahorro», «Farmacias Guadalajara», «Farmacias Benavides», «Walmart», «Soriana», «Chedraui», «HEB», «Farmalisto», etc.). `precio_lista` es opcional. Valida el JSON antes de terminar y responde en pocas líneas: productos con precio, precios encontrados por tienda y búsquedas usadas.
