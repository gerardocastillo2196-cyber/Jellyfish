"""Skill: Cap Table Simulation — Migración automática de 42_cap_table_simulation.md."""
from core.skills.base import BaseSkill


class CapTableSimulationSkill(BaseSkill):
    """Cap Table Simulation."""

    name = "Cap Table Simulation"
    agency = "Legal & Media"
    keywords = ['cap table', 'equity', 'dilución', 'ronda', 'inversión', 'vesting', 'acciones']

    def get_instructions(self) -> str:
        return """## Cap Table Simulation

**Agencia:** Legal
**Rol Sugerido:** @finance_analyst

## Objetivo de la Skill
Simula escenarios de cap table (capitalization table) para modelar dilucion en diferentes rondas de financiacion, employee option pools, exits, y acquihires. Ayuda en decisiones de fundraising y equity planning.

## Metodologia de Razonamiento (Paso a Paso)
1. **Capturar estructura actual**:
   - Founders equity (vesting schedules)
   - Existing investors y shares owned
   - Employee option pool (pre-money vs post-money)
   - Outstanding convertible notes
2. **Modelar escenarios de financiacion**:
   - Pre-money valuation inputs
   - Investment amount y price per share
   - New option pool creation (option pool shuffle)
3. **Calcular dilucion**:
   - Dilucion para founders = (New Shares / Total Post-Money Shares)
   - Dilucion por ronda
   - Fully diluted vs actual ownership
4. **Scenario analysis**:
   - Down round (dilucion extra para existing shareholders)
   - Liquidation preferences (1x, 2x, participating)
   - MFN clauses en convertible notes
5. **Exit modeling**:
   - IPO: Shares x price
   - Acquisition: Net proceeds segun preferences
   - Waterfall analysis
6. **ESOP planning**:
   - Pool size as % of fully diluted cap table
   - Cliff periods y vesting schedules
   - Early exercise options

## Anti-Patrones
- Ignoring option pool dilution en pre-money.
- Assuming linear dilution.
- Not modeling liquidation preferences.
- Forgetting about anti-dilution provisions.
- Miscalculating fully diluted shares.

## Formato de Salida Obligatorio
```markdown
# Cap Table Simulation - [Company Name]

**Date:** [YYYY-MM-DD]
**Fully Diluted Shares:** [X,XXX,XXX]

## Current Cap Table
| Shareholder | Shares | % Ownership | Fully Diluted |
|------------|--------|-------------|---------------|
| Founder A | 4,000,000 | 40% | 40% |
| Founder B | 2,000,000 | 20% | 20% |
| Investor X | 2,000,000 | 20% | 20% |
| ESOP Pool | 1,000,000 | 10% | 10% |

## Scenario: Series A Round

### Inputs
| Parameter | Value |
|-----------|-------|
| Pre-money Valuation | $10,000,000 |
| Investment Amount | $3,000,000 |
| New Option Pool | 1,500,000 shares |
| Price per Share | $2.00 |

### Post-Round Cap Table
| Shareholder | Pre-Round Shares | Post-Round Shares | Diluted % |
|-------------|-----------------|-------------------|-----------|
| Founder A | 4,000,000 | 4,000,000 | 26.7% |
| Founder B | 2,000,000 | 2,000,000 | 13.3% |
| Investor X | 2,000,000 | 2,000,000 | 13.3% |
| ESOP Pool (new) | 1,000,000 | 2,500,000 | 16.7% |
| Series A | 0 | 1,500,000 | 10.0% |
| **Total** | **9,000,000** | **15,000,000** | **100%** |

### Founder Dilution Summary
| Round | Founder A | Founder B |
|-------|-----------|----------|
| Post-Series A | 26.7% | 13.3% |
| Post-Series B (假设$20M @ $5/sh) | 16.8% | 8.4% |
| Post-IPO | 14.2% | 7.1% |

## Exit Waterfall (at $50M acquisition)
| Tranche | Preference | Proceeds | Remaining |
|---------|------------|----------|-----------|
| Series A (1x) | $3,000,000 | $3,000,000 | $47,000,000 |
| Remaining pro-rata | Distributed | Per ownership | - |
```"""
