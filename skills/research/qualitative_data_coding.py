"""Skill: Qualitative Data Coding — Migración automática de 35_qualitative_data_coding.md."""
from core.skills.base import BaseSkill


class QualitativeDataCodingSkill(BaseSkill):
    """Qualitative Data Coding."""

    name = "Qualitative Data Coding"
    agency = "Research"
    keywords = ['cualitativo', 'codificación', 'entrevista', 'tema', 'categoría', 'grounded theory']

    def get_instructions(self) -> str:
        return """## Qualitative Data Coding

**Agencia:** Research
**Rol Sugerido:** @researcher

## Objetivo de la Skill
Aplica tecnicas de codificacion cualitativa (abierta, axial, selectiva) para analizar datos de entrevistas, grupos focales, o notas de campo. Transforma texto no estructurado en insights tematicos accionables.

## Metodologia de Razonamiento (Paso a Paso)
1. **Preparacion de datos**:
   - Transcribir entrevistas verbatim
   - Limpiar identifiers (anonymize)
2. **Codificacion abierta**:
   - Leer linea por linea
   - Asignar codigos cortos a cada concepto
   - Usar in-vivo codes quando possivel
3. **Codificacion axial**:
   - Agrupar codigos en categorias
   - Identificar relationships entre categorias
   - Find central category
4. **Codificacion selectiva**:
   - Integrate categories around core phenomenon
   - Develop theory/model
5. **Saturation check**: Quando nuevos datos no generan nuevos codigos.
6. **Reliability check**: Dos coders independientes.

## Anti-Patrones
- Empezar con categorias predefinidas.
- Usar codigos muy amplios.
- No reach saturation.
- Ignorar datos que contradicen initial hypothesis.
- Over-interpreting small samples.

## Formato de Salida Obligatorio
```markdown
# Qualitative Analysis Report

**Study:** [Title]
**Method:** [Interviews / Focus Groups]
**Sample:** [N participants]

## Code Frequency
| Code | Times Used | % of Responses |
|------|------------|----------------|
| Trust issues | 45 | 78% |
| Integration difficulty | 38 | 66% |

## Thematic Categories

### Category 1: [Theme Name]
**Definition:** [How this category is defined]
**Frequency:** N occurrences

**Representative Quotes:**
> "[Quote 1]" - [Participant ID]

**Relationships:** [How this connects to other categories]

## Theoretical Model
[A visual model]

## Key Findings for [Product/Decision]
1. **[Finding]** - Supported by [N] occurrences
```"""
