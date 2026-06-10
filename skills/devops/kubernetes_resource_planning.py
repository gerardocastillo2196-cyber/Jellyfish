"""Skill: Kubernetes Resource Planning — Migración automática de 26_kubernetes_resource_planning.md."""
from core.skills.base import BaseSkill


class KubernetesResourcePlanningSkill(BaseSkill):
    """Kubernetes Resource Planning."""

    name = "Kubernetes Resource Planning"
    agency = "DevOps"
    keywords = ['kubernetes', 'k8s', 'pod', 'deployment', 'service', 'helm', 'cluster', 'recurso']

    def get_instructions(self) -> str:
        return """## Kubernetes Resource Planning

**Agencia:** DevOps
**Rol Sugerido:** @platform_engineer

## Objetivo de la Skill
Planifica recursos de Kubernetes con Requests y Limits apropiados para optimizar costos y garantizar performance. Configura HPA (Horizontal Pod Autoscaler) con metricas correctas.

## Metodologia de Razonamiento (Paso a Paso)
1. **Understand workloads**:
   - CPU-bound vs Memory-bound
   - Burstable vs steady-state
2. **Initial resource estimation**:
   - Requests: Lo que el workload "guaranteed" obtener
   - Limits: Lo maximo que puede usar
3. **Request/Limit ratios**:
   - CPU: Limits usually 2x requests (burstable)
   - Memory: Limits usually same as requests
4. **Load testing**:
   - Run k6/Locust con realistic load
   - Monitor CPU/memory utilization
5. **HPA configuration**:
   - Metric selection: CPU, Memory, custom metrics
   - Target utilization: 70-80%
   - Min/Max replicas

## Anti-Patrones
- Setting requests = limits para todo.
- No setting resource limits.
- Ignoring memory limits, OOMKilled pods.
- CPU limits muy bajos.
- HPA sin custom metrics.
- Over-provisioning "para picos".

## Formato de Salida Obligatorio
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-server
spec:
  template:
    spec:
      containers:
      - name: api-server
        image: registry.example.com/api-server:v1.2.3
        resources:
          requests:
            cpu: "250m"
            memory: "256Mi"
          limits:
            cpu: "1000m"
            memory: "512Mi"
        livenessProbe:
          httpGet:
            path: /health/live
            port: 8080
        readinessProbe:
          httpGet:
            path: /health/ready
            port: 8080
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: api-server-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: api-server
  minReplicas: 3
  maxReplicas: 20
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
```"""
