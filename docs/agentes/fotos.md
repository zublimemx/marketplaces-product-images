# Instrucciones para el agente de fotos (productos ya verificados)

Todas las rutas son relativas a la raíz del repositorio. `NN` es el número de sesión con dos dígitos y `XX` el número de lote.

Trabajas un lote de productos de una farmacia mexicana que ya tienen su ficha verificada. Tu tarea es conseguir sus fotos y completar la ficha técnica. **No hagas búsquedas web** (el presupuesto de búsquedas es para otros lotes). Abre páginas concretas con WebFetch (Claude) o `curl` desde la terminal; no uses buscadores generales (Google, Bing, DuckDuckGo…). Si tu agente no puede ver imágenes, usa `python scripts/revisar_fotos.py --gtin <gtin>` y anota en `notas_imagenes` que la revisión visual quedó pendiente.

## Entrada
Lote JSON en `trabajo/sesion_NN/lotes/img_XX.json` con `id`, `gtin`, `nombre`, `linea`, `estado`. La ficha de cada producto está en `products/<gtin>/product.json` (usa `titulo`, `ficha`, `url_oficial` y `fuentes`).

## Fotos
Objetivo: de 1 a 4 fotos correctas por producto, la primera de frente al empaque. Orden de preferencia del origen: `fabricante` (sitio oficial de la marca), `catalogo_ml` (ficha de catálogo de Mercado Libre, solo si pudiste abrirla), `tienda` (foto de producto de una farmacia o tienda). Páginas a probar, en orden: `url_oficial`; las URLs de `fuentes`; y si ninguna sirve, fichas de farmacias mexicanas cuya URL puedas construir sin buscador (por ejemplo `https://www.farmaciasmedina.com/detalleProducto/x/<gtin>`). Si una página da 403/404/429, pasa a otra; no insistas.

1. Candidatas: `python scripts/pagina_imagenes.py "<URL de la página>" <gtin> <palabra clave>`.
2. Prefiere fotos de 800 px o más por lado (el script muestra el tamaño original) y, si hay otra fuente con mejor resolución, úsala. Usa la mayor resolución: quita parámetros de redimensión (`?width=265&height=265…`, `_small`, `/thumb/`, `-150x150`) si la original existe.
3. Guarda: `CONTACT_DIR=trabajo/contactos python scripts/imagenes.py fetch <gtin> --origen <fabricante|catalogo_ml|tienda> --pagina "<URL de la página>" "<URL imagen 1>" "<URL imagen 2>"`.
4. Revisa visualmente la hoja de contacto (en Claude, con la herramienta Read; en otro agente, con su visor de imágenes) que imprime (`trabajo/contactos/<gtin>.jpg`). Borra toda foto que no sea exactamente el producto y presentación, que tenga logotipos o marcas de agua de la tienda, texto promocional o precios, o que sea un ícono o "sin imagen": `python scripts/imagenes.py rm <gtin> <archivo>`.
No edites a mano product.json ni la carpeta images; usa solo el script.

## Ficha técnica
Con las mismas páginas, completa los atributos que falten en `ficha` (omite los que no apliquen; no inventes): `marca`, `fabricante`, `linea`, `variante`, `presentacion`, `contenido_neto`, `unidad_contenido`, `unidades_por_envase`, `principio_activo`, `concentracion`, `via_administracion`, `edad_etapa`, `talla`, `sabor_aroma`, `genero`, `tipo_piel_cabello`, `registro_sanitario` (solo si lo viste), `otros` ("Atributo: valor; …").

## Salida
Escribe `trabajo/sesion_NN/resultados/img_XX.json`: arreglo JSON con un objeto por producto en el mismo orden, con `id`, `gtin`, `ficha` (la ficha completa, incluyendo lo que ya tenía), `fuentes_nuevas` (URLs que abriste y usaste, o []), `notas_imagenes` (qué fotos quedaron y de dónde, o por qué no hay).

Al terminar, responde solo con una línea: `img_XX: N productos, con fotos F, sin fotos S`.
