# State Management

**Agencia:** Frontend
**Rol Sugerido:** @frontend_architect

## Objetivo de la Skill
Selecciona e implementa la estrategia de state management apropiada para cada caso de uso: local state (useState), context providers, Zustand para global state, o Redux Toolkit para aplicaciones complejas.

## Metodologia de Razonamiento (Paso a Paso)
1. **Categorizacion de estado**:
   - Local UI state: Modals, dropdowns, form inputs -> useState
   - Cross-component state: Theme, auth -> Context o Zustand
   - Server state: Data de APIs con caching -> React Query / SWR
   - Form state: Validacion compleja -> React Hook Form
2. **Seleccion de herramienta**:
   - **useState**: State simple, un solo componente
   - **Zustand**: Global state con mejor rendimiento
   - **Redux Toolkit**: App grande con debugging needs
   - **React Query**: Server state con cache, refetch
3. **Separacion de concerns**: UI state vs business logic vs server state.
4. **Persistence**: LocalStorage para preferencias.
5. **Performance optimization**: Selectors para evitar re-renders.

## Anti-Patrones
- Meter todo en Redux cuando no es necesario.
- Props drilling profundo (5+ niveles).
- No separar server state de client state.
- Mutating state directamente en reducers.
- Overusing Context.
- Storing datos sensibles en localStorage sin encryption.

## Formato de Salida Obligatorio
```typescript
import { create } from 'zustand';

interface CartStore {
  items: CartItem[];
  addItem: (product: Product, quantity: number) => void;
  removeItem: (productId: string) => void;
  clearCart: () => void;
  total: () => number;
}

const useCartStore = create<CartStore>((set, get) => ({
  items: [],
  addItem: (product, quantity) => set(s => ({ items: [...s.items, { product, quantity }] })),
  removeItem: (productId) => set(s => ({ items: s.items.filter(i => i.product.id !== productId) })),
  clearCart: () => set({ items: [] }),
  total: () => get().items.reduce((sum, i) => sum + i.product.price * i.quantity, 0),
}));
```