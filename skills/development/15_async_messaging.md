# Async Messaging

**Agencia:** Development
**Rol Sugerido:** @integration_specialist

## Objetivo de la Skill
Diseña patrones de mensajeria asincrona para desacoplar servicios usando Kafka o RabbitMQ. Implementa Event-Driven Architecture con retry policies, dead letter queues, y idempotencia para sistemas distribuidos resilientes.

## Metodologia de Razonamiento (Paso a Paso)
1. **Identificacion de events vs commands**:
   - Event: Algo queoccurrio (OrderCreated)
   - Command: Una accion a ejecutar (ProcessPayment)
2. **Diseño de topic/queue structure**:
   - Topics para pub/sub (events)
   - Queues para point-to-point (commands)
3. **Schema definition**:
   - JSON Schema o Avro para validation
   - Include version en mensajes
   - Include correlationId para tracing
4. **Consumer group design**:
   - Un consumer group por servicio
   - Particiones segun scalability needs
5. **Retry & Dead Letter Queue**:
   - Exponential backoff retry policy
   - Max retry attempts before DLQ
   - DLQ para inspeccion y reprocessing
6. **Idempotency**: Consumidores deben ser idempotentes.

## Anti-Patrones
- Acoplar producers con consumers, pierde flexibilidad.
- No incluir message versioning.
- Mensajes sin correlation ID, imposible tracing.
- No manejar mensajes duplicados.
- Ignorar consumer lag.
- Mensajes sin schema validation.

## Formato de Salida Obligatorio
```typescript
class OrderEventProducer {
  async publishOrderCreated(order: Order): Promise<void> {
    const event = {
      eventType: 'ORDER_CREATED',
      version: '1.0.0',
      correlationId: uuid(),
      timestamp: DateTime.now().toISO(),
      payload: {
        orderId: order.id.value,
        userId: order.userId.value,
        totalAmount: order.totalAmount.toPrimitive()
      }
    };
    await this.producer.send({
      topic: 'commerce.orders.events',
      messages: [{ key: order.id.value, value: JSON.stringify(event) }]
    });
  }
}
```