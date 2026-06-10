"""Skill: SaaS Pricing Model — Migración automática de 41_saas_pricing_model.md."""
from core.skills.base import BaseSkill


class SaasPricingModelSkill(BaseSkill):
    """SaaS Pricing Model."""

    name = "SaaS Pricing Model"
    agency = "Legal & Media"
    keywords = ['saas', 'pricing', 'precio', 'modelo de negocio', 'freemium', 'suscripción', 'tier']

    def get_instructions(self) -> str:
        return """## SaaS Pricing Model

**Agencia:** Legal
**Rol Sugerido:** @product_manager

## Objetivo de la Skill
Diseña modelos de precios para SaaS que maximizan revenue mientras mantienen customer acquisition. Incluye freemium vs trial, tiered pricing, usage-based models, y estrategias de pricing psychological.

## Metodologia de Razonamiento (Paso a Paso)
1. **Understand customer value**:
   - Value-based pricing (que pagar por el valor obtenido)
   - Cost-plus pricing (margen sobre costo)
   - Competition-based pricing (vs alternativas)
2. **Freemium vs Trial decision**:
   - Freemium: Good para viral/network effects, freemium conversion ~2-5%
   - Trial: Good para enterprise/high-touch sales, trial conversion ~15-25%
3. **Tiered pricing structure**:
   - Entry tier: Capture price-sensitive customers
   - Mid tier: Most popular, best value perception
   - Enterprise tier: Custom pricing, high revenue per customer
   - Consider feature gating por tier
4. **Usage-based elements**:
   - Seat-based: Per user/month
   - Transaction-based: Per action (API calls, invoices)
   - Consumption-based: Per unit (storage, bandwidth)
5. **Price psychology**:
   - Charm pricing: $99 en lugar de $100
   - Anchoring: Mostrar enterprise tier primero
   - Decoy pricing: Tier del medio como "best value"
6. **Churn reduction**:
   - Annual discounts (15-20%)
   - Usage alerts antes de sobrepasar limits
   - Grace periods para limits

## Anti-Patrones
- Pricing basado solo en costos, no en valor percibido.
- Too many pricing tiers, decision paralysis.
- No annual discount option.
- Free tier too generous, canibalizing paid.
- Price changes sin communication o justification.
- Ignoring enterprise segment.

## Formato de Salida Obligatorio
```markdown
# SaaS Pricing Model - [Product Name]

**Last Updated:** [YYYY-MM-DD]

## Pricing Strategy
**Primary Model:** Tiered + Usage-based
**Secondary Model:** Seat-based
**Target ARPU:** $[X]

## Pricing Tiers

| Feature | Starter | Professional | Enterprise |
|---------|---------|--------------|------------|
| Price (monthly) | $29 | $79 | Custom |
| Price (annual) | $25 | $69 | Custom |
| Users | 1-5 | 5-50 | Unlimited |
| Storage | 10GB | 100GB | Unlimited |
| API Calls | 10K/mo | 100K/mo | Unlimited |
| Support | Email | Priority | Dedicated |

## Usage-Based Components
| Usage Type | Rate |
|-----------|------|
| Extra API calls | $0.001/call |
| Extra storage | $0.10/GB |
| Overage alerts | At 80% threshold |

## Conversion Metrics
| Metric | Current | Target |
|--------|---------|--------|
| Free to Paid | 3.2% | 5% |
| Trial to Paid | 18% | 25% |
| Annual/Monthly ratio | 45% | 60% |

## Churn Analysis
| Tier | Monthly Churn | Annual Churn |
|------|---------------|--------------|
| Starter | 8% | 65% |
| Professional | 4% | 40% |
| Enterprise | 1% | 12% |

## Recommended Changes
1. Add "Starter Plus" tier at $49 for market gap
2. Increase annual discount to 20%
3. Add usage-based add-on for storage overages
```"""
