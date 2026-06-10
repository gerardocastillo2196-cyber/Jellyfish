"""Skill: Historical Precedent Search — Migración automática de 37_historical_precedent_search.md."""
from core.skills.base import BaseSkill


class HistoricalPrecedentSearchSkill(BaseSkill):
    """Historical Precedent Search."""

    name = "Historical Precedent Search"
    agency = "Research"
    keywords = ['precedente', 'historia', 'caso similar', 'benchmarking', 'analogía']

    def get_instructions(self) -> str:
        return """## Historical Precedent Search

**Agencia:** Research
**Rol Sugerido:** @research_historian

## Objetivo de la Skill
Busca analogias historicas para informar decisiones de producto o estrategia. Analiza casos similares del pasado para extraer insights sobre outcomes probables, riesgos, y patterns que se repiten.

## Metodologia de Razonamiento (Paso a Paso)
1. **Define the problem**: Clarificar que decision o problema necesita context historico.
2. **Identify analog candidates**:
   - Same industry, different time
   - Different industry, same dynamics
   - Similar technological shifts
3. **Data collection**:
   - Primary sources (documents, interviews)
   - Secondary sources (academic, journalistic)
4. **Analyze case structure**:
   - What triggered the change?
   - Who were the key players?
   - What actions were taken?
   - What were the outcomes?
5. **Identify lessons**:
   - What worked?
   - What failed?
   - What patterns are universal?
6. **Assess applicability**:
   - What differs between past and present?

## Anti-Patrones
- Cherry-picking analogies que support pre-existing conclusion.
- Ignoring differences between past and present.
- Using analogy as proof instead of insight.
- Not considering multiple analogies.

## Formato de Salida Obligatorio
```markdown
# Historical Precedent Analysis

**Current Problem:** [Problem we're trying to solve]

## Analogical Cases Identified

### Case 1: [Historical Event/Company]
**Time Period:** [Year range]
**Similarity to Current Situation:** 75%

| Dimension | Historical Case | Current Situation | Similarity |
|-----------|----------------|-------------------|-----------|
| Technology | [Description] | [Description] | High |
| Market | [Description] | [Description] | Medium |

**Actions Taken:**
1. [Action 1]
2. [Action 2]

**Key Lessons:**
1. **[Lesson with evidence]**
2. **[Lesson with evidence]**

## Probability Assessment
**Based on historical precedent:**
| Outcome | Historical Base Rate | Our Adjustment | Estimated |
|---------|---------------------|----------------|-----------|
| [Positive outcome] | 60% | -10% | 50% |
```"""
