# CI/CD Pipeline Design

**Agencia:** DevOps
**Rol Sugerido:** @devops_engineer

## Objetivo de la Skill
Diseña pipelines de CI/CD que automatizan build, test, security scanning, y deployment con rollback automatico. Implementa GitHub Actions o GitLab CI con gating apropiado para calidad y velocidad.

## Metodologia de Razonamiento (Paso a Paso)
1. **Pipeline stages**:
   - Lint/Style: Fast feedback, < 2 min
   - Unit Tests: Core logic, < 5 min
   - Integration Tests: API/database, < 15 min
   - Security Scan: SAST, dependency check
   - Build: Create artifacts
   - E2E Tests: Full flow validation
   - Deploy: Staging -> Production
2. **Gating strategy**:
   - Must-pass: Lint, Unit Tests, Build
   - Quality gates: Coverage > 80%
3. **Artifact management**: Version, store, promote between stages.
4. **Deployment strategies**:
   - Blue-green: Two identical environments
   - Canary: Small % traffic to new version
   - Rolling: Incremental replacement
5. **Rollback strategy**: Automatic if health checks fail.

## Anti-Patrones
- Pipeline que corre todo siempre.
- No tener rollback automatico.
- Secrets en variables de pipeline en plaintext.
- Deploys manuales en produccion.
- No separar concerns.
- Pipeline sin tests que fail fast.

## Formato de Salida Obligatorio
```yaml
name: CI/CD Pipeline
on:
  push:
    branches: [main, develop]
jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Setup Node.js
        uses: actions/setup-node@v3
        with: { node-version: '18', cache: 'npm' }
      - run: npm ci && npm run lint

  test:
    runs-on: ubuntu-latest
    needs: lint
    steps:
      - uses: actions/checkout@v3
      - run: npm ci && npm run test:coverage
      - uses: codecov/codecov-action@v3

  security:
    runs-on: ubuntu-latest
    needs: test
    steps:
      - uses: actions/checkout@v3
      - name: Run Trivy
        uses: aquasecurity/trivy-action@master
        with: { scan-type: 'fs', severity: 'CRITICAL,HIGH', exit-code: '1' }

  build:
    runs-on: ubuntu-latest
    needs: security
    if: github.ref == 'refs/heads/main'
    steps:
      - uses: docker/build-push-action@v4
        with: { push: true, tags: ${{ env.REGISTRY }}/${{ github.repository }}:${{ github.sha }}}
```