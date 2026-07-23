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

---

## Retrospectiva 2026-05-27 15:56

# 🕵️‍♂️ Reporte del Scrum Master: Lecciones Aprendidas y Reglas de Acción
**Proyecto:** Jellyfish OS  
**Sprint:** 2026-05-27  
**Autor:** Scrum Master Agent

---

## 1. Análisis de Fallos e Incidentes (Análisis Forense)

Aunque la bitácora muestra un estado general de "Completado con éxito", un análisis detallado del flujo de trabajo, los tiempos de ejecución y la correlación de tareas revela fallos críticos de coordinación, tareas fantasma y anti-patrones de desarrollo:

### A. La Tarea Perdida: Vacío en la Secuencia (T-011)
*   **Fallo:** Existe un salto directo de la tarea **T-010** (15:39) a la **T-012** (15:44). La tarea **T-011** no fue registrada en el `DAILY.md`.
*   **Causa probable:** La tarea T-011 correspondía a la integración del cliente de sincronización en Android (el puente con el `syncController.ts` de la T-010). El agente asignado falló silenciosamente, experimentó un bucle de compilación infinito o el proceso de *auto-healing* abortó la tarea sin reportar el error al log.

### B. El "Gap" de 5 Minutos (Sospecha de Auto-healing / Compilación Fallida)
*   **Fallo:** Entre las 15:39 y las 15:44 hay una ventana de inactividad de 5 minutos. En entornos de agentes de IA, este tiempo de espera usualmente indica que un agente intentó compilar la base de datos Room con SQLCipher (T-006) o el motor de renderizado (T-007), falló debido a dependencias de Gradle/KSP incompatibles, y el sistema de *auto-healing* consumió tokens reintentando la compilación en segundo plano.

### C. Anti-patrón de Seguridad: Auditoría Tardía (Shift-Right Security)
*   **Fallo:** La auditoría de seguridad de Android Keystore y SQLCipher (T-012) se realizó a las 15:44, **después** de que el código de la base de datos (T-006) y el motor de renderizado (T-007) ya estuvieran completamente implementados y cerrados.
*   **Impacto:** Si el auditor de seguridad encuentra una vulnerabilidad en el manejo de claves de Room, se tendrá que reescribir todo el código de persistencia, generando desperdicio de recursos (*rework*).

### D. Ausencia Absoluta de Pruebas Unitarias y de Integración
*   **Fallo:** No se registra ninguna tarea de testing (Unit Tests, Espresso o Postman/Supertest para el backend). Se asumió que el código funciona solo porque "compiló".

---

## 2. Reglas Recomendadas para Futuros Sprints (Negative Prompts y Directrices)

Para evitar que estos errores de coordinación, vacíos de información y riesgos de seguridad se repitan, se establecen las siguientes reglas de diseño y ejecución para los agentes:

### 🚫 Negative Prompts (Lo que los agentes NO deben hacer)

```markdown
- NO declares una tarea como "Completada" si no has verificado que la tarea numéricamente anterior (T-X) esté registrada y cerrada en el DAILY.md.
- NO implementes código de persistencia cifrada (SQLCipher/Room) o autenticación sin que el diseño de seguridad (Keystore/Crypt) esté previamente aprobado por el Security Auditor.
- NO omitas el registro de fallos de compilación en el DAILY.md. Si una tarea requiere auto-healing o reintentos, el agente DEBE registrar un estado intermedio de [REINTENTO/AUTO-HEALING] antes de marcar el éxito.
- NO des por finalizada una tarea de desarrollo (Frontend/Backend) sin adjuntar o referenciar su respectivo archivo de pruebas unitarias (*.test.ts, *Test.kt).
```

### 🎯 Directrices de Acción (Mejores Prácticas)

1.  **Trazabilidad Estricta de Tareas (No gaps):**
    *   El orquestador de agentes debe validar que la secuencia de IDs de tareas (`T-001`, `T-002`, etc.) sea estrictamente correlativa. Si una tarea se cancela o falla críticamente, debe registrarse explícitamente como `[ESTADO: FALLIDO/CANCELADO]` en el log en lugar de desaparecer.

2.  **Seguridad "Shift-Left" Obligatoria:**
    *   La tarea de diseño de arquitectura de seguridad (ej. políticas de cifrado) debe ejecutarse en paralelo con el diseño de UI/UX, y siempre **antes** de la codificación de la base de datos local.

3.  **Sincronización de Dependencias en Android:**
    *   Antes de codificar con Room y SQLCipher, el agente de DevOps o Arquitectura debe definir y congelar las versiones de Gradle, Kotlin, KSP y SQLCipher en un archivo de configuración global (`libs.versions.toml`) para evitar bucles de compilación por incompatibilidad.

---

## Retrospectiva 2026-05-27 16:09

