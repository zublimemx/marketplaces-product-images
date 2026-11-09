# Instrucciones para un subagente: categoría (y fabricante) de un lote del catálogo Ecatepec

Fase 1 del catálogo Ecatepec: asignar a cada producto una categoría del árbol de **Farmacias del Ahorro** (ya convertido a nombres de Odoo dentro de «Farmacia» o «Perfumería») y, cuando el laboratorio del ERP es un distribuidor, el fabricante. Los productos que el Ahorro sí tiene ya traen su categoría confirmada; este lote es de los que **no** encontró. Todo en español de México.

Sustituye `XX` por el número de lote.

## Entrada

- `trabajo/ecatepec/lotes/cat_XX.json`: lista de productos con `gtin`, `nombre_erp` (abreviado, como en el ERP), `laboratorio_erp`, `categoria_erp` (Farmacia, Perfumería, Curación y Rebotica o DESCATALOGADO), `unspsc` (código y nombre UNSPSC del ERP), `nombre_ahorro` y `marca_ahorro` (si el Ahorro lo tiene), `necesita` (`categoria`, `+fabricante` o ambos), `categoria_confirmada` (si ya la tiene), `pista_unspsc` y `pista_laboratorio` (rutas más frecuentes entre productos confirmados con el mismo UNSPSC o el mismo laboratorio, con su conteo).
- `trabajo/ecatepec/rutas_odoo.txt`: las **únicas** categorías válidas (una por renglón, separada por tabulador del número de productos confirmados en ella). Léela completa antes de empezar.
- `data/ecatepec/laboratorios.json`: laboratorios del ERP ya normalizados (`fabricante`); úsalo para escribir los fabricantes con el mismo nombre.

## Qué hacer

1. **Categoría** (si `necesita` incluye `categoria`): interpreta el nombre abreviado del ERP (p. ej. «CRA» = crema, «SH» = shampoo, «DEO» = desodorante, «JBE» = jarabe, «TAB/CAPS/GRAG» = tabletas/cápsulas/grageas, «SUSP» = suspensión, «AMP» = ampolletas, «C30» = caja con 30, «CJ12» = caja de 12) y elige la ruta más específica de `rutas_odoo.txt` que corresponda al producto. Copia la ruta **exacta**, carácter por carácter.
   - Medicamentos: por especialidad o padecimiento, como lo hace el Ahorro: «Farmacia / Especialidades / …» para medicamentos de patente o con receta (antibióticos → Infectología; antihipertensivos → Cardiología; antiácidos y gastro → Gastroenterología; etc.), y las rutas de venta libre («Farmacia / Dolor y Fiebre», «Farmacia / Salud Respiratoria / Gripa», …) para analgésicos, antigripales y similares de mostrador. Genéricos: misma lógica por su principio activo.
   - Las pistas son orientación, no obligación: úsalas cuando el producto se parezca a los confirmados.
   - Prefiere rutas con productos confirmados (conteo > 0) cuando haya varias que sirvan.
2. **Fabricante** (si `necesita` incluye `+fabricante`): el fabricante o laboratorio dueño de la marca del producto (p. ej. «Nexcare» → «3M»; «Zinnat» → «GSK»). Escríbelo con el mismo nombre que en `data/ecatepec/laboratorios.json` si ya existe ahí. Si no lo reconoces con seguridad, deja `""`.
3. **No uses búsquedas web ni abras páginas**: esta fase es de inferencia; la confirmación con búsqueda se hace después. No inventes: si el nombre del ERP no permite saber qué es el producto, elige la ruta más general que sea segura (p. ej. «Farmacia / Especialidades») y pon confianza «baja».

## Salida

`trabajo/ecatepec/resultados/cat_XX.json`: lista JSON con un objeto por producto del lote, en el mismo orden:

```json
{"gtin": "…", "categoria": "Farmacia / Especialidades / Cardiología", "fabricante": "", "confianza": "media", "nota": ""}
```

- `categoria`: la ruta elegida (o `categoria_confirmada` sin cambios si ya venía).
- `fabricante`: solo cuando `necesita` incluye `+fabricante`; si no, `""`.
- `confianza`: «media» si el nombre deja claro qué es el producto; «baja» si dudas.
- `nota`: breve y solo si aporta (p. ej. «nombre ilegible»).

Antes de terminar, valida con Python que el archivo carga, que tiene el mismo número de objetos que el lote, que los `gtin` coinciden en orden y que **cada** `categoria` está en `rutas_odoo.txt`. Usa archivos temporales solo con prefijo `catXX_` dentro de `trabajo/ecatepec/`. Responde en pocas líneas: productos, cuántos por confianza y las categorías más usadas.
