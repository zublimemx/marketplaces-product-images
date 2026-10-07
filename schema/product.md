# Campos de product.json

| Campo | Descripción |
|---|---|
| gtin | Código de barras (texto, conserva ceros a la izquierda) |
| sku | SKU usado en marketplaces; igual al GTIN |
| linea | Línea de origen: Farma, Mark o Farma + Mark |
| nombre_sistema | Nombre en el sistema de la farmacia |
| nombres_sistema_alternos | Otros nombres del mismo GTIN en el sistema |
| titulo | Título comercial de hasta 60 caracteres |
| descripcion | Texto plano con secciones (Descripción, Beneficios, Ingredientes, Modo de uso, Presentación, Advertencias) |
| ficha | Atributos: marca, fabricante, linea, variante, presentacion, contenido_neto, unidad_contenido, unidades_por_envase, principio_activo, concentracion, via_administracion, edad_etapa, talla, sabor_aroma, genero, tipo_piel_cabello, registro_sanitario, otros |
| receta_mx | Si el principio activo normalmente requiere receta en México: Sí, No, Revisar, No aplica |
| marketplaces.mercadolibre | categoria_id, categoria_ruta, categoria_rx_sugerida, catalogo_id, estado manual de publicación (publication_status, published_at, meli_item_id) y, solo si se descartó de Mercado Libre, descartado {motivo, fecha} (`scripts/descartar.py`). `catalogo_id` identifica el producto del catálogo; `meli_item_id`, la publicación del vendedor. |
| marketplaces.amazon / shopify / odoo | Reservado para categorías y datos propios de cada canal |
| imagenes | Lista de fotos: archivo, fuente, fecha |
| url_oficial | Página del fabricante o marca |
| fuentes | URLs usadas para la ficha |
| investigacion | estado, confianza, encontrado_por, notas, fecha |
