"""Skill: Clean Architecture — Migración automática de 06_clean_architecture.md."""
from core.skills.base import BaseSkill


class CleanArchitectureSkill(BaseSkill):
    """Clean Architecture."""

    name = "Clean Architecture"
    agency = "Development"
    keywords = ['arquitectura', 'clean architecture', 'solid', 'capas', 'hexagonal', 'onion', 'ports adapters']

    def get_instructions(self) -> str:
        return """## Clean Architecture

**Agencia:** Development
**Rol Sugerido:** @software_architect

## Objetivo de la Skill
Diseña sistemas usando Clean Architecture donde las reglas de negocio estan en el centro, rodeadas de casos de uso, y alejadas de frameworks, databases y UI. Logra sistemas testeables, mantenibles e independientes.

## Metodologia de Razonamiento (Paso a Paso)
1. **Identificacion de Entities**: Objetos de negocio puros con logica intrinseca (ej: Invoice, Account, Order).
2. **Definicion de Use Cases**: Acciones que la aplicacion puede realizar (ej: CreateOrder, ProcessPayment).
3. **Separacion de capas**:
   - `Entities`: Logica de negocio pura
   - `Use Cases`: Reglas de aplicacion
   - `Interface Adapters`: Controllers, Gateways, Presenters
   - `Frameworks & Drivers`: Databases, Web Frameworks, External Services
4. **Dependency Rule**: Las dependencias solo apuntan hacia el centro. Nunca al reves.
5. **Definicion de boundaries**: Cada capa solo conoce a la capa inmediatamente inferior.
6. **Diseño de abstractions**: Define interfaces/contracts entre capas (ej: `IOrderRepository`).
7. **Dependency Injection**: Inyecta implementaciones concretas en runtime.
8. **Verificacion de testabilidad**: Puedes testar un Use Case sin database, sin UI, sin framework?

## Anti-Patrones
- Mezclar logica de negocio con codigo de framework (Doctrine, Hibernate, Express).
- Saltarse capas "por eficiencia", crea acoplamiento que destruye flexibilidad.
- Poner logica de validacion en Controllers en lugar de Use Cases o Entities.
- Consultar la database directamente desde Use Cases.
- Violar la Dependency Rule cuando hay presion de tiempo, acumula deuda tecnica.
- Crear "god classes" que conocen todo el sistema.

## Formato de Salida Obligatorio
```
src/
├── entities/
│   ├── User.ts
│   └── Product.ts
├── usecases/
│   ├── CreateOrder.ts
│   ├── ProcessPayment.ts
│   └── interfaces/
│       └── IOrderRepository.ts
├── adapters/
│   ├── controllers/
│   ├── presenters/
│   └── gateways/
└── frameworks/
    ├── database/
    ├── http/
    └── external/
```"""
