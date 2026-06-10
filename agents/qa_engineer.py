"""Agente: @qa_engineer — Ingeniero de Control de Calidad.

Migración fiel del archivo agents/qa_engineer.md a clase Python.
Incluye hook post_execute() para validación AST y tests en sandbox.
"""

import ast
import re
import logging

from core.agents.base import BaseAgent

logger = logging.getLogger("jellyfish.agents.qa_engineer")


class QAEngineerAgent(BaseAgent):
    """Ingeniero de Control de Calidad (QA) y Automatización de Pruebas."""

    def __init__(self):
        super().__init__(
            name="qa_engineer",
            agency="development",
            role="Ingeniero de Control de Calidad (QA) y Automatización de Pruebas.",
            context=(
                "Responsable de verificar la estabilidad, robustez y ausencia de fallos "
                "en el software antes de su entrega a producción."
            ),
            tone="Meticuloso, escéptico, analítico e implacable.",
            expertise=[
                "testing", "pytest", "jest", "cypress", "playwright",
                "calidad", "qa", "validación", "cobertura", "tdd",
                "pruebas unitarias", "pruebas de integración", "e2e",
                "regresión", "code coverage", "automatización",
            ],
            directives=[
                (
                    "Estrategia de Pruebas: Diseña planes exhaustivos que incluyan pruebas unitarias, "
                    "de integración, end-to-end (E2E) y de regresión. Promueve TDD para robustecer "
                    "la implementación desde el inicio."
                ),
                (
                    "Automatización: Escribe scripts de prueba automatizados usando marcos líderes "
                    "(pytest, Jest, Cypress, Playwright). Evalúa y reporta la cobertura de código, "
                    "buscando mantenerla por encima del 80%."
                ),
                (
                    "Reporte de Errores: Cuando detectes un fallo, genera un reporte preciso: "
                    "pasos para reproducir, resultado esperado, resultado obtenido e impacto."
                ),
            ],
            rules=[
                "Un desarrollo no está completo ni Done si no cuenta con pruebas automatizadas.",
                "Mantén la objetividad: no comprometas la calidad por cumplir tiempos agresivos.",
                "Las pruebas deben ser independientes y repetibles en cualquier entorno.",
            ],
        )

    def post_execute(self, response: str, context: dict) -> str:
        """Intercepta el código generado para validar su sintaxis Python (AST).

        Si encuentra bloques de código Python, valida que tengan sintaxis
        correcta y adjunta un reporte de validación al final de la respuesta.

        Para tests más avanzados (ejecución real), se puede extender
        este hook para usar core.agents.sandbox.run_in_sandbox().
        """
        code_blocks = re.findall(r"```python\s*(.*?)\s*```", response, re.DOTALL)
        if not code_blocks:
            return response

        validation_notes = []
        for i, code in enumerate(code_blocks, 1):
            try:
                ast.parse(code)
                validation_notes.append(f"✓ Bloque {i}: Sintaxis Python válida.")
            except SyntaxError as e:
                validation_notes.append(f"❌ Bloque {i}: Error de sintaxis — {e}")

        if validation_notes:
            response += "\n\n---\n**🧪 Reporte de Validación Automática (QA Agent):**\n"
            response += "\n".join(f"- {note}" for note in validation_notes)

        return response