# 📊 Reporte del Scrum Master: Lecciones Aprendidas y Directrices de Ejecución
**Proyecto:** Jellyfish OS  
**Fecha de Análisis:** 28 de Mayo de 2026  
**Autor:** Scrum Master Agent

---

## 1. Análisis del Sprint y Anomalías Detectadas

A primera vista, la bitácora `DAILY.md` muestra un progreso lineal y exitoso. Sin embargo, un análisis profundo de los tiempos de ejecución, la secuencia de tareas y la asignación de roles revela fallos metodológicos y riesgos técnicos latentes que deben corregirse de inmediato.

### 🔍 Hallazgos y Puntos de Falla:

1. **La Tarea Fantasma (T-011 Desaparecida):**
   * **Evidencia:** Se observa un salto directo de la tarea `T-010` (15:39) a la `T-012` (15:44). 
   * **Fallo:** La tarea `T-011` falló silenciosamente, fue descartada sin dejar registro, o se eliminó de la bitácora de manera manual. Esto rompe la trazabilidad del sprint y oculta errores de integración.

2. **Compromisos en "Ráfaga" (Ultra-Fast Commits):**
   * **Evidencia:** Entre las 15:35 y las 15:39 se completaron 7 tareas complejas (Room cifrado, motor de renderizado dinámico, algoritmo de scoring, fragmentos de UI, endpoints de API).
   * **Fallo:** Es físicamente imposible codificar, compilar, probar y asegurar la calidad de estos componentes en intervalos de 1 minuto. Los agentes están asumiendo que el código funciona solo por haber generado el archivo, omitiendo la fase de compilación y pruebas unitarias locales.

3. **Invasión de Roles y Riesgo de Compilación:**
   * **Evidencia:** El `@copywriter` modificó directamente `strings.xml` y el `@data_scientist` escribió directamente código Kotlin en `ScoringEngine.kt`.
   * **Fallo:** Permitir que roles no técnicos o de especialidades distintas escriban directamente en el código base sin un paso intermedio de validación sintáctica/compilación incrementa exponencialmente el riesgo de romper el build (ej. un XML mal formateado o un error de tipos en Kotlin).

4. **Ausencia Total de Pruebas (QA):**
   * **Evidencia:** Ningún agente de QA participó en el sprint. Se pasó directamente del desarrollo a la auditoría de seguridad (`CRYPT_AUDIT.md`) sin pruebas unitarias ni de integración registradas.

---

## 2. Reglas Recomendadas y Negative Prompts

Para evitar que los agentes cometan estos mismos errores en los próximos sprints, se establecen las siguientes directrices operativas estrictas.

### 🚫 Negative Prompts (Lo que los agentes NO deben hacer)

```markdown
- DO NOT skip task numbers in the sequence. If a task fails or is discarded, it must be logged as [FAILED] or [DEPRECATED] with an explanation. Never delete a task from the log.
- DO NOT mark a task as "Completado con éxito" immediately after generating the file. You must run a local compilation/validation check first.
- DO NOT allow non-developer roles (e.g., copywriters, designers, data scientists) to commit directly to production code branches without an explicit peer review or automated syntax validation.
- DO NOT proceed to security audits or deployment phases without at least one documented testing/QA task.
```

### 🛠️ Mejores Directrices (Mejores Prácticas para Agentes)

1. **Validación de Compilación Obligatoria:**
   * Antes de registrar una tarea de desarrollo como completada, el agente debe ejecutar el comando de compilación correspondiente (ej. `./gradlew assembleDebug` para Android o `npm run build` para el servidor) y adjuntar el resultado exitoso de manera interna.

2. **Flujo de Trabajo para Roles No-Dev:**
   * Los cambios de texto (`strings.xml`) o algoritmos matemáticos (`ScoringEngine.kt`) propuestos por Copywriters o Data Scientists deben pasar por un proceso de *Pull Request* donde un `@frontend_dev` o `@backend_dev` valide la integración antes de fusionar a la rama principal.

3. **Trazabilidad Absoluta:**
   * Cada tarea del backlog debe tener un estado claro. Si la tarea `T-011` falló debido a dependencias de SQLCipher o problemas de Keystore, debe registrarse como tal:
     > `[2026-05-27 15:41] @frontend_dev — T-011 [FALLIDO] — Error de enlace con SQLCipher. Reintentando en T-012.`

4. **Inclusión de Criterios de Aceptación (DoD - Definition of Done):**
   * Ninguna tarea de UI o lógica de negocio se considerará terminada sin su respectiva prueba unitaria o de renderizado.

---

## Retrospectiva 2026-05-27 16:28

# 🕵️‍♂️ Reporte del Scrum Master: Análisis de Retrospectiva y Lecciones Aprendidas (Jellyfish OS)

