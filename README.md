# 🪼 Jellyfish OS v6.9.12 — Manual Completo del Usuario y Desarrollador

Bienvenido a la documentación oficial de **Jellyfish OS v6.9.12**, un sistema operativo de agentes cognitivos corporativos, arquitectura multi-agencia y framework de orquestación ágil/secuencial diseñado para ejecutarse de forma nativa en sistemas Linux.

Jellyfish combina la potencia de múltiples modelos de lenguaje a gran escala (LLMs a través de Ollama, OpenAI, DeepSeek, Google Gemini y OpenRouter) con una robusta suite de herramientas del sistema, persistencia vectorial para RAG (Retrieval-Augmented Generation) y un **Director de Orquesta (CEO / Agency Orchestrator)** autónomo capaz de clasificar tareas y delegarlas a agencias especializadas (Desarrollo, Marketing, Investigación, etc.).

---

## 🗺️ 1. Arquitectura y Estructura del Core (Multi-Agencia)

Jellyfish v6.9.12 abandona el enfoque de un pool global y caótico de agentes, organizándolos en **Agencias Departamentales** especializadas y delimitadas por tableros independientes de trabajo. Esto asegura un aislamiento de tareas y previene la contaminación de contextos.

### Diagrama de Arquitectura y Flujo de Datos

```mermaid
graph TD
    User([Usuario / Developer]) --> CLI[jellyfish.py / CLI & Autocompletado]
    CLI <--> State[core.state / JellyfishState]
    CLI --> Commands[core.commands / Slash Commands]
    
    Commands --> Config[Configuración & Ignorados]
    Config -.-> RAG[core.rag_coder / RAG Vector DB]

    Commands --> AutoCEO[core.agency_orchestrator / CEO: /auto]
    Commands --> Run[core.terminal / Terminal Run]
    Commands --> PluginSys[plugins/plugin_core.py / Framework]

    AutoCEO --> CEO_Decision{Clasificador de Intentos}
    CEO_Decision --> AgencyDev[Agencia: Desarrollo]
    CEO_Decision --> AgencyMkt[Agencia: Marketing]
    CEO_Decision --> AgencyRes[Agencia: Investigación]

    AgencyDev --> PO_Scan[1. Product Owner: US-000 Sprint 0 Infraestructura]
    PO_Scan --> SM_Plan[2. Scrum Master: SPRINT_BOARD.md]
    SM_Plan --> Task_Run[3. Task Runner con Subprocess DoD Check]
    Task_Run <--> Run
    Task_Run --> AutoHeal[4. Auto-Healing Loop ReAct]
    AutoHeal --> Daily_Close[5. Sprint Close & Métricas] --> CLI
```

### Componentes Clave del Core v6.9.12

1. **`core/agency_orchestrator.py` (El CEO)**:
   Analiza semánticamente el prompt inicial del usuario. Empleando técnicas de clasificación Zero-Shot y Few-Shot, decide a qué agencia departamental (ej. *Development*, *Marketing*, *Research*) derivar la tarea.
2. **`core/orchestration/product_owner.py` (Sprint 0 Obligatorio)**:
   Garantiza que todo backlog generado empiece con la historia **`US-000: Sprint 0 - Infraestructura y Entorno Base`** como prioridad bloqueante Must-have, exigiendo gestor de dependencias (`package.json`, `requirements.txt`, `build.gradle`), contenedorización Docker y punto de entrada base (`server.js`, `main.py`, `App.tsx`).
3. **`core/orchestration/task_runner.py` (Validación Estricta DoD & Anti-Huérfanos)**:
   Ejecuta verificadores reales en subprocesos aislados (`subprocess.run` con `py_compile`, `node --check`, `json.tool`, `bash -n`, `docker compose config`). Rechaza el DoD si la compilación falla y alimenta la traza de error al bucle de Auto-Healing. Además, inyecta la **Directiva Anti-Archivos Huérfanos** exigiendo conectar todo módulo nuevo al punto de entrada principal en el mismo paso.
4. **`plugins/plugin_core.py` (Orquestador de Músculos)**:
   Núcleo del framework de plugins utilizando el patrón *Singleton* (`PluginRegistry`), ganchos de eventos (*hooks*) y auto-descubrimiento de capacidades de herramientas Python.
5. **`core/state.py` (Estado Global)**:
   Controla el estado reactivo, la persistencia en archivos de configuración (`.jellyfish_project_config.json`), el bloqueo de concurrencia y la contabilidad estricta del consumo de tokens.

---

## 🚀 2. Instalación y Configuración Inicial

### Requisitos del Sistema
- **Sistema Operativo**: Linux (Debian/Ubuntu/Fedora/Arch recomendado).
- **Python**: Versión `3.10` o superior.
- **Bubblewrap**: Recomendado para el aislamiento seguro (*sandbox*) de la ejecución de plugins.
  ```bash
  sudo apt install bubblewrap  # En Debian/Ubuntu
  sudo dnf install bubblewrap  # En Fedora/RHEL
  ```
- **Ollama**: Servidor local corriendo para generación de embeddings locales si no se usan servicios de nube.

