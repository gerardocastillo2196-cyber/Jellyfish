# TDD Methodology

**Agencia:** Development
**Rol Sugerido:** @senior_developer

## Objetivo de la Skill
Practica Test-Driven Development siguiendo el ciclo Red-Green-Refactor para crear software testeado desde el diseño, con especificaciones ejecutables y deuda tecnica controlada. Prioriza tests que reflejan comportamiento real sobre cobertura vacía.

## Metodologia de Razonamiento (Paso a Paso)
1. **RED - Escribe un test que falla**:
   - Antes de escribir codigo, escribe un test que describa el comportamiento deseado
   - El test debe fallar porque la funcionalidad no existe aun
   - Nombre descriptivo: `should_return_404_when_user_not_found`
2. **GREEN - Escribe codigo minimo para pasar**:
   - Escribe solo el codigo necesario para que el test pase
   - No optimices todavia, solo haz que funcione
   - El codigo puede ser "feo" temporalmente
3. **REFACTOR - Mejora el codigo**:
   - Elimina duplicacion
   - Aplica principios SOLID
   - Asegura que todos los tests sigan pasando
4. **Repite el ciclo**: Siguiente test, siguiente funcionalidad.
5. **Jerarquia de tests**:
   - Unit Tests: Logica pura, rapido, no I/O
   - Integration Tests: Con database real o mocks
   - E2E Tests: Flujos completos del usuario
6. **Naming convention**: `describe` para clase, `it` para metodo especifico.

## Anti-Patrones
- Escribir tests despues del codigo "por tiempo", no es TDD.
- Tests que no fallan nunca (tautologicos), no testean nada.
- Sobregenerar mocks que no testean integracion real.
- Tests que dependen de orden de ejecucion.
- No ejecutar tests frecuentemente, lose feedback loop.
- Coverage > 80% sin tests de comportamiento real.

## Formato de Salida Obligatorio
```typescript
describe('OrderService', () => {
  describe('confirmOrder', () => {
    it('should throw InvalidOrderError when order has no items', async () => {
      const emptyOrder = Order.createDraft(testCustomerId);
      const service = new OrderService(mockOrderRepository);
      
      await expect(service.confirmOrder(emptyOrder.id))
        .rejects.toThrow(InvalidOrderError);
    });

    it('should update status to CONFIRMED and emit event', async () => {
      const order = Order.createDraft(testCustomerId);
      order.addItem(testProduct, Quantity.of(2));
      const service = new OrderService(mockOrderRepository);
      
      const confirmedOrder = await service.confirmOrder(order.id);
      expect(confirmedOrder.status).toBe(OrderStatus.CONFIRMED);
    });
  });
});
```