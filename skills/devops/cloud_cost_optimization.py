"""Skill: Cloud Cost Optimization — Migración automática de 24_cloud_cost_optimization.md."""
from core.skills.base import BaseSkill


class CloudCostOptimizationSkill(BaseSkill):
    """Cloud Cost Optimization."""

    name = "Cloud Cost Optimization"
    agency = "DevOps"
    keywords = ['cloud', 'costo', 'aws', 'gcp', 'azure', 'presupuesto', 'ahorro', 'instancia']

    def get_instructions(self) -> str:
        return """## Cloud Cost Optimization

**Agencia:** DevOps
**Rol Sugerido:** @finops_engineer

## Objetivo de la Skill
Analiza y optimiza costos de infraestructura en AWS/Azure/GCP identificando recursos sobreprovisionados, aplicando Reserved Instances, Right-sizing, y automation para reducir costs sin comprometer reliability.

## Metodologia de Razonamiento (Paso a Paso)
1. **Cost allocation**: Tag resources por equipo/proyecto/servicio.
2. **Rightsizing analysis**:
   - CloudWatch metrics para CPU/Memory utilization
   - Target: 40-60% promedio de utilizacion
   - Downsize recursos subutilizados
3. **Reserved vs On-Demand**:
   - Reserved Instances para steady-state workloads
   - Spot instances para fault-tolerant batch jobs
4. **Storage tiering**:
   - S3 Intelligent Tiering para infrequently accessed data
   - Delete unused snapshots y volumes
5. **Compute optimization**:
   - Auto-scaling con right metrics
   - Lambda/Serverless para event-driven
6. **Unused resources**: Find and delete unattached volumes, IPs, snapshots.

## Anti-Patrones
- Provisioning resources "para futuro" sin immediately needed.
- No tagging resources.
- Ignoring reserved instance opportunities.
- Data transfer costs excesivamente altos.
- Not cleaning up dev/test environments.
- Auto-scaling sin right metrics.
- Storage sin lifecycle policies.

## Formato de Salida Obligatorio
```markdown
# Cloud Cost Optimization Report

**Period:** [Month YYYY]

## Cost Summary
| Service | Spend | % Total | vs Last Month |
|---------|-------|---------|--------------|
| EC2 | $12,450 | 45% | -8% |
| RDS | $3,200 | 12% | +2% |
| S3 | $1,800 | 7% | -15% |
| **Total** | **$27,550** | **100%** | **-3%** |

## Rightsizing Recommendations
| Resource | Current Type | Recommended | Monthly Savings |
|----------|--------------|-------------|-----------------|
| app-server-3 | t3.xlarge | t3.large | $85 |

## Total Potential Savings
**Monthly:** $574
**Annual:** $6,888
```"""
