🪼 Jellyfish OS v6.0 — Manual Completo del Usuario y Desarrollador

Bienvenido a la documentación oficial de Jellyfish OS v6.0, un sistema operativo corporativo multi-agencia y framework de orquestación ágil diseñado para ejecutarse de forma nativa en Linux.

Jellyfish combina la potencia de múltiples LLM (a través de Ollama, OpenAI, DeepSeek, Google Gemini y OpenRouter) con una suite de herramientas del sistema, persistencia vectorial para RAG (Retrieval-Augmented Generation) y un Director de Orquesta (CEO) autónomo capaz de clasificar tareas y asignarlas a agencias especializadas (Desarrollo, Marketing, Investigación, etc.).
🗺️ 1. Arquitectura y Estructura del Core (Multi-Agencia)

Jellyfish v6.0 abandona el pool global y caótico de agentes para organizarlos en Agencias departamentales especializadas, separando estrictamente la interfaz de usuario interactiva (jellyfish.py) de la lógica operativa.
Diagrama de Arquitectura y Flujo
Fragmento de código

graph TD
    User([Usuario / Developer]) --> CLI[jellyfish.py / CLI & Autocompletado]
    CLI <--> State[core.state / JellyfishState]
    CLI --> Commands[core.crud / Slash Commands]
    
    Commands --> Config[config / ignore / add]
    Config -.-> RAG[core.rag_coder / RAG Vector DB]

    Commands --> AutoCEO[core.agency_orchestrator / CEO: /auto]
    Commands --> Run[core.terminal / Terminal Run]
    Commands --> PluginSys[plugins/plugin_core.py / Framework]

    AutoCEO --> CEO_Decision{Clasificador de Intentos}
    CEO_Decision --> AgencyDev[Agencia: Desarrollo]
    CEO_Decision --> AgencyMkt[Agencia: Marketing]
    CEO_Decision --> AgencyRes[Agencia: Investigación]

    AgencyDev --> PO_Scan[1. Product Owner: BACKLOG.md]
    PO_Scan --> SM_Plan[2. Scrum Master: SPRINT_BOARD.md]
    SM_Plan --> Task_Run[3. Task Runner aislando Memoria]
    Task_Run <--> Run
    Task_Run --> Daily_Close[4. Sprint Close & Métricas] --> CLI

Componentes Clave

    core/agency_orchestrator.py (NUEVO): El "CEO" del sistema. Analiza el prompt del usuario y decide a qué agencia departamental (ej. Development, Marketing, Legal) derivar la tarea.

    core/project_orchestrator.py: El orquestador de metodología Scrum, ahora optimizado con aislamiento de memoria en su Compile & Debug Loop para evitar la saturación del contexto del LLM.

    plugins/plugin_core.py (NUEVO): El núcleo del framework de plugins utilizando el patrón Singleton (PluginRegistry), ganchos de eventos (hooks) y auto-descubrimiento de capacidades.

    plugins/integration/skill_loader.py (NUEVO): Plugin encargado de leer y cargar las más de 50 habilidades metodológicas (Skills) desde los archivos Markdown utilizando expresiones regulares.

    core/state.py: Controla el estado global, el lockfile del proyecto, la agencia activa y el cálculo estricto de presupuestos de tokens.

🚀 2. Instalación y Configuración Inicial
Requisitos del Sistema

    Python 3.10 o superior

    Bubblewrap (recomendado para sandbox de plugins): sudo apt install bubblewrap

    Ollama ejecutándose localmente para embeddings.

Instalación y Estructura v6

Instala las dependencias y genera la nueva estructura de directorios utilizando el script de configuración:
Bash

pip install -r requirements.lock
python setup.py --setup

Para auditar que todas las Skills y Plugins se hayan instalado correctamente, ejecuta:
Bash

python setup.py --status

🧠 3. Skills vs. Plugins (La Mente y El Músculo)

En v6.0 introducimos una división clara para extender las capacidades de Jellyfish:

    Skills (Las Habilidades - .md): Son metodologías cognitivas inyectadas en el System Prompt. Hay 50 habilidades distribuidas en agencias (ej. 01_backlog_grooming.md para Management, 17_react_best_practices.md para Frontend). Moldean cómo piensa y formatea sus salidas el LLM.

    Plugins (Los Músculos - .py): Son scripts ejecutables en Python. Pueden ser de utilidad, integración o automatización. Tienen un ciclo de vida propio (initialize, execute, shutdown) gobernado por la clase PluginInterface.

💡 4. Conceptos de Seguridad y Hardening Avanzado
🛡️ A. Aislamiento de Memoria en el Bucle de Compilación

El Compile & Debug Loop del Task Runner clona las directivas originales en cada intento de corrección de código. Esto evita que los errores de compilación redundantes se acumulen (.append) y contaminen el contexto del LLM, garantizando iteraciones veloces.
🔌 B. Fallbacks de Contingencia Autónoma (Zero-Breakage)

Si un modelo súper rápido (como Gemini Flash) responde con una cadena vacía ante parámetros restrictivos (Fase 1 - Product Owner), el sistema ya no colapsa en 0.3 segundos. En su lugar, intercepta el fallo y autogenera un andamiaje de Backlog Recovery estructurado, permitiendo que la orquestación continúe.
🖥️ C. Sincronización Visual TUI y Anti-Corrupción ANSI

Se implementó una limpieza estricta del búfer residual de la terminal (clear_scroll_region) y la re-impresión forzada de la cabecera tras pipelines masivos. Adicionalmente, el parche de autocompletado evita solaparse con el prompt de usuario en ventanas reducidas.
🔒 D. Sandbox con Bubblewrap y Lista Negra Regex

Se mantiene el aislamiento total de red y sistema de archivos temporal para la ejecución de scripts, bloqueando mediante Regex comandos destructivos (rm -rf /, formateos de disco o chmod masivos).
📋 5. Orquestación Multi-Agencia Autónoma

El flujo Scrum ahora escala a nivel corporativo:

[Usuario ejecuta /auto crea una investigación de mercado]
       │
       ▼
El CEO (Agency Orchestrator)
   - Analiza el prompt y determina que pertenece a la "Agencia de Marketing".
   - Deriva la tarea al Product Owner de esa agencia específica.
       │
       ▼
Planificación de la Agencia
   - El PO redacta el `MKT_BOARD.md` u objetivo.
   - El Scrum Master carga las Skills específicas (ej. `32_copywriting_pas.md`).
       │
       ▼
Task Runner (Ejecución y Traspaso)
   - Los agentes generan los entregables (con output streaming en vivo).
   - Capacidad de **Handoff**: La agencia puede generar un entregable que luego servirá de insumo para otra agencia.

🛠️ 6. Guía Completa de Comandos
Comando	Sintaxis	Descripción
/auto	/auto <idea>	Llama al CEO, clasifica la intención y arranca la orquestación autónoma en la agencia pertinente.
/agency	/agency switch <nombre>	Cambia el entorno manual a otra agencia, limitando el autocompletado (@) a sus especialistas.
/skill	/skill	Gestiona o visualiza las habilidades metodológicas cargadas desde skills/.
/plugin	/plugin <nombre> [args]	Lanza un script Python del directorio plugins/ de manera aislada.
/add	/add <ruta>	Añade archivos o indexa carpetas completas en la base vectorial del RAG.
/project	/project	Abre el administrador Scrum para crear o vincular un directorio como proyecto activo.
/compile	/compile	Ejecuta validación estática y el comando dinámico de build detectado.

    Nota: Ejecuta /help dentro del CLI para ver comandos adicionales como /rag, /context, /config, y el control de guías interactivas /gon y /goff.