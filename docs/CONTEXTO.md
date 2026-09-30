# Contexto del proyecto

## Qué se está haciendo

Una farmacia mexicana (líneas **Farma**: farmacia, y **Mark**: salud, perfumería, bebé) va a publicar en marketplaces sus productos más vendidos. El proyecto lo lleva Zublime (implementador de Odoo). Se empezó por **Mercado Libre México**; después siguen **Odoo, Shopify y Amazon**. Este repositorio es la base de datos común de contenido (fichas, descripciones, fichas técnicas y fotos) para armar la plantilla de importación de cualquier marketplace.

## Insumos originales (no versionados)

Los entregó el dueño como Excel y viven fuera del repositorio (tienen precios y ventas). Los precios y existencias que resultan del cruce sí se versionan dentro del layout y del visor (decisión 10):

| Archivo | Contenido | Uso |
|---|---|---|
| `Productos más vendidos de julio 2026 a septiembre 2026.xlsx` | Hoja 1 = Farma (866 renglones), hoja 2 = Mark (308). Columnas: Producto, julio 2026, agosto 2026, septiembre 2026, Total piezas, Total MXN | Define **qué** productos se publican y su prioridad (por Total MXN). Las cifras de venta no se usan en el layout. |
| `catalogo_productos_farma.xlsx`, `catalogo_productos_mark.xlsx` | Código de barras, Nombre, Precio de venta (IVA incluido), Cantidades disponibles | Se cruzan por nombre para obtener GTIN, precio y existencia. |
| `Categorias_MercadoLibre_Mexico_MLM.xlsx` | Árbol de categorías MLM (12,255 categorías; 10,647 hojas publicables) | Copiado a `reference/mercadolibre/` en CSV. |

Resultado del cruce: 1,174 renglones de ventas → 1,163 productos únicos (se excluyó el renglón genérico "Todo / Perfumería"; 2 nombres con sufijo "(2)" se cruzaron sin él; 10 GTIN estaban en Farma y en Mark y se unieron en una sola publicación). El orden de trabajo está en `data/prioridad.csv`.

## Decisiones del dueño (en orden cronológico)

1. Publicar en Mercado Libre con plantilla de carga masiva; imágenes después.
2. Títulos reescritos buscando el producto en internet, de preferencia por código de barras. Descripciones obtenidas de internet (se permite apoyarse en publicaciones de otros vendedores de Mercado Libre cuando convenga), lo más completas posible. Ficha técnica "de la forma más conveniente según cada producto".
3. SKU = código universal (GTIN). Publicación **Clásica**. **Mercado Envíos, sin envío gratis**. **Sin garantía**. Existencia = la del catálogo; sin existencia se publica en 0 pero se incluye.
4. "Todos los productos son 100 % de venta libre" (el dueño lo indicó así). Por eso los medicamentos van en categorías de venta libre; aun así se marca `receta_mx` y una categoría con receta sugerida para revisión, porque Mercado Libre podría rechazarlos.
5. Precios del catálogo ya incluyen impuestos. Reglas de precio en `docs/REGLAS_NEGOCIO.md` (+$4 de empaque, comisión aproximada, comparación con competencia).
6. Fotos: se rechazó copiar fotos de Amazon o de otros vendedores. Orden aceptado: catálogo de Mercado Libre, banco de imágenes oficial (fabricante), fotos propias para lo que falte. Luego el dueño indicó que las fotos **siempre se obtienen de internet**, se descargan y se versionan en este repositorio (nunca llegan en ZIP).
7. El repositorio es permanente: privado normalmente, público solo durante importaciones. Debe servir como base de datos para reconstruir plantillas de Odoo, Shopify, Amazon, Mercado Libre y futuros marketplaces.
8. Investigar 200 productos por sesión (por el límite de búsquedas) y llevar la cuenta de avance y sesiones restantes.
9. Todo cambio al repositorio por PR, fusionado, con pendientes y próximas tareas siempre actualizados; el repositorio debe permitir continuar el trabajo con otra IA (Claude o Codex).
10. Versionar el layout completo de Mercado Libre en el repositorio (con precios y existencias) y un visor web (HTML, CSS y JS separados) para validar visualmente la calidad y cantidad de los productos, con indicadores de descripción (mala/regular/buena), fotos (mala/regular/buena) y precios (incompletos/completos), filtros, orden, paginación y productos similares. Ver `docs/VISOR.md`. Los Excel originales, las cifras de venta y las credenciales siguen fuera de git.

## Hallazgos que conviene conocer

- La carga masiva de Mercado Libre usa la plantilla oficial que se descarga del Publicador masivo por categoría; el layout de este repositorio es la hoja maestra desde la que se copian los datos (o se llenan las plantillas oficiales si el dueño las comparte).
- Mercado Libre bloquea consultas automáticas de sus listados (redirige a verificación de cuenta) y su API de búsqueda pide token. Por eso las columnas de precio de competencia siguen vacías: hace falta una aplicación de vendedor con credenciales (ver `PENDIENTES.md`).
- En 2026 Mercado Libre México vende medicamentos con y sin receta mediante farmacias autorizadas; prohíbe psicotrópicos. Existen categorías "Medicamentos con Receta" y "Medicamentos de Venta Libre".
- El precio Meli de productos baratos sube mucho por el costo fijo por unidad (p. ej. $19.82 → $57). Considerar kits o paquetes.
- Desde $299 Mercado Libre obliga el envío gratis y lo cobra al vendedor; el costo estimado de ese envío está en 0 en `config/mercadolibre.json` hasta que el dueño dé su dato real.
- Las fotos son mayoritariamente de fichas de farmacias (origen `tienda`); muy pocas del fabricante. Algunas tienen resolución útil menor a 500 px (se marcan en la hoja Revisión del layout).

## Historial de sesiones

Ver `PROGRESO.md` (lo genera `scripts/progreso.py` con `config/mercadolibre.json → avance.historial`).
