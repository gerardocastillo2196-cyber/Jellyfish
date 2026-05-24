# Caching Strategies

**Agencia:** Development
**Rol Sugerido:** @performance_engineer

## Objetivo de la Skill
Diseña e implementa estrategias de cache que mejoren dramaticamente el rendimiento de aplicaciones: write-through, write-behind, cache-aside, con invalidacion apropiada usando Redis. Evita stale data y thundering herd.

## Metodologia de Razonamiento (Paso a Paso)
1. **Identificacion de patrones de acceso**:
   - Read-heavy vs Write-heavy
   - Temporal locality vs Spatial locality
   - Freshness requirements
2. **Seleccion de cache pattern**:
   - Cache-Aside (Lazy Loading): App -> Cache -> DB
   - Write-Through: App -> Cache -> DB simultaneo
   - Write-Behind: App -> Cache -> async write to DB
   - Read-Through: Cache -> miss -> load from DB -> populate cache
3. **Diseño de invalidation strategy**:
   - TTL-based: Simple pero puede generar staleness
   - Event-based: Pub/sub para invalidar cuando datos cambian
   - Version-based: Key incluye version para detectar cambios
4. **Prevencion de thundering herd**:
   - Probabilistic early expiration
   - Lock-based cache population
   - Background refresh

## Anti-Patrones
- Cachear todo "por si acaso", memory pressure y stale data.
- No definir TTL, el cache crece indefinidamente.
- Violations de atomicidad: Actualizas DB pero no invalidates cache.
- Cachear datos sensibles sin encryption.
- No tener estrategia de backup del cache.
- Ignorar cold cache penalty en deployments.

## Formato de Salida Obligatorio
```typescript
class CacheService {
  async get<T>(key: string): Promise<T | null> {
    const cached = await redis.get(key);
    if (cached) {
      const { data, expiresAt } = JSON.parse(cached);
      const ttlRemaining = expiresAt - Date.now();
      if (ttlRemaining < 0 && Math.random() < 0.5) {
        this.refreshInBackground(key);
        return data;
      }
      if (ttlRemaining > 0) return data;
    }
    return null;
  }

  async set(key: string, data: any, ttlSeconds: number): Promise<void> {
    const expiresAt = Date.now() + (ttlSeconds * 1000);
    await redis.set(key, JSON.stringify({ data, expiresAt }), 'EX', ttlSeconds);
  }

  async invalidate(key: string): Promise<void> {
    await redis.del(key);
  }
}
```