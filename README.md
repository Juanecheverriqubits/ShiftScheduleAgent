"""
Generador mensual de horario de turnos (shift schedule).
Genera un Excel con dos hojas: horario del mes y resumen de tarifas/ingresos.

Uso:
    python generate_schedule.py                          # mes siguiente automático
    python generate_schedule.py --year 2026 --month 7    # mes específico
    python generate_schedule.py --restriccion "Pedro:2026-07-05:2026-07-10"
"""
import argparse
import calendar
from datetime import date, timedelta

import holidays
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

PEOPLE = ["Diego", "Pedro", "Juan Carlos"]
RATE_MORNING = 15077
RATE_NIGHT = 17231
RATE_FULLDAY = 40000
MAX_DIFF_TARGET = 30000

MESES = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
         "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]


def get_holidays(year, month, extra=None):
    co = holidays.Colombia(years=year)
    hs = {d for d in co if d.year == year and d.month == month}
    if extra:
        hs |= set(extra)
    return hs


def is_fullday(d, hols):
    return d.weekday() >= 5 or d in hols


def month_days(year, month):
    n = calendar.monthrange(year, month)[1]
    return [date(year, month, day) for day in range(1, n + 1)]


def blocked(person, d, restrictions):
    """restrictions: list of (person, start_date, end_date, shift_type or None)"""
    for p, start, end, stype in restrictions:
        if p == person and start <= d <= end and stype is None:
            return True
    return False


def forced(d, shift, restrictions):
    """Returns person forced into a (date, shift) slot, or None."""
    for p, start, end, stype in restrictions:
        if stype == shift and start <= d <= end:
            return p
    return None


def build_schedule(year, month, hols, restrictions):
    """
    schedule: dict date -> {'morning': name|None, 'night': name|None, 'full': name|None}
    Weekly rotation: per ISO week, roles rotate among the 3 people.
    """
    days = month_days(year, month)
    schedule = {}
    week_roles = {}  # iso_week -> {'morning': p, 'night': p, 'full': p}

    iso_weeks = sorted({d.isocalendar()[1] for d in days})
    for i, wk in enumerate(iso_weeks):
        rot = i % 3
        week_roles[wk] = {
            "morning": PEOPLE[rot % 3],
            "night": PEOPLE[(rot + 1) % 3],
            "full": PEOPLE[(rot + 2) % 3],
        }

    for d in days:
        wk = d.isocalendar()[1]
        roles = week_roles[wk]
        entry = {"morning": None, "night": None, "full": None}
        if is_fullday(d, hols):
            entry["full"] = pick(d, "full", roles["full"], restrictions)
        else:
            entry["morning"] = pick(d, "morning", roles["morning"], restrictions)
            entry["night"] = pick(d, "night", roles["night"], restrictions)
        schedule[d] = entry
    return schedule


def pick(d, shift, preferred, restrictions):
    f = forced(d, shift, restrictions)
    if f and not blocked(f, d, restrictions):
        return f
    if not blocked(preferred, d, restrictions):
        return preferred
    for p in PEOPLE:
        if not blocked(p, d, restrictions):
            return p
    raise ValueError(f"Nadie disponible el {d} para turno {shift}")


def totals(schedule):
    t = {p: 0 for p in PEOPLE}
    for entry in schedule.values():
        if entry["morning"]:
            t[entry["morning"]] += RATE_MORNING
        if entry["night"]:
            t[entry["night"]] += RATE_NIGHT
        if entry["full"]:
            t[entry["full"]] += RATE_FULLDAY
    return t


