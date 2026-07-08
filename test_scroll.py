from prompt_toolkit.formatted_text import ANSI
import re

ANSI_CLEAN_RE = re.compile(r'\x1b\[[\d;?]*[a-ln-zABCDEFGJKHST]')
_log_text = ""

def append_log(text):
    global _log_text
    cleaned_text = ANSI_CLEAN_RE.sub('', text)
    for char in cleaned_text:
        if char == '\r':
            last_nl = _log_text.rfind('\n')
            if last_nl != -1:
                _log_text = _log_text[:last_nl + 1]
            else:
                _log_text = ""
        else:
            _log_text += char
    
    if len(_log_text) > 100_000:
        _log_text = _log_text[-100_000:]

guide_lines = [
    "",
    "==============================================================",
    "      🪼 GUÍA DE CONSTRUCCIÓN MULTI-AGENCIA JELLYFISH OS",
    "==============================================================",
    "",
    "ℹ️  ESTADO ACTUAL DEL PROYECTO: VINCULADO",
    "  • Metodología activa: SCRUM  • Agencia activa: DEFAULT",
    "",
    "--------------------------------------------------------------",
    "🪼 1. ARQUITECTURA MULTI-AGENCIA (JELLYFISH OS v6.9.3)",
    "Jellyfish OS agrupa a los agentes en agencias especializadas:",
    "  - DEVELOPMENT: Ingeniería de software, bugs, arquitectura y desarrollo.",
    "  - MARKETING: Estrategias de venta, SEO, redacción de copy y contenido.",
    "  - RESEARCH: Investigación profunda, análisis de mercado y ciencia de datos.",
    "  - MANAGEMENT: Orquestación, Scrum Master y Product Owner de proyectos.",
    "",
    "--------------------------------------------------------------",
    "🤖 2. EL CEO CLASIFICADOR (AGENCY ORCHESTRATOR)",
    "Al ejecutar /auto 'tu idea', el CEO clasifica tu prompt y lo delega",
    "a la agencia correspondiente para evitar interferencias entre tableros.",
    "",
    "--------------------------------------------------------------",
    "📋 3. TABLEROS DE TRABAJO DINÁMICOS",
    "Cada agencia gestiona sus tareas en tableros separados:",
    "  - Desarrollo / Default -> DEV_BOARD.md (o SPRINT_BOARD.md)",
    "  - Marketing -> MKT_BOARD.md",
    "  - Investigación -> RESEARCH_BOARD.md",
    "",
    "--------------------------------------------------------------",
    "🔄 4. HANDOFFS INTER-AGENCIA (TRASPASOS)",
    "Los Scrum Masters coordinan entregables cruzados. Si una tarea",
    "excede la agencia activa, planifican entregables como insumos para otra.",
    "",
    "--------------------------------------------------------------",
    "🚀 5. GUÍA DE TRABAJO PASO A PASO",
    "  PASO 1: Vincular o Crear un Proyecto",
    "  • Ejecuta /project new ./mi-proyecto para inicializar el espacio.",
    "",
    "  PASO 2: Navegar y Gestionar Agencias",
    "  • Ejecuta /agency para ver el catálogo disponible.",
    "  • Ejecuta /agency switch 'nombre' para cambiar de departamento.",
    "  • El autocompletador @ se limita a los agentes del departamento activo.",
    "",
    "  PASO 3: Lanzar el Pipeline Autónomo",
    "  • Escribe: /auto 'Tu idea de proyecto'",
    "    - Ejemplo: /auto Diseña una landing page y escribe su campaña",
    "  • Fase 1 (PO): Diseña BACKLOG.md con los requerimientos.",
    "  • Fase 2 (SM): Desglosa las tareas en el tablero.",
    "  • Fase 3 (Dev): Ejecuta autónomamente la codificación y pruebas.",
    "",
    "  PASO 4: Interactuar con Agentes de la Agencia",
    "  • Invoca personalidades con @agente (ej. @developer).",
    "  • Usa /add 'archivo' para cargarlo en el contexto del chat.",
    "",
    "--------------------------------------------------------------",
    "👉 ¿Quieres ocultar esta guía? Escribe /goff · Escribe /help para el manual.",
    "==============================================================",
    ""
]

for line in guide_lines:
    append_log(line + "\n")

print("Lines count:", len(_log_text.splitlines()))

