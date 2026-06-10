"""Skill: Game Economy Balancing — Migración automática de 47_game_economy_balancing.md."""
from core.skills.base import BaseSkill


class GameEconomyBalancingSkill(BaseSkill):
    """Game Economy Balancing."""

    name = "Game Economy Balancing"
    agency = "Legal & Media"
    keywords = ['economía', 'balance', 'juego', 'moneda', 'reward', 'progresión', 'game design']

    def get_instructions(self) -> str:
        return """## Game Economy Balancing

**Agencia:** Media
**Rol Sugerido:** @economy_designer

## Objetivo de la Skill
Diseña y balancea economias de juegos con focus en sinks (donde el dinero sale del sistema), faucets (donde entra), progression pacing, y drop rates que mantienen engagement sin pay-to-win dynamics.

## Metodologia de Razonamiento (Paso a Paso)
1. **Define economy goals**:
   - Primary: Engagement (time to progression)
   - Secondary: Monetization potential
   - Constraints: No pay-to-win, ethical monetization
2. **Map gold flow**:
   - **Faucets** (inflow sources):
     - Quest rewards
     - Selling items
     - Daily login bonuses
     - Achievement rewards
   - **Sinks** (outflow destinations):
     - Equipment upgrades
     - Consumables
     - Fast travel
     - Crafting materials
     - Housing/decoration
3. **Calculate equilibrium**:
   - Target: Sinks >= Faucets long-term
   - Monitor: Per-session gold accumulation
   - Adjust: If players accumulate excess
4. **Progression pacing**:
   - Time-to-level curves
   - milestone rewards
   - Soft caps and hard caps
5. **Drop rate design**:
   - Common: 50-70%
   - Uncommon: 20-30%
   - Rare: 5-10%
   - Epic: 1-3%
   - Legendary: < 1%
   - Consider pity systems para fairness
6. **Real-money integration**:
   - Premium currency vs gameplay currency
   - Exchange rates
   - Ethical considerations

## Anti-Patrones
- Sink/Faucet imbalance causing inflation.
- Too many faucets, devaluing rewards.
- No sinks, unlimited gold accumulation.
- Pay-to-win mechanics alienating players.
- Grind walls that feel unfair.
- No catch-up mechanisms para new players.

## Formato de Salida Obligatorio
```markdown
# Game Economy Balance - [Game Name]

**Version:** [X.Y]
**Last Updated:** [YYYY-MM-DD]

## Economy Overview
**Primary Currency:** Gold
**Premium Currency:** Gems
**Exchange Rate:** 100 Gold = 1 Gem

## Gold Flow Analysis

### Faucets (Monthly Inflow)
| Source | Amount | Frequency | % of Total |
|--------|--------|-----------|------------|
| Daily quests | 5,000 | Daily | 25% |
| Main story | 50,000 | Per chapter | 20% |
| Side quests | 20,000 | Per quest | 10% |
| Selling loot | 15,000 | Average | 8% |
| Achievement unlocks | 30,000 | Milestones | 15% |
| **Total** | **200,000** | - | **100%** |

### Sinks (Monthly Outflow)
| Sink | Amount | Frequency | % of Total |
|------|--------|-----------|------------|
| Equipment upgrades | 80,000 | Per upgrade | 45% |
| Consumables | 40,000 | Per dungeon | 22% |
| Fast travel | 10,000 | Per use | 6% |
| Housing items | 25,000 | Per purchase | 14% |
| Crafting | 15,000 | Per craft | 8% |
| Repairs | 10,000 | Per death | 5% |
| **Total** | **180,000** | - | **100%** |

## Balance Sheet
| Metric | Current | Target | Status |
|--------|---------|--------|--------|
| Net Gold/Month | +20,000 | ~0 | ⚠️ Inflation Risk |
| Gold per Active Session | 2,500 | 1,500 | ⚠️ Too Generous |

## Drop Rates

### Equipment Drop Table
| Rarity | Drop Rate | Avg Kills to Get |
|--------|-----------|------------------|
| Common | 60% | 1-2 |
| Uncommon | 25% | 4 |
| Rare | 10% | 10 |
| Epic | 4% | 25 |
| Legendary | 1% | 100 |

### Pity System
**Guaranteed Epic after:** 50 kills without Epic
**Guaranteed Legendary after:** 500 kills without Legendary

## Progression Pacing

### Time to Max Level
| Player Type | Days to Max | Hours/Day |
|-------------|-------------|-----------|
| Casual | 90 days | 1 hour |
| Regular | 45 days | 2 hours |
| Hardcore | 20 days | 4 hours |

### Milestone Rewards
| Level | Gold Reward | Bonus Item |
|-------|-------------|------------|
| 10 | 5,000 | Starter mount |
| 20 | 15,000 | Rare weapon |
| 30 | 30,000 | Epic armor set |
| 40 | 50,000 | Legendary accessory |
| 50 | 100,000 | Exclusive title |

## Recommendations
1. **Reduce quest gold rewards by 15%** to approach equilibrium
2. **Add premium housing sink** for 50,000 gold/month
3. **Implement trading post** with 5% gold tax
4. **Adjust Legendary drop rate** to 0.5% for rarity perception
```"""
