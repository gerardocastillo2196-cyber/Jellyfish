# 🪼 Jellyfish OS v6.9.15 — Manual Completo del Usuario y Desarrollador

Bienvenido a la documentación oficial de **Jellyfish OS v6.9.15**, un sistema operativo de agentes cognitivos corporativos, arquitectura multi-agencia de enjambre (*Swarm Architecture*) y framework de orquestación ágil/secuencial diseñado para ejecutarse de forma nativa en sistemas Linux.

Jellyfish combina la potencia de múltiples modelos de lenguaje a gran escala (LLMs a través de Ollama, Google Gemini 3.x, OpenAI, Claude, Groq, DeepSeek y OpenRouter) con una robusta suite de herramientas de sistema, persistencia vectorial para RAG inteligente (*Retrieval-Augmented Generation*) y un **Director de Orquesta (CEO / Agency Orchestrator)** autónomo con capacidades de enrutamiento heterogéneo y reparación determinística (*Auto-Healing*).

---

## 🗺️ 1. Arquitectura y Estructura del Core (Enjambre Multi-Agencia)

Jellyfish v6.9.15 evoluciona la arquitectura multi-agencia mediante la integración de **Enjambres Especializados (Swarm Architecture)** y enrutamiento heterogéneo inteligente. Los agentes se agrupan en agencias departamentales delimitadas por tableros independientes, evitando la contaminación de contextos y optimizando el rendimiento mediante modelos de IA especializados según el rol operativo.

### Diagrama de Arquitectura y Flujo del Enjambre (Swarm)

```mermaid
graph TD
    User([Usuario / Developer]) --> CLI[jellyfish.py / TUI & Autocompletado]
    CLI <--> State[core.state / JellyfishState & Blackboard]
    CLI --> Commands[core.commands / Slash Commands]
    
    Commands --> Config[Configuración & SwarmRouter]
    Config -.-> RAG[core.rag_coder / RAG Vector DB (Auto-OFF/ON)]

    Commands --> AutoCEO[core.agency_orchestrator / CEO: /auto & Mega Planner]
    Commands --> Run[core.terminal / Terminal Seguro]
    Commands --> PluginSys[plugins/plugin_core.py / Sandbox Bubblewrap]

    AutoCEO --> SwarmRouter{Enrutador Heterogéneo SwarmRouter}
    SwarmRouter -->|QA / Crítica / Seguridad| Groq[Modelos Baja Latencia: Groq / QA]
    SwarmRouter -->|Código / Plan / Arquitectura| Gemini[Modelos Gran Contexto: Gemini 3.x / OpenAI / Ollama]

    AutoCEO --> AgencyDev[Agencia: Desarrollo & Ingeniería]
    AutoCEO --> AgencyMkt[Agencia: Marketing & Estrategia]
    AutoCEO --> AgencyRes[Agencia: Investigación RAG]

    AgencyDev --> PO_Scan[1. Product Owner: US-000 Sprint 0 Infraestructura]
    PO_Scan --> SM_Plan[2. Scrum Master & Mega Planner: SPRINT_BOARD.md]
    SM_Plan --> Task_Run[3. Task Runner con Subprocess DoD Check]
    Task_Run <--> Run
    Task_Run --> AutoHeal[4. BuildHealer: Auto-Healing & Patch/Diff Determinístico]
    AutoHeal --> Daily_Close[5. Sprint Close & Auditoría de Consenso] --> CLI
```

### Componentes Clave del Core v6.9.15

1. **`core/agency_orchestrator.py` & `core/orchestration/mega_planner.py` (El CEO & Mega Planner)**:
   Analizan semánticamente el prompt del usuario y descompicran desarrollos corporativos a gran escala en planes arquitectónicos granulares y tableros secuenciales, delegando tareas a las agencias departamentales especializadas (*Development*, *Marketing*, *Research*).
2. **`core/llm_engine.py` (Swarm Router & Fábrica Heterogénea)**:
   Implementa el enrutamiento inteligente en tiempo de ejecución (`SwarmRouter`). Asigna los agentes de auditoría, crítica y seguridad (`@qa_engineer`, `@security_auditor`, `@critic`, `@sentinel`) a motores de ultra-baja latencia y alta precisión lógica (ej. Groq / Llama 3.3 70B), mientras enruta a los constructores y planificadores (`@developer`, `@architect`, `@scrum_master`) a modelos de ventana de contexto masivo y razonamiento extensivo (ej. Google Gemini 3.6 Flash / Pro, Claude 3.5, OpenAI o modelos locales Qwen 2.5).
3. **`core/orchestration/build_healer.py` & `file_writer.py` (Auto-Healing Determinístico & Diffs)**:
   Desvinculado del orquestador monolítico, el módulo especializado `BuildHealer` supervisa las compilaciones y validaciones sintácticas en subprocesos. Aplica correcciones a nivel de parches y diffs directos en el sistema de archivos, con ciclos de auto-reparación determinística supervisados por interruptores de circuito (*Circuit Breaker*).