Como Scrum Master de Jellyfish OS, he analizado la bitácora de ejecución del sprint (`DAILY.md`). A pesar de que todas las tareas se marcaron finalmente como "Completado con éxito", un análisis detallado de los tiempos de ejecución, la secuencia de las tareas y la asignación de recursos revela cuellos de botella críticos y fallas de proceso que deben corregirse de inmediato para futuros sprints.

---

## 1. Análisis de Incidentes y Cuellos de Botella

### 🚨 El Cuello de Botella de WorkManager (T-011)
* **Síntoma:** Mientras que las tareas T-001 a T-010 se completaron en intervalos de 1 a 2 minutos, la tarea **T-011 (SyncWorker con WorkManager)** tomó **41 minutos** (de 15:39 a 16:20).
* **Causa raíz:** Implementar sincronización en segundo plano con `WorkManager` sobre una base de datos Room cifrada con `SQLCipher` suele generar conflictos severos de dependencias, bloqueos de hilos (thread locking) y problemas al recuperar la clave de cifrado desde el `Android Keystore` desde un contexto de background worker. El agente se enfrentó a un escenario complejo de debugging/auto-healing no documentado explícitamente.

### ⚠️ Desfase Cronológico en la Auditoría de Seguridad (T-012 vs T-011)
* **Síntoma:** La auditoría de seguridad de cifrado (T-012) se completó a las **15:44**, pero el servicio de sincronización en segundo plano (T-011), que transmite esos mismos datos cifrados, se terminó a las **16:20**.
* **Causa raíz:** Falla de proceso. Se auditó la seguridad del almacenamiento local *antes* de que el mecanismo de transmisión y sincronización de datos (el componente con mayor superficie de ataque) estuviera siquiera construido. Esto invalida parcialmente la auditoría.

### 👤 Sobrecarga del Frontend Developer (`@frontend_dev`)
* **Síntoma:** El agente `@frontend_dev` asumió secuencialmente las tareas T-006 (DB), T-007 (Form Engine), T-009 (Dossier UI) y T-011 (Sync Worker).
* **Causa raíz:** Mala distribución de la carga de trabajo. Mientras otros agentes terminaron a las 15:39, el desarrollador frontend quedó como único cuello de botella del equipo durante más de 40 minutos.

---

## 2. Reglas de Acción y Negative Prompts para Futuros Agentes

Para evitar que estos errores de integración, seguridad y estimación se repitan, se establecen las siguientes directrices estrictas para los agentes de Jellyfish OS:

### 🛠️ Reglas Técnicas (Android, Room, SQLCipher y WorkManager)

```markdown
[NEGATIVE PROMPT]
DO NOT implement Android WorkManager tasks that access Room + SQLCipher without:
1. Verifying that the SQLCipher passphrase is safely retrieved from Android Keystore using a non-blocking, thread-safe provider.
2. Explicitly declaring the dependency versions of 'androidx.work:work-runtime-ktx' and 'sqlite-ktx' to avoid classpath collisions.
3. Ensuring the database instance is a Singleton and is not re-initialized inside the Worker's 'doWork()' thread, which causes "Database locked" exceptions.
```

* **Mejor Práctica:** Antes de codificar un `Worker`, el agente debe validar la compatibilidad de las firmas de inicialización de la base de datos cifrada en hilos secundarios.

### 🔒 Reglas de Proceso y Seguridad (Auditorías)

```markdown
[NEGATIVE PROMPT]
NEVER complete or sign off on a Security Audit (e.g., CRYPT_AUDIT) if there are pending tasks related to data transit, background sync, or API communication. 
The security audit MUST be the absolute last step of the feature lifecycle, executed only when all code touching sensitive data is merged.
```

* **Mejor Práctica:** El rol de `@security_auditor` no debe iniciar su análisis final hasta que el estado de las tareas de sincronización y red asociadas sea `Completado`.

### 📋 Reglas de Planificación y Asignación (Scrum)

```markdown
[NEGATIVE PROMPT]
DO NOT assign database setup, UI rendering, and background synchronization to a single developer in the same sprint without establishing intermediate integration checkpoints.
If a developer is assigned more than 3 critical path tasks, the Scrum Master agent must trigger a redistribution alert.
```

* **Mejor Práctica:** Dividir las tareas de infraestructura (Room/SQLCipher) y las de integración (WorkManager) entre diferentes agentes, o asegurar que el `@backend_dev` o `@arquitecto_software` apoyen en la lógica de sincronización para balancear la carga.

---

## Retrospectiva 2026-05-27 16:49

# 🕵️‍♂️ Reporte del Scrum Master: Lecciones Aprendidas y Reglas de Acción (Sprint 1)

**De:** Scrum Master de Jellyfish OS  
**Para:** Agentes de Desarrollo y Automatización  
**Asunto:** Retrospectiva del Sprint - Análisis de Tiempos, Cuellos de Botella y Directrices de Mitigación

---

## 1. Análisis del Sprint (Retrospectiva)

