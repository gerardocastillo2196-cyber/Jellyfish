"""Skill: REST API Design — Diseño de APIs RESTful.

Migración fiel de skills/development/07_rest_api_design.md a clase Python.
Incluye keywords para inyección selectiva y esquema Pydantic de entrada.
"""

from core.skills.base import BaseSkill


class RestApiDesignSkill(BaseSkill):
    """Diseño de APIs RESTful siguiendo mejores prácticas de la industria."""

    name = "REST API Design"
    agency = "Development"
    role = "@backend_developer"
    keywords = [
        "api", "rest", "endpoint", "openapi", "swagger",
        "http", "crud", "ruta", "recurso", "url",
        "get", "post", "put", "patch", "delete",
        "paginación", "versionado",
    ]

    def get_instructions(self) -> str:
        return """## Objetivo de la Skill
Diseña APIs RESTful que siguen las mejores prácticas de la industria: endpoints consistentes, códigos de estado HTTP correctos, versionado, paginación, y documentación OpenAPI. Crea APIs predecibles, escalables y fáciles de consumir.

## Metodología de Razonamiento (Paso a Paso)
1. **Identificación de recursos**: nouns, no verbs. `users`, `products`, `orders`, no `getUsers`.
2. **Diseño de URLs jerárquicas**: `/users/{userId}/orders/{orderId}`.
3. **Selección de HTTP verbs correctos**:
   - GET: Recuperar recursos (sin side effects)
   - POST: Crear nuevos recursos
   - PUT: Reemplazar completamente un recurso
   - PATCH: Actualización parcial
   - DELETE: Eliminar recursos
4. **Selección de status codes**:
   - 2xx: Éxito (200, 201, 204)
   - 3xx: Redirección (304)
   - 4xx: Error del cliente (400, 401, 403, 404, 422)
   - 5xx: Error del servidor (500, 502, 503)
5. **Diseño de request/response bodies**: JSON con camelCase, nulls explícitos.
6. **Implementación de paginación**: Cursor-based para datasets grandes, Offset para pequeños.
7. **Versionado**: URL versioning (`/v1/users`) o Header versioning.
8. **Documentación OpenAPI 3.0**: Todos los endpoints documentados con ejemplos.

## Anti-Patrones
- Usar verbs en URLs (`getUser`, `createOrder`, `deleteProduct`).
- Retornar 200 para todos los casos incluyendo errores.
- No versionar la API, breaking changes rompen clientes.
- Exponer IDs incrementales secuenciales (enumeración).
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
```"""
