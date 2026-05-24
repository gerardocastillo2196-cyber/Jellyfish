# Design System Extractor

**Agencia:** Frontend
**Rol Sugerido:** @design_engineer

## Objetivo de la Skill
Extrae tokens de diseño de interfaces existentes (color palettes, typography scales, spacing, shadows) y los formaliza en un sistema de diseño escalable que puede implementarse en codigo y usado por multiples productos.

## Metodologia de Razonamiento (Paso a Paso)
1. **Color extraction**:
   - Identify primary, secondary, neutral palettes
   - Calculate semantic colors (success, error, warning, info)
   - Ensure contrast ratios meet WCAG AA
   - Name using semantic naming
2. **Typography audit**:
   - Extract font families, weights, sizes
   - Calculate type scale (1.25 ratio or custom)
   - Define line heights apropiados por uso
3. **Spacing system**:
   - Base unit system (4px, 8px, 16px)
   - Spacing scale (xs, sm, md, lg, xl, 2xl)
4. **Shadow/elevation**: Define elevation levels (0-5).
5. **Border radius**: Unificar radios (sm: 4px, md: 8px, lg: 16px).
6. **Component inventory**: Buttons, inputs, cards, modals.

## Anti-Patrones
- Hardcoding colors directamente en componentes.
- No documentar los tokens extracted.
- Ignorar estados hover/active de componentes.
- Sistema de spacing inconsistente.
- No tener version control del design system.

## Formato de Salida Obligatorio
```typescript
export const colors = {
  primitive: {
    gray: {
      50: '#F9FAFB',
      100: '#F3F4F6',
      200: '#E5E7EB',
      300: '#D1D5DB',
      400: '#9CA3AF',
      500: '#6B7280',
      600: '#4B5563',
      700: '#374151',
      800: '#1F2937',
      900: '#111827',
    },
  },
  semantic: {
    success: { main: '#059669', light: '#D1FAE5' },
    error: { main: '#DC2626', light: '#FEE2E2' },
  },
};

export const spacing = {
  1: '0.25rem',
  2: '0.5rem',
  4: '1rem',
  6: '1.5rem',
  8: '2rem',
};
```