Aunque el log `DAILY.md` reporta un estado final de **"Completado con éxito"** para todas las tareas, un análisis detallado de la línea de tiempo revela asimetrías críticas en los tiempos de ejecución que denotan fricción técnica, bloqueos de dependencias y posibles re-trabajos (auto-healing silencioso):

*   **Fase de Inicialización y Diseño (15:34 - 15:35):** Flujo ultra-rápido. El diseño de arquitectura, UI, strings y Docker se generó en paralelo sin fricción.
*   **Fase de Desarrollo Core (15:36 - 15:39):** Implementación masiva de Room, SQLCipher, el motor de renderizado y el Scoring Engine en solo 3 minutos. Esto sugiere generación de código sin pruebas unitarias previas.
*   **Primer Cuello de Botella - Auditoría de Seguridad (15:39 - 15:44):** Un desfase de 5 minutos para la auditoría de seguridad (`CRYPT_AUDIT.md`). Esto indica que la auditoría se realizó *después* de escribir el código de cifrado, lo que usualmente fuerza refactorizaciones reactivas en el Keystore.
*   **Segundo Cuello de Botella - Sincronización en Segundo Plano (15:44 - 16:20 | 36 minutos):** La implementación de `SyncWorker.kt` con `WorkManager` tomó la mayor parte del tiempo del sprint. Esto se debe a la complejidad de inyectar dependencias cifradas (SQLCipher) en hilos de fondo y gestionar el ciclo de vida de Android.
*   **Tercer Cuello de Botella - Pruebas de Integración (16:20 - 16:49 | 29 minutos):** La creación de `SyncIntegrationTest.kt` experimentó retrasos significativos. Configurar pruebas instrumentadas que involucren bases de datos cifradas, trabajadores en segundo plano y llamadas de red simuladas suele fallar por falta de sincronización (idling resources).

---

## 2. Qué falló / Qué causó fricción (Análisis Técnico)

1.  **Seguridad como "Afterthought" (Pensamiento Tardío):** Se implementó `AppDatabase.kt` con SQLCipher antes de definir formalmente la auditoría de seguridad. Esto genera vulnerabilidades en la gestión de la clave de cifrado en el Android Keystore.
2.  **Complejidad de Hilos en WorkManager:** `SyncWorker` requiere acceder a la base de datos cifrada. Si la clave del Keystore no está disponible en segundo plano o el hilo principal bloquea la base de datos, el Worker falla silenciosamente.
3.  **Pruebas Instrumentadas Inestables (Flaky Tests):** Intentar probar la sincronización offline/online sin un servidor de pruebas mockeado (`MockWebServer`) o sin detener el `WorkManager` real genera falsos negativos en el pipeline de CI/CD.

---

## 3. Reglas de Acción para Futuros Agentes (Negative Prompts y Directrices)

Para evitar que los agentes cometan los mismos errores en los siguientes sprints, se establecen las siguientes reglas de diseño y desarrollo:

### 🚫 NEGATIVE PROMPTS (Lo que NO deben hacer los agentes)

*   **PROHIBIDO** implementar bases de datos locales cifradas (SQLCipher/Room) sin inicializar y validar primero el alias del `AndroidKeystore` en una clase de configuración de seguridad aislada.
*   **PROHIBIDO** hardcodear strings, URLs de API o esquemas de bases de datos dentro de los componentes de UI (`DossierFragment`, `DynamicFormEngine`). Todo debe consumirse desde recursos (`strings.xml`) o inyectarse mediante arquitectura limpia.
*   **PROHIBIDO** escribir Workers de `WorkManager` que realicen consultas directas a la base de datos sin manejar excepciones de base de datos bloqueada (`SQLiteDatabaseLockedException`) o base de datos cerrada.
*   **PROHIBIDO** crear pruebas de integración (`androidTest`) que dependan de la conectividad de red real o de un servidor externo activo.

### 🎯 MEJORES DIRECTRICES (Lo que SÍ deben hacer los agentes)

#### Para el Arquitecto y Desarrollador Frontend:
1.  **Seguridad Primero:** Diseñe el flujo de descifrado de la base de datos de manera que la clave nunca se guarde en texto plano en memoria RAM. Use `char[]` en lugar de `String` para manejar contraseñas/claves.
2.  **Robustez en Formularios Dinámicos:** El `DynamicFormEngine` debe validar el JSON Schema localmente antes de intentar renderizar la vista. Si el JSON está corrupto, debe mostrar un estado de error amigable en lugar de lanzar un `NullPointerException`.

#### Para el Ingeniero de QA y DevOps:
3.  **Aislamiento de Pruebas:** Al probar `SyncWorker`, utilice `WorkManagerTestInitHelper` para controlar manualmente el estado de ejecución del Worker y simular la pérdida de conexión de red de forma controlada.
4.  **Mocking Obligatorio:** Utilice `MockWebServer` para interceptar las peticiones de sincronización salientes del dispositivo durante las pruebas de integración.

