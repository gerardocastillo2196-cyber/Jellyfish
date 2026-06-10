"""Skill: Domain-Driven Design — Migración automática de 09_domain_driven_design.md."""
from core.skills.base import BaseSkill


class DomainDrivenDesignSkill(BaseSkill):
    """Domain-Driven Design."""

    name = "Domain-Driven Design"
    agency = "Development"
    keywords = ['ddd', 'domain driven', 'dominio', 'bounded context', 'aggregate', 'entidad', 'value object']

    def get_instructions(self) -> str:
        return """## Domain-Driven Design

**Agencia:** Development
**Rol Sugerido:** @domain_architect

## Objetivo de la Skill
Aplica Domain-Driven Design (DDD) para modelar dominios complejos con un lenguaje ubicuo compartido entre developers y domain experts. Define bounded contexts, aggregates, value objects, y repositories que capturan la esencia del negocio.

## Metodologia de Razonamiento (Paso a Paso)
1. **Identificacion del Ubiquitous Language**: Documenta terminos del dominio con definiciones exactas.
2. **Definicion de Bounded Contexts**: Delimita areas del dominio con responsabilidades claras.
3. **Identificacion de Aggregates**: Grupos de entities relacionadas que se modifican juntas.
4. **Diseño de Aggregate Roots**: Una sola entity por aggregate que controla el acceso.
5. **Creacion de Value Objects**: Objetos inmutables sin identidad propia (Money, Address, DateRange).
6. **Definicion de Domain Events**: Eventos que representan cambios de estado significativos.
7. **Diseño de Repositories**: Abstracciones para persistir aggregates, no tablas.
8. **Mapeo de Context Maps**: Visualiza relaciones entre bounded contexts.

## Anti-Patrones
- Crear un "god aggregate" que contiene todo el sistema.
- Violar aggregate boundaries haciendo referencias entre aggregates por ID.
- Modelar el mundo real como base de datos (anemic domain model).
- Usar terminos tecnicos en lugar del lenguaje del negocio.
- Ignorar bounded contexts, intenta modelar toda la empresa en un modelo.
- Exponer entidades internas a traves de la API, rompe encapsulacion.
- No aplicar invariantes, permite estados inconsistentes en produccion.

## Formato de Salida Obligatorio
```typescript
// Value Object Example
class Money {
  private constructor(
    public readonly amount: Decimal,
    public readonly currency: Currency
  ) {}

  static of(amount: number, currency: string): Money {
    return new Money(new Decimal(amount), new Currency(currency));
  }

  add(other: Money): Money {
    if (!this.currency.equals(other.currency)) {
      throw new DomainException('Cannot add money of different currencies');
    }
    return new Money(this.amount.plus(other.amount), this.currency);
  }
}

// Aggregate Root Example
class Order extends AggregateRoot {
  static create(customerId: CustomerId): Order {
    const order = new Order(OrderId.generate(), customerId, [], OrderStatus.DRAFT, DateTime.now());
    order.addDomainEvent(new OrderCreatedEvent(order.id));
    return order;
  }

  confirm(): void {
    if (this.items.isEmpty()) {
      throw new DomainException('Cannot confirm order without items');
    }
    this.status = OrderStatus.CONFIRMED;
    this.addDomainEvent(new OrderConfirmedEvent(this.id));
  }
}
```"""