4. **`core/local_transformers.py` (Transformadores In-Memory)**:
   Procesadores locales de sintaxis y transformación de datos (Markdown, estructuras JSON, AST Splitter) que operan en memoria sin generar llamadas ni latencia adicional a proveedores LLM externos.
5. **`core/orchestration/product_owner.py` & `task_runner.py` (Sprint 0 & DoD Estricto)**:
   Garantiza que todo backlog inicie de forma obligatoria con la historia **`US-000: Sprint 0 - Infraestructura y Entorno Base`**. Valida en tiempo de ejecución los entregables mediante herramientas reales (`py_compile`, `node --check`, `json.tool`, `bash -n`, `docker compose config`) e impone la **Directiva Anti-Archivos Huérfanos**, conectando activamente cada nuevo componente a los puntos de entrada base del proyecto (`main.py`, `server.js`, `App.tsx`).
6. **`core/event_bus.py` & `core/state.py` (Blackboard & Eventos Asíncronos)**:
   Gobernanza del sistema mediante cerrojos duales hilo/asíncronos (`threading.Lock` y `asyncio.Lock`), persistencia de transacciones en `.jellyfish_project_config.json` y bus de eventos reactivo Pub/Sub para coordinar debates de consenso del enjambre (`CODE_SUBMITTED`, `DEBATE_CYCLE_STARTED`, `CIRCUIT_BREAKER_TRIPPED`).

---

## 🚀 2. Instalación y Configuración Inicial

### Requisitos del Sistema
- **Sistema Operativo**: Linux (Debian/Ubuntu/Fedora/Arch recomendado).
- **Python**: Versión `3.10` o superior (con soporte para creación de entornos `.venv`).
- **Bubblewrap**: Recomendado para el aislamiento seguro (*sandbox*) de la ejecución de plugins y extensiones.
  ```bash
  sudo apt install bubblewrap  # En Debian/Ubuntu
  sudo dnf install bubblewrap  # En Fedora/RHEL / Arch
  ```
- **Ollama**: Servidor local corriendo para modelos de ejecución local y generación de embeddings (ej. `nomic-embed-text`, `qwen2.5-coder`).

### Instalación de Dependencias e Inicialización v6.9.15
Instale las dependencias oficiales y configure la estructura de la agencia, plugins y habilidades con el script principal:
```bash
pip install -r requirements.txt
python setup.py --setup
```

Para auditar y verificar la integridad operacional del enjambre, rutas de sistema y proveedores activos:
```bash
python setup.py --status
```

---

## 🧠 3. Habilidades (Skills), Plugins y Motor RAG Inteligente

En Jellyfish OS v6.9.15 se define una separación conceptual estricta para la expansión cognitiva y operativa del sistema:

- **Skills (Cognición - `.md` o `.py`)**:
  Metodologías, estándares y plantillas de razonamiento inyectadas al prompt del sistema. Clasificadas por agencia (ej. `01_backlog_grooming.md` en Management, `17_react_best_practices.md` en Frontend) para estructurar el flujo analítico y la calidad arquitectónica.
- **Plugins (Acción y Músculo - `.py`)**:
  Módulos ejecutables en Python orientados a llamadas de sistema, red y utilidades automatizadas bajo el control y aislamiento del `PluginInterface` en entornos sandbox Bubblewrap.
- **Motor RAG Auto-Habilitable (Estado OFF por Defecto)**:
  Para optimizar recursos de cómputo y memoria RAM, el motor de indexación vectorial inicia en estado **OFF** por defecto. Al utilizar el comando `/add` sobre un archivo o directorio del proyecto, Jellyfish cambia de manera inteligente a estado **ON**, procesando el código con el analizador AST-Aware por proyecto en bases de datos aisladas y cifradas por hash.

---

## 💡 4. Seguridad, Aislamiento `.venv`, Anti-Huérfanos y Consenso Swarm

### 🛡️ A. Sprint 0 de Infraestructura & Entornos Virtuales Aislados
Todo proyecto desarrollado en v6.9.15 bloquea tareas de negocio hasta completar exitosamente la **`US-000`**, generando los archivos de dependencias y contenedorización. Asimismo, al importar proyectos con código Python vía `/project`, Jellyfish crea y activa automáticamente un entorno virtual local (`.venv`), protegiendo de dependencias cruzadas al sistema host.

### 🧪 B. Validación Estricta por Subproceso & Auto-Healing Determinístico
Cada entregable se somete a validaciones en subprocesos independientes. Cuando se detectan excepciones o fallos en tiempo de compilación, interviene automáticamente el `BuildHealer`, contrastando trazas de error, aplicando diffs precisos y regenerando código con una política determinística.

### ⚖️ C. El Juez & Debates de Consenso en el Enjambre
Durante la ejecución de tareas críticas, los agentes constructores (`@developer`) y auditores (`@qa_engineer`) entablan ciclos de debate en el `Blackboard`. Si no logran consenso de calidad tras superar `MAX_DEBATE_CYCLES` (3 ciclos), interviene automáticamente **El Juez (Circuit Breaker)**, marcando la tarea como bloqueada para salvaguardar la integridad de la base de código.

