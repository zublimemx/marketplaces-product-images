# Reglas de negocio

Todas vienen del dueño salvo donde se indica "supuesto". Los valores numéricos viven en `config/mercadolibre.json`; si cambian, cambia el JSON, no el código.

## Productos que se publican

- Los del Excel de más vendidos (jul–sep 2026) de Farma y Mark, cruzados por nombre contra su catálogo (`scripts/preparar_insumos.py`).
- Un solo registro por GTIN. Si el GTIN está en Farma y en Mark: existencia sumada y precio mayor.
- Existencia negativa → 0. Productos sin existencia se incluyen con 0.
- El dueño puede **descartar** productos de Mercado Libre (normalmente pidiéndolo en el Excel de pendientes del visor). Un descartado se conserva en el repositorio pero sale del layout (hoja Descartados). Se marca con `scripts/descartar.py`.

## Publicación en Mercado Libre (valores fijos)

| Campo | Valor |
|---|---|
| SKU | GTIN (código universal de producto) |
| Condición | Nuevo |
| Tipo de publicación | Clásica |
| Forma de envío | Mercado Envíos |
| Costo de envío | A cargo del comprador (Mercado Libre obliga envío gratis desde $299; el layout lo indica en esos productos) |
| Retiro en persona | No acepto |
| Garantía | Sin garantía |
| Categoría de medicamentos | Venta libre, por grupo terapéutico (el dueño indicó que todo es de venta libre); se registra `receta_mx` y `categoria_rx_sugerida` para revisión |

## Contenido

- Título: máximo 60 caracteres; Producto + Marca + variante + dato clave; sin lote, caducidad, promociones ni emojis.
- Descripción: texto plano de 800 a 2,000 caracteres con secciones "Descripción:", "Beneficios:", "Ingredientes:", "Modo de uso:", "Presentación:", "Advertencias:". Redacción original a partir de las fuentes. Medicamentos cierran con "Lea las instrucciones del empaque. Consulte a su médico. No se deje al alcance de los niños." Sin contactos, enlaces, precios ni nombres de tiendas.
- Ficha técnica: atributos que apliquen (ver `docs/CONTRATOS.md`); nunca inventar datos.

## Fotos

- Siempre de internet, descargadas y versionadas aquí. Origen preferido: fabricante > catálogo de Mercado Libre > tienda.
- JPG cuadrado con fondo blanco, recorte automático del borde, 500 a 2,000 px por lado (`scripts/imagenes.py`). Preferir fotos con 800 px útiles o más.
- Rechazar: otra presentación, marcas de agua o logos de tienda, texto promocional, precios, íconos "sin imagen".
- Nombre: `<GTIN>_<n>.jpg` (n = 1 es la foto principal). URL pública: `https://raw.githubusercontent.com/zublimemx/marketplaces-product-images/main/products/<GTIN>/images/<GTIN>_<n>.jpg`.

## Precio

| Columna | Regla |
|---|---|
| Precio de venta | Precio del catálogo (IVA incluido) |
| Precio de venta Marketplaces | Precio de venta + $4 por pieza (empaque y logística interna) |
| Precio Meli calculado | Precio de venta Marketplaces + comisión aproximada de Mercado Libre, redondeado al peso hacia arriba |
| Precio Meli promedio otros vendedores | Dato de entrada, solo de referencia (pendiente de obtener) |
| Precio mejor vendedor | Dato de entrada: precio de la publicación del mismo producto con más ventas (pendiente; si la API no da ventas, ganador del catálogo) |
| Precio Meli Final | Precio con el que se publica. Si hay precio del mejor vendedor y (mejor vendedor − $1) ≥ calculado: mejor vendedor − $1; si no, el calculado. Regla del dueño del 29 sep 2026 (antes se usaba el promedio de otros vendedores) |

Comisión aproximada (publicación Clásica, fuentes en `config/mercadolibre.json`):
- Porcentaje por categoría raíz: Salud y Equipamiento Médico 14 %, Belleza y Cuidado Personal 14 %, Bebés 15 %, Alimentos y Bebidas 10 %, otras 16 % (supuesto conservador).
- Costo fijo por unidad según precio final: menos de $99 → $25; $99 a $149 → $30; $149 a $299 → $37; $299 o más → $0.
- Desde $299 se suma el costo de envío a cargo del vendedor (parámetro, hoy $0 por confirmar).
- Fórmula por tramo: precio = ROUNDUP((Precio Marketplaces + costo fijo del tramo + envío) / (1 − comisión)); se usa el primer tramo cuyo resultado cae dentro de su rango; si el tramo de $149–$299 da $299 o más, se usa el máximo entre el cálculo sin costo fijo y $299.
- Las retenciones de IVA (8 %) e ISR (2.5 %) no se suman: son acreditables.
