## Retrospectiva 2026-05-24 20:31

## 📋 BACKLOG RECOVERY


### US-001: Arquitectura y Capas Base de la Aplicación
- **Como** Desarrollador del sistema, **quiero** andamiar la idea inicial: 'DAILY.md:
# 📝 Daily Standup Log

> Registro de com...', **para** garantizar la continuidad del flujo de desarrollo.
#### Criterios de Aceptación:
  - Dado que la entrada fue procesada con fallas de respuesta por el LLM, cuando el Task Runner la reciba, entonces creará las configuraciones base requeridas.
  - Prioridad: Must-have | Estimación: 5pts


---

## Retrospectiva 2026-05-24 21:45

---

### Summary of Tasks Completed:

- **Backend Development:**
  - Implemented logic for responding to surveys offline.
  - Created a system for storing and sending reports.

- **Frontend Development:**
  - Organized all files into a specific directory structure.
  
- **UI/UX Design:**
  - Developed user interfaces with options to modify the appearance.

- **Data Science:**
  - Set up a system to store and send documents and reports.

- **DevOps:**
  - Updated the server to handle modifications to surveys.
  - Organized all files in a specific directory structure.

- **QA and Testing:**
  - Defined QA strategies for retrieving artifacts and installation tests.

- **Security:**
  - Defined security policies and management practices for encrypted keystores.

- **Analytics:**
  - Created an architecture for recommending items (blocks).

- **Recommendations Engine:**
  - Designed the architecture of the recommendation engine, including UI/UX blocks.

### Summary of Tasks In Progress:

- **CI/CD Pipeline Configuration:**
  - Defined requirements and set up scripts for the CI/CD pipeline.
  - Implemented script for automatic compilation on main push.
  
- **Environment Setup:**
  - Configured scripts to initialize both local and server environments.

- **Performance Analysis:**
  - Conducted performance analysis, identified memory leaks, and CPU issues.

- **Auditing and Reporting:**
  - Consolidated findings into a final audit report for recommendations engine blocks.

### Summary of Tasks Scheduled:

- **Final Integration Testing:**
  - Perform final integration testing to ensure all components work seamlessly together.

- **Documentation:**
  - Prepare comprehensive documentation for each component, focusing on user interfaces and backend logic.

- **User Feedback Loop:**
  - Gather user feedback to iterate on current designs and functionalities.

---

### Conclusion:

The project has made significant progress in various areas including backend, frontend, and UI/UX design. The CI/CD pipeline is being configured, and the environment setup scripts are refined to ensure efficient development processes. Performance analysis and auditing have identified areas for improvement that will be addressed in subsequent stages. The final integration testing will help validate the overall system's functionality before going live.

---

## Retrospectiva 2026-05-26 22:52

# Lecciones Aprendidas y Reglas Recomendadas

## Fallas Durante el Sprint
1. **Repetición de Tareas**: Algunos agentes realizaron tareas que ya habían sido completadas, lo que duplicó esfuerzos y tiempo.
2. **Desincronización de Archivos**: Hubo inconsistencias en la generación de archivos, donde algunos agentes crearon documentos con sufijos numéricos (`D-001`, `D-002`, etc.) mientras otros no.

## Reglas Recomendadas
1. **Evitar Repetición de Tareas**: **Negativa Prompts:** Evita que los agentes repitan tareas que ya han sido completadas en el sprint.
2. **Consistencia en la Generación de Archivos**: **Positive Prompts:** Establece un sistema consistente para generar archivos, preferiblemente con un formato uniforme y sin sufijos numéricos para evitar confusiones.

```markdown
# Reglas Recomendadas

- **Evitar Repetición de Tareas**:
  - Negativa Prompts: Evita que los agentes repitan tareas que ya han sido completadas en el sprint.
  
- **Consistencia en la Generación de Archivos**:
  - Positive Prompts: Establece un sistema consistente para generar archivos, preferiblemente con un formato uniforme y sin sufijos numéricos para evitar confusiones.
```

Estas lecciones y reglas ayudarán a mejorar la eficiencia y la coherencia del trabajo en futuros sprints de Jellyfish OS.

---

## Retrospectiva 2026-05-27 02:24

