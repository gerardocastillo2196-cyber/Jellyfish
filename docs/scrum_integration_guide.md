# Guía de Trabajo: Integración de Metodología Scrum y Proyectos Autogestionados en Jellyfish

Esta guía detalla las fases necesarias para implementar la creación de proyectos y la automatización del flujo ágil Scrum en Jellyfish OS.

---

## 🗺️ Flujo General del Sistema Scrum

```mermaid
graph TD
    User[/Usuario/] -->|/project| CLI[CLI de Jellyfish]
    CLI -->|1. Solicita ruta| Selector[Selector de Rutas]
    Selector -->|2. Inicializa| Files[Crear Estructura Scrum]
    Files -->|3. Actualiza| Env[.env & JellyfishState]
    Files -.->|Crea| Method[SCRUM_METHODOLOGY.md]
    Files -.->|Crea| Backlog[BACKLOG.md]
    Files -.->|Crea| Board[SPRINT_BOARD.md]
    Files -.->|Crea| Daily[DAILY.md]
    
    Env -->|Inyecta Contexto| SM[@scrum_master]
    SM -->|Lee/Escribe| Backlog
    SM -->|Lee/Escribe| Board
    SM -->|Registra Dailies| Daily
```

---

## 📌 Fase 1: Persistencia del Proyecto Activo
El framework necesita saber cuál es el proyecto de desarrollo activo en todo momento. Para ello, extendemos el sistema de configuración y estado:

1. **`JellyfishState` (`core/state.py`)**:
   - Agregar una propiedad `self.active_project` (cadena con la ruta absoluta o `None`).
   - Cargar `JELLYFISH_ACTIVE_PROJECT` desde `.env` al inicializar.
   - Asegurar que al llamar a `save_config`, esta variable se persista correctamente en el archivo `.env`.
2. **Compatibilidad Estática**:
   - Exportar `ACTIVE_PROJECT` como constante de conveniencia en `core/state.py` para otros módulos.

---

## 📌 Fase 2: El Comando `/project` e Interfaz de Usuario
El usuario debe tener un control centralizado para inicializar y cambiar de proyecto.

1. **Implementación de `/project` (`core/crud.py`)**:
   - El comando `/project` (alias corto `/p`) ofrecerá las siguientes opciones interactivas:
     - **"Crear/Abrir Proyecto"**: Solicita una ruta absoluta o relativa. Si la carpeta no existe, pregunta al usuario si desea crearla.
     - **"Ver Proyecto Activo"**: Muestra el proyecto seleccionado actualmente y el estado de sus archivos Scrum.
     - **"Desvincular Proyecto"**: Desactiva el proyecto actual en `state.active_project`.
2. **Autocompletado (`jellyfish.py`)**:
   - Registrar `/project` y su descripción en `JellyfishCompleter.COMMANDS` para permitir autocompletado nativo.

---

## 📌 Fase 3: Plantillas Preconfiguradas de Metodología Scrum
Cuando se crea o inicializa un proyecto en un directorio, se deben generar archivos con una estructura predeterminada.

1. **`SCRUM_METHODOLOGY.md`**:
   - Describe las reglas de juego: cómo se estiman las tareas (puntos de historia, T-shirt sizes), cuándo se considera terminada una tarea (Definition of Done) y las pautas para que los agentes colaboren.
2. **`BACKLOG.md`**:
   - Contiene la lista general de requerimientos (historias de usuario) organizados por prioridad.
3. **`SPRINT_BOARD.md`**:
   - Tablero Kanban en texto plano con tres secciones claras:
     - `## 📋 POR HACER (TODO)`
     - `## ⏳ EN PROCESO (IN PROGRESS)`
     - `##  HECHO (DONE)`
4. **`DAILY.md`**:
   - Bitácora diaria donde los agentes anotarán:
     - ¿Qué hice ayer?
     - ¿Qué haré hoy?
     - ¿Qué impedimentos tengo?

---

## 📌 Fase 4: Creación del Agente `@scrum_master`
El Scrum Master es el rol que facilita el cumplimiento de la metodología y la actualización del estado del proyecto.

1. **Definición de Perfil (`agents/scrum_master.md`)**:
   - El agente asumirá el rol de Scrum Master técnico.
   - **Reglas Inquebrantables**:
     - Cada vez que el usuario solicite planificar una nueva característica, el Scrum Master debe actualizar `BACKLOG.md`.
     - Cuando se decida trabajar en una tarea, debe moverla en `SPRINT_BOARD.md` de TODO a IN_PROGRESS.
     - Al finalizar cualquier trabajo o comando sugerido, actualizará la tarea a DONE y registrará una entrada corta en `DAILY.md`.
2. **Habilidad de Manipulación de Tablero (`skills/scrum_master_skills.md`)**:
   - Ofrece al agente la lógica Bash/Python necesaria para modificar de manera segura los archivos markdown (evitando sobreescrituras corruptas).

---

## 📌 Fase 5: Autoedición y Comunicación Síncrona entre Agentes
Para que el sistema sea realmente autónomo y autoeditable:

1. **Monitoreo del Contexto**:
   - Dado que los archivos `BACKLOG.md`, `SPRINT_BOARD.md` y `DAILY.md` se añaden automáticamente al contexto activo cuando el proyecto está seleccionado, los agentes tienen visibilidad en tiempo real de lo que otros agentes han escrito o modificado.
2. **Protocolo de Actualización Autoprompting**:
   - Añadir instrucciones al prompt del sistema para que, al concluir cualquier tarea técnica, el orquestador o agente activo invoque la habilidad del Scrum Master para documentar los cambios. Esto asegura que la comunicación entre agentes fluya de manera ágil a través del repositorio compartido.
