# Dockerfile Optimization

**Agencia:** DevOps
**Rol Sugerido:** @devops_engineer

## Objetivo de la Skill
Crea Dockerfiles optimizados con multi-stage builds que minimizan image size, mejora build times, y refuerza security posture. Incluye best practices de no-root users, minimal base images, y proper layer caching.

## Metodologia de Razonamiento (Paso a Paso)
1. **Multi-stage builds**:
   - Stage 1: Build dependencies (compilers, build tools)
   - Stage 2: Runtime image minimal
   - Copiar solo artefactos necesarios
2. **Base image selection**:
   - Alpine para minimal footprint
   - Distroless para security extrema
3. **Layer optimization**:
   - Order operations to maximize cache
   - COPY package files before running install
   - Combine RUN commands para fewer layers
4. **Security hardening**:
   - Create non-root user (USER instruction)
   - No secrets en layers (use secrets management)
   - .dockerignore para excluir sensitive files
5. **Health checks**: Add HEALTHCHECK instruction.

## Anti-Patrones
- Base image con OS completo cuando no es necesario.
- COPY . /app sin .dockerignore.
- Running como root sin justificacion.
- Secrets hardcoded en Dockerfile.
- No limpiar package manager cache.
- No usar version tags, latest causa inconsistencia.

## Formato de Salida Obligatorio
```dockerfile
# syntax=docker/dockerfile:1.4
# Multi-stage build for Node.js application
# Stage 1: Build
FROM node:18-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production
COPY . .
RUN npm run build

# Stage 2: Production
FROM node:18-alpine AS production
RUN addgroup -g 1001 -S appgroup && adduser -u 1001 -S appuser -G appgroup
WORKDIR /app
COPY --from=builder --chown=appuser:appgroup /app/dist ./dist
COPY --from=builder --chown=appuser:appgroup /app/node_modules ./node_modules
USER appuser
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=3s CMD wget --no-verbose --tries=1 --spider http://localhost:3000/health
CMD ["node", "dist/server.js"]
```