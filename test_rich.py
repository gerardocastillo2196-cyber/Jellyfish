import sys
from rich.console import Console

console = Console(force_terminal=True, width=60)

guide_lines = [
    "--------------------------------------------------------------",
    "📋 3. TABLEROS DE TRABAJO DINÁMICOS",
    "Cada agencia gestiona sus tareas en tableros separados:",
    "  - Desarrollo / Default -> DEV_BOARD.md (o SPRINT_BOARD.md)",
    "  - Marketing -> MKT_BOARD.md",
    "  - Investigación -> RESEARCH_BOARD.md",
    "",
    "--------------------------------------------------------------",
]

with open("output.txt", "wb") as f:
    class Redirector:
        def write(self, data):
            if isinstance(data, str):
                f.write(data.encode('utf-8'))
            else:
                f.write(data)
        def flush(self):
            pass
        def isatty(self):
            return True

    original_stdout = sys.stdout
    sys.stdout = Redirector()
    try:
        for line in guide_lines:
            console.print(line)
    finally:
        sys.stdout = original_stdout

