name: Horario mensual de turnos

on:
  schedule:
    # Todos los lunes a las 7:00am hora Colombia (UTC-5) = 12:00 UTC
    - cron: "0 12 * * 1"
  workflow_dispatch:
    # Permite ejecución manual desde la pestaña Actions (útil para pruebas
    # o para regenerar un mes con restricciones)
    inputs:
      force:
        description: "Forzar generación aunque no sea el último lunes"
        type: boolean
        default: false
      year:
        description: "Año (opcional, ej. 2026)"
        required: false
      month:
        description: "Mes (opcional, 1-12)"
        required: false
      restricciones:
        description: 'Restricciones separadas por ; ej: Pedro:2026-07-05:2026-07-10'
        required: false

jobs:
  generar-horario:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Instalar dependencias
        run: pip install -r requirements.txt

      - name: Generar y enviar horario
        env:
          POWER_AUTOMATE_URL: ${{ secrets.POWER_AUTOMATE_URL }}
          FORCE: ${{ inputs.force }}
          INPUT_YEAR: ${{ inputs.year }}
          INPUT_MONTH: ${{ inputs.month }}
          RESTRICCIONES: ${{ inputs.restricciones }}
        run: python main.py

      - name: Guardar copia como artifact (respaldo si falla Teams)
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: horario
          path: output/
          if-no-files-found: ignore
          retention-days: 90