# 📝 Lecciones Aprendidas y Reglas de Acción

Durante el sprint, los agentes lograron completar todas las tareas asignadas con éxito. Sin embargo, se identificó un error recurrente en la documentación generada por algunos agentes. Específicamente, no todos los archivos estaban correctamente nombrados y organizados, lo que dificultó el seguimiento de los avances del proyecto.

## Fallas Identificadas
1. **Errores de Nomenclatura:** Algunos archivos no seguiron un formato consistente o coherente, lo que llevó a confusión durante el seguimiento.
2. **Dependencias Desactualizadas:** La documentación de ciertos componentes del sistema no reflejaba las últimas modificaciones realizadas en los mismos.

## Reglas Recomendadas
1. **Formato Consistente para Archivos:** Todos los archivos generados deben seguir un formato consistente, incluyendo una convención de nombres clara y coherente.
2. **Actualización Regular de Documentación:** La documentación debe actualizarse regularmente para reflejar las últimas modificaciones en los componentes del sistema.

Estas reglas ayudarán a prevenir errores futuros y mejorar la organización general del proyecto, facilitando la colaboración entre los agentes y el seguimiento de los avances.

---

## Retrospectiva 2026-05-27 12:34

# 📊 Reporte del Scrum Master: Lecciones Aprendidas y Reglas de Acción (Jellyfish OS)

**Para:** Equipo de Desarrollo de Jellyfish OS  
**De:** Scrum Master  
**Fecha de Análisis:** 27 de Mayo de 2026  
**Estado del Sprint:** Inicialización / Planificación del Sprint 1  

---

## 1. Análisis del Estado Actual (`DAILY.md`)

La bitácora actual registra únicamente el hito de **inicialización del proyecto** (2026-05-27). 
* **Estado:** Sin fallos reportados ni impedimentos activos hasta el momento. El proyecto se encuentra en fase de planificación.
* **Diagnóstico:** Al ser el "Día 0", el riesgo principal es la falta de fricción inicial. Para evitar que los agentes cometan errores comunes de desarrollo autónomo una vez que comience la ejecución, debemos establecer **reglas proactivas de control de calidad y mitigación de errores**.

---

## 2. Riesgos Identificados y Fallos Comunes a Prevenir

Basado en el comportamiento estándar de agentes autónomos en entornos de desarrollo de sistemas operativos/sistemas complejos (como Jellyfish OS), anticipamos los siguientes puntos críticos de fallo:

1. **Bucles de Auto-healing Infinitos:** Agentes intentando corregir un error de compilación repetidamente usando la misma estrategia fallida.
2. **Infierno de Dependencias (Dependency Hell):** Introducción de librerías externas incompatibles con el núcleo de Jellyfish OS.
3. **Falta de Pruebas Locales:** Subir cambios directamente al repositorio sin verificar la compilación o el paso de tests unitarios.
4. **Silencio de Bloqueos:** Agentes que no actualizan el `DAILY.md` cuando encuentran un impedimento técnico, retrasando la intervención humana o de otros agentes.

---

## 3. Reglas de Acción y Negative Prompts para Agentes

Para garantizar una ejecución limpia del Sprint, se implementan las siguientes directrices obligatorias para todos los agentes de Jellyfish OS.

### 🚫 NEGATIVE PROMPTS (Lo que NO deben hacer los agentes)

* **NO hagas commits directos a `main`** sin antes ejecutar la suite de pruebas local y verificar que el build compile al 100%.
* **NO entres en bucles de corrección automática (Auto-healing):** Si un error de compilación o test persiste después de **dos (2) intentos** de corrección, detén el proceso, documenta el error en `DAILY.md` como `[IMPEDIMENTO]` y solicita asistencia.
* **NO agregues dependencias externas** (paquetes npm, crates de Rust, librerías de C, etc.) en los archivos de configuración sin la aprobación explícita del Scrum Master o del Arquitecto de Software en el backlog.
* **NO dejes el archivo `DAILY.md` sin actualizar** al final de tu ciclo de ejecución. Está prohibido omitir el estado de los impedimentos.

### 🎯 MEJORES DIRECTRICES (Lo que SÍ deben hacer los agentes)

