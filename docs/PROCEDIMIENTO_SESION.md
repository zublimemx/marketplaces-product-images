# Procedimiento de una sesión

Una sesión investiga hasta 200 productos (1 búsqueda web por producto) y baja sus fotos. Todos los comandos se corren desde la raíz del repositorio.

## 0. Preparar

```bash
bash scripts/setup.sh            # solo la primera vez en un entorno nuevo
git checkout main && git pull --ff-only
git checkout -b sesion-NN
```

Si cambió el catálogo o el Excel de ventas, regenerar insumos (necesita los Excel originales, que no están en el repositorio):

```bash
python scripts/preparar_insumos.py --ventas "<ventas>.xlsx" --farma catalogo_productos_farma.xlsx --mark catalogo_productos_mark.xlsx
```

## 1. Armar lotes

```bash
python scripts/seleccionar_lote.py --sesion NN --tamano 200 [--fotos]
```

Crea `trabajo/sesion_NN/lotes/inv_01.json … inv_08.json` (25 productos cada uno, en orden de prioridad; primero `pendiente` y `sin_verificar`) y, con `--fotos`, `img_XX.json` para productos verificados sin fotos.

## 2. Investigar

Por cada lote, un agente sigue `docs/agentes/investigacion.md` (o `docs/agentes/fotos.md` para `img_XX`) sustituyendo `NN` y `XX`. En Claude se lanzan como subagentes en paralelo; en Codex u otro agente sin subagentes se corren uno tras otro (ver "Notas para Codex" en `AGENTS.md`). Cada agente:

- hace exactamente 1 búsqueda web por producto y abre las páginas necesarias;
- descarga fotos con `scripts/imagenes.py` (que las registra en `product.json`) y las revisa visualmente;
- escribe `trabajo/sesion_NN/resultados/inv_XX.json`.

## 3. Validar e integrar

```bash
python scripts/validar.py --sesion NN          # esquema de resultados y de product.json
python scripts/integrar_resultados.py --sesion NN
python scripts/revisar_fotos.py                 # fotos de baja resolución, posible fondo gris y verificados sin fotos
python scripts/progreso.py                      # actualiza PROGRESO.md
python scripts/validar.py
```

Revisa visualmente una muestra de fotos nuevas (hoja de contacto por producto en `trabajo/contactos/`).

## 4. Regenerar el layout y el visor (en cada sesión que cambie fichas, fotos o precios)

```bash
python scripts/envios.py                        # si cambiaron fichas o tramos de envío (data/envios.csv)
python scripts/ajustes_precios.py <archivo.xlsx> # si el dueño mandó ajustes de precio del visor
python scripts/build_mercadolibre.py --precios insumos/precios_existencias.csv --salida layouts/mercadolibre/layout_mercadolibre.xlsx
python scripts/build_visor.py
python scripts/build_db.py                       # base de datos data/catalogo.db (siempre después del visor)
```

`build_mercadolibre.py` escribe fórmulas sin valores calculados. Antes de versionarlo, recalcúlalo para que la copia del repositorio traiga valores: en Claude, con el `recalc.py` de la habilidad xlsx; en otro entorno, abriéndolo y guardándolo en LibreOffice o Excel. Si no hay `insumos/precios_existencias.csv` (por ejemplo, en otra IA sin los Excel del ERP), no regeneres el layout: `build_visor.py` toma precios y existencias del layout versionado.

Revisa el resultado en el visor (`visor/index.html`, ver `docs/VISOR.md`): filtra por indicador «mala» para ver qué falta.

## 4 quater. Precios en otros marketplaces

- **Con subagentes:** lotes `trabajo/sesion_NN/lotes/precios_XX.json` (25 productos por prioridad de ventas: `orden`, `gtin`, `titulo`, `nombre_sistema`, `presentacion`, `contenido`, `fuentes`) con `docs/agentes/precios_otros.md`; luego `python scripts/otros_marketplaces.py integrar --sesion NN`.
- **Del dueño:** visor → «Comparar precios» → «Exportar comparación»; el dueño llena la hoja Captura y la adjunta → `python scripts/otros_marketplaces.py excel <archivo.xlsx>`.
- Luego §4 (layout, visor y base de datos).

## 4 ter. Procesar un Excel de pendientes del dueño

Cuando el dueño adjunta un `pendientes_meli_*.xlsx` exportado del visor:

```bash
python scripts/solicitudes.py <archivo.xlsx> --csv trabajo/solicitudes.csv    # resumen por acción
python scripts/solicitudes.py <archivo.xlsx> --aplicar-descartes              # si hay «Descartar de Meli»
```

- **Completar información**: lotes con `docs/agentes/investigacion.md` (en `trabajo/sesion_NN/lotes/`, con los GTIN pedidos).
- **Buscar más imágenes**: lotes con `docs/agentes/fotos.md`.
- **Completar precios**: `scripts/meli_precios.py --gtin …` (necesita token) o el dato que el dueño escribió en Comentarios (`data/ajustes_precios.json`).
- **Revisar con el dueño**: aplicar lo que el dueño escribió en Comentarios; si no escribió nada, preguntarle.

Después: regenerar layout y visor (§4), `python scripts/validar.py`, actualizar `PENDIENTES.md` y PR.

## 4 bis. Competencia, fotos y descripciones con la API de Mercado Libre (con token vigente)

```bash
python scripts/meli_precios.py --gtin 7501123013302 7501058623300          # prueba
python scripts/meli_precios.py --guardar-catalogo --descripciones --hilos 4 # corrida completa
python scripts/meli_fotos.py                                                # fotos de catálogo para fotos malas o regulares
python scripts/preparar_revision_ml.py fotos && python scripts/preparar_revision_ml.py descripciones
# subagentes con docs/agentes/revision_ml.md (8 de fotos por rangos de hojas; lotes d y c de descripciones)
python scripts/aplicar_revision_ml.py && python scripts/meli_precios.py --solo-csv
```

Luego §4 (regenerar). Detalle en `docs/MERCADOLIBRE_API.md`.

## 5. Publicar cambios (siempre por PR)

1. Actualiza `PENDIENTES.md` (estado, pendientes abiertos, próximas tareas).
2. Commits separados: primero `product.json`, `config`, `PROGRESO.md`, `PENDIENTES.md`, el layout y `visor/data/productos.js`; luego las fotos en partes de ~100 productos para no exceder límites de empuje.
3. `git push -u origin sesion-NN`
4. Crear y fusionar el PR: `gh pr create … && gh pr merge --merge` o `python scripts/pr.py --rama sesion-NN --titulo "Sesión NN: …" --cuerpo cuerpo.md --fusionar`.
5. `git checkout main && git pull --ff-only`.

## Criterios de calidad

- Títulos ≤ 60 caracteres, categorías hoja válidas, JSON válido (lo revisa `scripts/validar.py`).
- Confianza `alta` solo si el GTIN se confirmó en una fuente y la presentación coincide.
- Fotos: exactamente el producto y la presentación; sin marcas de agua, logos de tienda, texto promocional ni precios.
- Nunca inventar datos de ficha técnica ni afirmaciones de salud.
