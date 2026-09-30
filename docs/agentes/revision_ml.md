# Instrucciones para los agentes de revisión del catálogo de Mercado Libre

Todas las rutas son relativas a la raíz del repositorio. Hay tres tareas; cada subagente recibe una y un rango de hojas o un lote (`XX`). Los datos salen de `scripts/meli_precios.py` y `scripts/meli_fotos.py` y se preparan con `python scripts/preparar_revision_ml.py fotos|descripciones` (flujo completo en `docs/MERCADOLIBRE_API.md`). **No hagas búsquedas web ni llames a la API**: todo lo necesario está en los archivos. **No modifiques el repositorio**: escribe solo tu archivo de resultado y deja cualquier temporal en tu carpeta de trabajo con prefijo propio. Texto de salida en español de México.

## A. Revisión de fotos (`trabajo/revision_fotos_ml/`)

Entrada: hojas `hoja_NNN.jpg` de tu rango y `indice.json` (`{gtin: {hoja, titulo, presentacion, imagenes: [{n, archivo, origen}]}}`). En cada hoja, cada producto trae su GTIN y título, y sus fotos numeradas (`#n origen px`) en el orden actual (la primera es la principal). Mira cada hoja (en Claude, con la herramienta Read; en otro agente, con su visor). Si dudas, abre la foto original en `products/<GTIN>/images/<archivo>`.

Marca para quitar toda foto que:
- sea de otro producto, otra presentación (otra cantidad, etapa, talla, sabor, concentración) o un paquete de varias piezas cuando se vende una;
- tenga bandas, sellos, cintillos o textos añadidos que no están impresos en el empaque ("150 ml", "Familiar", "Nuevo", precios, logotipos de tienda), o sea infografía, foto de ambiente o con personas o manos;
- sea duplicada visual de otra (misma vista) con peor resolución o tono gris.

Elige principal cuando la actual se quita, es el reverso o un costado, o hay otra de frente claramente mejor. Si un producto se quedaría sin fotos, dilo en tu respuesta. En duda, conserva.

Salida `trabajo/revision_fotos_ml/resultado_XX.json`:

```json
{"revisadas": ["hoja_001.jpg", "…"],
 "quitar": [{"gtin": "…", "archivo": "…_3.jpg", "motivo": "Banda añadida '150 ml'"}],
 "principal": [{"gtin": "…", "archivo": "…_2.jpg"}]}
```

Los nombres de archivo deben existir en `indice.json`; la principal no puede estar en `quitar`. Responde en pocas líneas: hojas revisadas, fotos a quitar, cambios de principal y avisos (productos sin fotos, dudas).

## B. Descripciones y confirmación (`trabajo/descripciones_ml/lote_dXX.json`)

Entrada por producto: `gtin`, `titulo`, `nombre_sistema`, `receta_mx`, `categoria`, `investigacion` (estado, confianza, notas), `catalogo_ml` (`id`, `origen` = `gtin` si Mercado Libre lo asocia al GTIN, `nombre`, `caracteristicas`, `descripcion_corta`, `atributos`), `descripciones_otros_vendedores`, `descripcion_actual` y `ficha_actual`.

1. Compara el catálogo con el producto (marca, línea, variante, presentación, contenido, piezas, concentración). `confirmado` = true solo si `origen` es `gtin` y la identidad coincide sin contradicciones; si no, explica en `diferencias`. Si el catálogo es otro producto, ignóralo por completo.
2. Reescribe `descripcion` con las reglas de `docs/agentes/investigacion.md` (800 a 2,000 caracteres; secciones "Descripción:", "Beneficios:" o "Características:", "Ingredientes:"/"Composición:"/"Fórmula:", "Modo de uso:", "Presentación:", "Advertencias:"; listas con "- "; frase obligatoria de medicamentos; sin enlaces, precios, tiendas, emojis ni afirmaciones de salud fuera de la etiqueta). Usa solo datos del catálogo, de las descripciones de otros vendedores que coincidan con el producto y de la descripción actual; no inventes. Si no alcanza para 800, déjala más corta y explícalo en `notas`. Lo que no se sabe se remite al empaque.
3. `ficha`: solo las claves que cambian o se agregan (claves de `docs/agentes/fotos.md` § Ficha técnica). Si incluyes `otros`, va completo (lo que ya había más lo nuevo): reemplaza al anterior.
4. `titulo`: solo si el actual está mal y el catálogo lo confirma (60 caracteres o menos).

## C. Solo confirmación (`trabajo/descripciones_ml/lote_cXX.json`)

Igual que B, pero sin `descripcion` ni `titulo`: confirma el GTIN, corrige o completa `ficha` y explica dudas en `notas`.

## Salida de B y C

`trabajo/descripciones_ml/resultado_dXX.json` o `resultado_cXX.json`: arreglo en el mismo orden del lote, un objeto por producto:

```json
{"gtin": "…", "confirmado": true, "diferencias": "", "descripcion": "Descripción:\n…", "ficha": {"registro_sanitario": "…"}, "titulo": "…", "notas": "Qué se comparó, qué fuente dio cada dato nuevo y qué queda por confirmar en el empaque."}
```

`descripcion` y `titulo` son opcionales (solo B); `diferencias` va vacío cuando `confirmado` es true. Valida el JSON antes de terminar. Responde en pocas líneas: productos, confirmados, descripciones fuera de rango y puntos a revisar.

## Después (agente principal)

`python scripts/aplicar_revision_ml.py` aplica los tres resultados. Si un catálogo resultó ser otro producto u otra presentación, agrégalo antes a `data/catalogo_ml_rechazados.csv` (`gtin, producto_catalogo, nombre_catalogo, tipo, motivo, fecha`; `tipo` = `otro_producto` u `otra_presentacion`). Luego `python scripts/meli_precios.py --solo-csv` y regenerar layout y visor.