* **Compilación Primero:** Antes de dar una tarea por finalizada, ejecuta el comando de build específico del proyecto (ej. `npm run build`, `cargo build`, etc.) y adjunta el resultado exitoso en los logs de la tarea.
* **Formato de Daily Estricto:** Cada actualización en `DAILY.md` debe seguir la estructura:
  ```markdown
  ### @nombre_agente
  - **Ayer:** [Breve descripción de lo completado]
  - **Hoy:** [Foco principal del día]
  - **Impedimentos:** [Ninguno / Detalle del bloqueo técnico con logs]
  ```
* **Aislamiento de Cambios:** Trabaja siempre en ramas de características (`feature/`) específicas y abre un Pull Request (PR) para la revisión de código. No mezcles múltiples tareas en un solo PR.

---

## Retrospectiva 2026-05-27 12:37

¡Hola equipo de Jellyfish OS! Como Scrum Master, he analizado nuestra bitácora inicial en `DAILY.md` y el estado de arranque del proyecto. 

Aunque estamos en el Día 1 (Planificación del Sprint 1) y técnicamente "no hay impedimentos" registrados por mi parte, el análisis del estado actual revela un **olor de proceso (process smell)** crítico y riesgos técnicos latentes que debemos mitigar de inmediato antes de que los agentes comiencen a escribir código.

A continuación, presento el reporte de lecciones aprendidas tempranas y las reglas de acción (Negative Prompts y Directrices) para blindar la ejecución de nuestros agentes.

---

# 📋 Reporte de Scrum Master: Lecciones Aprendidas y Reglas de Ejecución

## 1. ¿Qué falló (o está fallando) en este inicio de Sprint?

*   **Silencio y falta de sincronización de los Agentes de Desarrollo/QA:** El `DAILY.md` solo registra la actividad del `@scrum_master`. Los agentes de desarrollo (`@developer`), arquitectura (`@architect`) o testing (`@tester`) no han reportado su estado de alineación para el Sprint 1. En un entorno multi-agente, el silencio es el primer síntoma de desalineación.
*   **Riesgo de "Cold Start" sin restricciones:** Al no haber reglas claras de compilación y dependencias desde el día cero, los agentes de desarrollo tienden a tomar decisiones autónomas que rompen el entorno local (ej. instalar dependencias incompatibles o entrar en bucles infinitos de corrección de errores).

---

## 2. Reglas Recomendadas para Futuros Agentes (Negative Prompts y Directrices)

Para asegurar que los agentes de Jellyfish OS operen de manera eficiente, sin romper el repositorio y manteniendo la transparencia, se establecen las siguientes reglas de comportamiento obligatorias.

### 🚫 NEGATIVE PROMPTS (Lo que los agentes NO deben hacer)

1.  **NO inicies tareas de desarrollo sin actualizar el Daily:**
    *   *Negative Prompt:* `[CONSTRAINT] DO NOT start writing code or modifying files for a user story without first writing your daily standup entry in DAILY.md under the current date section.`
2.  **NO entres en bucles infinitos de Auto-Healing:**
    *   *Negative Prompt:* `[CONSTRAINT] DO NOT attempt to auto-heal or fix a compilation/test error more than 3 times consecutively. If the build fails 3 times after your fixes, STOP, roll back to the last stable commit, and log an IMPEDIMENT in DAILY.md tagging @scrum_master.`
3.  **NO instales dependencias "fantasma":**
    *   *Negative Prompt:* `[CONSTRAINT] DO NOT install any third-party library or package without immediately declaring it in the project's dependency manifest (e.g., package.json, requirements.txt, go.mod) in the exact same commit.`
4.  **NO hagas commits con pruebas rotas:**
    *   *Negative Prompt:* `[CONSTRAINT] DO NOT push or commit code to the main/develop branch if the local test suite is failing. Broken builds are strictly prohibited.`

---

### 🎯 DIRECTRICES DE ACCIÓN (Mejores Prácticas)

#### A. Protocolo de Comunicación Diaria (Daily Standup)
Cada vez que un agente sea invocado o complete un ciclo de trabajo en el día, debe actualizar el archivo `DAILY.md` con el siguiente formato estricto:

