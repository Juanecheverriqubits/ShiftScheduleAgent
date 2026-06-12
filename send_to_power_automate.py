# Agente de Horarios de Turnos → Microsoft Teams

Sistema 100% automático: cada **último lunes del mes**, GitHub Actions genera
el horario de turnos del mes siguiente (Excel con festivos de Colombia,
rotación y balance de ingresos) y lo envía a Teams vía Power Automate.
No requiere servidor ni PC encendida.

## Arquitectura

```
GitHub Actions (cron: todos los lunes 7am Colombia)
        ↓
main.py → ¿es el último lunes? → No: termina
        ↓ Sí
generate_schedule.py → Excel + mensaje
        ↓
POST (JSON con archivo en base64) → trigger HTTP de Power Automate
        ↓
Power Automate: guarda en OneDrive/SharePoint + postea en Teams
```

## Estructura del repo

```
.github/workflows/horario.yml   ← scheduler (GitHub Actions)
main.py                         ← orquestador (último lunes + envío)
generate_schedule.py            ← lógica del horario y el Excel
send_to_power_automate.py       ← envío HTTP del archivo
requirements.txt
```

## Paso 1 — Crear el flujo en Power Automate

1. https://make.powerautomate.com → **Create** → **Instant cloud flow** →
   trigger **"When an HTTP request is received"**.
2. En *Request Body JSON Schema* pegar:

```json
{
  "type": "object",
  "properties": {
    "filename":    { "type": "string" },
    "filecontent": { "type": "string" },
    "mensaje":     { "type": "string" }
  }
}
```

3. Acción **Create file** (OneDrive for Business o SharePoint):
   - Folder Path: carpeta destino, ej. `/Horarios`
   - File Name: `filename` (contenido dinámico del trigger)
   - File Content: expresión `base64ToBinary(triggerBody()?['filecontent'])`
4. Acción **Post message in a chat or channel** (Microsoft Teams):
   - Post as: Flow bot · Post in: Channel
   - Message: contenido dinámico `mensaje` + el **link del archivo creado**
     (salida *Web Url* / *Link to item* del paso anterior).
5. Guardar. Copiar la **HTTP URL** que genera el trigger (la necesitas en el paso 2).

## Paso 2 — Configurar GitHub

1. Crear un repositorio (privado recomendado) y subir todos estos archivos.
2. En el repo: **Settings → Secrets and variables → Actions → New repository secret**
   - Name: `POWER_AUTOMATE_URL`
   - Value: la URL del trigger HTTP copiada en el paso 1.
3. Listo. El workflow corre solo cada lunes; actúa únicamente el último lunes.

## Paso 3 — Probar

En GitHub: pestaña **Actions** → *Horario mensual de turnos* → **Run workflow**:
- `force`: ✓ (genera aunque no sea último lunes)
- `year`/`month`: opcional (ej. 2026 / 7)
- `restricciones`: opcional, separadas por `;`
  - Ej: `Pedro:2026-07-05:2026-07-10;Juan Carlos:2026-07-14:2026-07-15`
  - Forzar turno: `Diego:2026-07-01:2026-07-01:morning`

En 1-2 minutos debe llegar el mensaje a Teams con el resumen y el link al Excel.

## Restricciones mensuales

Las restricciones solo aplican al mes para el que se indican (no se guardan).
Si un mes tiene restricciones, ejecuta el workflow **manualmente** con el campo
`restricciones` antes de que corra el automático, usando `year`/`month` del mes
siguiente — la ejecución automática del último lunes no las conoce.

## Respaldo ante fallos

Si el envío a Power Automate falla, el Excel **no se pierde**: queda guardado
como *artifact* del workflow en GitHub (pestaña Actions → la ejecución →
sección Artifacts, retención 90 días), y el workflow marca error para que
recibas la notificación de GitHub.

## Prueba local (opcional)

```bash
pip install -r requirements.txt
python generate_schedule.py --year 2026 --month 7
python generate_schedule.py --year 2026 --month 7 --restriccion "Pedro:2026-07-05:2026-07-10"
FORCE=true python main.py   # pipeline completo sin enviar (sin POWER_AUTOMATE_URL)
```

## Tarifas (fijas)

| Turno | Valor |
|---|---|
| Mañana (5:30am–8:00am) | 15.077 |
| Noche (6:00pm–10:00pm) | 17.231 |
| Día completo (fin de semana/festivo) | 40.000 |

Balance objetivo: diferencia máxima entre personas ≤ 30.000.

## Nota sobre el cron de GitHub Actions

GitHub puede retrasar ejecuciones programadas algunos minutos (a veces más en
horas pico). Si la hora exacta importa, adelanta el cron. La hora está en UTC:
`0 12 * * 1` = lunes 7:00am Colombia (UTC-5).
