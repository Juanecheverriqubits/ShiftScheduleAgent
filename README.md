# Agente de Horarios de Turnos → Microsoft Teams

Genera mensualmente (último lunes) el horario de turnos del mes siguiente en Excel,
con festivos de Colombia, balance de ingresos y restricciones, y lo envía
automáticamente a Teams vía Power Automate.

## Arquitectura

```
Task Scheduler / cron (todos los lunes)
        ↓
main.py  →  ¿es el último lunes?  →  No: termina
        ↓ Sí
generate_schedule.py  →  Excel + mensaje de resumen
        ↓
Carpeta de OneDrive/SharePoint
        ↓
Power Automate ("When a file is created")
        ↓
Mensaje en Teams con adjunto + resumen
```

## 1. Instalación

```bash
pip install -r requirements.txt
```

## 2. Probar manualmente

```bash
# Mes específico
python generate_schedule.py --year 2026 --month 7

# Con restricciones (Persona:inicio:fin, fechas ISO)
python generate_schedule.py --year 2026 --month 7 --restriccion "Pedro:2026-07-05:2026-07-10"

# Forzar a alguien a un turno específico (morning|night|full)
python generate_schedule.py --year 2026 --month 8 --restriccion "Diego:2026-08-01:2026-08-01:morning"

# Festivo extra manual
python generate_schedule.py --year 2026 --month 7 --festivo-extra 2026-07-15

# Simular la ejecución mensual completa (ignora la verificación de último lunes)
OUTPUT_DIR=~/OneDrive/Horarios python main.py --force
```

## 3. Programar la ejecución

**Linux/Mac (cron):** ejecutar todos los lunes; el script decide si es el último.
```
0 7 * * 1 OUTPUT_DIR=/home/usuario/OneDrive/Horarios /usr/bin/python3 /ruta/agent/main.py
```

**Windows (Task Scheduler):**
- Trigger: semanal, lunes 7:00am
- Acción: `python C:\ruta\agent\main.py`
- Variable de entorno `OUTPUT_DIR` apuntando a la carpeta sincronizada de OneDrive.

## 4. Configurar el flujo de Power Automate

1. Ir a https://make.powerautomate.com → **Create** → **Automated cloud flow**.
2. Trigger: **"When a file is created"** (conector *OneDrive for Business* o
   *SharePoint*, según dónde esté la carpeta `Horarios`).
   - Folder: la carpeta donde `main.py` guarda los archivos.
3. Acción 1: **Get file content** (mismo conector), usando el *File identifier*
   del trigger.
4. Acción 2 (opcional, para el texto del resumen): **Get file content using path**
   apuntando al `.txt` de mensaje. Alternativa simple: escribir un mensaje fijo.
5. Acción 3: **Post message in a chat or channel** (conector *Microsoft Teams*).
   - Post as: Flow bot (o User).
   - Post in: Channel / Group chat según corresponda.
   - Message: el contenido del resumen.
6. Acción 4 (adjunto): el conector de Teams no adjunta archivos directamente
   en todos los planes; las dos opciones habituales:
   - **Opción A (recomendada):** incluir en el mensaje el **enlace de SharePoint/OneDrive**
     al archivo (`Link to item` del trigger). Una línea en el mensaje:
     `Archivo: <link>`.
   - **Opción B:** usar **"Send an HTTP request"** del conector de Teams/Graph
     para subir el archivo al canal (requiere permisos adicionales).
7. Guardar y probar: ejecutar `python main.py --force` y verificar que el
   mensaje llega a Teams.

## 5. Restricciones mensuales

Las restricciones **solo aplican al mes que se está generando** y se pasan
como argumentos en la ejecución. No se guardan entre meses (tal como exige
el comportamiento definido). Para un mes con restricciones, ejecutar
manualmente antes del último lunes:

```bash
python main.py --force --restriccion "Juan Carlos:2026-08-14:2026-08-15"
```

## 6. Archivos generados

- `horario_MM_YYYY.xlsx` — dos hojas:
  - **"[Mes] [Año]"**: Fecha (dd/mm/yyyy), Día, Turno mañana, Turno noche,
    Turno día completo, Semana ISO. Fines de semana/festivos resaltados.
  - **"Resumen y Tarifas"**: tarifas, festivos del mes y fuente, restricciones
    aplicadas, ingreso por persona, diferencia máxima y total general.
- `horario_MM_YYYY_mensaje.txt` — texto del resumen para el mensaje de Teams.

## Tarifas (fijas)

| Turno | Valor |
|---|---|
| Mañana (5:30am–8:00am) | 15.077 |
| Noche (6:00pm–10:00pm) | 17.231 |
| Día completo (fin de semana/festivo) | 40.000 |

Balance objetivo: diferencia máxima entre personas ≤ 30.000.
