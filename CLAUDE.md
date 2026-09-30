# CLAUDE.md

Lee y sigue `AGENTS.md`; es la guía común para Claude y Codex. Lo de abajo solo aplica a Claude.

- Paraleliza la investigación con subagentes: un subagente por lote de 25 productos, con el modelo Sonnet, pasándole `docs/agentes/investigacion.md` (o `docs/agentes/fotos.md`) con `NN` y `XX` reemplazados. Para revisar lo que llega del catálogo de Mercado Libre, `docs/agentes/revision_ml.md` (un subagente por rango de ~17 hojas de fotos o por lote de descripciones). Lanza los 8 lotes de una sesión en un solo mensaje y pide a cada uno que use archivos temporales con prefijo propio.
- El presupuesto de búsquedas web (200 por sesión) es compartido por todos los subagentes: no hagas búsquedas de prueba antes de lanzarlos.
- Revisa las hojas de contacto de fotos con la herramienta Read.
- La conversación original se llevó en claude.ai; el resumen de decisiones está en `docs/CONTEXTO.md`.
- Para probar el visor (`visor/index.html`) usa Playwright con el Chromium preinstalado sobre `file://`, captura cuadrícula, lista, detalle, móvil y tema oscuro, y revisa las capturas con Read.
