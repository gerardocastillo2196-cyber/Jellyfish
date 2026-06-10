"""Skill: Sprint Planning — Migración automática de 02_sprint_planning.md."""
from core.skills.base import BaseSkill


class SprintPlanningSkill(BaseSkill):
    """Sprint Planning."""

    name = "Sprint Planning"
    agency = "Management"
    keywords = ['sprint', 'planificación', 'velocidad', 'capacidad', 'objetivo del sprint']

    def get_instructions(self) -> str:
        return """## Sprint Planning

**Agencia:** Management
**Rol Sugerido:** @product_owner

## Objetivo de la Skill
Capacita al agente para planificar sprints de 1-4 semanas seleccionando items del backlog que maximicen el valor entregado alineado con los OKRs del equipo. Incluye calculo de velocidad historica, capacidad del equipo y compromisos realistas.

## Metodologia de Razonamiento (Paso a Paso)
1. **Recopilacion de datos historicos**: Obtener velocidad promedio de los ultimos 3 sprints.
2. **Calculo de capacidad real**: Resta vacaciones, dias administrativos, ceremonias.
3. **Estimacion de disponibilidad**: `Capacidad = Miembros * Horas * Dias - Perdidas`.
4. **Conversion a puntos de historia**: `Puntos objetivo = Capacidad / Velocidad por hora`.
5. **Seleccion de items del backlog**: Priorizar por valor de negocio, no por complejidad tecnica.
6. **Verificacion de dependencias**: Confirma que todos los items intra-sprint no bloqueen otros.
7. **Definicion del Sprint Goal**: Frase de una linea que resuma el objetivo del sprint.
8. **Commitment check**: Valida que el equipo puede completar los items con 80% de confianza.

## Anti-Patrones
- Sobregargar el sprint por "optimismo", causa burnout y deuda tecnica.
- Ignorar la deuda tecnica existente, acelera el deterioro del sistema.
- No considerar dias de ausencia o holidays, distorsiona la capacidad.
- Seleccionar items sin verificar dependencias con otros equipos.
- Comprometer items de baja prioridad cuando hay alta prioridad pendiente.

## Formato de Salida Obligatorio
```markdown
## Sprint Planning - Sprint #[N]

**Duracion:** [Fecha inicio] a [Fecha fin]
**Capacidad del equipo:** [X] puntos de historia
**Sprint Goal:** [Frase objetivo]

### Compromiso del Sprint
| ID | Historia | Puntos | Responsable |
|----|----------|--------|-------------|
| US-01 | [Titulo] | [N] | [@nombre] |

### Definicion de Terminado (DoD)
- [ ] Codigo mergueado a develop
- [ ] Pruebas unitarias > 80% cobertura
- [ ] Documentacion actualizada
- [ ] Aprobacion por QA
```"""
