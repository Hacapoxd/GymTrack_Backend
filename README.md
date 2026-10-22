# GymTrack · Backend

API de GymTrack: una aplicación para **entrenar en el gimnasio con un plan claro** (qué ejercicios, cuántas series, cuánto descanso y con qué carga empezar), pensada para personas que no quieren improvisar.

> **Alcance importante:** GymTrack **no cubre salud, nutrición ni seguimiento médico**. No diagnostica, no recomienda dietas ni suplementos y no reemplaza a un médico o a un entrenador presencial. Esta decisión está aplicada en el código (ver [Registro de decisiones](docs/REGISTRO_Y_PRUEBAS.md)).

Este repositorio es solo el **backend** (datos, reglas y API). La interfaz está en [GymTrack_Frontend](https://github.com/Hacapoxd/GymTrack_Frontend).

---

## 1. ¿Qué está implementado?

De los 10 módulos de la *Especificación Técnica de Módulos* se implementaron **2 completos y funcionales**, más una capa de IA opcional:

| # | Módulo | Estado |
|---|--------|--------|
| 1 | Perfil y Evaluación Inicial | **Hecho** (sin PAR-Q ni datos de salud, ver decisiones) |
| 2 | Panel Principal (Dashboard) | Pendiente |
| 3 | Generación y Estructura del Plan (Motor de Plantillas) | **Hecho** (incluye edición libre y fichas técnicas) |
| 4 | Registro de la Sesión (One-Tap Logging) | Pendiente |
| 5 | Adaptación Inteligente de Cargas y Tiempo | Pendiente (la IA por token ya cubre ajustes manuales del plan) |
| 6 | Seguridad, Molestias y Semáforo de Recuperación | Fuera de alcance (es salud) |
| 7 | Progreso, Métricas y Notación Rápida | Pendiente |
| 8 | Adherencia y Rachas Flexibles | Pendiente |
| 9 | Asistente Interactivo (chat Trainer IA) | Pendiente (hay IA para asignar y ajustar rutinas, pero no chat) |
| 10 | Configuración y Administración General | Parcial (solo administración del catálogo de ejercicios) |

**Lo que ya puede hacer un usuario:**

1. Crear cuenta e iniciar sesión.
2. Registrar su perfil: fecha de nacimiento, sexo biológico, estatura, peso, días por semana (2 a 6), objetivo (hipertrofia, fuerza, acondicionamiento) y nivel percibido. El sistema calcula edad e IMC.
3. Recibir un **plan de 2 a 6 días** elegido por filtros (días + objetivo + nivel) entre **45 plantillas maestras** guardadas en la base de datos, con series, repeticiones, descanso y carga inicial sugerida.
4. **Editar el plan libremente**: cambiar series, repeticiones, descanso y carga; intercambiar un ejercicio (por ejemplo si la máquina está ocupada); agregar, quitar o reordenar ejercicios; volver al plan recomendado.
5. Ver la **ficha técnica** de cada ejercicio (técnica paso a paso, errores comunes y GIF/video si el administrador cargó uno).
6. **Bajar la intensidad sin IA** con un botón.
7. Con IA activada: pedir que **personalice** el plan, **baje o suba la intensidad** o **acorte la sesión**. La IA solo propone; el usuario decide (ver [IA por token](docs/IA_POR_TOKEN.md)).

---

## 2. Cómo está organizado (MVC explicado simple)

Ya conocen el patrón Modelo–Vista–Controlador. Así se reparte en este proyecto:

| Pieza MVC | Dónde vive | Qué hace |
|-----------|-----------|----------|
| **Modelo** | `app/models.py` y la base de datos | Define las tablas y sus relaciones |
| **Controlador** | `app/routers/*.py` | Recibe la petición, valida quién es el usuario, llama a la lógica y responde |
| **Vista** | Repo `GymTrack_Frontend` | Pantallas que ve el usuario. El backend solo responde JSON |
| *Contrato* | `app/schemas.py` | Define qué JSON se acepta y se devuelve (y rechaza lo inválido) |
| *Lógica de negocio* | `app/services/*.py` | Las reglas: motor de plantillas, cálculo de cargas, validación de la IA |

```
Navegador (Frontend) ──HTTP/JSON──► routers (controlador) ──► services (reglas) ──► models (BD)
                                            │                        │
                                            └── schemas (valida)     └── llm.py ──► proveedor de IA (opcional)
```

Más detalle, diagrama de tablas y glosario en [docs/ARQUITECTURA.md](docs/ARQUITECTURA.md).

```
app/
├── main.py            Arranque, CORS, límite de solicitudes, carga de datos iniciales
├── config.py          Variables de entorno (BD, claves, IA)
├── database.py        Conexión a la base de datos
├── models.py          TABLAS (modelo)
├── schemas.py         Contrato JSON de entrada y salida
├── security.py        Hash de contraseñas y tokens de sesión (JWT)
├── errors.py          Formato único de errores {code, message, details}
├── deps.py            "Quién es el usuario" y "¿es administrador?"
├── seed.py            Carga catálogo, plantillas y administrador la primera vez
├── routers/           CONTROLADORES: auth, athletes, exercises, plans, ai, admin
└── services/
    ├── catalog_data.py   30 ejercicios con ficha técnica
    ├── planner.py        Motor de plantillas, series/reps/descanso y carga sugerida
    ├── ai_assist.py      Prompt, validación estricta y aplicación de lo que propone la IA
    ├── llm.py            Cliente de IA por token (Anthropic u OpenAI-compatible)
    └── profile.py        Edad e IMC
tests/                 59 pruebas automáticas
docs/                  Documentación ampliada
railway.json           Configuración de despliegue en Railway
```

---

## 3. Cómo correrlo en tu computador

Necesitas **Python 3.12** y Git. No necesitas instalar ninguna base de datos: en local usa SQLite (un archivo).

```bash
git clone https://github.com/Hacapoxd/GymTrack_Backend.git
cd GymTrack_Backend

python -m venv .venv
# Windows (PowerShell):  .venv\Scripts\Activate.ps1
# Linux / Mac:           source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env            # en Windows: copy .env.example .env  (los valores por defecto sirven para probar)

uvicorn app.main:app --reload --port 8000
```

- Documentación interactiva de la API (puedes probar cada endpoint): <http://localhost:8000/docs>
- Comprobar que vive: <http://localhost:8000/health> → `{"status":"ok"}`
- La primera vez se crean solas las tablas, los 30 ejercicios y las 45 plantillas.
- Para empezar de cero, borra el archivo `gymtrack.db`.

> `.env.example` es una plantilla y `.env` es tu copia personal: el proyecto la lee solo al iniciar y **nunca se sube a GitHub** (está en `.gitignore`). En Railway no se usa archivo: las variables se cargan en el panel.

**Pruebas automáticas** (recomendado después de cada cambio):

```bash
pytest -q          # deben pasar las 59 pruebas
```

---

## 4. Reglas de negocio implementadas

**Asignación de la plantilla** (Módulo 3): se busca en la tabla `routine_templates` la fila que coincide con *días por semana + objetivo + nivel*. Hay 5 × 3 × 3 = **45 plantillas**.

| Días | Estructura del plan |
|------|---------------------|
| 2 | Cuerpo completo A / B |
| 3 | Empuje / Tirón / Pierna |
| 4 | Torso / Pierna / Torso / Pierna |
| 5 | Empuje / Tirón / Pierna / Torso / Pierna |
| 6 | Empuje / Tirón / Pierna (dos veces) |

**Ejercicios por día según el nivel:** principiante 4 (con variantes más simples, p. ej. sentadilla goblet), intermedio 5, avanzado 6.

**Series, repeticiones y descanso** (descanso: 90 a 120 s en compuestos y 60 s en aislamiento, como indica la especificación):

| Objetivo | Compuestos | Aislamiento | Descanso compuesto |
|----------|-----------|-------------|--------------------|
| Hipertrofia | 8–12 reps | 10–15 reps | 90 s |
| Fuerza | 4–6 reps (6–8 en principiantes) | 8–10 reps | 120 s |
| Acondicionamiento | 12–15 reps | 15–20 reps | 90 s |

**Carga sugerida inicial** = `peso corporal × ratio del ejercicio × factor de nivel × factor de objetivo × factor de sexo`, redondeada a pasos de 2,5 kg. Factores: nivel (0,6 / 1,0 / 1,3), objetivo (hipertrofia 1,0 · fuerza 1,15 · acondicionamiento 0,75), sexo femenino (0,65 en tren superior y 0,8 en tren inferior). Los ejercicios de peso corporal no llevan carga. **Es una estimación de partida, no una prescripción**: el usuario la ajusta. Los ratios deben calibrarse con datos reales (ver plan de pruebas).

**Edición libre:** máximo 12 ejercicios por día, sin repetir el mismo ejercicio en un día, series de 1 a 10, descanso de 0 a 600 s. Al reemplazar o agregar, el sistema recalcula repeticiones, descanso y carga del ejercicio nuevo.

**Plan desactualizado:** si el usuario cambia días, objetivo o nivel en el perfil, su plan activo se marca como *desactualizado* y se le ofrece regenerarlo. El plan anterior se guarda en el historial.

---

## 5. Endpoints principales

Todos viven bajo `/v1`. Los marcados con 🔒 requieren el encabezado `Authorization: Bearer <token>`.

| Grupo | Método y ruta | Para qué |
|-------|---------------|----------|
| Acceso | `POST /auth/register` · `POST /auth/login` · `POST /auth/refresh` · 🔒`GET /auth/me` | Cuenta y sesión |
| Perfil | 🔒`POST /athletes/me` · 🔒`GET /athletes/me` · 🔒`PATCH /athletes/me` · 🔒`GET /athletes/me/weights` | Perfil, IMC e historial de peso |
| Ejercicios | 🔒`GET /exercises` · 🔒`GET /exercises/{id}` · 🔒`GET /exercises/{id}/alternatives` | Catálogo, ficha técnica y alternativas |
| Plan | 🔒`GET /plans/preview` · 🔒`POST /plans` · 🔒`GET /plans/active` · 🔒`GET /plans` · 🔒`GET /plans/{id}` | Asignar, ver y consultar historial |
| Edición | 🔒`PATCH /plans/active/exercises/{id}` · `DELETE …/{id}` · `POST …/{id}/replace` · `POST /plans/active/days/{dia}/exercises` · `PUT …/order` · `POST …/reset` | Edición libre |
| Intensidad | 🔒`POST /plans/active/intensity` | Bajar intensidad sin IA |
| IA | 🔒`GET /ai/status` · `POST /ai/proposals` · `GET /ai/proposals` · `POST /ai/proposals/{id}/apply` · `POST …/reject` | IA por token |
| Admin | 🔒`POST /admin/exercises` · `PATCH /admin/exercises/{id}` | Catálogo (rol ADMIN) |

Los errores siempre tienen la forma `{"code": "GT-4220", "message": "...", "details": [...]}`. Códigos: `GT-4000` JSON mal formado · `GT-4010` sin sesión · `GT-4030` sin permiso · `GT-4040` no existe · `GT-4090` conflicto · `GT-4220` dato inválido · `GT-4290` demasiadas solicitudes · `GT-5030` servicio no disponible.

---

## 6. IA por token (opcional)

Si defines `AI_API_KEY`, el backend puede pedirle a un modelo de lenguaje (se paga **por token**) que personalice el plan o lo ajuste. Si no la defines, la IA queda apagada y **todo lo demás funciona igual**.

Tres reglas de diseño: la IA **solo propone**, el backend **valida cada cambio** con reglas fijas y el usuario **confirma** antes de que algo se aplique. Además, nunca se envía nombre ni correo al proveedor, y los mensajes sobre salud o nutrición se bloquean antes de gastar tokens. Detalle completo, costos y cómo activarla: [docs/IA_POR_TOKEN.md](docs/IA_POR_TOKEN.md).

---

## 7. Despliegue en Railway

El repositorio ya trae `railway.json` (comando de arranque y comprobación de salud en `/health`). Resumen: crear un proyecto desde este repositorio de GitHub, añadir PostgreSQL y cargar las variables de entorno. Paso a paso con capturas de qué poner en cada variable: [docs/DESPLIEGUE_RAILWAY.md](docs/DESPLIEGUE_RAILWAY.md).

---

## 8. Si algo falla

Revisa [docs/GUIA_DE_ERRORES.md](docs/GUIA_DE_ERRORES.md): lista los errores más comunes con su causa probable y qué hacer, y trae una **plantilla para pedir ayuda a una IA** sin exponer claves.

## 9. Qué se verificó y qué no

Verificado con ejecución real: 59 pruebas automáticas en **SQLite y en PostgreSQL 16**; reinicio del servidor conservando datos; CORS; y un recorrido completo de la interfaz (registro → plan → edición → IA → perfil → reingreso) contra este backend, con un servidor de IA **simulado**.

**No verificado todavía:** una llamada real a un proveedor de IA (hace falta una clave), la interfaz en un navegador real (se probó en un navegador simulado) y el despliegue en Railway. Detalle en [docs/REGISTRO_Y_PRUEBAS.md](docs/REGISTRO_Y_PRUEBAS.md).