---

## Retrospectiva 2026-05-27 19:12

# 🕵️‍♂️ Reporte del Scrum Master: Lecciones Aprendidas & Reglas de Acción
**Proyecto:** Jellyfish OS  
**Sprint:** Sprint 1 (Inicialización y Core Offline-First)

---

## 1. Análisis del Sprint (Retrospectiva de Tiempos)

Aunque todas las tareas se registraron como **"Completado con éxito"**, el análisis de las marcas de tiempo (*timestamps*) revela cuellos de botella y fricciones críticas en el flujo de desarrollo de los agentes:

*   **Desarrollo Fluido (15:34 - 15:39):** El diseño de arquitectura, UI, base de datos local (Room + SQLCipher) y el motor de renderizado dinámico se generaron en cascada casi inmediata.
*   **Primer Cuello de Botella - Sincronización en Segundo Plano (T-011 | 15:39 a 16:20 - 41 minutos):** Implementar `SyncWorker` con `WorkManager` tomó un tiempo desproporcionado. Esto suele deberse a conflictos de hilos al acceder a bases de datos cifradas (SQLCipher) desde hilos de fondo de WorkManager y problemas de inyección de dependencias.
*   **Segundo Cuello de Botella - Pruebas de Integración (T-013 | 16:20 a 16:49 - 29 minutos):** Las pruebas automatizadas de flujos offline/online requirieron múltiples iteraciones. Probar `WorkManager` y Room cifrado de forma instrumental suele fallar por falta de inicialización del contexto de pruebas.
*   **Anomalía de Secuencia (T-012):** La auditoría de seguridad se completó a las **15:44**, *antes* de que se terminara de implementar el servicio de sincronización en segundo plano (`SyncWorker` a las **16:20**). Esto dejó una ventana de riesgo sin auditar en el flujo de transmisión de datos.

---

## 2. Puntos de Fricción Detectados

1.  **Acceso Concurrente a SQLCipher:** Bloqueos de base de datos al intentar escribir desde el hilo principal (UI) y leer/sincronizar desde el hilo de `WorkManager`.
2.  **Serialización en WorkManager:** Intentos de pasar objetos complejos o entidades de Room directamente a través de los parámetros de entrada (`Data`) de `WorkManager`, lo cual viola las limitaciones de tamaño (10KB) de la API.
3.  **Desfase de Auditoría:** Validar la seguridad del almacenamiento local sin haber implementado el transporte/sincronización de esos mismos datos.

---

## 3. Reglas de Acción para Futuros Agentes (Negative Prompts & Directrices)

Para evitar que los agentes cometan estos errores en los siguientes sprints, se establecen las siguientes directrices estrictas:

### 🚫 NEGATIVE PROMPTS (Lo que NO deben hacer los agentes)

*   **[DATABASE/SECURITY]** `DO NOT` inicializar la base de datos Room con SQLCipher utilizando contraseñas en texto plano en el código. `DO NOT` permitir que el hilo principal (UI Thread) realice operaciones de escritura en la base de datos cifrada; usa siempre corrutinas (`withContext(Dispatchers.IO)`).
*   **[WORKMANAGER]** `DO NOT` pasar objetos serializados, JSONs grandes o entidades completas dentro del `Data` de entrada de un `Worker`. `DO NOT` instanciar manualmente el `SyncWorker` sin usar el `WorkManagerTestInitHelper` en el entorno de pruebas.
*   **[JSON SCHEMA]** `DO NOT` generar esquemas de cuestionarios dinámicos sin definir un campo de versión (`schema_version`) y un mecanismo de fallback para campos desconocidos en el parser móvil.
*   **[WORKFLOW]** `DO NOT` dar por finalizada una auditoría de seguridad (`security_auditor`) si existen tareas de transmisión de datos (sincronización, APIs, workers) pendientes de implementar en el mismo sprint.

### 🎯 MEJORES PRÁCTICAS (Lo que SÍ deben hacer los agentes)

*   **Patrón de Identificadores en Workers:** Pasa únicamente IDs únicos (UUIDs/Primary Keys) en el `Data` de `WorkManager`. El `Worker` debe encargarse de consultar la base de datos local cifrada utilizando ese ID dentro de su propio hilo de ejecución.
*   **Secuenciación de Auditoría:** El rol de `security_auditor` debe ser el último en firmar el sprint. Su tarea debe ejecutarse únicamente cuando el código de persistencia (Room) y el de transporte (WorkManager/Retrofit) estén en estado *Pull Request* o *Merge Ready*.
*   **Aislamiento de Pruebas de Sincronización:** Para pruebas de integración offline-online, utiliza siempre `MockWebServer` para simular fallos de red (latencia, error 500, timeout) y asegurar que el mecanismo de reintento exponencial de `WorkManager` funcione sin realizar peticiones reales.

---

## Retrospectiva 2026-05-27 19:20

