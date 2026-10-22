# Registro de lo construido, decisiones, pendientes y plan de pruebas

Este documento es el **registro del proyecto**: qué se hizo, por qué, qué falta y cómo validarlo con el equipo.

**Documentos usados como fuente:** *GymTrack_Especificacion_Tecnica_Modulos* (vigente), *GymTrack_Mockups_v4* (pantallas de referencia) y, al inicio, *GymTrack_SRS_V1* (reemplazado por la especificación técnica; no se implementó nada de él que la contradiga).

---

## 1. Qué se construyó

| Área | Detalle |
|------|---------|
| Backend (este repo) | FastAPI + SQLAlchemy; 13 tablas; 32 rutas; datos iniciales: 30 ejercicios con ficha técnica y 45 plantillas maestras |
| Frontend | Repositorio [GymTrack_Frontend](https://github.com/Hacapoxd/GymTrack_Frontend): JavaScript puro, sin compilación; acceso, onboarding, plan editable, panel de IA y perfil |
| Base de datos | SQLite en local; PostgreSQL en Railway (misma lógica, se cambia con `DATABASE_URL`) |
| IA por token | Cliente para Anthropic y APIs compatibles con OpenAI; propuestas validadas y confirmadas por el usuario; control de tokens |
| Despliegue | `railway.json` en ambos repositorios, `.python-version`, script que genera la URL de la API del frontend |
| Pruebas | 59 automáticas (acceso, perfil, plantillas, edición, IA, adaptadores de proveedor, normalización de URL) |

### Cumplimiento de la especificación

**Módulo 1: Perfil y Evaluación Inicial**

| Requisito | Estado |
|-----------|--------|
| Edad, peso, estatura, sexo biológico, IMC automático | Cumplido (la edad se calcula desde la fecha de nacimiento) |
| Cuestionario PAR-Q obligatorio | **No implementado por decisión de alcance** (ver D1) |
| Días por semana, objetivo, nivel percibido | Cumplido |
| Peso y días actualizables desde el perfil | Cumplido; cada cambio de peso queda en `weight_entries` |
| Historial inmutable de la evaluación médica | No aplica al quitar la evaluación médica (ver D1) |

**Módulo 3: Generación y Estructura del Plan**

| Requisito | Estado |
|-----------|--------|
| Asignación por filtros días + objetivo + nivel desde la BD | Cumplido (`GET /plans/preview`, `POST /plans`) |
| Series, rango de repeticiones, carga inicial, descanso 90–120 s / 60 s | Cumplido (la carga es una estimación, ver D5) |
| Intercambiar ejercicios, agregar/eliminar series, reordenar | Cumplido; además agregar/quitar ejercicios y volver al plan recomendado |
| "Antes o durante la rutina" | Parcial (ver D7) |
| Fichas técnicas: técnica y errores comunes | Cumplido para los 30 ejercicios |
| Fichas técnicas: GIF/video | La plataforma lo soporta (`mediaUrl`, `mediaType`, carga vía administrador), pero **no hay GIF/video cargados**: falta contenido |

---

## 2. Decisiones tomadas

| # | Decisión | Motivo / consecuencia |
|---|----------|----------------------|
| D1 | **Se quitó todo lo de salud:** PAR-Q, consentimiento de datos de salud, restricción de intensidad por PAR-Q, categoría de IMC y registro inmutable de la evaluación | El equipo definió que GymTrack no cubre salud, nutrición ni seguimiento médico. Se reemplazó por un consentimiento explícito en el registro: *"GymTrack no ofrece asesoría médica, nutricional ni seguimiento clínico"*. Ventaja: no se guardan datos sensibles de salud. Riesgo: no hay filtro de aptitud previo; el aviso y el consejo de consultar a un profesional quedan como única barrera. **Si luego se decide volver a incluir el PAR-Q**, hay que tratarlo como dato sensible (consentimiento, acceso restringido, historial inmutable) |
| D2 | El IMC se calcula y se muestra **sin categoría ni interpretación** | La especificación pide el cálculo automático; se evita clasificar al usuario porque sería un juicio de salud. Si prefieren eliminarlo por completo, es un campo calculado en `profile.py` |
| D3 | El nivel es **percibido** (lo elige el usuario) | Así lo define la especificación. Los mockups v4 mostraban un nivel calculado por puntaje (0–8): no se implementó |
| D4 | El plan guarda **cuántos** días entrena, no **cuáles** días de la semana | La especificación habla de cantidad. El calendario por día y hora corresponde al Dashboard (Módulo 2) |
| D5 | La carga inicial es una **fórmula** (peso corporal × ratio × nivel × objetivo × sexo) | La especificación pide "carga sugerida inicial" pero no da fórmula. Los ratios son estimaciones: deben calibrarse con el plan de pruebas |
| D6 | La IA **propone, el backend valida y el usuario confirma** | Evita que un modelo (que puede equivocarse) modifique el plan directamente |
| D7 | La edición está disponible en cualquier momento, pero afecta **al plan**, no a una sesión puntual | Todavía no existe el Módulo 4 (sesión). Cuando exista, convendrá distinguir "solo hoy" de "para siempre" |
| D8 | El rol administrador solo gestiona el **catálogo** de ejercicios | Es lo necesario para cargar GIF/video; el resto del Módulo 10 queda pendiente |
| D9 | **Sin chat** de IA | La IA por token se usa para asignar/ajustar rutinas, no para conversar (el chat es el Módulo 9) |
| D10 | Tablas creadas con `create_all`, **sin migraciones** | Suficiente mientras no haya usuarios reales; ver pendientes |
| D11 | El límite de solicitudes por minuto vive en memoria | Suficiente con una instancia; con varias haría falta Redis |
| D12 | El frontend guarda los tokens en `localStorage` | Simple para esta etapa; cookies `HttpOnly` serían más seguras (ver pendientes) |

### Diferencias entre mockups v4 y lo implementado

Los mockups incluyen pantallas de **molestias por articulación, horas de sueño, equipo disponible, recomendaciones de descanso, semáforo, mapa muscular, sesión con registro de series y RIR, asistente de chat, progreso y rachas**. No están en esta entrega: unas son de salud (fuera de alcance) y otras pertenecen a los módulos pendientes. El mockup de acceso incluye "¿Olvidaste tu contraseña?", tampoco implementado.

---

## 3. Pendientes

**Funcionales:** Módulos 2, 4, 5, 7, 8 y el resto del 10 (cuenta, unidades kg/lb, modo claro/oscuro manual, exportar/eliminar datos) · chat del Módulo 9 · cargar GIF/video de los ejercicios · recuperación de contraseña y verificación de correo (requieren servicio de correo).

**Técnicos:** migraciones con Alembic **antes de tener usuarios reales** · limpieza periódica de tokens vencidos · límite de solicitudes con Redis si hay varias instancias · tokens en cookies `HttpOnly` · integración continua (ejecutar `pytest` en cada push) · probar con un navegador real y con un proveedor de IA real.

**Calibración:** ajustar los ratios de carga (`app/services/catalog_data.py`) y los factores de nivel (`app/services/planner.py`) con los datos del plan de pruebas.

---

## 4. Qué se verificó y qué no

| Verificación | Resultado |
|--------------|-----------|
| 59 pruebas automáticas en SQLite | Pasan |
| Las mismas 59 pruebas en **PostgreSQL 16** | Pasan |
| Reinicio del servidor con archivo de BD: datos y semillas intactos, sin duplicados | Correcto |
| CORS: origen permitido responde, origen no permitido se rechaza | Correcto |
| Recorrido completo de la interfaz (21 pasos) en un navegador **simulado** (jsdom) contra el backend real y un servidor de IA **simulado** | Correcto, sin errores de JavaScript |
| Adaptadores de IA (forma de peticiones, lectura de tokens, errores sin filtrar la clave) con servidor simulado | Correcto |
| Configuración de Railway contrastada con su documentación (`railway.json`, `startCommand`, `healthcheckPath`, variable `${{Postgres.DATABASE_URL}}`) | Correcta según la documentación consultada |
| **Llamada real a un proveedor de IA** | **No realizada** (requiere clave) |
| **Interfaz en un navegador real** (Chrome, Safari, celular) | **No realizada**: probar el diseño responsive y el modo oscuro |
| **Despliegue real en Railway** | **No realizado** (requiere la cuenta del equipo) |

Hallazgos corregidos durante la verificación: un mensaje de error de validación mostraba un nombre de campo técnico; `.env` ahora se lee automáticamente; las pruebas se blindaron para que ninguna clave real active la IA.

---

## 5. Plan de pruebas con el equipo

El equipo tiene 6 personas con experiencias distintas, lo que sirve para validar cosas distintas:

| Persona | Experiencia | Qué valida |
|---------|-------------|-----------|
| A | Va al gimnasio hace ~1 año | Que el plan y las cargas sean razonables para un nivel intermedio-inicial |
| B | Va hace ~2 años | La frontera entre *Intermedio* y *Avanzado* y el realismo de las cargas |
| C | Lleva solo semanas | Que el plan de principiante sea claro y no abrume |
| D, E, F | Solo conocimiento teórico | Que la app se entienda sin saber gimnasio (usabilidad pura) |

Cada prueba debe hacerse con datos reales de cada persona y registrando lo que pasó. **Importante para A, B y C:** la carga sugerida es un punto de partida. No la usen a ciegas: empiecen ligero y ajusten con criterio, como siempre.

### P1. Calibración de cargas (A, B, C)
1. Crear cuenta, perfil real (peso, estatura, sexo) y elegir el nivel que sienta propio.
2. Generar el plan y anotar la carga sugerida de 4 a 5 ejercicios principales.
3. Anotar lo que realmente maneja en una serie de trabajo equivalente y calcular la diferencia.

| Persona | Ejercicio | Sugerida (kg) | Real (kg) | Diferencia % | Comentario |
|---------|-----------|---------------|-----------|--------------|------------|
| | | | | | |

*Criterio propuesto:* diferencias menores a ±20 % son aceptables. Si varias van en la misma dirección, ajustar `load_ratio` o los factores de nivel.

### P2. Coherencia del plan y del nivel (A, B, C)
¿El plan asignado coincide con lo que haría esa persona? Probar también el nivel vecino (A: Principiante e Intermedio; B: Intermedio y Avanzado) y comparar cuál se siente más adecuado. Anotar si las descripciones de nivel de la pantalla ("Menos de 6 meses", "De 6 meses a 2 años", "Más de 2 años") ayudaron a elegir.

### P3. Edición durante una sesión real (A, B, C)
En el gimnasio y desde el celular: intercambiar un ejercicio como si la máquina estuviera ocupada, cambiar series y reordenar. Medir **cuántos toques** y **cuántos segundos** tomó, y anotar fricciones (botones pequeños, texto difícil, conexión lenta).

### P4. Usabilidad sin conocimientos (D, E, F)
Sin ayuda y con un observador que no intervenga: crear cuenta, completar el perfil, generar el plan, abrir la ficha de un ejercicio, intercambiar un ejercicio y bajar la intensidad. El observador anota dónde se traban y cuánto tardan. Después preguntar con sus palabras: ¿qué es una serie?, ¿qué es una repetición?, ¿qué significa el descanso?, ¿qué hace "Volver al plan recomendado"?

### P5. GymTrack contra un chatbot general (todo el equipo, con la IA activada)
Misma tarea en ambos: *"Quiero bajar mi intensidad esta semana"* y *"Solo tengo 40 minutos por sesión"*. Medir pasos, tiempo y si el resultado quedó aplicado al plan sin copiar y pegar. Es la forma honesta de comprobar si el sistema se prefiere o no.

### P6. Alcance y seguridad (cualquiera)
Escribir mensajes sobre dolor, dieta o medicamentos en el campo de la IA y confirmar que se rechazan. Revisar que ninguna pantalla dé consejos médicos ni nutricionales. Intentar entrar a la ruta de otro usuario cambiando un id (debe dar `404`).

### P7. Robustez (quienes programan más)
Contraseña débil, correo repetido, 5 intentos fallidos, sesión vencida, plan con día vacío, modo avión durante una edición, recarga de la página a mitad del onboarding.

### Criterios de éxito (propuestos, el equipo los ajusta)
- D, E y F completan el flujo hasta ver su plan **sin ayuda**.
- El onboarding toma menos de 3 minutos.
- A, B y C califican el plan como "razonable" para su nivel.
- Menos del 20 % de las cargas sugeridas quedan fuera de ±20 % del valor real.
- En P5, GymTrack requiere menos pasos que el chatbot general.

---

## 6. Seguridad del proyecto

- El token personal de GitHub se compartió en un chat para publicar el código. **Revócalo** en GitHub (*Settings → Developer settings → Personal access tokens*) y crea otro si se necesita. Nunca se guardó en el repositorio.
- No subir `.env`, claves de IA ni contraseñas. El `.gitignore` ya excluye `.env` y `*.db`.
- Definir `JWT_SECRET` propio, `CORS_ORIGINS` sin `*` y alerta de gasto en el proveedor de IA antes de publicar.
