# HABILIDAD: @SCRUM_BOARD_OPS
**OBJETIVO:** Permite al agente @scrum_master (y otros agentes) manipular de forma segura los archivos Markdown del proyecto Scrum: `BACKLOG.md`, `SPRINT_BOARD.md` y `DAILY.md`.
**TRIGGER:** Cuando el agente necesite agregar, mover o actualizar una tarea en los archivos Scrum del proyecto activo.
**DEPENDENCIAS:** `sed`, `cat`, `date` (utilidades estándar de Linux, no requieren instalación).

## OPERACIONES DISPONIBLES

### 1. Agregar historia al Backlog
**INSTRUCCIÓN:** Genera este bloque para agregar una nueva historia de usuario al final de la tabla en `BACKLOG.md`:

```bash
# Variables del proyecto (ajustar PROJECT_DIR según el proyecto activo)
PROJECT_DIR="$JELLYFISH_ACTIVE_PROJECT"
BACKLOG="$PROJECT_DIR/BACKLOG.md"
TODAY=$(date +%Y-%m-%d)

# Obtener el último ID de historia
LAST_ID=$(grep -oP 'US-\K[0-9]+' "$BACKLOG" 2>/dev/null | sort -n | tail -1)
NEXT_ID=$(printf "US-%03d" $(( ${LAST_ID:-0} + 1 )))

# Agregar nueva historia antes de la línea separadora final
sed -i "/^---$/i | $NEXT_ID | $HISTORIA | $ESTIMACION | $PRIORIDAD | Pendiente |" "$BACKLOG"

# Actualizar timestamp
sed -i "s/Última actualización:.*/Última actualización: $TODAY/" "$BACKLOG"
```

### 2. Mover tarea de TODO a IN PROGRESS
**INSTRUCCIÓN:** Genera este bloque para mover una tarea del tablero:

```bash
PROJECT_DIR="$JELLYFISH_ACTIVE_PROJECT"
BOARD="$PROJECT_DIR/SPRINT_BOARD.md"
TODAY=$(date +%Y-%m-%d)

# Leer el contenido actual del tablero antes de modificar
cat "$BOARD"

# Para mover: eliminar la fila de TODO e insertar en IN PROGRESS
# (El agente debe especificar el ID de la tarea y generar el sed apropiado)
```

### 3. Mover tarea a DONE
**INSTRUCCIÓN:** Genera este bloque:

```bash
PROJECT_DIR="$JELLYFISH_ACTIVE_PROJECT"
BOARD="$PROJECT_DIR/SPRINT_BOARD.md"
DAILY="$PROJECT_DIR/DAILY.md"
TODAY=$(date +%Y-%m-%d)

# Actualizar SPRINT_BOARD: mover de IN PROGRESS a DONE
# (El agente debe especificar el ID y generar el sed apropiado)

# Registrar en DAILY.md
echo "" >> "$DAILY"
echo "### @$(whoami)" >> "$DAILY"
echo "- **Completado:** Tarea $TASK_ID finalizada." >> "$DAILY"
echo "- **Fecha:** $TODAY" >> "$DAILY"

# Actualizar timestamp del board
sed -i "s/Última actualización:.*/Última actualización: $TODAY/" "$BOARD"
```

### 4. Registrar Daily Standup
**INSTRUCCIÓN:** Genera este bloque para registrar un standup en `DAILY.md`:

```bash
PROJECT_DIR="$JELLYFISH_ACTIVE_PROJECT"
DAILY="$PROJECT_DIR/DAILY.md"
TODAY=$(date +%Y-%m-%d)
AGENT_NAME="scrum_master"

# Agregar nueva entrada de daily
cat >> "$DAILY" << EOF

---

## $TODAY

### @$AGENT_NAME
- **Ayer:** $AYER
- **Hoy:** $HOY
- **Impedimentos:** $IMPEDIMENTOS
EOF
```

## ERRORES COMUNES
- **Archivo no encontrado:** Verificar que `$JELLYFISH_ACTIVE_PROJECT` esté definido. Si no lo está, indicar al usuario que ejecute `/project` primero.
- **Tabla Markdown corrupta:** Siempre leer el archivo con `cat` antes de modificar con `sed`. Verificar que las columnas estén alineadas.
- **Sobreescritura accidental:** Usar `>>` (append) en lugar de `>` (overwrite) cuando se agregan entradas al `DAILY.md`.