# 🕵️‍♂️ Reporte del Scrum Master: Lecciones Aprendidas y Reglas de Acción
**Proyecto:** Jellyfish OS  
**Fecha de Análisis:** 27 de Mayo de 2026  

---

## 1. Análisis de Fricciones y Puntos de Dolor (¿Qué falló?)

Al analizar la secuencia temporal y la naturaleza de las tareas en el `DAILY.md`, se identificó un patrón de **"desarrollo acelerado seguido de un cuello de botella de estabilización"**. 

A pesar de que todas las tareas se marcaron como "Completado con éxito", el flujo revela las siguientes anomalías operativas:

*   **Bloqueo por Desalineación de Dependencias y Tipado (Brecha de 2.5 horas):**  
    Entre las 16:49 (fin de las pruebas de integración de QA) y las 19:14, el desarrollo se detuvo por completo. Esto se debió a que el código de Android (Room, SQLCipher, WorkManager) y del Servidor (Node.js/TypeScript) se escribió sin un marco de compilación estricto ni dependencias unificadas. El equipo tuvo que pausar para resolver errores de tipado, sintaxis y conflictos de versiones de último minuto.
*   **Configuración Tardía del Pipeline de CI/CD y Calidad:**  
    El pipeline de CI (`ci.yml`), el linter (`.eslintrc.json`) y el escáner de seguridad (SAST) se implementaron al final del día (19:18 - 19:20), *después* de haber escrito y "completado" todo el código core. Esto significa que el código inicial se desarrolló "a ciegas", sin validación automatizada de calidad ni de seguridad en tiempo real.
*   **Auditoría de Seguridad Reactiva:**  
    La auditoría de seguridad sobre el cifrado local (T-012) se realizó a las 15:44, *después* de que el desarrollador frontend ya había implementado la base de datos Room cifrada a las 15:36 (T-006). Esto pudo haber generado refactorizaciones masivas si se hubieran encontrado fallos de diseño en el uso de SQLCipher.

---

## 2. Reglas de Acción para Futuros Sprints (Directrices y Negative Prompts)

Para evitar que los agentes repitan estos errores de secuenciación y configuración en los próximos sprints, se establecen las siguientes reglas de diseño y desarrollo:

### 🚫 Negative Prompts (Lo que los agentes NO deben hacer)

```markdown
# [NEGATIVE PROMPT: ORDEN DE CONFIGURACIÓN]
NO inicies el desarrollo de lógica de negocio o interfaces de usuario (código funcional) si no se han definido y unificado previamente las dependencias base (package.json, build.gradle) y las reglas del compilador (tsconfig.json, reglas de Kotlin).

# [NEGATIVE PROMPT: CI/CD Y LINTING POST-MORTEM]
NO postergues la creación del pipeline de Integración Continua (CI), linter o herramientas de análisis estático (SAST) para el final del sprint. Estas herramientas deben estar operativas antes de fusionar el primer Pull Request de código funcional.

# [NEGATIVE PROMPT: SEGURIDAD REACTIVA]
NO implementes mecanismos de persistencia sensible, criptografía o manejo de credenciales (ej. SQLCipher, Keystore, JWT) sin que el rol de Arquitectura o Seguridad haya aprobado formalmente el diseño técnico y el esquema de datos.
```

### 🎯 Mejores Directrices (Lo que los agentes SÍ deben hacer)

1.  **Estrategia "Shift-Left" en Configuración:**  
    La primera tarea de cualquier sprint de desarrollo de software debe ser la creación del entorno de compilación estricto (`tsconfig.json` con `strict: true`, linters configurados para fallar en advertencias y matriz de dependencias fijadas con versiones exactas).
2.  **Definición de Esquemas Antes de la Implementación:**  
    El JSON Schema (T-005) y el diseño de arquitectura (T-001) deben estar completamente cerrados y validados por el Arquitecto antes de que el Frontend o el Backend escriban una sola línea de código que consuma dichos datos.
3.  **Automatización del Feedback Loop:**  
    Cualquier prueba de humo (`smoke.test.js`) o prueba de integración (`SyncIntegrationTest.kt`) debe ejecutarse de manera obligatoria en el pipeline de CI ante cada commit, impidiendo la mezcla de código que rompa la compilación o el tipado.

---

## Retrospectiva 2026-07-15 16:34

## 📋 BACKLOG RECOVERY


### US-001: Arquitectura y Capas Base de la Aplicación
- **Como** Desarrollador del sistema, **quiero** andamiar la idea inicial: 'DAILY.md:
# 📝 Daily Standup Log

> Registro de com...', **para** garantizar la continuidad del flujo de desarrollo.
#### Criterios de Aceptación:
  - Dado que la entrada fue procesada con fallas de respuesta por el LLM, cuando el Task Runner la reciba, entonces creará las configuraciones base requeridas.
  - Prioridad: Must-have | Estimación: 5pts


