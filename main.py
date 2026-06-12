"""
Orquestador mensual.
Ejecutar todos los lunes (cron / Task Scheduler). Solo genera el archivo
si hoy es el último lunes del mes. Guarda el Excel y el mensaje de resumen
en la carpeta sincronizada con OneDrive/SharePoint, de donde Power Automate
lo recoge y lo envía a Teams.

Configuración por variables de entorno (o editar abajo):
    OUTPUT_DIR  -> carpeta vigilada por Power Automate (OneDrive/SharePoint local)

Cron sugerido (todos los lunes 7:00am):
    0 7 * * 1 /usr/bin/python3 /ruta/agent/main.py

Windows Task Scheduler: trigger semanal, lunes, 7:00am.
"""
import calendar
import os
import subprocess
import sys
from datetime import date

OUTPUT_DIR = os.environ.get("OUTPUT_DIR", os.path.expanduser("~/OneDrive/Horarios"))


def is_last_monday(today=None):
    today = today or date.today()
    if today.weekday() != 0:
        return False
    last_day = calendar.monthrange(today.year, today.month)[1]
    return today.day + 7 > last_day


def main():
    today = date.today()
    force = "--force" in sys.argv

    if not is_last_monday(today) and not force:
        print(f"{today}: no es el último lunes del mes. No se genera nada.")
        return

    if today.month == 12:
        year, month = today.year + 1, 1
    else:
        year, month = today.year, today.month + 1

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "generate_schedule.py")

    # Restricciones del mes: pasar como argumentos extra al ejecutar manualmente,
    # p. ej.:  python main.py --force --restriccion "Pedro:2026-07-05:2026-07-10"
    extra = [a for a in sys.argv[1:] if a != "--force"]

    out_name = f"horario_{month:02d}_{year}.xlsx"
    out_path = os.path.join(OUTPUT_DIR, out_name)

    cmd = [sys.executable, script, "--year", str(year), "--month", str(month),
           "--out", out_path] + extra
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print("ERROR generando el horario:", result.stderr, file=sys.stderr)
        sys.exit(1)

    print(result.stdout)
    print(f"Archivo guardado en: {out_path}")
    print("Power Automate lo detectará y lo enviará a Teams.")


if __name__ == "__main__":
    main()
