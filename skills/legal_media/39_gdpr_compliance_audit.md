# GDPR Compliance Audit

**Agencia:** Legal
**Rol Sugerido:** @privacy_officer

## Objetivo de la Skill
Realiza auditorias de cumplimiento GDPR para asegurar que las organizaciones protegen datos personales de ciudadanos de la UE, con focus en privacy by design, derechos de los interesados, y documentation requerida.

## Metodologia de Razonamiento (Paso a Paso)
1. **Scope definition**:
   - Identificar que datos personales se procesan
   - Determinar bases legales para procesamiento
   - Mapear flujos de datos transfronterizos
2. **Privacy by Design check**:
   - Data minimization implementada?
   - Purpose limitation documentada?
   - Storage limitation aplicada?
3. **Rights of data subjects**:
   - Access, rectification, erasure
   - Right to be informed
   - Data portability
   - Right to object
4. **Consent management**:
   - Granular consent options
   - Easy withdrawal mechanism
   - Consent records maintained
5. **Data breach procedures**:
   - Detection and reporting < 72 horas
   - Breach notification documentation
6. **Documentation requirements**:
   - Records of Processing Activities (RoPA)
   - Data Protection Impact Assessments (DPIA)

## Anti-Patrones
- Generic privacy policy sin specifics.
- Consent como unica base legal cuando no aplica.
- No mantener registros de procesamiento.
- Ignorar derechos de erasure (right to be forgotten).
- No conducting DPIAs para high-risk processing.

## Formato de Salida Obligatorio
```markdown
# GDPR Compliance Audit

**Organization:** [Name]
**Audit Date:** [YYYY-MM-DD]
**Auditor:** [@nombre]

## Data Processing Inventory
| Data Category | Legal Basis | Retention | Transfers |
|---------------|-------------|-----------|-----------|
| Customer names | Contract | 7 years | None |
| Email addresses | Consent | Until withdrawal | US via SCCs |

## Rights Implementation Status
| Right | Implemented | Evidence |
|-------|-------------|----------|
| Access | ✅ Yes | Self-service portal |
| Erasure | ⚠️ Partial | Manual process |
| Portability | ❌ No | Not implemented |

## Compliance Score
| Area | Score |
|------|-------|
| Lawfulness | 85% |
| Transparency | 70% |
| Data Subject Rights | 75% |
| Security | 90% |
| **Overall** | **80%** |

## Critical Gaps
| Gap | Risk | Remediation | Deadline |
|-----|------|-------------|----------|
| No DPIA for profiling | High | Conduct DPIA | 30 days |
```