---

## Retrospectiva 2026-07-15 17:08

## 📋 BACKLOG RECOVERY


### US-001: Arquitectura y Capas Base de la Aplicación
- **Como** Desarrollador del sistema, **quiero** andamiar la idea inicial: 'DAILY.md:
# 📝 Daily Standup Log

> Registro de com...', **para** garantizar la continuidad del flujo de desarrollo.
#### Criterios de Aceptación:
  - Dado que la entrada fue procesada con fallas de respuesta por el LLM, cuando el Task Runner la reciba, entonces creará las configuraciones base requeridas.
  - Prioridad: Must-have | Estimación: 5pts


---

## Retrospectiva 2026-07-15 18:28

# Lecciones Aprendidas y Reglas de Acción

## 1. Fallas Durante el Sprint

### Errores de Compilación
- **Problema:** El archivo de documentación estaba truncado, lo que indicaba que el proceso de configuración no había sido documentado en su totalidad.
- **Solución:** Asegúrate de revisar y completar todos los pasos del proceso de configuración antes de la compilación.

### Falta de Documentación
- **Problema:** No se especificó el punto de entrada principal de la aplicación y el comando de ejecución local.
- **Solución:** Documenta claramente el punto de entrada principal y el comando de ejecución local en los archivos README y setup.

## 2. Reglas Recomendadas (Negative Prompts o Mejores Directrices)

### Negativa Prompts
1. **No olvides documentar todos los pasos del proceso de configuración antes de la compilación.**
   - **Razón:** Una documentación completa facilita el entendimiento y la replicabilidad del proceso.
   
2. **Asegúrate de revisar y completar todos los pasos del proceso de configuración antes de la compilación.**
   - **Razón:** Una documentación completa facilita el entendimiento y la replicabilidad del proceso.

3. **No olvides especificar el punto de entrada principal y el comando de ejecución local en los archivos README y setup.**
   - **Razón:** La claridad en estos aspectos es crucial para la correcta instalación y ejecución del proyecto.

4. **Verifica que todos los componentes y servicios estén correctamente documentados.**
   - **Razón:** Una buena documentación mejora la comprensión y facilita el mantenimiento del proyecto.

### Mejores Directrices
1. **Documenta todos los pasos del proceso de configuración antes de la compilación.**
   - **Razón:** Una documentación completa facilita el entendimiento y la replicabilidad del proceso.

2. **Especifica el punto de entrada principal y el comando de ejecución local en los archivos README y setup.**
   - **Razón:** La claridad en estos aspectos es crucial para la correcta instalación y ejecución del proyecto.

3. **Verifica que todos los componentes y servicios estén correctamente documentados.**
   - **Razón:** Una buena documentación mejora la comprensión y facilita el mantenimiento del proyecto.

4. **Realiza pruebas de compilación y verificación periódicas para asegurar que todo funciona como se espera.**
   - **Razón:** Las pruebas regulares ayudan a identificar problemas temprano y mejorar la calidad del producto final.

5. **Revisa y actualiza regularmente los archivos README y setup para reflejar cualquier cambio en el proyecto.**
   - **Razón:** Una documentación actualizada asegura que todos los miembros del equipo tienen la información más reciente sobre cómo configurar y ejecutar el proyecto.

---

Estas lecciones aprendidas y recomendaciones deberán ser incorporadas en futuros sprints para mejorar la eficiencia y calidad de los proyectos.

---

## Retrospectiva 2026-07-15 19:44

# Lecciones Aprendidas y Reglas de Acción

## 1. Qué Falló Durante el Sprint

- **Error en la documentación:** El archivo de documentación estaba truncado, lo que indicaba que el proceso de configuración no había sido documentado completamente.
- **Punto de entrada principal:** No se identificó el punto de entrada principal de la aplicación y no se definió el comando de ejecución local.

## 2. Reglas Recomendadas (Negative Prompts o Mejores Directrices)

1. **Documentación Completa:**
   - **Regla:** Asegúrate de que todos los procesos de configuración, instalación y compilación estén completamente documentados en el archivo `README.md` y cualquier otro documento relevante.
   - **Negative Prompt:** No permitir que la documentación sea incompleta o truncada.

2. **Identificación del Punto de Entrada Principal:**
   - **Regla:** Identifica claramente el punto de entrada principal de la aplicación y define el comando de ejecución local en los archivos de configuración.
   - **Negative Prompt:** No permitir que el punto de entrada principal sea desconocido o que no se defina el comando de ejecución local.

3. **Revisión y Aprobación:**
   - **Regla:** Realiza una revisión exhaustiva de la documentación y los archivos de configuración antes de marcarlas como completadas.
   - **Negative Prompt:** No marcar tareas como completas sin una revisión previa.