```markdown
### @nombre_agente
- **Ayer:** [Qué hiciste brevemente]
- **Hoy:** [Qué vas a hacer ahora]
- **Impedimentos:** [Ninguno / Detalle del bloqueo técnico]
```

#### B. Gestión de Errores de Compilación y Dependencias
*   **Validación Local Obligatoria:** Antes de dar por terminada una tarea, el agente debe ejecutar el comando de compilación y la suite de pruebas unitarias.
*   **Aislamiento de Cambios:** Si una dependencia rompe el entorno de Jellyfish OS, el agente debe revertir el cambio inmediatamente y proponer una alternativa en el log, en lugar de intentar parchar el error con más dependencias dudosas.

---

### Próximos Pasos:
He habilitado el espacio para el Sprint 1. Los agentes asignados a las tareas de desarrollo deben presentarse en el `DAILY.md` de hoy para registrar su plan de trabajo. ¡Hagamos de Jellyfish OS un sistema robusto y eficiente!

---

## Retrospectiva 2026-05-27 12:54

# 🕵️‍♂️ Reporte del Scrum Master: Lecciones Aprendidas y Reglas de Acción
**Proyecto:** Jellyfish OS  
**Fecha de Análisis:** 28 de Mayo de 2026 (Post-Kickoff)

---

## 1. Diagnóstico del Estado Actual y Fallas Detectadas

Al analizar la bitácora `DAILY.md`, se identifica un fallo crítico de **proceso y comunicación agentic**:

### 🔴 El Síndrome del "Agente Fantasma" (Ghosting de Ejecución)
* **Qué falló:** El sprint fue planificado e inicializado el 2026-05-27. Sin embargo, **no existen registros de los agentes de desarrollo (Dev) ni de pruebas (QA)** en los días subsecuentes. 
* **Causa raíz:** Los agentes están ejecutando tareas en segundo plano (o se han quedado bloqueados en bucles de ejecución/auto-healing) sin actualizar el canal de comunicación síncrona (`DAILY.md`). 
* **Impacto:** Pérdida total de visibilidad. No podemos saber si el sprint está detenido por errores de compilación, dependencias rotas o si los agentes simplemente no se han activado.

---

## 2. Reglas Recomendadas para Futuros Agentes (Negative Prompts y Directrices)

Para evitar que este comportamiento se repita y asegurar que Jellyfish OS mantenga un flujo de desarrollo saludable, se establecen las siguientes reglas de comportamiento obligatorias para todos los agentes del sistema.

### 🚫 Negative Prompts (Lo que NO deben hacer los agentes)

* **`PROHIBIDO_TRABAJO_SILENCIOSO`**: No realices commits, modificaciones de código o ejecuciones de pruebas sin haber actualizado primero tu estado diario en `DAILY.md`. Si trabajas en una tarea, debe haber un registro de "Ayer/Hoy/Impedimentos".
* **`PROHIBIDO_BUCLE_INFINITO_AUTOHEALING`**: No intentes corregir un error de compilación o de dependencias más de **3 veces** de forma autónoma. Si el auto-healing falla en el tercer intento, detén la ejecución, documenta el error en `DAILY.md` bajo la sección de **Impedimentos** y solicita intervención.
* **`PROHIBIDO_IGNORAR_DEPENDENCIAS`**: No instales paquetes de sistema o dependencias de Node/Python sin verificar la compatibilidad con el core de Jellyfish OS. No asumas que los entornos de ejecución tienen acceso ilimitado a internet.

### 🟢 Directrices de Acción (Lo que SÍ deben hacer los agentes)

1. **Actualización Obligatoria por Ciclo de Vida:**
   * Cada vez que un agente tome una tarea del Backlog, debe escribir en `DAILY.md` usando el formato estándar:
     ```markdown
     ### @nombre_agente
     - **Ayer:** [Qué hiciste]
     - **Hoy:** [Qué vas a hacer]
     - **Impedimentos:** [Bloqueos, errores de compilación, etc.]
     ```
2. **Protocolo de Escalación de Errores:**
   * Si una prueba falla o el build se rompe, el agente de QA o Dev debe registrar inmediatamente el error exacto en la sección de **Impedimentos** del Daily Log.
3. **Sincronización de Estado:**
   * Antes de dar por terminada una tarea en el tablero Kanban, el agente debe validar que su último mensaje en `DAILY.md` refleje el éxito de la operación.

