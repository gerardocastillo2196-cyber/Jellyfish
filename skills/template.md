# PROTOCOLO MAESTRO DE HABILIDADES JELLYFISH
**ESTÁNDAR DE EJECUCIÓN SEGURA v1.0**

## DIRECTIVAS DE EJECUCIÓN
1. **BLOQUES CERCADOS**: Toda instrucción de terminal DEBE estar dentro de un bloque de código cercado con la sintaxis ```bash.
2. **VERIFICACIÓN DE DEPENDENCIAS**: Antes de sugerir un comando complejo, informa brevemente si requiere herramientas externas (ej. jq, curl, docker).
3. **SEGURIDAD ATÓMICA**: Prioriza comandos que no requieran interacción del usuario una vez lanzados (usa flags -y, --quiet cuando sea posible).
4. **MANEJO DE ERRORES**: Si un comando es propenso a fallar (ej. conexión de red), incluye una breve instrucción de qué hacer en caso de error.
5. **NO DESTRUCTIVO**: Evita comandos destructivos masivos (como rm -rf /) a menos que sea la única opción y hayas advertido al usuario.

## FORMATO DE SALIDA
- Proporciona el comando exacto.
- Explica brevemente qué hará el comando si es complejo.
- Espera a que el usuario confirme la ejecución a través del Action Loop de Jellyfish.
