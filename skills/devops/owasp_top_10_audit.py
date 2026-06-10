"""Skill: OWASP Top 10 Audit — Migración automática de 25_owasp_top_10_audit.md."""
from core.skills.base import BaseSkill


class OwaspTop10AuditSkill(BaseSkill):
    """OWASP Top 10 Audit."""

    name = "OWASP Top 10 Audit"
    agency = "DevOps"
    keywords = ['owasp', 'seguridad web', 'inyección', 'xss', 'csrf', 'autenticación', 'auditoría']

    def get_instructions(self) -> str:
        return """## OWASP Top 10 Audit

**Agencia:** DevOps
**Rol Sugerido:** @security_engineer

## Objetivo de la Skill
Realiza auditorias de seguridad contra OWASP Top 10 identificando vulnerabilidades de inyeccion, broken authentication, sensitive data exposure, y otras amenazas comunes. Provee remediacion priorizada y verificable.

## Metodologia de Razonamiento (Paso a Paso)
1. **A01 - Broken Access Control**:
   - Verificar authorization en todos los endpoints
   - Check IDOR vulnerability
2. **A02 - Cryptographic Failures**:
   - Data in transit: TLS 1.2+ everywhere
   - Data at rest: AES-256 para sensitive data
3. **A03 - Injection**:
   - SQL Injection: Parameterized queries
   - XSS: Output encoding, CSP
   - Command Injection: Input validation
4. **A04 - Insecure Design**: Threat modeling, secure design patterns.
5. **A05 - Security Misconfiguration**:
   - Default credentials changed
   - Error handling no revela stack traces
6. **A06 - Vulnerable Components**: Dependency scanning.
7. **A07 - Auth Failures**: MFA, password policies, session management.

## Anti-Patrones
- Solo relying en scanners automaticos.
- No encrypting sensitive data "por performance".
- Default credentials en produccion.
- Ignoring security headers.
- Storing passwords en plaintext.
- Not validating file uploads.

## Formato de Salida Obligatorio
```markdown
# OWASP Top 10 Security Audit

**Application:** [Name]
**Date:** [YYYY-MM-DD]

## Executive Summary
**Overall Risk Level:** 🔴 CRITICAL | 🟠 HIGH | 🟡 MEDIUM | 🟢 LOW
**Critical Findings:** [N]

## A01 - Broken Access Control
**Status:** ⚠️ FAIL

**Finding 1:** [Title]
**Severity:** 🔴 Critical
**Description:** [Vulnerability description]
**Remediation:** [Steps]

## Remediation Priority Matrix
| ID | Finding | Category | Severity | Priority |
|----|---------|----------|----------|----------|
| F-01 | Broken Access Control on Orders | A01 | 🔴 | P1 |
```"""
