# IA por token: cómo funciona y cómo controlar el costo

## 1. ¿Qué es un "token" y por qué se paga por token?

Los modelos de IA no leen palabras sino **tokens** (fragmentos de texto; en español, una palabra suele ser 1 a 3 tokens). El proveedor cobra por los tokens que **envías** (entrada) y por los que el modelo **responde** (salida). Más texto enviado = más costo. Por eso GymTrack envía un resumen compacto y no una conversación larga.

## 2. Qué hace la IA en GymTrack

| Acción | Qué pide el usuario | Qué puede proponer la IA |
|--------|--------------------|--------------------------|
| **Personalizar** | "Ajusta mi plan a mi perfil" | Cambiar series, repeticiones, descanso o carga; reemplazar ejercicios por otros del mismo grupo muscular; agregar o quitar ejercicios |
| **Bajar intensidad** | "Estoy corto de energía esta semana" | Solo reducciones (menos series o menos carga) |
| **Subir intensidad** | "Quiero algo más exigente" | Solo aumentos moderados |
| **Acortar sesión** | "Solo tengo 40 minutos" | Quitar series o ejercicios secundarios; avisa si aún se pasa del tiempo |

Además existe **Bajar intensidad (sin IA)**: −1 serie (mínimo 2) y −10 % de carga. No gasta tokens y funciona aunque la IA esté apagada.

**Lo que la IA no hace:** consejos de salud, nutrición, suplementos, diagnósticos ni rehabilitación. No hay chat libre: solo propuestas sobre el plan.

## 3. Propone → valida → confirma

```
1. El usuario pide una acción (y opcionalmente escribe una frase).
2. El backend arma un resumen: perfil + plan + catálogo.   (sin nombre ni correo)
3. El modelo responde JSON con operaciones.                 ← aquí se gastan tokens
4. El backend VALIDA cada operación con reglas fijas.       ← lo inválido se descarta
5. Se guarda la propuesta (estado PENDING).                 ← el plan NO ha cambiado
6. El usuario revisa y toca "Aplicar" o "Descartar".
7. Al aplicar, se vuelve a validar contra el plan de ese momento.
```

Ejemplo de operación que devuelve el modelo (el backend la acepta solo si cumple las reglas):

```json
{ "op": "UPDATE", "itemId": "…", "sets": 3, "loadKg": 52.5, "reason": "Menos volumen esta semana." }
```

### Reglas que el backend aplica (no dependen de que el modelo obedezca)

- Solo ids que existen en **tu** plan y en el catálogo. Los ids inventados se descartan.
- Series 1 a 10, repeticiones 1 a 50, descanso 0 a 600 s; cambio de series de máximo ±2 por ejercicio.
- Carga entre 50 % y 115 % de la actual; ejercicios de peso corporal no reciben carga.
- **Dirección según la intención:** bajar o acortar no puede subir series, carga ni descansos y no agrega ejercicios; subir no puede bajar nada.
- Reemplazos: mismo grupo muscular y sin repetir ejercicio en el día.
- Máximo 10 operaciones por propuesta, una por ejercicio, y cada día conserva al menos 2 ejercicios.
- Quitar ejercicios solo en *Acortar sesión*, *Personalizar* y la petición libre (`FREE`, disponible en la API).
- Si el mensaje del usuario habla de salud o nutrición (dolor, lesión, dieta, medicamentos, suplementos, etc.), **se rechaza antes de llamar al modelo** (cero tokens gastados).

Cada propuesta muestra al usuario qué se descartó y por qué, y el motivo (`reason`) de cada cambio en lenguaje simple.

## 4. Privacidad

Se envía al proveedor: edad, sexo, peso, estatura, nivel, objetivo, días por semana, el plan (ejercicios, series, cargas), el catálogo y el texto que el usuario escribió. **No se envía** nombre, apellido, correo ni identificadores de cuenta. Aun así, el texto libre lo escribe el usuario: la pantalla le advierte que no escriba temas de salud.

## 5. Costo: cómo estimarlo y controlarlo

**Tamaño aproximado medido en el código** (estimación de tokens por caracteres; el valor real queda guardado en cada propuesta):

| Plan | Entrada aproximada por propuesta |
|------|----------------------------------|
| 3 días, principiante | ≈ 3 000 tokens |
| 4 días, intermedio | ≈ 3 500 tokens |
| 6 días, avanzado | ≈ 4 300 tokens |

Elegir **"Solo este día"** reduce la entrada porque se envía un solo día. La salida está limitada por `AI_MAX_OUTPUT_TOKENS` (1 500 por defecto) y suele ser bastante menor.

