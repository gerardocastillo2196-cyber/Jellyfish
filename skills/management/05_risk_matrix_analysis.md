# Risk Matrix Analysis

**Agencia:** Management
**Rol Sugerido:** @risk_manager

## Objetivo de la Skill
Estandariza la identificacion, analisis y mitigacion de riesgos en proyectos usando una matriz de probabilidad vs impacto. Permite priorizacion objetiva de riesgos y asignacion eficiente de recursos de mitigacion.

## Metodologia de Razonamiento (Paso a Paso)
1. **Brainstorming de riesgos**: Sesion con stakeholders para identificar todos los riesgos potenciales.
2. **Clasificacion de probabilidad**: Escala 1-5 (1=Raro, 2=Improbable, 3=Posible, 4=Probable, 5=Casi Seguro).
3. **Clasificacion de impacto**: Escala 1-5 (1=Ninguno, 2=Menor, 3=Moderado, 4=Mayor, 5=Catastrofico).
4. **Calculo del riesgo**: `Riesgo = Probabilidad x Impacto`. Rango 1-25.
5. **Clasificacion del nivel**: 
   - 1-4: Bajo (verde) - Aceptar y monitorear
   - 5-9: Medio (amarillo) - Plan de mitigacion
   - 10-16: Alto (naranja) - Accion inmediata
   - 17-25: Critico (rojo) - Escalamiento urgente
6. **Diseño de estrategias**: Mitigar, Transferir, Aceptar, Evitar, Explotar.
7. **Asignacion de owners**: Un responsable por riesgo.
8. **Definicion de triggers**: Condiciones que activan el plan de contingencia.

## Anti-Patrones
- Identificar riesgos vagos sin consecuencias especificas concretas.
- Subestimar riesgos de baja probabilidad, los "cisnes negros" ocurren.
- No asignar owners, quedan sin seguimiento.
- Crear planes de mitigacion sin budget o recursos asignados.
- Ignorar riesgos inter-dependientes, la mitigacion de uno puede crear otro.
- No revisar la matriz periodicamente, los riesgos cambian con el proyecto.

## Formato de Salida Obligatorio
```markdown
# Risk Matrix - [Nombre del Proyecto]

| ID | Riesgo | Prob. | Imp. | Score | Nivel | Estrategia | Owner |
|----|--------|-------|------|-------|-------|------------|-------|
| R-01 | [Descripcion] | [1-5] | [1-5] | [N] | Rojo/Naranja/Amarillo/Verde | [Mitigar/etc] | [@nombre] |

## Plan de Mitigacion - Riesgo [R-XX]
**Estrategia:** [Nombre]
**Acciones:**
1. [Accion especifica con owner y deadline]
2. [Accion]

**Contingencia:** [Que hacer si el riesgo se materializa]
```