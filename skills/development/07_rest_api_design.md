# REST API Design

**Agencia:** Development
**Rol Sugerido:** @backend_developer

## Objetivo de la Skill
Diseña APIs RESTful que siguen las mejores practicas de la industria: endpoints consistentes, codigos de estado HTTP correctos, versionado, paginacion, y documentacion OpenAPI. Crea APIs predecibles, escalables y faceis de consumir.

## Metodologia de Razonamiento (Paso a Paso)
1. **Identificacion de recursos**: nouns, no verbs. users, products, orders, no getUsers.
2. **Diseño de URLs jerarquicas**: /users/{userId}/orders/{orderId}.
3. **Seleccion de HTTP verbs correctos**:
   - GET: Recuperar recursos (sin side effects)
   - POST: Crear nuevos recursos
   - PUT: Reemplazar completamente un recurso
   - PATCH: Actualizacion parcial
   - DELETE: Eliminar recursos
4. **Seleccion de status codes**:
   - 2xx: Exito (200, 201, 204)
   - 3xx: Redireccion (304)
   - 4xx: Error del cliente (400, 401, 403, 404, 422)
   - 5xx: Error del servidor (500, 502, 503)
5. **Diseño de request/response bodies**: JSON con camelCase, nulls explicitos.
6. **Implementacion de paginacion**: Cursor-based para datasets grandes, Offset para pequenos.
7. **Versionado**: URL versioning (/v1/users) o Header versioning.
8. **Documentacion OpenAPI 3.0**: Todos los endpoints documentados con ejemplos.

## Anti-Patrones
- Usar verbs en URLs (getUser, createOrder, deleteProduct).
- Retornar 200 para todos los casos incluyendo errores.
- No versionar la API, breaking changes rompen clientes.
- Exponer IDs incrementales secuenciales (enumeracion).
- No implementar rate limiting ni throttling.
- Retornar datos sensibles (passwords, tokens) en respuestas.
- Usar XML cuando el cliente espera JSON.

## Formato de Salida Obligatorio
```yaml
openapi: 3.0.3
info:
  title: User Management API
  version: 1.0.0
paths:
  /v1/users:
    get:
      summary: List all users
      parameters:
        - name: page
          in: query
          schema:
            type: integer
            default: 1
      responses:
        '200':
          description: Successful response
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/UserList'
```