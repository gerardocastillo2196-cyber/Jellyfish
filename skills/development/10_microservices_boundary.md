# Microservices Boundary

**Agencia:** Development
**Rol Sugerido:** @solutions_architect

## Objetivo de la Skill
Define fronteras de microservicios que maximizan la cohesion funcional y minimizan el acoplamiento. Usa principios de DDD (Bounded Contexts), patterns de descomposicion, y criterios objetivos para decidir que va en cada servicio.

## Metodologia de Razonamiento (Paso a Paso)
1. **Analisis de procesos de negocio**: Mapea procesos de negocio end-to-end.
2. **Identificacion de dominios naturales**: Grupos de funcionalidad que cambian juntos.
3. **Aplicacion de criterios de descomposicion**:
   - Single Responsibility: Un servicio, una razon para cambiar
   - Stable Dependencies: Buscar modulos estables que no cambian frecuentemente
   - Team Structure: Si dos features requieren equipos diferentes,分开
   - Data Sovereignty: Datos que pertenecen a un dominio, no se comparten
4. **Definicion de APIs de servicio**: Contratos estables con versioning.
5. **Identificacion de comunicacion sincrona vs asincrona**:
   - Sincrona: Commands, Queries que requieren respuesta inmediata
   - Asincrona: Events para desacoplamiento temporal
6. **Diseño de database per service**: No shared databases.
7. **Verificacion de autonomia**: Cada servicio puede deployarse independientemente.

## Anti-Patrones
- Crear microservicios por "moda" sin justificacion de complejidad real.
- Shared databases entre servicios, viola la autonomia.
- Chatty communication: 50 llamadas para completar una operacion simple.
- Distribuir funcionalidad relacionada en multiples servicios (distributed monolith).
- Olvidar que distributed systems son mas complejos de mantener.
- No tener estrategia de observabilidad (logs, metrics, tracing).
- Crear servicios demasiado pequenos (nanoservices) que generan overhead.

## Formato de Salida Obligatorio
```markdown
# Microservices Architecture

## Service Inventory
| Service | Domain | Team | Language | Database | SLA |
|---------|--------|------|----------|----------|-----|
| user-service | Identity | Team Alpha | Go | PostgreSQL | 99.9% |
| catalog-service | Catalog | Team Beta | Java | MongoDB | 99.5% |
| order-service | Orders | Team Gamma | Node.js | PostgreSQL | 99.9% |
| payment-service | Billing | Team Delta | Python | MySQL | 99.95% |

## Context Map
- order-service -> payment-service (command)
- order-service -> shipping-service (event)
- shipping-service -> notification-svc (event)
```