### Instalación de Dependencias e Inicialización v6.9.12
Instale las dependencias bloqueadas y configure la estructura del espacio de trabajo utilizando el script de configuración:
```bash
pip install -r requirements.lock
python setup.py --setup
```

Para verificar e inspeccionar el estado actual de los proveedores, habilidades registradas y APIs configuradas, ejecute:
```bash
python setup.py --status
```

---

## 🧠 3. Habilidades (Skills) vs. Plugins

En Jellyfish v6.9.12 se define una separación conceptual clara para la extensión del sistema:

- **Skills (Cognición - `.md` o `.py` de Skill)**:
  Son metodologías de diseño y plantillas de pensamiento que se inyectan en el prompt del sistema. Se distribuyen en agencias (ej. `01_backlog_grooming.md` en Management, `17_react_best_practices.md` en Frontend) y dictan el formato y el flujo analítico de la respuesta del LLM.
- **Plugins (Acción - `.py`)**:
  Son extensiones de código imperativo en Python. Tienen acceso a llamadas del sistema operativo, APIs y herramientas de red. Poseen un ciclo de vida estructurado gobernado por la clase `PluginInterface`.

---

## 💡 4. Conceptos de Seguridad, Anti-Huérfanos y DoD Estricto

### 🛡️ A. Sprint 0 de Infraestructura Obligatorio
Todo proyecto desarrollado en v6.9.12 comienza bloqueando cualquier tarea de negocio hasta que la **`US-000`** entregue el gestor de dependencias (`package.json`, `requirements.txt`, `build.gradle`), contenedorización Docker (`Dockerfile`, `docker-compose.yml`) y el punto de entrada base.

### 🧪 B. Validación Estricta por Subproceso (`subprocess.run`)
El Task Runner valida que el entregable de cada tarea compile y se verifique sintácticamente en tiempo de ejecución mediante verificadores reales (`py_compile`, `node --check`, `json.tool`, `bash -n`, `docker compose config`). Los errores activan automáticamente el bucle ReAct de Auto-Healing.

### 🔗 C. Directiva Anti-Archivos Huérfanos
Los agentes tienen prohibido crear vistas, controladores o módulos aislados. Cada nuevo archivo o componente debe ser importado, exportado e integrado activamente en la aplicación principal (`App.tsx`, `server.js`, `main.py`, etc.) en el mismo paso.

### 🔌 D. Circuit Breakers y Fallbacks Autónomos
Si un modelo en la nube genera una salida nula o excede los límites permitidos debido a tokens corruptos o latencia excesiva, Jellyfish OS activa mecanismos de **Circuit Breaker** y andamiajes de recuperación (*Backlog Recovery*), evitando el colapso abrupto del pipeline de automatización.

---

## 📋 5. Guía Completa de Comandos

| Comando | Sintaxis | Descripción |
| :--- | :--- | :--- |
| `/auto` | `/auto <descripción>` | Activa el CEO (Agency Orchestrator), clasifica la tarea y arranca la orquestación autónoma Scrum en la agencia pertinente. |
| `/agency` | `/agency switch <nombre>` | Cambia manualmente a la agencia departamental indicada, limitando los agentes del autocompletador (`@`). |
| `/skill` | `/skill` | Visualiza e inyecta dinámicamente habilidades de la carpeta `skills/`. |
| `/plugin` | `/plugin <nombre> [args]` | Ejecuta un plugin de Python de forma aislada en sandbox. |
| `/add` | `/add <ruta>` | Carga un archivo en el contexto activo o indexa recursivamente una carpeta en la base de datos RAG del proyecto. |
| `/project` | `/project new <ruta>` | Crea o vincula un proyecto asignándole metodología Scrum o Cascada. |
| `/compile` | `/compile` | Ejecuta la verificación estática de tipos o compilación autónoma detectada en el proyecto. |
| `/gon` / `/goff`| `/gon` o `/goff` | Habilita o deshabilita las guías de construcción y tableros interactivos Scrum. |
| `/help` | `/help` | Muestra el manual de comandos integrados detallados de Jellyfish OS. |

---

## 🔑 6. Variables de Entorno del Sistema (`.env`)

| Variable | Valor por Defecto | Propósito |
| :--- | :--- | :--- |
| `JELLYFISH_PROVIDER` | `ollama` | Proveedor principal de la IA (`openai`, `deepseek`, `gemini`, `openrouter`, `ollama`, etc.). |
| `JELLYFISH_MODEL` | *(depende)* | Nombre exacto del modelo a utilizar para el Lead Agent (ej. `gpt-4o`, `gemini-2.5-flash`). |
| `JELLYFISH_CONTEXT_LIMIT` | `8192` | Cantidad máxima de tokens de contexto gestionados en ventana deslizante. |
| `JELLYFISH_PLUGIN_UNSAFE` | `0` | Si se establece en `1`, desactiva el sandbox Bubblewrap para la ejecución de plugins. |
| `JELLYFISH_RAG_THRESHOLD` | `1.2` | Umbral de distancia euclidiana mínima para el filtrado de similitud en RAG. |

---



















*Última actualización de especificación técnica: 2026-07-29 16:58:48 — Arquitectura: REPL Interactivo + Orquestación Multi-Agencia*
