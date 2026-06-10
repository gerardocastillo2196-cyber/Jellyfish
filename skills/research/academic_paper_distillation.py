"""Skill: Academic Paper Distillation — Migración automática de 33_academic_paper_distillation.md."""
from core.skills.base import BaseSkill


class AcademicPaperDistillationSkill(BaseSkill):
    """Academic Paper Distillation."""

    name = "Academic Paper Distillation"
    agency = "Research"
    keywords = ['paper', 'artículo', 'investigación', 'académico', 'resumen', 'abstract']

    def get_instructions(self) -> str:
        return """## Academic Paper Distillation

**Agencia:** Research
**Rol Sugerido:** @research_analyst

## Objetivo de la Skill
Extrae informacion clave de papers academicos: metodologia, resultados, limitaciones, y sesgos. Distila conocimiento complejo en resumenes accionables para decisiones de negocio o producto.

## Metodologia de Razonamiento (Paso a Paso)
1. **Quick scan**:
   - Title, abstract, conclusions
   - Authors y publication venue
   - Citation count y recency
2. **Read with purpose**:
   - What question does it answer?
   - What methodology did they use?
   - What did they find?
3. **Methodology analysis**:
   - Study design (RCT, observational)
   - Sample size y demographics
   - Statistical methods used
4. **Results synthesis**:
   - Key findings principais
   - Effect sizes (not just p-values)
5. **Bias identification**:
   - Selection bias
   - Funding sources conflicts
   - Publication bias
6. **Applicability assessment**: Results apply to our context?

## Anti-Patrones
- Trusting conclusions sin evaluar metodologia.
- Ignoring limitations section.
- Treating correlation as causation.
- Generalizing mas alla de la poblacion del estudio.
- Not checking if findings replicated.

## Formato de Salida Obligatorio
```markdown
# Paper Distillation

**Paper Title:** [Full title]
**Authors:** [First author et al.]
**Publication:** [Journal]
**Year:** [YYYY]

## Quick Summary
[One sentence capturing the main finding]

## Research Question
[What specific question did the paper address?]

## Methodology
**Study Design:** [RCT, longitudinal cohort]
**Sample:** [N, demographics]
**Statistical Methods:** [Tests used]

## Key Findings
| Finding | Effect Size | Significance | Confidence |
|---------|------------|--------------|------------|
| [Finding 1] | [d=0.45] | [p<0.001] | [95% CI] |

## Limitations
- [ ] [Limitation 1]
- [ ] [Limitation 2]

## Bias Assessment
| Bias Type | Risk | Notes |
|-----------|------|-------|
| Selection bias | Medium | [Explanation] |

## Actionable Insights
1. **[Insight]**
   - **Confidence:** High/Medium/Low
```"""
