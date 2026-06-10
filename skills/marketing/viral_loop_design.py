"""Skill: Viral Loop Design — Migración automática de 30_viral_loop_design.md."""
from core.skills.base import BaseSkill


class ViralLoopDesignSkill(BaseSkill):
    """Viral Loop Design."""

    name = "Viral Loop Design"
    agency = "Marketing"
    keywords = ['viral', 'loop', 'referral', 'viralidad', 'k-factor', 'invitación', 'compartir']

    def get_instructions(self) -> str:
        return """## Viral Loop Design

**Agencia:** Marketing
**Rol Sugerido:** @growth_hacker

## Objetivo de la Skill
Diseña mecanismos de crecimiento viral donde usuarios comparten naturalmente el producto, resultando en referrals automaticos. Implementa loops de invitacion, rewards por referals, y tracking del K-factor.

## Metodologia de Razonamiento (Paso a Paso)
1. **Identify viral moments**: Cuando y que motiva a users to share.
2. **Design the loop**:
   - User takes action
   - Triggers share prompt
   - User invites friends
   - Friend signs up
   - User gets reward
3. **K-factor calculation**:
   - K = i x c
   - i = Number of invites sent per user
   - c = Conversion rate of invites
   - K > 1 = Viral growth
4. **Incentive design**:
   - Both referrer and referee get value
   - Tiered rewards for multiple referrals
5. **Share channels**:
   - Native: Email, SMS, messaging apps
   - Social: Twitter, LinkedIn, WhatsApp
6. **Tracking & analytics**:
   - Invite events
   - Conversion events

## Anti-Patrones
- Rewards alone no guarantees viral.
- Spam-like invites.
- Not tracking attribution.
- Rewards that attract only deal-hunters.
- K-factor < 1 pero pensando es viral.

## Formato de Salida Obligatorio
```markdown
# Viral Loop Design Document

**Product:** [Name]

## Viral Loop Architecture
[User A] -> [Action] -> [Share Prompt] -> [Invites Sent]
                                               |
                                      [Friend B Joins]
                                               |
                                      [Reward A + B]

## Current K-Factor Analysis
| Metric | Last 30 Days | Target |
|--------|--------------|--------|
| Invites per user | 0.8 | 2.0 |
| Invite conversion rate | 15% | 25% |
| K-factor | 0.12 | > 1.0 |

## Reward Structure
| Referral # | Referrer Reward | Referee Reward |
|------------|----------------|----------------|
| 1st | 1 month free | 20% discount |
| 2nd-5th | $10 credit | 20% discount |
| 6th+ | $25 credit | 20% discount |

## Success Criteria
- K-factor > 1.0 within 6 months
- Cost per acquisition < $5 (organic)
```"""
