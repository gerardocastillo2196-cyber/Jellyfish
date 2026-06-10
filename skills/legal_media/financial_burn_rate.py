"""Skill: Financial Burn Rate — Migración automática de 44_financial_burn_rate.md."""
from core.skills.base import BaseSkill


class FinancialBurnRateSkill(BaseSkill):
    """Financial Burn Rate."""

    name = "Financial Burn Rate"
    agency = "Legal & Media"
    keywords = ['burn rate', 'runway', 'financiero', 'gasto', 'presupuesto', 'cashflow']

    def get_instructions(self) -> str:
        return """## Financial Burn Rate

**Agencia:** Legal
**Rol Sugerido:** @cfo

## Objetivo de la Skill
Calcula y proyecta burn rate (tasa de consumo de capital), runway (tiempo hasta quedarse sin efectivo), y cash flow para startups y empresas en crecimiento. Identifica puntos de inflection y acciones recomendadas.

## Metodologia de Razonamiento (Paso a Paso)
1. **Calculate Gross Burn Rate**:
   - Monthly cash outflows
   - Fixed costs (salaries, rent, software)
   - Variable costs (COGS, hosting, contractors)
2. **Calculate Net Burn Rate**:
   - Gross Burn - Monthly Revenue
   - Net Burn = Cash Outflows - Cash Inflows
3. **Calculate Runway**:
   - Runway = Current Cash / Net Burn Rate
   - Consider seasonal variations
   - Model different scenarios
4. **Cash Flow Projections**:
   - 13-week cash flow model (rolling)
   - Scenario: Conservative (80% of expected revenue)
   - Scenario: Base Case
   - Scenario: Optimistic
5. **Identify Runway Triggers**:
   - 12 months runway: Green
   - 9 months: Yellow - start fundraising
   - 6 months: Orange - accelerate fundraising
   - 3 months: Red - immediate action needed
6. **Expense Optimization**:
   - Identify largest expense categories
   - Model cost reductions with impact
   - Prioritize by ROI

## Anti-Patrones
- Calculating burn sin incluir all obligations.
- Assuming linear revenue growth.
- Not modeling seasonality.
- Ignoring founder salary adjustments.
- No contingency buffer.
- Waiting too long to start fundraising.

## Formato de Salida Obligatorio
```markdown
# Financial Burn Rate Analysis - [Company Name]

**Analysis Date:** [YYYY-MM-DD]
**Cash Position:** $[X,XXX,XXX]

## Current Financials

### Monthly Burn Rate
| Category | Monthly Amount | % of Total |
|----------|----------------|-------------|
| Salaries & Benefits | $150,000 | 68% |
| Software & Tools | $15,000 | 7% |
| Marketing | $25,000 | 11% |
| Hosting & Infrastructure | $12,000 | 5% |
| Professional Services | $10,000 | 5% |
| Other | $8,000 | 4% |
| **Total Gross Burn** | **$220,000** | **100%** |

### Net Burn Rate
| Metric | Amount |
|--------|--------|
| Gross Burn | $220,000 |
| Monthly Revenue | $80,000 |
| **Net Burn** | **$140,000** |

## Runway Analysis
| Scenario | Net Burn | Months of Runway |
|---------|----------|------------------|
| Current | $140,000 | 14.3 months |
| Conservative (-20% revenue) | $156,000 | 12.8 months |
| Growth (+30% revenue) | $116,000 | 17.2 months |

## Runway Triggers
| Status | Trigger | Action |
|--------|---------|--------|
| 🟢 Green | 12+ months | Continue executing |
| 🟡 Yellow | 9-12 months | Begin fundraising process |
| 🟠 Orange | 6-9 months | Accelerate fundraising |
| 🔴 Red | < 6 months | Immediate action required |

## 13-Week Cash Flow Forecast
| Week | Projected Inflows | Projected Outflows | Net | Cumulative Cash |
|------|-------------------|-------------------|-----|----------------|
| 1 | $30,000 | $220,000 | -$190,000 | $[current] |
| 2 | $25,000 | $215,000 | -$190,000 | ... |

## Recommendations
1. **Reduce burn by 15%** ($33K/month) through contractor reduction
2. **Extend runway to 18 months** to reach Series A milestones
3. **Target fundraising** to start immediately given current runway
4. **Review pricing** for potential ARPU increase

## Scenario: 15% Cost Reduction
| Category | Reduction | New Monthly |
|----------|-----------|-------------|
| Contractors | $15,000 | - |
| Marketing | $10,000 | - |
| Software | $5,000 | - |
| **New Net Burn** | **$110,000** | **18 months runway** |
```"""