---

## Retrospectiva 2026-05-27 13:00

# 🕵️‍♂️ Reporte del Scrum Master: Lecciones Aprendidas y Reglas de Acción
**Proyecto:** Jellyfish OS  
**Estado del Sprint:** Post-Planificación / Inicio de Ejecución  
**Analizado por:** Scrum Master Agent  

---

## 1. Análisis del Estado Actual y Fallas Identificadas

Al analizar la bitácora `DAILY.md`, se observa que el proyecto se encuentra en su fase inicial absoluta (Planificación del Sprint 1). Aunque el log indica *"Impedimentos: Ninguno"*, desde la perspectiva de Scrum y la coordinación de agentes, se identifican las siguientes **fallas de proceso y riesgos latentes**:

### Fallas Detectadas:
1. **Silencio de los Agentes de Ejecución:** Solo el `@scrum_master` ha registrado actividad. Los agentes de Desarrollo (Dev), Aseguramiento de Calidad (QA) y DevOps no han iniciado su participación en la bitácora. 
2. **Falta de Detalle Técnico Proactivo:** El registro actual es demasiado genérico. En entornos de agentes autónomos, la falta de estructura en el primer día suele derivar en problemas de dependencias y desalineación en los días subsecuentes.

---

## 2. Reglas Recomendadas (Negative Prompts y Directrices)

Para evitar que los agentes cometan errores comunes de compilación, dependencias, bucles de *auto-healing* o reportes deficientes durante el sprint, se establecen las siguientes reglas de acción obligatorias.

### 🚫 Negative Prompts para los Agentes

#### 1. Sobre el Registro en `DAILY.md` (Evitar el "Silencio de Radio")
> **PROHIBIDO** finalizar un ciclo de ejecución o jornada de desarrollo sin actualizar el archivo `DAILY.md`. 
> **PROHIBIDO** usar estados genéricos como "Trabajando en la tarea" o "Sin impedimentos" si se presentaron errores de compilación, de tests o de dependencias, incluso si estos fueron resueltos por mecanismos de *auto-healing*. Todo error superado debe ser registrado como lección aprendida.

#### 2. Sobre Gestión de Dependencias y Entorno
> **PROHIBIDO** instalar paquetes, librerías o dependencias de forma local/temporal sin actualizar inmediatamente los archivos de configuración del proyecto (`package.json`, `requirements.txt`, `go.mod`, etc.).
> **PROHIBIDO** asumir que un entorno de ejecución externo tiene preinstaladas herramientas que no estén explícitamente declaradas en el repositorio.

#### 3. Sobre Bucles de Auto-Healing (Auto-corrección)
> **PROHIBIDO** realizar más de tres (3) intentos consecutivos de *auto-healing* (corrección automática de código/compilación) sobre el mismo error. Si el error persiste tras el tercer intento, el agente **DEBE** detenerse, registrar el impedimento detallado en `DAILY.md` con el stack trace, y solicitar intervención o feedback del Scrum Master/Usuario.

---

### 🛠️ Directrices de Buenas Prácticas para el Sprint

*   **Formato de Reporte Diario Obligatorio para Agentes:**
    Cada agente (Dev, QA, DevOps) deberá reportar bajo el siguiente esquema estricto:
    ```markdown
    ### @nombre_agente
    - **Ayer:** [Qué código/test/infraestructura se escribió/modificó]
    - **Hoy:** [Objetivo específico del día]
    - **Impedimentos/Errores:** [Ninguno / Detalle de errores de compilación o dependencias encontrados y cómo se resolvieron]
    ```
*   **Compilación Temprana:** Antes de dar por terminada una tarea, el agente de desarrollo debe ejecutar el comando de build/compilación en un entorno limpio y documentar el resultado exitoso.

---

## Retrospectiva 2026-05-27 14:29

# 🕵️‍♂️ Reporte del Scrum Master: Lecciones Aprendidas y Reglas de Acción
**Proyecto:** Jellyfish OS  
**Estado del Sprint:** Inicialización / Planificación de Sprint 1  
**Fecha de Análisis:** 2026-05-27  

---

