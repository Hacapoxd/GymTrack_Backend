# Despliegue en Railway (backend + frontend + PostgreSQL)

Método: **Railway conectado a GitHub**. Cada vez que hagas `push` a la rama principal, Railway vuelve a construir y publicar. La configuración de arranque ya está en `railway.json` de cada repositorio; tú solo cargas variables.

> Los nombres de los menús de Railway pueden cambiar con el tiempo. Si algo no coincide, consulta <https://docs.railway.com>. Los costos de Railway y del proveedor de IA son por uso: revisa sus páginas de precios antes de publicar.

## Orden recomendado

### 1. Proyecto y base de datos
1. En Railway: **New Project → Deploy from GitHub repo** y elige `GymTrack_Backend`.
2. En el mismo proyecto: **New → Database → PostgreSQL**. Anota el nombre del servicio (normalmente `Postgres`).

### 2. Variables del backend (pestaña *Variables* del servicio backend)

| Variable | Valor |
|----------|-------|
| `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` (referencia al servicio de base de datos; si tu servicio se llama distinto, usa ese nombre) |
| `JWT_SECRET` | Texto largo y aleatorio. Genéralo con: `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `CORS_ORIGINS` | Se completa en el paso 5 con la URL del frontend |
| `ADMIN_EMAIL` y `ADMIN_PASSWORD` | Tu administrador del catálogo (opcional pero necesario para cargar GIF/video) |
| `AI_PROVIDER`, `AI_API_KEY`, `AI_MODEL` | Solo si activas la IA (ver [IA por token](IA_POR_TOKEN.md)) |

No necesitas definir `PORT`: Railway lo entrega solo.

### 3. Dirección pública del backend
En el servicio backend: **Settings → Networking → Generate Domain**. Se obtiene algo como `https://gymtrack-backend-xxxx.up.railway.app`.

Comprueba: abre `https://<tu-backend>/health` (debe responder `{"status":"ok"}`) y `https://<tu-backend>/docs`.

### 4. Frontend
1. **New → GitHub Repo → `GymTrack_Frontend`**.
2. Variable: `GYMTRACK_API_URL` = `https://<tu-backend>/v1` (con `/v1` al final).
3. **Generate Domain** del frontend.

### 5. Cerrar el círculo (CORS)
Vuelve al backend y define `CORS_ORIGINS` = `https://<tu-frontend>` (sin barra final). Si el frontend tiene dominio propio, agrégalo separado por coma. Railway vuelve a desplegar solo.

### 6. Prueba final
Abre el frontend, crea una cuenta, completa el perfil y genera el plan.

## Importante

- **No uses SQLite en Railway.** El disco del servicio se borra en cada despliegue y perderías los datos. Usa el PostgreSQL del paso 1.
- Las tablas se crean solas al iniciar. **Antes de cambiar columnas con usuarios reales**, hay que adoptar migraciones (Alembic): ver pendientes en el [registro](REGISTRO_Y_PRUEBAS.md).
- Cambiar `JWT_SECRET` cierra todas las sesiones activas (es normal).
- Nunca subas `.env` ni claves a GitHub.
- El límite de solicitudes por minuto vive en la memoria de cada servidor; con una sola instancia funciona bien.

## Lista de comprobación antes de mostrarlo

- [ ] `/health` responde y `/docs` abre.
- [ ] `JWT_SECRET` propio y largo.
- [ ] `CORS_ORIGINS` apunta solo al frontend (no `*`).
- [ ] La base de datos es PostgreSQL y no SQLite.
- [ ] Registro, perfil, plan y edición funcionan desde la URL pública.
- [ ] Si activaste la IA: límite diario (`AI_DAILY_LIMIT`) y tope de tokens definidos, y alerta de gasto configurada en el proveedor.