def rebalance(schedule, restrictions, max_iters=500):
    """Greedy: move single shifts from richest to poorest until diff <= target."""
    for _ in range(max_iters):
        t = totals(schedule)
        rich = max(t, key=t.get)
        poor = min(t, key=t.get)
        diff = t[rich] - t[poor]
        if diff <= MAX_DIFF_TARGET:
            break
        moved = False
        # Try shifts in order of size closest to half the diff
        candidates = []
        for d, entry in schedule.items():
            for shift, rate in (("night", RATE_NIGHT), ("morning", RATE_MORNING),
                                ("full", RATE_FULLDAY)):
                if entry[shift] == rich and not blocked(poor, d, restrictions) \
                        and forced(d, shift, restrictions) is None:
                    new_diff = abs((t[rich] - rate) - (t[poor] + rate))
                    others = [t[p] for p in PEOPLE if p not in (rich, poor)]
                    spread = max([t[rich] - rate, t[poor] + rate] + others) - \
                             min([t[rich] - rate, t[poor] + rate] + others)
                    candidates.append((spread, new_diff, d, shift))
        if not candidates:
            break
        candidates.sort()
        spread, _, d, shift = candidates[0]
        cur_spread = max(t.values()) - min(t.values())
        if spread >= cur_spread:
            break
        schedule[d][shift] = poor
        moved = True
        if not moved:
            break
    return schedule


def validate(schedule, year, month, hols, restrictions):
    days = month_days(year, month)
    errors = []
    if set(schedule.keys()) != set(days):
        errors.append("Faltan días o hay días duplicados")
    for d in days:
        e = schedule[d]
        if is_fullday(d, hols):
            if not e["full"] or e["morning"] or e["night"]:
                errors.append(f"{d}: fin de semana/festivo mal asignado")
        else:
            if not e["morning"] or not e["night"] or e["full"]:
                errors.append(f"{d}: día laboral mal asignado")
        for shift in ("morning", "night", "full"):
            p = e[shift]
            if p and p not in PEOPLE:
                errors.append(f"{d}: nombre inválido {p}")
            if p and blocked(p, d, restrictions):
                errors.append(f"{d}: {p} asignado en día bloqueado")
    return errors


def write_excel(schedule, year, month, hols, restrictions, out_path):
    mes = MESES[month]
    wb = Workbook()

    # ---------- Hoja 1: Horario ----------
    ws = wb.active
    ws.title = f"{mes} {year}"
    header_fill = PatternFill("solid", start_color="D9E1F2")
    weekend_fill = PatternFill("solid", start_color="FCE4D6")
    bold = Font(bold=True, name="Arial")
    normal = Font(name="Arial")
    center = Alignment(horizontal="center")
    thin = Border(*[Side(style="thin")] * 4)

    ws["A1"] = f"SHIFT SCHEDULE {mes.upper()} {year}"
    ws["A1"].font = Font(bold=True, size=14, name="Arial")
    ws.merge_cells("A1:F1")
    ws["A1"].alignment = center

    headers = ["Fecha", "Día", "Turno 5:30am - 8:00am",
               "Turno 6:00pm - 10:00pm", "Turno 5:30am - 10:00pm", "Semana ISO"]
    for col, h in enumerate(headers, 1):
        c = ws.cell(row=3, column=col, value=h)
        c.font = bold
        c.fill = header_fill
        c.alignment = center
        c.border = thin

    row = 4
    for d in sorted(schedule):
        e = schedule[d]
        fd = is_fullday(d, hols)
        vals = [d.strftime("%d/%m/%Y"), DIAS[d.weekday()],
                e["morning"] or "", e["night"] or "", e["full"] or "",
                d.isocalendar()[1]]
        for col, v in enumerate(vals, 1):
            c = ws.cell(row=row, column=col, value=v)
            c.font = normal
            c.border = thin
            c.alignment = center
            if fd:
                c.fill = weekend_fill
        row += 1

    for col, w in zip("ABCDEF", [14, 12, 24, 24, 24, 12]):
        ws.column_dimensions[col].width = w
    ws.freeze_panes = "A4"

    # ---------- Hoja 2: Resumen y Tarifas ----------
    ws2 = wb.create_sheet("Resumen y Tarifas")
    t = totals(schedule)
    diff = max(t.values()) - min(t.values())
    total_general = sum(t.values())

    def put(r, a, b=None, b_bold=False):
        ws2.cell(row=r, column=1, value=a).font = bold if b is None else normal
        if b is not None:
            c = ws2.cell(row=r, column=2, value=b)
            c.font = bold if b_bold else normal

    r = 1
    put(r, "TARIFAS"); r += 1
    put(r, "Turno Mañana", RATE_MORNING); r += 1
    put(r, "Turno Noche", RATE_NIGHT); r += 1
    put(r, "Día Completo", RATE_FULLDAY); r += 2

    put(r, "FESTIVOS CONSIDERADOS"); r += 1
    if hols:
        co = holidays.Colombia(years=year)
        for h in sorted(hols):
            name = co.get(h, "Festivo agregado manualmente")
            put(r, h.strftime("%d/%m/%Y"), name); r += 1
    else:
        put(r, "Ninguno", ""); r += 1
    put(r, "Fuente", "Librería 'holidays' (calendario oficial de Colombia)"); r += 2

    put(r, "RESTRICCIONES APLICADAS"); r += 1
    if restrictions:
        for p, s, e_, stype in restrictions:
            desc = f"{s.strftime('%d/%m/%Y')} a {e_.strftime('%d/%m/%Y')}"
            desc += f" (forzado a {stype})" if stype else " (no disponible)"
            put(r, p, desc); r += 1
    else:
        put(r, "Ninguna", ""); r += 1
    r += 1

    put(r, "INGRESO POR PERSONA"); r += 1
    income_start = r
    for p in PEOPLE:
        put(r, p, t[p]); r += 1
    put(r, "Diferencia máxima", diff, b_bold=True); r += 1
    put(r, "Total general del mes",
        f"=SUM(B{income_start}:B{income_start + len(PEOPLE) - 1})", b_bold=True)

    for c_, w in zip("AB", [28, 50]):
        ws2.column_dimensions[c_].width = w
    for rr in range(income_start, income_start + len(PEOPLE) + 2):
        ws2.cell(row=rr, column=2).number_format = '#,##0'
    ws2.cell(row=2, column=2).number_format = '#,##0'
    ws2.cell(row=3, column=2).number_format = '#,##0'
    ws2.cell(row=4, column=2).number_format = '#,##0'

    wb.save(out_path)
    return t, diff, total_general


