# Backlog Grooming

**Agencia:** Management
**Rol Sugerido:** @scrum_master

## Objetivo de la Skill
Habilita al agente para facilitar sesiones de refinamiento de backlog donde se clarifican historias de usuario, se definen criterios de aceptacion en formato Gherkin, y se estima el esfuerzo de manera colaborativa. Esta habilidad transforma requisitos vagos en funcionalidades testeables y priorizadas.

## Metodologia de Razonamiento (Paso a Paso)
1. **Recepcion del requerimiento**: Recibe la descripcion inicial del usuario o stakeholder.
2. **Identificacion de ambiguedades**: Busca terminos vagos como "optimizado", "rapido", "seguro". Convierte en metricas especificas.
3. **Redaccion en formato User Story**: Estructura como "Como [tipo de usuario], quiero [funcionalidad] para [beneficio]".
4. **Definicion de Criterios de Aceptacion Gherkin**: 
   - `Given`: Contexto inicial del sistema
   - `When`: Accion que ejecuta el usuario
   - `Then`: Resultado esperado verificable
   - `And`: Condiciones adicionales
5. **Clasificacion de esfuerzo**: Asigna puntos usando la secuencia Fibonacci modificada (1, 2, 3, 5, 8, 13, 21).
6. **Verificacion de dependencias**: Identifica historias que requieren otras completadas primero.
7. **Priorizacion**: Clasifica usando framework MoSCoW (Must have, Should have, Could have, Won't have).

## Anti-Patrones
- No definir criterios de aceptacion antes de estimar, genera sobredisposicion.
- Permitir historias que excedan 13 puntos, indica scopes que necesitan division.
- Omitir criterios negativos (escenarios de error), crea deuda tecnica.
- Aceptar requisitos que no son testeables automaticamente.
- Priorizar por opinion personal en lugar de datos de negocio.

## Formato de Salida Obligatorio
```gherkin
Feature: [Nombre de la funcionalidad]
  
  Scenario: [Titulo descriptivo del escenario]
    Given [contexto]
    When [accion del usuario]
    Then [resultado esperado]
    And [condiciones adicionales]
    
  Scenario: [Escenario de error]
    Given [condicion de error]
    When [accion]
    Then [comportamiento correcto]
```