**Fórmula:** `costo = entrada/1 000 000 × precio_entrada + salida/1 000 000 × precio_salida`. Los precios dependen del proveedor y del modelo: consúltalos en su página de precios (cambian con frecuencia, por eso no se anotan aquí).

**Controles incluidos:**

| Control | Dónde | Efecto |
|---------|-------|--------|
| `AI_DAILY_LIMIT` (10) | Variable de entorno | Máximo de propuestas por usuario y por día; al llegar, responde `429` y ofrece el botón sin IA |
| `AI_MAX_OUTPUT_TOKENS` (1500) | Variable de entorno | Tope de salida por llamada |
| Filtro de salud/nutrición | Código | No gasta tokens en mensajes fuera de alcance |
| Registro de tokens | Tabla `ai_proposals` | Cada propuesta guarda tokens de entrada y salida |
| Uso del día | `GET /v1/ai/status` | Muestra propuestas y tokens del usuario hoy |
| Alerta de gasto | Panel del proveedor | **Configúrala tú**: es la protección real contra sorpresas |

Para sumar el consumo total en PostgreSQL:

```sql
SELECT date_trunc('day', created_at) AS dia, count(*) AS propuestas,
       sum(input_tokens) AS entrada, sum(output_tokens) AS salida
FROM ai_proposals GROUP BY 1 ORDER BY 1 DESC;
```

## 6. Cómo activarla

La IA se enciende con variables de entorno (en local, en `.env`; en Railway, en *Variables*). Sin `AI_API_KEY`, queda apagada.

| Proveedor | Variables |
|-----------|-----------|
| **Anthropic (Claude)** | `AI_PROVIDER=anthropic` · `AI_API_KEY=<tu clave>` · `AI_MODEL=` (vacío usa un modelo pequeño y económico; confirma el nombre vigente en la documentación de Anthropic) |
| **OpenAI** | `AI_PROVIDER=openai` · `AI_API_KEY=<clave>` · `AI_MODEL=<modelo>` |
| **Gemini u otros compatibles con OpenAI** | `AI_PROVIDER=openai` · `AI_API_KEY=<clave>` · `AI_MODEL=<modelo>` · `AI_BASE_URL=<URL compatible del proveedor>` (para Gemini: `https://generativelanguage.googleapis.com/v1beta/openai/`) |

Recomendación: para esta tarea (JSON corto y reglas claras) conviene un **modelo pequeño y barato**; las validaciones del backend son las que garantizan la calidad, no el tamaño del modelo.

La clave **nunca** debe ir en el frontend ni en GitHub. Si se filtra, revócala en el panel del proveedor y crea otra.

## 7. ¿Por qué usar GymTrack y no un chatbot general?

Con ChatGPT, Gemini o Claude se puede pedir una rutina. La ventaja de GymTrack no es "una IA mejor", sino que **ya conoce tu contexto y actúa sobre tu plan real**:

| En un chatbot general | En GymTrack |
|----------------------|-------------|
| Escribes tu perfil y tu rutina cada vez | Ya tiene tu perfil y tu plan |
| Recibes texto que debes copiar y ordenar | Ves los cambios y los aplicas con un toque |
| Puede inventar un ejercicio o una carga absurda | Solo usa ejercicios del catálogo y rechaza cambios fuera de rango |
| No recuerda qué cambiaste | Historial de planes y "volver al plan recomendado" |
| Sin ficha técnica integrada | Técnica y errores comunes en cada ejercicio |
| Depende de la IA para todo | Sin IA igual funciona (plantillas y botón de bajar intensidad) |

**Limitación honesta:** un chatbot general responde cualquier tema y GymTrack no. Que los usuarios lo prefieran se debe **comprobar**, no asumir: en las pruebas con el equipo, midan cuántos pasos y cuánto tiempo toma lograr "bajar mi intensidad" o "acortar mi sesión" en GymTrack frente a un chatbot general (ver [plan de pruebas](REGISTRO_Y_PRUEBAS.md)).

## 8. Cómo se probó sin gastar tokens

- Las 59 pruebas automáticas usan un **modelo falso** que devuelve respuestas fijas (incluidas respuestas inválidas y maliciosas).
- Los adaptadores de Anthropic y OpenAI-compatible se probaron con respuestas simuladas para verificar la forma exacta de las peticiones, la lectura de tokens y que los errores no filtren la clave.
- Se hizo un recorrido completo contra un servidor HTTP que imita la API compatible con OpenAI.
- **Falta** una prueba con un proveedor real: hacen falta una clave y unos centavos de crédito.
