# Database Schema Optimization

**Agencia:** Development
**Rol Sugerido:** @dba_specialist

## Objetivo de la Skill
Diseña esquemas de base de datos normalizados hasta 3NF (o desnormalizados justificadamente), con indices optimizados, constraints apropiadas, y foreign keys que mantengan la integridad referencial. Evita problemas de rendimiento que destruyen aplicaciones.

## Metodologia de Razonamiento (Paso a Paso)
1. **Identificacion de entidades**: Extrae entidades del dominio y sus atributos.
2. **Normalizacion hasta 3NF**:
   - 1NF: Eliminar grupos repetitivos, atomicidad de celdas
   - 2NF: Eliminar dependencias parciales (solo en claves compuestas)
   - 3NF: Eliminar dependencias transitivas
3. **Seleccion de tipos de datos**:
   - VARCHAR para strings variables, CHAR para fijos
   - INT para IDs, BIGINT para alta escala
   - DECIMAL para dinero (nunca FLOAT)
   - TIMESTAMP vs DATETIME segun zona horaria
4. **Definicion de primary keys**: GUIDs para APIs, auto-increment para OLTP.
5. **Creacion de indices**:
   - Primary keys ya tienen indice clustered
   - Foreign keys necesitan indice non-clustered
   - Columns en WHERE, JOIN, ORDER BY considerar indices
6. **Constraints apropiadas**: NOT NULL, UNIQUE, CHECK, DEFAULT.
7. **Foreign keys con ON DELETE/UPDATE**: CASCADE, SET NULL, RESTRICT.

## Anti-Patrones
- Usar VARCHAR(MAX) sin limite real, desperdicia storage.
- Indexar todo "por si acaso", degrade writes.
- Crear tablas sin normalized form, anomalias de insercion/actualizacion.
- No usar constraints, depende de la aplicacion para integridad.
- Olvidar indices en foreign keys, slow joins garantizados.
- Usar FLOAT para dinero, errores de redondeo acumulados.
- Crear tablas sin considering queries, luego el rendimiento es malo.

## Formato de Salida Obligatorio
```sql
-- PostgreSQL Example
CREATE TABLE orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    total_amount DECIMAL(12, 2) NOT NULL,
    currency_code CHAR(3) NOT NULL DEFAULT 'USD',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT chk_status CHECK (status IN ('pending', 'processing', 'shipped', 'delivered', 'cancelled')),
    CONSTRAINT chk_positive_amount CHECK (total_amount > 0)
);

-- Indexes for common query patterns
CREATE INDEX idx_orders_user_id ON orders(user_id);
CREATE INDEX idx_orders_status ON orders(status) WHERE status != 'delivered';
```