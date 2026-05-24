# GraphQL Schema Design

**Agencia:** Development
**Rol Sugerido:** @backend_developer

## Objetivo de la Skill
Diseña schemas GraphQL eficientes con queries optimizadas, mutations bien definidas, y subscriptions para real-time updates. Balancea la flexibilidad de GraphQL con la eficiencia del servidor.

## Metodologia de Razonamiento (Paso a Paso)
1. **Identificacion de domain entities**: User, Product, Order, etc.
2. **Diseño de tipos segun modelo de negocio**:
   - Object Types: Entidades con ID unico
   - Input Types: Para mutations
   - Enum Types: Status, roles, categorias
   - Scalar Types: DateTime, UUID, Decimal
3. **Diseño de Queries**:
   - Queries para lectura, mutations para escritura
   - Args con paginacion (first, after, limit)
   - Filtros como input types
4. **Diseño de Mutations**:
   - Convencion: `verb + Noun` (createUser, updateProduct)
   - Input type para cada mutation
   - Payload type con success flag y data/errors
5. **N+1 problem solutions**:
   - DataLoader para batching y caching
   - Query complexity analysis
   - Max depth limits

## Anti-Patrones
- Exponer la base de datos directamente en el schema.
- No usar DataLoader, causa N+1 queries masivas.
- Mutations que retornan todo el objeto modificado.
- No validar argumentos.
- Sin rate limiting.
- Queries sin limite.

## Formato de Salida Obligatorio
```graphql
type User {
  id: ID!
  email: String!
  name: String!
  orders: OrderConnection!
}

type Order {
  id: ID!
  status: OrderStatus!
  totalAmount: Decimal!
}

enum OrderStatus {
  PENDING
  CONFIRMED
  SHIPPED
  DELIVERED
}

type Mutation {
  createOrder(input: CreateOrderInput!): CreateOrderPayload!
}

type Query {
  user(id: ID!): User
  users(first: Int, after: String): UserConnection!
}
```