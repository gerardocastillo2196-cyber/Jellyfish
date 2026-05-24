# Threat Modeling STRIDE

**Agencia:** DevOps
**Rol Sugerido:** @security_architect

## Objetivo de la Skill
Aplica la metodologia STRIDE para modelar amenazas en sistemas software: Spoofing, Tampering, Repudiation, Information Disclosure, Denial of Service, Elevation of Privilege. Identifica y prioriza mitigaciones de seguridad para cada categoria.

## Metodologia de Razonamiento (Paso a Paso)
1. **Decomposition**: Identifica componentes, data flows, trust boundaries.
2. **Data flow diagram**: Visualiza como data se mueve entre componentes.
3. **STRIDE per component**:
   - S - Spoofing: Puede un attacker suplantar identidad?
   - T - Tampering: Puede data ser modificada sin deteccion?
   - R - Repudiation: Pueden usuarios negar acciones realizadas?
   - I - Information Disclosure: Puede data ser expuesta?
   - D - Denial of Service: Puede el sistema ser bloqueado?
   - E - Elevation of Privilege: Puede un attacker gain admin access?
4. **Mitigation mapping**:
   - Spoofing -> Autenticacion fuerte (MFA, certificates)
   - Tampering -> Integrity checks (HMAC, digital signatures)
   - Repudiation -> Audit logs
   - Information Disclosure -> Encriptacion (TLS, AES)
   - DoS -> Rate limiting, redundancy
   - Elevation of Privilege -> Authorization, least privilege

## Anti-Patrones
- Modelar amenazas solo al inicio, no re-evaluar con cambios.
- Tratar seguridad como "feature" postponeable.
- No incluir third-party components en el modelo.
- Ignorar amenazas internas.
- Mitigaciones sin validacion.

## Formato de Salida Obligatorio
```markdown
# Threat Model - [Application Name]

## STRIDE Threat Analysis

| ID | Threat | Category | Likelihood | Severity | Risk | Mitigation |
|----|--------|----------|------------|----------|------|------------|
| T-001 | Session hijacking via XSS | S | Medium | High | High | CSP, output encoding |
| T-002 | SQL injection | T | Low | Critical | High | Parameterized queries |
| T-003 | Credit card exposure | I | Low | Critical | High | PCI-DSS, tokenization |
```