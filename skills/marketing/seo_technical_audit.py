"""Skill: SEO Technical Audit — Migración automática de 27_seo_technical_audit.md."""
from core.skills.base import BaseSkill


class SeoTechnicalAuditSkill(BaseSkill):
    """SEO Technical Audit."""

    name = "SEO Technical Audit"
    agency = "Marketing"
    keywords = ['seo', 'auditoría', 'sitemap', 'robots', 'canonical', 'meta', 'velocidad', 'core web vitals']

    def get_instructions(self) -> str:
        return """## SEO Technical Audit

**Agencia:** Marketing
**Rol Sugerido:** @seo_specialist

## Objetivo de la Skill
Ejecuta auditorias tecnicas SEO verificando Core Web Vitals, meta tags, sitemaps, robots.txt, schema markup, y arquitectura de URLs. Identifica issues que impiden indexacion y ranking.

## Metodologia de Razonamiento (Paso a Paso)
1. **Core Web Vitals analysis**:
   - LCP (Largest Contentful Paint): < 2.5s
   - FID (First Input Delay): < 100ms
   - CLS (Cumulative Layout Shift): < 0.1
2. **Indexability check**:
   - robots.txt blocking issues
   - noindex tags incorrectly applied
   - Canonical URL misconfigurations
3. **Meta tags audit**:
   - Title tags (50-60 chars optimal)
   - Meta descriptions (150-160 chars)
4. **Sitemap validation**:
   - XML format correct
   - < 50,000 URLs
   - All important pages included
5. **Schema markup**: Valid JSON-LD con structured data.
6. **URL structure**: Descriptive, readable URLs, HTTPS everywhere.

## Anti-Patrones
- Duplicate content sin canonical tags.
- Bloquear pages importantes en robots.txt.
- Meta descriptions genericos o faltantes.
- Imagenes sin alt text.
- Ignoring Core Web Vitals.
- Slow page speed.

## Formato de Salida Obligatorio
```markdown
# SEO Technical Audit Report

**Website:** [URL]
**Date:** [YYYY-MM-DD]

## Core Web Vitals Status
| Metric | Mobile | Desktop | Target | Status |
|--------|--------|---------|--------|--------|
| LCP | 3.2s | 2.1s | < 2.5s | ⚠️ |
| FID | 45ms | 12ms | < 100ms | ✅ |
| CLS | 0.15 | 0.08 | < 0.1 | ⚠️ |

## Critical Issues
| Issue | Impact | Pages | Priority |
|-------|--------|-------|----------|
| Missing meta descriptions | High | 45 pages | P1 |
| Images without alt text | Medium | 120 images | P2 |
```"""
