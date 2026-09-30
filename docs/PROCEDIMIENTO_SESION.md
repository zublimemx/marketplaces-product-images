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

## 4. Regenerar el layout (opcional en cada sesión, obligatorio antes de importar)

```bash
python scripts/build_mercadolibre.py --precios insumos/precios_existencias.csv --salida trabajo/layout_mercadolibre.xlsx
```

El archivo lleva fórmulas sin valores calculados: se calculan al abrirlo en Excel, LibreOffice o Google Sheets.

## 4 bis. Precios de competencia (cuando haya credenciales)

```bash
python scripts/meli_precios.py --muestra 3 --limite 3     # prueba y revisa trabajo/meli_muestras/
python scripts/meli_precios.py --guardar-catalogo [--fotos-catalogo]
```

Detalle en `docs/MERCADOLIBRE_API.md`.

## 5. Publicar cambios (siempre por PR)

1. Actualiza `PENDIENTES.md` (estado, pendientes abiertos, próximas tareas).
2. Commits separados: primero `product.json`, `config`, `PROGRESO.md`, `PENDIENTES.md`; luego las fotos en partes de ~100 productos para no exceder límites de empuje.
3. `git push -u origin sesion-NN`
4. Crear y fusionar el PR: `gh pr create … && gh pr merge --merge` o `python scripts/pr.py --rama sesion-NN --titulo "Sesión NN: …" --cuerpo cuerpo.md --fusionar`.
5. `git checkout main && git pull --ff-only`.

## Criterios de calidad

- Títulos ≤ 60 caracteres, categorías hoja válidas, JSON válido (lo revisa `scripts/validar.py`).
- Confianza `alta` solo si el GTIN se confirmó en una fuente y la presentación coincide.
- Fotos: exactamente el producto y la presentación; sin marcas de agua, logos de tienda, texto promocional ni precios.
- Nunca inventar datos de ficha técnica ni afirmaciones de salud.
