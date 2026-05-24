# SLA Drafting

**Agencia:** Legal
**Rol Sugerido:** @legal_counsel

## Objetivo de la Skill
Redacta Service Level Agreements (SLAs) para servicios SaaS que definen niveles de servicio medibles, metricas, remediaciones, y consecuencias por incumplimiento. Balances riesgo y comercialidad.

## Metodologia de Razonamiento (Paso a Paso)
1. **Definir servicios cubiertos**:
   - Core functionality
   - Supporting services
   - Excluded services
2. **Establecer metricas de servicio**:
   - Uptime/SLA percentage (99.9%, 99.95%, etc.)
   - Downtime allowance por tier
   - Response times (critical, high, medium, low)
   - Resolution times
3. **Measurement methodology**:
   - How uptime is calculated
   - Exclusions (scheduled maintenance, force majeure)
   - Monitoring methods
4. **Credit structure**:
   - Service credits as sole remedy
   - Escalating credits based on severity
   - Caps on credits
   - Interaction with termination rights
5. **Escalation procedures**:
   - Contact information
   - Response requirements
   - Authority levels
6. **Review and amendment**:
   - Annual review clause
   - Process for service changes

## Anti-Patrones
- 100% uptime guarantee, impossible de cumplir.
- SLA credits as only remedy pero sin caps de responsabilidad.
- No definition clara de como se mide uptime.
- Exclusions muy amplias que vacian la SLA.
- No process para dispute de metricas.
- Ignoring geographic regulatory requirements.

## Formato de Salida Obligatorio
```markdown
# Service Level Agreement - [Company Name]

**Effective Date:** [YYYY-MM-DD]
**Parties:** [Provider] ("Provider") and [Customer] ("Customer")

## 1. Service Description
[Description of covered services]

## 2. Service Level Commitments

### 2.1 Availability SLA
| Service Tier | Monthly Uptime | Monthly Downtime Allowed |
|--------------|----------------|-------------------------|
| Enterprise | 99.95% | 21.9 minutes |
| Professional | 99.9% | 43.8 minutes |
| Starter | 99.5% | 3h 39m |

### 2.2 Performance SLA
| Metric | Commitment |
|--------|------------|
| API Response Time (p95) | < 200ms |
| Batch Processing | < 5 min per 10K records |
| Report Generation | < 30 seconds |

### 2.3 Support Response Times
| Priority | Response Time | Resolution Target |
|----------|---------------|-------------------|
| Critical (P1) | 15 minutes | 4 hours |
| High (P2) | 1 hour | 8 hours |
| Medium (P3) | 4 hours | 48 hours |
| Low (P4) | 24 hours | 5 business days |

## 3. Uptime Calculation
**Formula:** (Total Minutes - Downtime Minutes) / Total Minutes x 100

**Exclusions:**
- Scheduled maintenance (with 48h notice)
- Customer-caused issues
- Force majeure events
- Third-party infrastructure failures

## 4. Service Credits
| Monthly Uptime Achieved | Credit (% of Monthly Fee) |
|------------------------|---------------------------|
| 99.0% - 99.5% | 5% |
| 98.0% - 99.0% | 10% |
| 95.0% - 98.0% | 25% |
| Below 95.0% | 50% |

**Maximum Credits:** Not to exceed 50% of monthly fees in any billing period.

## 5. Remedies and Limitations
** Sole Remedy:** Service credits are Customer's sole and exclusive remedy for any failure to meet Service Levels.

**Limitations:**
- Credits are not applicable to Enterprise Support add-on
- Credits may not be exchanged for, or applied to, future service fees
```