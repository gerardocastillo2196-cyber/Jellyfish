"""Skill: A/B Test Planning — Migración automática de 28_ab_test_planning.md."""
from core.skills.base import BaseSkill


class AbTestPlanningSkill(BaseSkill):
    """A/B Test Planning."""

    name = "A/B Test Planning"
    agency = "Marketing"
    keywords = ['a/b test', 'experimento', 'hipótesis', 'variante', 'conversión', 'significancia']

    def get_instructions(self) -> str:
        return """## A/B Test Planning

**Agencia:** Marketing
**Rol Sugerido:** @growth_hacker

## Objetivo de la Skill
Diseña experimentos A/B con hipotesis claras, metricas de exito definidas, y analisis estadistico riguroso. Calcula sample size, duracion, y evita common pitfalls que invalidan resultados.

## Metodologia de Razonamiento (Paso a Paso)
1. **Formulate hypothesis**: "Creemos que [cambio] resultara en [metrica] porque [razon]".
2. **Define primary metric**: La metrica principal que determina exito.
3. **Secondary metrics**: Metricas adicionales a trackear.
4. **Calculate sample size**:
   - Baseline conversion rate
   - Minimum Detectable Effect (MDE)
   - Statistical power (80%)
   - Confidence level (95%)
5. **Calculate duration**:
   - Duration = Sample Size / Daily Visitors x 2
6. **Randomization unit**: User-level vs page-level.
7. **Statistical analysis**: T-test, chi-square, or bayesian methods.

## Anti-Patrones
- Testing too many variants simultaneously.
- Stopping test cuando resultados "se ven bien".
- Not defining primary metric antes del test.
- Ignoring seasonality.
- Not documenting exclusions.
- Trusting results sin statistical significance.

## Formato de Salida Obligatorio
```markdown
# A/B Test Specification

**Test Name:** [Descriptive name]
**Date Created:** [YYYY-MM-DD]

## Hypothesis
**We believe that** [changing element]
**will result in** [expected outcome]
**because** [rationale]

## Test Design
| Element | Control | Treatment A |
|---------|---------|-------------|
| CTA Text | "Sign Up Now" | "Get Started Free" |
| Button Color | Blue | Green |

## Success Metrics
**Primary:** Conversion Rate (Sign Up) - Absolute +2% MDE
**Secondary:** Click-through Rate, Bounce Rate

## Statistical Parameters
| Parameter | Value |
|-----------|-------|
| Confidence Level | 95% |
| Statistical Power | 80% |
| Baseline Conversion | 3.2% |
| Estimated Sample Size | 12,500 per variant |
| Test Duration | 14 days |
```"""
