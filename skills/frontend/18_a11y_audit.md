# A11Y Audit

**Agencia:** Frontend
**Rol Sugerido:** @accessibility_specialist

## Objetivo de la Skill
Realiza auditorias de accesibilidad siguiendo WCAG 2.1 Level AA para asegurar que las aplicaciones son usables por personas con discapacidades. Identifica issues de keyboard navigation, screen reader compatibility, y contraste de colores.

## Metodologia de Razonamiento (Paso a Paso)
1. **Automated testing**: Ejecuta axe-core o Lighthouse.
2. **Keyboard navigation audit**:
   - Tab order sigue logical flow
   - All interactive elements reachable via keyboard
   - Focus visible at all times
   - Escape key closes modals/dropdowns
3. **Screen reader testing**:
   - NVDA + Firefox (Windows)
   - VoiceOver + Safari (macOS)
   - Check reading order logical
4. **Color contrast verification**:
   - Text: 4.5:1 minimum (AA), 7:1 (AAA)
   - Large text: 3:1 minimum (AA)
5. **Semantic HTML verification**:
   - Use landmarks (<main>, <nav>, <header>, <footer>)
   - Headings in hierarchical order
   - Form inputs with associated labels
6. **Touch target sizing**: 44x44px minimum para mobile.

## Anti-Patrones
- Usar <div> para todo.
- Imagenes sin alt text o alt="" cuando son decorativas.
- Formularios sin labels asociadas correctamente.
- Color como unico means of conveying information.
- Dialogs/modals sin focus trap.
- Animaciones que no se pueden pausar.

## Formato de Salida Obligatorio
```markdown
# Accessibility Audit Report

**URL:** [URL evaluada]
**Date:** [YYYY-MM-DD]
**Standard:** WCAG 2.1 Level AA

## Automated Testing Results
| Tool | Issues Found | Critical | Moderate | Low |
|------|--------------|----------|----------|-----|
| axe-core | 12 | 2 | 6 | 4 |

## Critical Issues
| # | WCAG Criterion | Issue | Severity |
|---|----------------|-------|----------|
| 1 | 1.1.1 | Images without alt text | P0 |
| 2 | 2.1.1 | Non-keyboard accessible button | P0 |

## Compliance Summary
| Criterion | Score |
|-----------|-------|
| Perceivable | 78% |
| Operable | 65% |
| Understandable | 82% |
| Robust | 90% |
| **Overall** | **74%** |
```