### 🔍 D. Diagnóstico Forense y Seguridad Sentinel
El agente `@sentinel` realiza un escaneo asíncrono no bloqueante del sistema al iniciar. Si encuentra reportes de caída previos (`jellyfish_error_report_*.md`), efectúa un análisis forense sobre el stacktrace y recomienda acciones preventivas antes de continuar la ejecución de comandos.

---

## 📋 5. Guía Completa de Comandos v6.9.15

| Comando | Sintaxis | Descripción |
| :--- | :--- | :--- |
| `/model` | `/m` o `/model` | Abre el selector interactivo TUI para configurar enrutamiento y modelos de IA en nube o locales. |
| `/config` | `/config <subcomando>` | Panel interactivo en caliente para gestionar API keys, proveedores, endpoints y variables del Swarm. |
| `/auto` | `/auto <descripción>` | Activa el CEO y el Mega Planner, planificando e iniciando el ciclo autónomo Scrum de desarrollo. |
| `/research` | `/research <consulta>` | Desata un pipeline de 4 fases para investigar y sintetizar documentación técnica compleja con el RAG. |
| `/agent` | `/agent` o `@<nombre>` | Configura agencias de agentes o cambia instantáneamente de rol activo (ej. `@developer`, `@qa_engineer`). |
| `/skill` | `/skill` | Consulta e inyecta dinámicamente macros y habilidades automatizadas desde el registro de skills. |
| `/plugin` | `/plugin <nombre> [args]` | Ejecuta un plugin de extensión dentro de un contenedor seguro de aislamiento Bubblewrap. |
| `/add` | `/add <ruta>` | Ingresa archivos en la memoria activa del chat o habilita e indexa carpetas completas al RAG con AST Splitter. |
| `/rag` | `/rag <subcomando>` | Control del índice vectorial: `status`, `reindex`, `remove` o `clear` por proyecto activo. |
| `/project` | `/project <ruta>` | Inicializa o carga un proyecto de software, creando un entorno aislado `.venv` con bloqueos de concurrencia. |
| `/compile` | `/compile` | Ejecuta la verificación de build y compilación en el entorno activo con supervisión del BuildHealer. |
| `/gon` / `/goff`| `/gon` o `/goff` | Activa o deshabilita la asistencia didáctica de guías ágiles y tableros durante la sesión de chat. |
| `/ignore` | `/ignore <subcomando>` | Gestiona listas de exclusión de archivos `.jellyfishignore` para limpiezas en la indexación del RAG. |
| `/errors` / `/d`| `/errors` | Abre el monitor de excepciones de la sesión TUI con soporte para diagnóstico de crash bugs. |
| `/status` | `/status` o `/info` | Despliega un panel con el diagnóstico completo de la configuración, variables de estado y recursos del sistema. |
| `/purge` / `/c` | `/purge` o `/clear` | `/clear` limpia la terminal visual; `/purge` efectúa amnesia total borrando memoria activa e índice vectorial. |
| `/help` / `/h` | `/help` | Muestra el manual de referencia rápida y comandos integrados de Jellyfish OS v6.9.15. |
| `/exit` | `/exit` | Cierra Jellyfish de forma ordenada, apagando servidores locales en segundo plano (`ollama`) y sincronizando historial. |

---

## 🔑 6. Variables de Entorno del Sistema (`.env`)

| Variable | Valor por Defecto | Propósito y Configuración en v6.9.15 |
| :--- | :--- | :--- |
| `JELLYFISH_PROVIDER` | `ollama` | Proveedor principal de la IA (`ollama`, `gemini`, `openai`, `claude`, `groq`, `openrouter`, `deepseek`). |
| `JELLYFISH_MODEL` | `qwen2.5-coder:latest` | Modelo principal designado para ejecución de código y desarrollo del agente ejecutor. |
| `JELLYFISH_PLANNER_MODEL` | `gemini-3.6-flash` | Modelo de amplio contexto asignado al Lead Planner / CEO en la arquitectura Swarm. |
| `JELLYFISH_QA_MODEL` | `llama-3.3-70b-versatile` | Modelo para auditores de calidad y crítica, priorizado para baja latencia (Groq/Ollama). |
| `JELLYFISH_USE_HYBRID` | `1` | Activa (`1`) o desactiva (`0`) el enrutamiento heterogéneo inteligente del `SwarmRouter`. |
| `JELLYFISH_CONTEXT_LIMIT` | `8192` | Cantidad máxima de tokens en ventana deslizante para preservación y truncamiento del historial. |
| `JELLYFISH_PLUGIN_UNSAFE` | `0` | Si se establece en `1`, desactiva el sandbox Bubblewrap en la ejecución de plugins (bajo riesgo del usuario). |
| `JELLYFISH_RAG_THRESHOLD` | `1.2` | Umbral de distancia euclidiana mínima para el filtrado de similitud en RAG vectorial. |
| `JELLYFISH_EMBED_MODEL` | `nomic-embed-text` | Modelo vectorial utilizado en Ollama para generar embeddings de fragmentos de código. |

---

*Última actualización de especificación técnica: 2026-08-04 17:15:00 — Arquitectura: REPL Interactivo + Enrutador Heterogéneo Swarm Multi-Agencia*
