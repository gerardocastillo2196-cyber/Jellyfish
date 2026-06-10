"""Skill: Geopolitical Risk Analysis — Migración automática de 34_geopolitical_risk_analysis.md."""
from core.skills.base import BaseSkill


class GeopoliticalRiskAnalysisSkill(BaseSkill):
    """Geopolitical Risk Analysis."""

    name = "Geopolitical Risk Analysis"
    agency = "Research"
    keywords = ['geopolítica', 'riesgo país', 'conflicto', 'comercio', 'regulación']

    def get_instructions(self) -> str:
        return """## Geopolitical Risk Analysis

**Agencia:** Research
**Rol Sugerido:** @risk_analyst

## Objetivo de la Skill
Aplica analisis PESTEL para evaluar riesgos geopoliticos que afectan operaciones de negocio: politicos, economicos, sociales, tecnologicos, ambientales, y legales.

## Metodologia de Razonamiento (Paso a Paso)
1. **Political (P)**:
   - Government stability
   - Trade policies y tariffs
   - Sanctions y restrictions
2. **Economic (E)**:
   - Currency fluctuations
   - Inflation rates
   - GDP growth projections
3. **Social (S)**:
   - Demographics trends
   - Cultural considerations
   - Labor market dynamics
4. **Technological (T)**:
   - Digital infrastructure
   - IP protection regimes
5. **Environmental (E)**:
   - Climate risks
   - ESG regulations
6. **Legal (L)**:
   - Contract enforcement
   - Compliance requirements
7. **Scenario planning**: Best/base/worst cases.
8. **Risk scoring**: Impact x Likelihood matrix.

## Anti-Patrones
- Analyzing only current situation.
- Missing interconnections between PESTEL factors.
- Treating all markets the same way.
- Ignoring cultural nuances.
- Overreacting to media headlines.

## Formato de Salida Obligatorio
```markdown
# Geopolitical Risk Analysis - [Country/Region]

**Analysis Date:** [YYYY-MM-DD]

## Executive Summary
**Overall Risk Level:** 🔴 HIGH | 🟠 MEDIUM-HIGH | 🟡 MEDIUM | 🟢 LOW
**Key Threats:** [List 3-5]
**Key Opportunities:** [List 2-3]

## PESTEL Analysis

### Political
| Factor | Status | Trend | Impact | Risk Score |
|--------|--------|-------|--------|------------|
| Government stability | Stable | -> | Neutral | 3/10 |

### Economic
| Factor | Status | Trend | Impact | Risk Score |
|--------|--------|-------|--------|------------|
| Currency stability | Volatile | -> | Negative | 7/10 |

## Risk Heat Map
[Matrix visualization]

## Recommendations
### Immediate Actions (0-30 days)
1. [Action]

### Medium-term Actions (30-90 days)
1. [Action]
```"""
