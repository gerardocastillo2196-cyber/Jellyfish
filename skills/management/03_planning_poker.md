# Planning Poker

**Agencia:** Management
**Rol Sugerido:** @scrum_master

## Objetivo de la Skill
Estandariza la tecnica de estimacion colaborativa Planning Poker para que equipos distribuidos o centralizados alcancen convergencia rapida en estimaciones de esfuerzo. Usa la secuencia Fibonacci para forzar decisiones binarias y evitar medias tintas.

## Metodologia de Razonamiento (Paso a Paso)
1. **Presentacion del item**: Lee en voz alta la historia de usuario con sus criterios de aceptacion.
2. **Aclaracion de dudas**: Invita a preguntas durante 2 minutos maximo.
3. **Estimacion individual**: Cada miembro selecciona su carta en privado (0, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, infinity).
4. **Revelacion sincronizada**: Todos muestran su carta simultáneamente.
5. **Discusion de anomalias**: Si hay dispersion > 2 pasos Fibonacci, el mas alto y bajo explican su razonamiento.
6. **Nueva ronda**: Sin influencia de estimaciones previas, re-estimen.
7. **Convergencia**: El valor modal o la mediana se acepta como estimacion oficial.
8. **Registro**: Anota la estimacion junto con las notas de la discusion.

## Anti-Patrones
- Revelar estimaciones antes de tiempo, crea efecto de anclaje.
- Permitir que el lider tecnico estimule sin datos, sesga al equipo.
- Discutir indefinidamente sin limite de rondas, pierde eficiencia.
- Aceptar estimaciones basadas en tiempo (horas/dias) en lugar de puntos relativos.
- Ignorar estimaciones outliers sin investigar la causa raiz.

## Formato de Salida Obligatorio
```json
{
  "storyId": "US-042",
  "title": "Implementar login con OAuth2",
  "estimations": {
    "dev_alice": 8,
    "dev_bob": 5,
    "dev_carol": 8,
    "qa_dave": 5,
    "lead_eric": 8
  },
  "finalEstimate": 8,
  "dispersion": "low",
  "rounds": 1,
  "consensusNotes": "Alice y Carol tenian en cuenta la integracion con el provider externo"
}
```