## 1. Análisis del Estado Actual (DAILY.md)

La bitácora actual muestra únicamente el registro de inicialización del proyecto por parte del `@scrum_master` el **2026-05-27**. 

*   **Fallas detectadas:** Ninguna de manera activa en el código, ya que el desarrollo técnico no ha comenzado.
*   **Riesgo detectado:** Falta de participación activa de otros agentes en el Daily. Para que la metodología Scrum funcione, los agentes de desarrollo, testing y arquitectura deben reportar su estado diariamente.

---

## 2. Reglas de Acción y "Negative Prompts" para Futuros Sprints

Para prevenir los errores comunes en entornos de desarrollo basados en agentes (como bucles infinitos de auto-healing, dependencias rotas y falta de comunicación), se establecen las siguientes directrices de obligatorio cumplimiento para todos los agentes de Jellyfish OS.

### 🚫 NEGATIVE PROMPTS (Lo que los agentes NO deben hacer)

1. **NO omitir el registro diario:** 
   * *Negative Prompt:* `PROHIBIDO realizar commits, modificaciones de código o avanzar en tareas del backlog sin haber actualizado previamente el archivo DAILY.md con tu estado actual, tareas de ayer, tareas de hoy e impedimentos.`
2. **NO entrar en bucles infinitos de Auto-Healing:** 
   * *Negative Prompt:* `PROHIBIDO realizar más de 3 intentos consecutivos de auto-healing (corrección automática de errores de compilación o tests) de forma autónoma. Si el tercer intento falla, detén la ejecución, documenta el error en DAILY.md como un IMPEDIMENTO y solicita intervención del Scrum Master o Arquitecto.`
3. **NO romper dependencias sin validación cruzada:** 
   * *Negative Prompt:* `PROHIBIDO actualizar, agregar o eliminar dependencias en los archivos de configuración del proyecto (ej. package.json, requirements.txt, go.mod) sin ejecutar una suite de pruebas de regresión completa antes de hacer commit.`
4. **NO silenciar errores de compilación:** 
   * *Negative Prompt:* `PROHIBIDO usar bloques try-catch vacíos, ignorar warnings de compilación críticos o forzar flags de ignorar errores (--force, --legacy-peer-deps, etc.) para hacer que el código "pase" la pipeline.`

---

### 🟢 DIRECTRICES DE ACCIÓN (Lo que los agentes DEBEN hacer)

1. **Formato Estricto de Comunicación:**
   Cada agente debe reportar en `DAILY.md` utilizando exactamente el siguiente formato:
   ```markdown
   ### @nombre_agente
   - **Ayer:** [Qué hiciste]
   - **Hoy:** [Qué vas a hacer]
   - **Impedimentos:** [Ninguno / Detalle del bloqueo]
   ```

2. **Estrategia de Auto-Healing Controlada:**
   Si un test o compilación falla, el agente debe:
   * Identificar la causa raíz (no solo parchar el síntoma).
   * Registrar el error en el log de ejecución.
   * Si se resuelve, documentar brevemente la solución en el Daily del día siguiente para transferir el conocimiento.

3. **Definición de Terminado (DoD - Definition of Done):**
   Ninguna tarea se considera finalizada si no cumple con:
   * Código limpio y documentado.
   * Pruebas unitarias pasando al 100%.
   * Registro correspondiente en `DAILY.md`.
   * Sin warnings de compilación activos.

---

## Retrospectiva 2026-05-27 14:54

# 🕵️‍♂️ Reporte del Scrum Master: Retrospectiva de Ejecución (Sprint 1)

Como Scrum Master de **Jellyfish OS**, he analizado la bitácora de ejecución del `DAILY.md`. A pesar de que todas las tareas registradas figuran como "Completado con éxito", un análisis profundo del flujo de trabajo, las dependencias y la secuencia de tareas revela brechas críticas de integración, inconsistencias técnicas y omisiones que deben corregirse de inmediato para futuros sprints.

---

## 1. Análisis de Fallos y Riesgos Detectados

