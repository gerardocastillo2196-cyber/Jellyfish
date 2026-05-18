# HABILIDAD: @REFACTOR_MASTER
**OBJETIVO:** Ejecutar refactorizaciones masivas y cambios de arquitectura en proyectos de gran escala (20,000+ archivos) de forma segura y consistente.

**PROTOCOLO DE OPERACIÓN:**
1. **Fase de Auditoría (Read-Only):**
   - Usa `grep -r` o `find` para identificar la extensión total del cambio.
   - Usa el motor RAG para entender las dependencias del código que vas a modificar.
   - Informa al usuario: "He detectado X archivos que requieren este cambio".

2. **Fase de Planificación:**
   - Define si el cambio debe ser manual (vía edición de archivos core) o automático (vía scripts de terminal).
   - Crea un script de Python o un comando `sed` complejo para aplicar el cambio de forma atómica.

3. **Fase de Ejecución:**
   - Aplica los cambios preferiblemente usando herramientas de Linux nativas para máxima velocidad.
   - Si el proyecto es masivo, procesa en bloques para evitar bloqueos del sistema.

4. **Fase de Verificación:**
   - Realiza un escaneo post-refactor para asegurar que no hay inconsistencias.
   - Verifica que los archivos core (UI, API, DB) mantienen la integridad.

**COMANDOS RECOMENDADOS:**
- `grep -rl "patron_antiguo" . | xargs sed -i 's/patron_antiguo/patron_nuevo/g'`
- `find . -name "*.py" -exec python3 -c "import sys; ..."`

**REGLA DE ORO:** Nunca intentes abrir 20,000 archivos en el editor de Jellyfish. Usa la terminal para cambios masivos y el RAG para la inteligencia de decisión.
