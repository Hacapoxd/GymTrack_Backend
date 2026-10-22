# Guía de errores comunes

Para equipos que programan poco: primero identifiquen **dónde** ocurre el error y **qué dice exactamente**. La mayoría de los problemas son de configuración, no de código.

## 1. ¿Dónde mirar primero?

| Dónde ocurre | Qué revisar |
|--------------|-------------|
| En la terminal al arrancar el backend | El **último** mensaje del error (el que está más abajo) |
| En el navegador (pantalla) | El mensaje rojo. Si dice "No se pudo conectar", es red/CORS/URL |
| En el navegador (F12 → pestaña *Console*) | Errores en rojo; los de CORS lo dicen explícitamente |
| En el navegador (F12 → pestaña *Network*) | La petición que falló: estado (401, 422, 500) y su respuesta |
| En Railway | Pestaña *Deployments* → *View logs* |

## 2. Errores de la API (códigos y qué significan)

| Código | Significado | Qué hacer |
|--------|-------------|-----------|
| `401` / `GT-4010` | Sin sesión, token vencido o credenciales incorrectas | Volver a iniciar sesión. Tras 5 fallos seguidos hay bloqueo de 15 min |
| `403` / `GT-4030` | No tienes permiso (ruta de administrador) | Entrar con la cuenta definida en `ADMIN_EMAIL` |
| `404` / `GT-4040` | No existe o no es tuyo (plan, día, propuesta) | Revisar el id; "Aún no completaste tu perfil" = falta crear el perfil |
| `409` / `GT-4090` | Conflicto: ya existe plan activo, ejercicio repetido, correo repetido | Leer el mensaje; para reemplazar el plan, confirmar el reemplazo |
| `422` / `GT-4220` | Dato inválido (rango, formato, regla) | Leer `details`: dice el campo y el problema |
| `429` / `GT-4290` | Demasiadas solicitudes o límite diario de IA | Esperar o usar "Bajar intensidad (sin IA)" |
| `503` / `GT-5030` | La IA no está activada o el proveedor falló | Ver sección de IA más abajo |

## 3. Problemas frecuentes

| Síntoma | Causa probable | Qué hacer |
|---------|----------------|-----------|
| "No se pudo conectar con el servidor" | El backend no está corriendo, o `config.js` apunta a otra URL | Abrir `<API>/health`; revisar `GYMTRACK_API_URL` del frontend |
| En *Console*: "blocked by CORS policy" | La URL del frontend no está en `CORS_ORIGINS` | Agregar la URL exacta del frontend (sin barra final) en el backend y redesplegar |
| Funciona en local pero no en Railway | Variables sin cargar o `localhost` en la URL de la API | Revisar *Variables* en ambos servicios |
| `ModuleNotFoundError: No module named ...` | Falta instalar dependencias o el entorno virtual no está activo | Activar `.venv` y correr `pip install -r requirements.txt` |
| `Address already in use` | Otro programa usa el puerto 8000 | Cambiar el puerto (`--port 8001`) y actualizar el frontend |
| `no such table` / `relation "..." does not exist` | Base de datos distinta o antigua | Local: borrar `gymtrack.db` y reiniciar. Railway: revisar `DATABASE_URL` |
| Cambié `models.py` y ahora falla | Las tablas ya existían con la forma vieja (no hay migraciones aún) | Local: borrar `gymtrack.db`. Producción: **no** borrar; hay que crear una migración |
| `password authentication failed` | `DATABASE_URL` incorrecta | Usar la referencia `${{Postgres.DATABASE_URL}}` de Railway |
| Se cierran todas las sesiones | Se cambió `JWT_SECRET` | Es normal; volver a iniciar sesión |
| Los datos desaparecen en Railway | Se usa SQLite (disco temporal) | Usar PostgreSQL |
| Build falla en Railway | Versión de Python o dependencia | Ver el log; el repositorio fija Python 3.12 en `.python-version` |
| Healthcheck falla en Railway | La app no arrancó (variable faltante, BD inaccesible) | Ver logs de arranque |
| El botón de IA no aparece | `AI_API_KEY` vacía → IA apagada (comportamiento esperado) | Ver [IA por token](IA_POR_TOKEN.md) |
| IA responde "no está disponible" | Clave inválida, sin crédito o proveedor caído | Revisar la clave y el saldo en el panel del proveedor (el detalle técnico queda en los logs, no en pantalla) |
| La IA devolvió "propuesta vacía" | El modelo no cumplió el formato o todo se descartó | Mirar "sugerencias descartadas" en la propuesta; reintentar con un mensaje más claro |
| Cambié el plan y la propuesta ya no se puede aplicar | La propuesta se valida contra el plan actual | Pedir una nueva |

## 4. Cómo pedir ayuda a una IA (sin exponer claves)

Copia y completa esta plantilla:

```text
Contexto: proyecto GymTrack (backend FastAPI + SQLAlchemy, frontend JavaScript puro).
Qué quería hacer: ...
Qué hice (pasos exactos): ...
Qué pasó: [pega el mensaje de error COMPLETO, de la terminal o de la consola del navegador]
Dónde ocurre: [local / Railway] — [archivo o endpoint, si lo sabes]
Lo que ya probé: ...
Pídele: primero explícame la causa en palabras simples; luego propón el cambio MÍNIMO y dime
qué archivo tocar. No cambies cosas que no estén relacionadas.
```

Antes de pegar nada, **borra claves, tokens, contraseñas y correos reales**. Después de aplicar un cambio sugerido, corran `pytest -q`: si algo se rompió, las pruebas lo dirán.

## 5. Errores que pueden resolver ustedes sin IA

Un mensaje de `422` indica el campo exacto; un `404` casi siempre es un id mal copiado; "No se pudo conectar" casi siempre es la URL o el backend apagado; un cambio de variable de entorno requiere reiniciar el servicio para surtir efecto. Dejen a la IA los errores con trazas largas, cambios de estructura de tablas y problemas de despliegue que no se aclaren con los logs.
