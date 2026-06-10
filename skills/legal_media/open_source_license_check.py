"""Skill: Open Source License Check — Migración automática de 40_open_source_license_check.md."""
from core.skills.base import BaseSkill


class OpenSourceLicenseCheckSkill(BaseSkill):
    """Open Source License Check."""

    name = "Open Source License Check"
    agency = "Legal & Media"
    keywords = ['licencia', 'open source', 'mit', 'gpl', 'apache', 'copyright', 'compliance']

    def get_instructions(self) -> str:
        return """## Open Source License Check

**Agencia:** Legal
**Rol Sugerido:** @legal_engineer

## Objetivo de la Skill
Identifica y evalua licencias de software open source en proyectos para asegurar compliance legal. Detecta conflicts entre licencias, copyleft implications, y obligaciones de attribution.

## Metodologia de Razonamiento (Paso a Paso)
1. **Dependency inventory**:
   - Listar todas las dependencias directes e indirectas
   - Incluir transitive dependencies
   - Usar tools como FOSSA, Snyk, oLicense-cop
2. **License identification**:
   - Categorizar por license type:
     - Permissive: MIT, BSD, Apache 2.0
     - Copyleft weak: LGPL, MPL
     - Copyleft strong: GPL, AGPL
     - Proprietary: EULA, Commercial
   - Verificar version de license
3. **Compatibility analysis**:
   - GPL code no puede linkear con proprietary code
   - AGPL es mas restrictivo que GPL
   - Apache 2.0 es compatible con GPL v3 pero no v2
4. **Copyleft analysis**:
   - Determine si codigo debe ser released
   - Scope de la obligacion (file-level vs module-level)
   - License chaining implications
5. **Attribution requirements**:
   - Copyright notices necesarios
   - License texts to distribute
   - NOTICE files para Apache projects

## Anti-Patrones
- Asumir que todas las dependencias tienen la misma license.
- Ignorar transitive dependencies.
- No tracking license changes en updates.
- Desconocer AGPL vs GPL differences.
- No documentar licensing decisions.

## Formato de Salida Obligatorio
```markdown
# Open Source License Compliance Report

**Project:** [Name]
**Scan Date:** [YYYY-MM-DD]
**Tool:** [FOSSA/Snyk/License-cop]

## Summary
| Metric | Count |
|--------|-------|
| Total dependencies | 127 |
| Unique licenses | 12 |
| Copyleft dependencies | 8 |
| High-risk licenses | 2 |

## License Distribution
| License | Count | Risk Level |
|---------|-------|-----------|
| MIT | 45 | Low |
| Apache 2.0 | 32 | Low |
| GPL-3.0 | 8 | High |
| AGPL-3.0 | 2 | Critical |
| Unknown | 1 | Medium |

## Compliance Issues

### Critical: AGPL-3.0 Dependencies
| Package | Version | Issue | Action Required |
|---------|---------|-------|-----------------|
| mongodb-client | 4.2.1 | AGPL license | Consider alternative |
| libx | 1.0.2 | AGPL license | Review linking |

### Warning: GPL-3.0 in Core Product
| Package | Version | Copyleft Scope | Action |
|---------|---------|---------------|--------|
| sqlite-wrapper | 3.1.0 | Module-level | Document justification |

## Recommended Actions
1. **Replace AGPL dependencies** within 90 days
2. **Document GPL linking** decision with legal review
3. **Update attribution files** for Apache dependencies
```"""
