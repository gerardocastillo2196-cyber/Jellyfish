# Code Review Master

**Agencia:** Development
**Rol Sugerido:** @code_reviewer

## Objetivo de la Skill
Ejecuta revisiones de codigo que mejoren la calidad del software sin bloquear el desarrollo. Identifica code smells, anti-patterns, problemas de seguridad, y oportunidades de mejora mientras mantienes relaciones positivas con el equipo.

## Metodologia de Razonamiento (Paso a Paso)
1. **Understand the context**: Lee la descripcion del PR y los requisitos.
2. **Verify tests exist and pass**: No revisar logica si no hay tests.
3. **Run the code locally**: Nunca revises codigo sin ejecutarlo.
4. **Check design consistency**: Sigue patrones establecidos del codebase?
5. **Look for code smells**:
   - Long methods (> 40 lines)
   - High cyclomatic complexity
   - Deep nesting (> 3 niveles)
   - Magic numbers/constants
   - Dead code
6. **Security check**:
   - SQL injection vectors
   - XSS vulnerabilities
   - Authentication/authorization gaps
   - Secrets in code
7. **Provide constructive feedback**:
   - Comenta con el autor
   - Usa prefix: [nit], [suggestion], [blocker], [question]
   - Explica el "por que" no solo el "que"

## Anti-Patrones
- Rechazar PRs por preferencia personal sin justificacion objetiva.
- Solo revisar estilo, ignorar logica y arquitectura.
- No ejecutar los tests antes de aprobar.
- Dejar pasar code smells "porque no es critico".
- Tardar mas de 48 horas en revisar, bloquea al equipo.
- Revisar mas de 400 lineas en una sola sesion.

## Formato de Salida Obligatorio
```markdown
## Code Review - PR #[N] Title

**Author:** [@username]
**Reviewer:** [@reviewer]
**Date:** [YYYY-MM-DD]

### Summary
[Brief description of changes and overall impression]

### Blockers
- [ ] [Issue]: [Explanation] - [Suggestion for fix]
  - *File: `src/path/file.ts:line`*

### Suggestions
- [ ] [Issue]: [Explanation with optional code snippet]

### Approval Status
**[APPROVE / REQUEST_CHANGES]**
```