### ⚠️ El "Vacío" de la Tarea T-010 (Fallo de Orquestación)
*   **Qué falló:** Existe un salto directo de la tarea `T-009` (Generación de PDF) a la `T-011` (Endpoints API). **La tarea T-010 desapareció del flujo.**
*   **Impacto:** Al revisar la arquitectura propuesta en `T-001` (*Offline-First + Sync*), el motor de sincronización bidireccional (Android <-> Servidor) era el núcleo del sistema. Al no ejecutarse la T-010, el sistema actual está fragmentado: la app guarda localmente (`T-004`) y el servidor expone endpoints (`T-011`), pero **no existe el puente de sincronización activa**.

### ⚠️ Inconsistencia Tecnológica y Deuda Técnica Temprana
*   **Qué falló:** El backend se desarrolló en JavaScript puro (`surveyController.js` en `T-011`), mientras que el panel de administración se construyó en TypeScript (`App.tsx` en `T-012`). 
*   **Impacto:** Falta de tipado unificado entre el cliente administrativo y la API, lo que generará errores de integración en tiempo de ejecución al consumir los cuestionarios dinámicos.

### ⚠️ Puntos Ciegos de Compilación y Dependencias (Android)
*   **Qué falló:** Se implementó SQLCipher (`T-004`) y un generador de PDF (`T-009`) sin un paso previo de validación de dependencias en el `build.gradle`.
*   **Impacto:** SQLCipher requiere inicialización nativa (`SQLiteDatabase.loadLibs(context)`) y dependencias específicas de arquitectura (ARM/x86). Sin pruebas de compilación cruzada, la app fallará al iniciar en dispositivos reales.

### ⚠️ Ausencia Total de QA y Pruebas Unitarias
*   **Qué falló:** El sprint se dio por cerrado sin una sola tarea de testing (unitario, de integración o de UI).
*   **Impacto:** El motor de scoring financiero (`T-008`) y el renderizador dinámico (`T-007`) son altamente propensos a fallos lógicos que no han sido validados.

---

## 2. Reglas de Acción y Negative Prompts para Futuros Agentes

Para evitar que estos errores de integración, consistencia y omisión se repitan, se establecen las siguientes directrices estrictas para los agentes de Jellyfish OS:

### 🚫 Negative Prompts (Lo que NO deben hacer los agentes)

```markdown
- [NO] procedas con la implementación de código sin haber verificado la secuencia numérica correlativa de las tareas del Sprint (ej. no saltar de T-009 a T-011 sin justificar la omisión de T-010).
- [NO] mezcles paradigmas de tipado en el mismo entorno de backend/frontend (ej. NO uses JavaScript para la API si el cliente web o móvil consume tipos estrictos en TypeScript/Kotlin).
- [NO] agregues librerías nativas complejas en Android (como SQLCipher o generadores de PDF de terceros) sin actualizar y verificar explícitamente el archivo `build.gradle` y los archivos de inicialización de la aplicación.
- [NO] des por "Completada" una tarea de desarrollo de core-business (como algoritmos de scoring o motores de renderizado) sin adjuntar o referenciar su respectivo archivo de pruebas unitarias (*Test.kt / *test.js).
- [NO] asumas que el almacenamiento local y el servidor se comunicarán por arte de magia; prohíbase omitir el desarrollo del agente/módulo de sincronización (Sync Manager).
```

### 🛠️ Mejores Directrices de Ejecución (Reglas de Oro)

1.  **Trazabilidad de Secuencia Obligatoria:** Antes de iniciar una tarea, el agente debe validar que la tarea inmediatamente anterior en el backlog haya sido completada y que sus outputs (ej. esquemas de base de datos o contratos de API) estén disponibles.
2.  **Contrato de API Primero (API-First):** El desarrollador de Backend (`@backend_dev`) y el de Frontend (`@frontend_dev`) deben acordar y documentar un JSON Schema de los cuestionarios dinámicos antes de escribir código en `surveyController.js` o `DynamicFormRenderer.kt`.
3.  **Checklist de Inicialización de SQLCipher:** Cualquier tarea que involucre `AppDatabase.kt` con encriptación debe incluir la configuración de ProGuard/R8 y la carga de librerías nativas en la clase `Application`.
4.  **Estrategia de Sincronización Explícita:** Toda arquitectura *Offline-First* debe contar con un manejador de conflictos (Conflict Resolution Policy) documentado antes de codificar los endpoints de sincronización.