def parse_restriction(s):
    """Format: 'Persona:YYYY-MM-DD:YYYY-MM-DD[:morning|night|full]'"""
    parts = s.split(":")
    p = parts[0]
    start = date.fromisoformat(parts[1])
    end = date.fromisoformat(parts[2])
    stype = parts[3] if len(parts) > 3 else None
    return (p, start, end, stype)


def next_month(today=None):
    today = today or date.today()
    if today.month == 12:
        return today.year + 1, 1
    return today.year, today.month + 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int)
    ap.add_argument("--month", type=int)
    ap.add_argument("--restriccion", action="append", default=[],
                    help="Persona:YYYY-MM-DD:YYYY-MM-DD[:morning|night|full]")
    ap.add_argument("--festivo-extra", action="append", default=[],
                    help="YYYY-MM-DD")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    if args.year and args.month:
        year, month = args.year, args.month
    else:
        year, month = next_month()

    restrictions = [parse_restriction(s) for s in args.restriccion]
    extra = [date.fromisoformat(s) for s in args.festivo_extra]
    hols = get_holidays(year, month, extra)

    schedule = build_schedule(year, month, hols, restrictions)
    schedule = rebalance(schedule, restrictions)

    errors = validate(schedule, year, month, hols, restrictions)
    if errors:
        raise SystemExit("VALIDACIÓN FALLIDA:\n" + "\n".join(errors))

    out = args.out or f"horario_{MESES[month].lower()}_{year}.xlsx"
    t, diff, total = write_excel(schedule, year, month, hols, restrictions, out)

    mes = MESES[month]
    resumen = (
        f"Hola, ya está listo el horario de disponibilidad de {mes} {year}.\n\n"
        "Resumen:\n"
        + "\n".join(f"* {p}: ${t[p]:,}".replace(",", ".") for p in PEOPLE)
        + f"\n* Diferencia máxima: ${diff:,}".replace(",", ".")
        + f"\n* Total general: ${total:,}".replace(",", ".")
        + "\n\nTambién se tuvieron en cuenta los festivos de Colombia"
          " y las restricciones indicadas para este mes."
    )
    print(resumen)
    with open(out.replace(".xlsx", "_mensaje.txt"), "w") as f:
        f.write(resumen)
    print(f"\nArchivo generado: {out}")


if __name__ == "__main__":
    main()
