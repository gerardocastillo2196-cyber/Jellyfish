# UI/UX Heuristic Evaluation

**Agencia:** Frontend
**Rol Sugerido:** @ux_analyst

## Objetivo de la Skill
Evalua interfaces de usuario contra las 10 heuristicas de Nielsen para identificar problemas de usability. Provee un framework estructurado de evaluacion que resulta en recomendaciones priorizadas y accionables.

## Metodologia de Razonamiento (Paso a Paso)
1. **Preparacion**: Define el contexto de uso, usuarios target, y tasks a evaluar.
2. **Familiarizacion**: Navega la interfaz como un usuario nuevo sin asistencia.
3. **Evaluacion por heuristica**:
   - H1 - Visibility of system status
   - H2 - Match between system and real world
   - H3 - User control and freedom
   - H4 - Consistency and standards
   - H5 - Error prevention
   - H6 - Recognition rather than recall
   - H7 - Flexibility and efficiency of use
   - H8 - Aesthetic and minimalist design
   - H9 - Help users recover from errors
   - H10 - Help and documentation
4. **Documentacion de findings**: Severity rating, description, recommendation.
5. **Priorizacion**: Por impacto en usuario y frecuencia de ocurrencia.

## Anti-Patrones
- Evaluar sin conocer el contexto de uso real.
- Confundir preferencia personal con problema de usability.
- No documentar con evidencia concreta.
- Ignorar heuristicas que no se aplican al contexto.
- Proponer recomendaciones vagas sin implementacion practica.
- No validar hallazgos con usuarios reales.

## Formato de Salida Obligatorio
```markdown
# Usability Heuristic Evaluation Report

**Product:** [Nombre del producto]
**Date:** [YYYY-MM-DD]
**Evaluator:** [@nombre]

## Executive Summary
[Resumen de hallazgos principales]

## Detailed Findings

### H1 - Visibility of System Status
**Severity:** 4 (Critical) | 3 (Major) | 2 (Minor) | 1 (Cosmetic)

**Finding:** [Titulo descriptivo]
**Location:** [Screen/Component]
**Description:** [Descripcion del problema]
**Recommendation:** [Accion especifica]
```