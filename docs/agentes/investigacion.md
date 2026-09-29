# Instrucciones para el agente de investigación (fichas + fotos)

Todas las rutas son relativas a la raíz del repositorio. `NN` es el número de sesión con dos dígitos y `XX` el número de lote.

Trabajas un lote de productos de una farmacia mexicana (líneas "Farma" = farmacia y "Mark" = cuidado personal/perfumería/bebé). Para cada producto investiga en internet, obtén sus datos de publicación y descarga sus fotos al repositorio. Todo el texto de salida va en español de México.

## LÍMITE ESTRICTO DE BÚSQUEDAS
La sesión tiene un presupuesto compartido de búsquedas web. Tienes **exactamente 1 llamada a WebSearch por producto** de tu lote, nunca más, y nunca reintentes una búsqueda. Si WebSearch responde que se agotó el presupuesto, deja de buscar: termina los productos restantes solo con lo que ya tengas (confianza "baja") y dilo en tu respuesta. Para todo lo demás usa WebFetch o `curl` en Bash (abrir páginas no consume búsquedas). No uses WebFetch ni curl sobre buscadores generales (Google, Bing, DuckDuckGo, etc.).

## Entrada
Lote JSON en `trabajo/sesion_NN/lotes/inv_XX.json` con `id`, `gtin`, `nombre` (nombre abreviado del sistema; puede traer lote o caducidad al final, p. ej. "JUNIO 27", "FEB27"; ignóralos), `linea`, `estado`. Si el producto ya tiene un borrador sin verificar en `products/<gtin>/product.json`, úsalo solo como pista.

## Cómo investigar cada producto
1. Una sola búsqueda con WebSearch que combine el GTIN y el nombre descifrado, p. ej. `7501943441804 Huggies Supreme etapa 5 36 pañales`. Si el GTIN tiene 12 dígitos, ponlo con un 0 al inicio. Abreviaturas comunes: "CRA" crema, "SH" shampoo, "DESOD" desodorante, "JBE" jarabe, "TAB/TABS" tabletas, "CAPS" cápsulas, "AMP" ampolletas, "SUSP" suspensión, "GTS" gotas, "C30" caja con 30, "SPY" spray, "ENJ BUC" enjuague bucal, "CEP DENT" cepillo dental, "TAS" toallitas, "HU" Huggies, "E5" etapa 5.
2. De los resultados, abre con WebFetch (o curl) de 1 a 3 páginas: primero la del fabricante o marca si aparece; luego la mejor ficha de farmacia o tienda mexicana (Farmacias del Ahorro, San Pablo, Guadalajara, Benavides, Medina, Farmalisto, Walmart, Soriana, Chedraui, HEB, Sanborns…); para medicamentos, PLM (medicamentosplm.com) es buena fuente de principio activo, indicaciones y presentación. Si una página devuelve 403/404/429, pasa a otra; no insistas. Mercado Libre y Amazon suelen bloquear el acceso: no insistas con ellos.
3. Confirma que la presentación coincide (contenido, piezas, concentración). Si solo encuentras otra presentación, úsala para la descripción general, respeta la presentación del nombre del sistema y baja la confianza.
4. Si en resultados o páginas aparece una URL de catálogo de Mercado Libre `mercadolibre.com.mx/.../p/MLM12345678` que corresponde exactamente al producto, anota `MLM12345678` en `catalogo_ml`.

## Fotos (obligatorio intentarlo en cada producto)
Objetivo: de 1 a 4 fotos correctas por producto, la primera de frente al empaque. Orden de preferencia del origen:
- `fabricante`: sitio oficial de la marca o fabricante.
- `catalogo_ml`: fotos de la ficha de catálogo de Mercado Libre (solo si pudiste abrirla).
- `tienda`: foto de producto de una farmacia o tienda (normalmente es la foto oficial que distribuye el fabricante).

Pasos:
1. Obtén URLs de imágenes de la página con: `python scripts/pagina_imagenes.py "<URL de la página>" <gtin> <palabra clave>` (lista candidatas; las de mayor puntaje primero). También puedes pedirlas con WebFetch.
2. Prefiere fotos de 800 px o más por lado (el script muestra el tamaño original de cada foto guardada) y, si una foto sale chica y hay otra fuente con mejor resolución, usa la mejor. Usa la versión de mayor resolución: quita parámetros de redimensión de la URL (p. ej. `?width=265&height=265…`, `_small`, `/thumb/`, `-150x150`) si la imagen original existe.
3. Descarga y guarda con: `CONTACT_DIR=trabajo/contactos python scripts/imagenes.py fetch <gtin> --origen <fabricante|catalogo_ml|tienda> --pagina "<URL de la página>" "<URL imagen 1>" "<URL imagen 2>"`. El script convierte a JPG con fondo blanco, rechaza imágenes de menos de 500 px y duplicadas, y registra cada foto en product.json.
4. Revisa visualmente la hoja de contacto que imprime (`HOJA_DE_CONTACTO trabajo/contactos/<gtin>.jpg`) (en Claude, con la herramienta Read; en otro agente, con su visor de imágenes). Borra toda foto que no sea exactamente el producto y presentación (otra etapa, otro tamaño, otro sabor), que tenga logotipos o marcas de agua de la tienda, texto promocional, precios, o que sea un ícono o un "sin imagen": `python scripts/imagenes.py rm <gtin> <archivo>`.
5. Si no consigues ninguna foto válida, anótalo en `notas_imagenes`.
No edites a mano product.json ni la carpeta images; usa solo el script.

