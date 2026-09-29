# CLAUDE.md

Lee y sigue `AGENTS.md`; es la guía común para Claude y Codex. Lo de abajo solo aplica a Claude.

- Paraleliza la investigación con subagentes: un subagente por lote de 25 productos, con el modelo Sonnet, pasándole `docs/agentes/investigacion.md` (o `docs/agentes/fotos.md`) con `NN` y `XX` reemplazados. Lanza los 8 lotes de una sesión en un solo mensaje.
- El presupuesto de búsquedas web (200 por sesión) es compartido por todos los subagentes: no hagas búsquedas de prueba antes de lanzarlos.
- Revisa las hojas de contacto de fotos con la herramienta Read.
- La conversación original se llevó en claude.ai; el resumen de decisiones está en `docs/CONTEXTO.md`.
