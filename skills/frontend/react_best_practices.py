"""Skill: React Best Practices — Migración automática de 17_react_best_practices.md."""
from core.skills.base import BaseSkill


class ReactBestPracticesSkill(BaseSkill):
    """React Best Practices."""

    name = "React Best Practices"
    agency = "Frontend"
    keywords = ['react', 'hooks', 'componente', 'jsx', 'estado', 'prop', 'virtual dom', 'next.js']

    def get_instructions(self) -> str:
        return """## React Best Practices

**Agencia:** Frontend
**Rol Sugerido:** @frontend_developer

## Objetivo de la Skill
Implementa aplicaciones React con hooks optimizados, memoizacion apropiada, y patrones de composicion que maximizan rendimiento y mantenibilidad. Evita re-renders innecesarios y memory leaks.

## Metodologia de Razonamiento (Paso a Paso)
1. **Component decomposition**: Extraer componentes pequenos y enfocados.
2. **State colocation**: Colocar estado lo mas cerca posible de donde se usa.
3. **Custom hooks extraction**: Extraer logica reusable en hooks personalizados.
4. **useMemo para computacion costosa**: Solo para calculos que dependen de datos especificos.
5. **useCallback para callbacks**: Solo cuando el callback se pasa a child optimizado.
6. **React.memo para components**: Solo cuando el component recibe mismas props frecuentemente.
7. **useEffect cleanup**: Siempre limpiar side effects (subscriptions, timers).
8. **Code splitting**: Lazy load componentes no criticos.

## Anti-Patrones
- useMemo/useCallback ubiquitous sin medicion.
- React.memo en todos los components.
- useEffect sin dependencias o con demasiadas.
- Callbacks en dependencies de useEffect.
- Mutating state directamente.
- No limpiar intervals/timeouts en unmount.
- Props que cambian referencia en cada render.

## Formato de Salida Obligatorio
```typescript
const UserList = React.memo(({ userIds, onSelect }: UserListProps) => {
  const users = useUsers(userIds);
  const sortedUsers = useMemo(
    () => [...users].sort((a, b) => a.name.localeCompare(b.name)),
    [users]
  );
  const handleSelect = useCallback((userId: string) => onSelect(userId), [onSelect]);
  return <ul>{sortedUsers.map(u => <UserItem key={u.id} user={u} onSelect={handleSelect} />)}</ul>;
});

function useWebSocket(url: string) {
  const [messages, setMessages] = useState<Message[]>([]);
  useEffect(() => {
    const ws = new WebSocket(url);
    ws.onmessage = (e) => setMessages(prev => [...prev, JSON.parse(e.data)]);
    return () => ws.close();
  }, [url]);
  return { messages };
}
```"""