## Qué devolver por producto
- `titulo`: máximo 60 caracteres. Producto + Marca + variante/línea + dato clave (concentración, contenido o piezas). Ej.: "Pañales Huggies Supreme Unisex Etapa 5 36 Piezas", "Aspirina Protect 100 mg 28 Tabletas". Mayúscula inicial en palabras importantes; unidades en minúscula (mg, ml, g). Sin lote, caducidad, promociones, "envío gratis", "original", "nuevo", emojis ni signos de exclamación.
- `descripcion`: texto plano original, lo más completo que permitan las fuentes, de 800 a 2,000 caracteres (mínimo 500 solo si de verdad no hay más información). Redáctalo tú; no copies párrafos literales. Secciones, cada una con su encabezado en una línea propia seguido de dos puntos, omitiendo las que no tengan datos confiables: "Descripción:", "Beneficios:" (o "Características:"), "Ingredientes:" (o "Composición:" / "Fórmula:"), "Modo de uso:", "Presentación:", "Advertencias:". Separa secciones con una línea en blanco (`\n\n`); dentro de una sección puedes usar renglones que empiecen con "- ". Para medicamentos, "Advertencias:" termina con: "Lea las instrucciones del empaque. Consulte a su médico. No se deje al alcance de los niños." Prohibido: datos de contacto, enlaces, precios, nombres de tiendas o marketplaces, lote o caducidad, HTML, emojis, afirmaciones de salud que no estén en la etiqueta o ficha oficial.
- `categoria_id` y `categoria_ruta`: categoría hoja publicable de `reference/mercadolibre/categorias_relevantes.csv` (columnas ID, Ruta completa, Dominio de catálogo, Items en categoría); búscala con Grep. Si nada encaja, busca en `reference/mercadolibre/categorias_mlm_hojas_publicables.csv`. Reglas: todos los medicamentos van como venta libre en `Salud y Equipamiento Médico > Cuidado de la Salud > Farmacia > Medicamentos de Venta Libre > ...` según grupo terapéutico ("Otros Medicamentos" solo si ninguna encaja); vitaminas y suplementos `MLM438195`; fórmulas lácteas infantiles `MLM189058`; pañales de bebé `MLM178488`; pañales de adulto `MLM194512`; entre dos categorías equivalentes elige la de más "Items en categoría". Copia ID y ruta exactos del CSV.
- `ficha`: objeto con los atributos que apliquen (omite los que no; no inventes). Llénala lo más completa posible con datos de las fuentes: `marca`, `fabricante`, `linea`, `variante`, `presentacion`, `contenido_neto` (número), `unidad_contenido`, `unidades_por_envase`, `principio_activo`, `concentracion`, `via_administracion`, `edad_etapa`, `talla`, `sabor_aroma`, `genero`, `tipo_piel_cabello`, `registro_sanitario` (solo si lo viste), `otros` ("Atributo: valor; Atributo: valor", p. ej. dimensiones o peso del empaque, libre de gluten, formato de venta).
- `receta_mx`: para medicamentos, si en México su principio activo normalmente requiere receta: "Sí", "No" o "Revisar"; si no es medicamento: "No aplica". Si es "Sí", `categoria_rx_sugerida` = ID equivalente de `reference/mercadolibre/categorias_con_receta.csv`; si no, "".
- `catalogo_ml`, `url_oficial` (página del fabricante o ""), `fuentes` (1 a 3 URLs usadas), `encontrado_por` ("gtin", "nombre" o "no_encontrado"), `confianza` ("alta": GTIN confirmado y presentación igual; "media": identificado por nombre o presentación inferida; "baja": no confirmado), `notas` (dudas breves o ""), `notas_imagenes` (qué fotos quedaron y de dónde, o por qué no hay).

Si no encuentras el producto, llena lo que se deduce con seguridad del nombre, descripción breve y neutral, `confianza` = "baja", y explícalo en `notas`.

## Salida
Escribe `trabajo/sesion_NN/resultados/inv_XX.json` (mismo número de lote): arreglo JSON, un objeto por producto en el mismo orden, con las llaves `id`, `gtin`, `titulo`, `descripcion`, `categoria_id`, `categoria_ruta`, `ficha`, `receta_mx`, `categoria_rx_sugerida`, `catalogo_ml`, `url_oficial`, `fuentes`, `encontrado_por`, `confianza`, `notas`, `notas_imagenes`. JSON válido (escapa comillas, `\n` en cadenas). Puedes escribir el archivo al final o ir guardándolo por partes.

Al terminar, responde solo con una línea: `inv_XX: N productos, alta A, media M, baja B, con fotos F, búsquedas usadas S`.