4. **Comunicación Clara:**
   - **Regla:** Comunica claramente cualquier impedimento o problema encontrado durante el sprint para que pueda ser abordado inmediatamente.
   - **Negative Prompt:** Ignorar los problemas y seguir adelante sin resolverlos.

5. **Seguimiento de Tareas:**
   - **Regla:** Mantén un seguimiento constante de las tareas asignadas y asegúrate de que se completan todas las tareas programadas.
   - **Negative Prompt:** Dejar tareas incompletas o pendientes sin resolver.

6. **Pruebas Iniciales:**
   - **Regla:** Realiza pruebas iniciales para verificar que la instalación y compilación sean exitosas antes de avanzar a las siguientes etapas.
   - **Negative Prompt:** Ignorar las pruebas iniciales y pasar directamente a los pasos posteriores.

7. **Revisión de Código:**
   - **Regla:** Realiza una revisión de código exhaustiva para asegurarte de que no haya errores o problemas de compilación.
   - **Negative Prompt:** Ignorar los errores de compilación y seguir adelante con la tarea.

8. **Documentación de Requisitos:**
   - **Regla:** Documenta claramente todos los requisitos del sistema en el archivo `ARCHITECTURE.md` para evitar confusiones posteriores.
   - **Negative Prompt:** No documentar los requisitos del sistema o documentarlos incompletamente.

9. **Pruebas de Integración:**
   - **Regla:** Realiza pruebas de integración para asegurarte de que todos los componentes funcionen correctamente juntos.
   - **Negative Prompt:** Ignorar las pruebas de integración y seguir adelante con la tarea.

10. **Revisión Final:**
    - **Regla:** Realiza una revisión final del proyecto antes de marcar el sprint como completo para asegurarte de que no haya errores o problemas.
    - **Negative Prompt:** Ignorar la revisión final y marcar el sprint como completo sin verificar los resultados.

---

## Retrospectiva 2026-07-23 10:05

## Análisis de Bitácora DAILY.md - Lecciones Aprendidas (Sprint 1)

### 1. Qué falló durante el sprint (o en la preparación)

El sprint aún no ha comenzado su ejecución, por lo que no se han identificado fallos técnicos (errores de compilación, auto-healing, dependencias) en esta etapa.

El principal fallo identificado es de **proceso y comunicación**:

*   **Fallo en la adherencia al proceso de comunicación:** La bitácora `DAILY.md` solo contiene una entrada del Scrum Master. No hay registros de otros agentes, lo que impide la visibilidad del progreso, la coordinación entre equipos y la identificación temprana de impedimentos por parte de los desarrolladores.
*   **Falta de datos para el análisis:** La ausencia de entradas de otros agentes impide realizar un análisis significativo sobre el rendimiento del sprint o problemas técnicos, ya que no hay información sobre las actividades o bloqueos de los miembros del equipo.

### 2. Reglas recomendadas para futuros agentes

Para asegurar una comunicación efectiva y una ejecución fluida del sprint, se establecen las siguientes reglas:

1.  **[Regla 1] Actualización Diaria Obligatoria:** Cada agente *debe* registrar su progreso y cualquier impedimento en `DAILY.md` al inicio de cada jornada laboral. Esto incluye incluso si el progreso es mínimo o no hay impedimentos (en cuyo caso se indicará "Ninguno").
2.  **[Regla 2] Formato Estricto:** Los agentes *deben* seguir el formato `[FECHA] [@AGENTE] — Mensaje` para asegurar la consistencia y facilitar el parseo automático y la lectura rápida.
3.  **[Regla 3] Contenido Esencial:** Las entradas *deben* incluir claramente:
    *   **Ayer:** Qué tareas se completaron o en qué se trabajó.
    *   **Hoy:** Qué tareas se planea abordar.
    *   **Impedimentos:** Cualquier bloqueo, dificultad o dependencia que impida el progreso.
4.  **[Regla 4] Transparencia de Impedimentos:** Los agentes *no deben* ocultar impedimentos, por pequeños que parezcan. Su registro es crucial para que el Scrum Master pueda actuar y el equipo pueda colaborar en su resolución.
5.  **[Regla 5] Responsabilidad Colectiva:** La `DAILY.md` es una herramienta de equipo. Todos los agentes son responsables de mantenerla actualizada para el beneficio de la transparencia y la eficiencia del sprint.

---

## Retrospectiva 2026-07-23 15:29

## 📋 BACKLOG RECOVERY


### US-001: Arquitectura y Capas Base de la Aplicación
- **Como** Desarrollador del sistema, **quiero** andamiar la idea inicial: 'DAILY.md:
# 📝 Daily Standup Log

> Registro de com...', **para** garantizar la continuidad del flujo de desarrollo.
#### Criterios de Aceptación:
  - Dado que la entrada fue procesada con fallas de respuesta por el LLM, cuando el Task Runner la reciba, entonces creará las configuraciones base requeridas.
  - Prioridad: Must-have | Estimación: 5pts
