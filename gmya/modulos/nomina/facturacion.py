"""Facturacion por horas EMPRESA A (v6.21, sin Streamlit): cuanto facturar
cada mes por los empleados de una BU (BU1) segun dias pagados en la PILA
y la tarifa por hora de cada colaborador.

Contrato:
  leer_costos_nomina(contenido) -> {"meses": OrderedDict(mes -> [fila]),
      "ingresos": {cedula: {...}}, "anio", "bus", "avisos"}. Libro «NOMINA Y
      COSTOS COLOMBIA …» (hojas «Nomina <mes>» y «INGRESOS Y RETIROS»).
      fila: {mes, n_mes, bu, cedula, nombre, dias (None si vacio), fila}.
  leer_tarifas(contenido) -> {"por_cedula": {ced: {nombre, cargo, min,
      max}}, "cargos": {cargo: (min, max)}, "avisos"}. Hoja «Tarifa
      Colaborador» de «Resumen Tarifas» (Identificación, Nombre, Cargo, Min,
      Max; USD por hora).
  armar_facturacion(costos, tarifas, config=None) -> {"meses": [...],
      "observaciones", "sin_tarifa", "tarifas" (las usadas, con las
      asignadas por cargo), "totales", "config"}.
  horas_mes(dias, config) / tarifa_aplicada(min, max, factor).
  excel_facturacion(resultado) -> bytes: RESUMEN, PARAMETROS, TARIFAS, una
      hoja por mes y OBSERVACIONES, con formulas vivas (factor, metodo de
      horas y tarifas editables en el Excel). Valor por empleado redondeado
      a centavos (igual en pantalla y en el Excel).
  nombre_archivo(resultado) -> "FACTURACION HORAS BU1 ENE-OCT 2026.xlsx".
Reglas (confirmadas con la firma, nov-2026):
  - Solo las BU elegidas (BU1). Cada mes, quien trabajo ese mes (dias > 0);
    los retirados se cobran en sus meses.
  - Dias = DÍAS PAGADOS EN ESTE MES (PILA). Si estan vacios, salen de
    INGRESOS Y RETIROS (dias del mes de ingreso o retiro; 30 en los meses
    completos intermedios) y se avisa.
  - Horas: proporcion de 30 dias = 168 h (dias / 30 x 168) o semanas de 5
    dias (dias / 5 x 42); hora completa (0,5 sube), tope 168 (42 x 4).
  - Tarifa = minima + factor x (maxima - minima); por defecto la minima.
    Quien no esta en la lista de tarifas toma la de su cargo segun el
    contrato (config["cargos"], editable y guardado); si no, queda sin valor y se
    avisa. Nada se inventa.
Depende de: (solo openpyxl)
"""

import datetime
import io
import re
import unicodedata
from collections import OrderedDict
from decimal import ROUND_HALF_UP, Decimal

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
ABREV = ["ENE", "FEB", "MAR", "ABR", "MAY", "JUN", "JUL", "AGO", "SEP",
         "OCT", "NOV", "DIC"]
METODOS = OrderedDict([
    ("proporcion", "PROPORCIÓN 30 DÍAS"),
    ("semanas", "SEMANAS DE 5 DÍAS"),
])
# Cargo segun el contrato de trabajo de empleados que no estan en «Tarifa
# Colaborador» (p. ej. retirados). Dato privado del cliente: no va en el
# codigo; la pantalla lo guarda en facturacion_cargos.json (GMYA Tools) y lo
# pasa en config["cargos"].
CARGOS_SIN_TARIFA = OrderedDict()
CONFIG_FACTURACION = {
    "bus": ["BU1"], "factor": 0.0, "metodo": "proporcion",
    "horas_semana": 42, "semanas_mes": 4, "dias_semana": 5, "dias_mes": 30,
    "cargos": dict(CARGOS_SIN_TARIFA),
}


def clave(texto):
    t = unicodedata.normalize("NFKD", str(texto or "")).encode(
        "ascii", "ignore").decode().upper()
    return re.sub(r"\s+", " ", t).strip()


def _cedula(valor):
    if isinstance(valor, float) and valor.is_integer():
        valor = int(valor)
    return re.sub(r"\D", "", str(valor or ""))


def _abrir(contenido):
    from openpyxl import load_workbook
    return load_workbook(io.BytesIO(contenido), data_only=True)


# ------------------------------------------------------------
# Lectura
# ------------------------------------------------------------
def _columnas(ws, maximo=4):
    for r in range(1, maximo + 1):
        h = {clave(c.value): c.column for c in ws[r] if c.value}
        if "BU" in h and any(k.startswith("DIAS PAGADOS EN ESTE MES")
                             for k in h):
            return r, h
    return None, None


def leer_costos_nomina(contenido):
    libro = _abrir(contenido)
    meses, ingresos, avisos, bus = OrderedDict(), {}, [], OrderedDict()
    anio = None
    for hoja in libro.worksheets:
        t = clave(hoja.title)
        if "INGRESOS Y RETIROS" in t:
            for r in range(1, hoja.max_row + 1):
                ced = _cedula(hoja.cell(r, 1).value)
                if not ced or len(ced) < 5:
                    continue
                d = {"nombre": hoja.cell(r, 2).value,
                     "ingreso": hoja.cell(r, 3).value,
                     "dias_ingreso": hoja.cell(r, 5).value,
                     "retiro": hoja.cell(r, 6).value,
                     "dias_retiro": hoja.cell(r, 8).value}
                ingresos[ced] = d
                for f in (d["ingreso"], d["retiro"]):
                    if isinstance(f, datetime.datetime):
                        anio = anio or f.year
    for hoja in libro.worksheets:
        m = re.match(r"^NOMINA\s+([A-Z]+)$", clave(hoja.title))
        if not m or m.group(1).lower() not in MESES:
            continue
        mes = m.group(1).lower()
        fila_cab, h = _columnas(hoja)
        if not h:
            avisos.append(f"Hoja «{hoja.title}»: no se encontraron las "
                          "columnas BU y DÍAS PAGADOS EN ESTE MES; se omitió.")
            continue
        c_bu, c_nit = h["BU"], h.get("NIT")
        c_nom = h.get("SUELDOS") or h.get("NOMBRE")
        c_dias = next(v for k, v in h.items()
                      if k.startswith("DIAS PAGADOS EN ESTE MES"))
        filas = []
        for r in range(fila_cab + 1, hoja.max_row + 1):
            bu = hoja.cell(r, c_bu).value
            nom = hoja.cell(r, c_nom).value
            if not isinstance(nom, str) or not nom.strip() or not bu:
                continue
            ced = _cedula(hoja.cell(r, c_nit).value) if c_nit else ""
            if not ced:
                m2 = re.search(r"\(\s*I[dD]\.?\s*([0-9]+)", nom)
                ced = m2.group(1) if m2 else ""
            dias = hoja.cell(r, c_dias).value
            filas.append({
                "mes": mes, "n_mes": MESES.index(mes) + 1,
                "hoja": hoja.title, "fila": r, "bu": str(bu).strip(),
                "cedula": ced,
                "nombre": re.sub(r"\(.*$", "", nom).strip().upper(),
                "dias": dias if isinstance(dias, (int, float)) else None})
            bus[str(bu).strip().upper()] = True
        meses[mes] = filas
    if not meses:
        raise ValueError("No se encontraron hojas «Nomina <mes>» con las "
                         "columnas BU y DÍAS PAGADOS EN ESTE MES (PILA).")
    meses = OrderedDict(sorted(meses.items(),
                               key=lambda kv: MESES.index(kv[0])))
    return {"meses": meses, "ingresos": ingresos,
            "anio": anio or datetime.date.today().year,
            "bus": list(bus), "avisos": avisos}


def leer_tarifas(contenido):
    libro = _abrir(contenido)
    for hoja in libro.worksheets:
        for r in range(1, min(hoja.max_row, 10) + 1):
            h = {clave(c.value): c.column for c in hoja[r] if c.value}
            if {"IDENTIFICACION", "NOMBRE", "CARGO", "MIN", "MAX"} <= set(h):
                por, cargos, avisos = OrderedDict(), OrderedDict(), []
                for rr in range(r + 1, hoja.max_row + 1):
                    ced = _cedula(hoja.cell(rr, h["IDENTIFICACION"]).value)
                    mn = hoja.cell(rr, h["MIN"]).value
                    mx = hoja.cell(rr, h["MAX"]).value
                    if not ced or not isinstance(mn, (int, float)):
                        continue
                    cargo = str(hoja.cell(rr, h["CARGO"]).value or "").strip()
                    por[ced] = {"nombre": hoja.cell(rr, h["NOMBRE"]).value,
                                "cargo": cargo, "min": float(mn),
                                "max": float(mx)}
                    previo = cargos.get(clave(cargo))
                    if previo and previo[1:] != (float(mn), float(mx)):
                        avisos.append(f"El cargo «{cargo}» tiene tarifas "
                                      "distintas según el colaborador: para "
                                      "asignar por cargo se usa la primera.")
                    cargos.setdefault(clave(cargo),
                                      (cargo, float(mn), float(mx)))
                return {"por_cedula": por, "cargos": cargos,
                        "avisos": avisos, "hoja": hoja.title}
    raise ValueError("No se encontró la tabla de tarifas (Identificación, "
                     "Nombre, Cargo, Min, Max), hoja «Tarifa Colaborador».")


# ------------------------------------------------------------
# Calculo
# ------------------------------------------------------------
def horas_mes(dias, config):
    tope = config["horas_semana"] * config["semanas_mes"]
    if config["metodo"] == "semanas":
        bruto = Decimal(str(dias)) / Decimal(str(config["dias_semana"])) \
            * Decimal(str(config["horas_semana"]))
    else:
        bruto = Decimal(str(dias)) / Decimal(str(config["dias_mes"])) \
            * Decimal(str(tope))
    return min(int(bruto.quantize(Decimal("1"), rounding=ROUND_HALF_UP)),
               int(tope))


def tarifa_aplicada(minima, maxima, factor):
    return minima + factor * (maxima - minima)


def _dias_por_fechas(d, n_mes, anio):
    if not d:
        return None
    ing, ret = d.get("ingreso"), d.get("retiro")
    clave_mes = (anio, n_mes)

    def ym(f):
        return (f.year, f.month) if isinstance(f, datetime.datetime) else None
    if ym(ing) == clave_mes and ym(ret) == clave_mes:
        return None                     # ingreso y retiro el mismo mes
    if ym(ing) == clave_mes:
        return d.get("dias_ingreso")
    if ym(ret) == clave_mes:
        return d.get("dias_retiro")
    if ym(ing) and ym(ing) > clave_mes:
        return 0
    if ym(ret) and ym(ret) < clave_mes:
        return 0
    return 30


def armar_facturacion(costos, tarifas, config=None):
    config = dict(CONFIG_FACTURACION, **(config or {}))
    bus = {clave(b) for b in config["bus"]}
    obs, meses = [], []
    # Tarifas usadas: las de la lista + las asignadas por cargo.
    usadas = OrderedDict((c, dict(t, origen="lista"))
                         for c, t in tarifas["por_cedula"].items())
    for ced, cargo in config["cargos"].items():
        if ced in usadas or not cargo:
            continue
        t = tarifas["cargos"].get(clave(cargo))
        if t:
            usadas[ced] = {"nombre": "", "cargo": t[0], "min": t[1],
                           "max": t[2], "origen": "cargo"}
    sin_tarifa = OrderedDict()
    for mes, filas in costos["meses"].items():
        nombre_mes = mes.capitalize()
        salida = []
        for f in filas:
            if clave(f["bu"]) not in bus:
                if f["cedula"] in tarifas["por_cedula"]:
                    obs.append((nombre_mes, f["nombre"], f["cedula"],
                                f"Tiene tarifa pero su BU es {f['bu']}: no "
                                "se incluyó."))
                continue
            if not re.match(r"^\d{5,11}$", f["cedula"] or "") or \
                    f["cedula"].startswith("8001"):
                if f["dias"] is None:
                    obs.append((nombre_mes, f["nombre"], f["cedula"],
                                "Sin días ni cédula de empleado (proveedor o "
                                "fila sin datos): no se incluyó."))
                    continue
            nota, dias = [], f["dias"]
            por_fechas = _dias_por_fechas(costos["ingresos"].get(
                f["cedula"]), f["n_mes"], costos["anio"])
            if dias is None:
                if por_fechas is None:
                    obs.append((nombre_mes, f["nombre"], f["cedula"],
                                "Sin días pagados en la nómina ni fechas de "
                                "ingreso/retiro: no se incluyó."))
                    continue
                dias = por_fechas
                if dias:
                    nota.append("Días tomados de INGRESOS Y RETIROS (la "
                                "nómina del mes no los trae).")
                    obs.append((nombre_mes, f["nombre"], f["cedula"],
                                f"Días pagados vacíos en la nómina: se "
                                f"tomaron {dias} de INGRESOS Y RETIROS."))
            elif por_fechas is not None and por_fechas != dias:
                nota.append(f"Nómina {dias} días; según ingreso/retiro "
                            f"{por_fechas}.")
                obs.append((nombre_mes, f["nombre"], f["cedula"],
                            f"Días distintos: nómina {dias}, fechas "
                            f"{por_fechas}. Se usaron los de la nómina."))
            if not dias:
                continue                # no trabajo ese mes
            t = usadas.get(f["cedula"])
            if t is None:
                sin_tarifa.setdefault(f["cedula"], f["nombre"])
                nota.append("Sin tarifa: asignar el cargo.")
                obs.append((nombre_mes, f["nombre"], f["cedula"],
                            "Sin tarifa ni cargo asignado: valor no "
                            "calculado."))
            elif t["origen"] == "cargo":
                nota.append(f"Tarifa del cargo «{t['cargo']}» (contrato).")
            horas = horas_mes(dias, config)
            tarifa = tarifa_aplicada(t["min"], t["max"], config["factor"]) \
                if t else None
            salida.append({"bu": f["bu"], "nombre": f["nombre"],
                           "cedula": f["cedula"], "dias": dias,
                           "horas": horas, "tarifa": tarifa,
                           "valor": round(horas * tarifa, 2) if t else None,
                           "nota": " ".join(nota)})
        meses.append({"mes": mes, "nombre": nombre_mes, "filas": salida,
                      "dias": sum(x["dias"] for x in salida),
                      "horas": sum(x["horas"] for x in salida),
                      "valor": round(sum(x["valor"] or 0 for x in salida), 2),
                      "sin_tarifa": sum(1 for x in salida
                                        if x["valor"] is None)})
    usadas = OrderedDict((c, t) for c, t in usadas.items()
                         if t["origen"] == "lista" or any(
                             x["cedula"] == c for m in meses
                             for x in m["filas"]))
    for c in usadas:
        if not usadas[c]["nombre"]:
            usadas[c]["nombre"] = next((x["nombre"] for m in meses
                                        for x in m["filas"]
                                        if x["cedula"] == c), "")
    return {"meses": meses, "observaciones": obs, "sin_tarifa": sin_tarifa,
            "tarifas": usadas, "config": config, "anio": costos["anio"],
            "totales": {"horas": sum(m["horas"] for m in meses),
                        "valor": round(sum(m["valor"] for m in meses), 2)}}


# ------------------------------------------------------------
# Excel con formulas vivas
# ------------------------------------------------------------
def nombre_archivo(resultado):
    meses = [m for m in resultado["meses"] if m["filas"]]
    rango = (f"{ABREV[MESES.index(meses[0]['mes'])]}-"
             f"{ABREV[MESES.index(meses[-1]['mes'])]}") if meses else ""
    bus = " ".join(resultado["config"]["bus"]).upper()
    return re.sub(r"\s+", " ", f"FACTURACION HORAS {bus} {rango} "
                  f"{resultado['anio']}.xlsx")


def excel_facturacion(resultado):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.workbook.defined_name import DefinedName
    from openpyxl.worksheet.datavalidation import DataValidation
    cfg = resultado["config"]
    neg = Font(bold=True)
    gris = PatternFill("solid", fgColor="FFD9D9D9")
    amarillo = PatternFill("solid", fgColor="FFFFFF99")
    naranja = PatternFill("solid", fgColor="FFFFCC99")
    azul = Font(color="FF0000FF", bold=True)
    usd = "#,##0.00"
    libro = Workbook()
    libro.remove(libro.active)

    # PARAMETROS
    p = libro.create_sheet("PARAMETROS")
    p["A1"] = ("PARÁMETROS DEL CÁLCULO (cambie las celdas azules y todo se "
               "recalcula)")
    p["A1"].font = Font(bold=True, size=12)
    filas = [("Factor de tarifa (0 = mínima, 1 = máxima, 0,5 = punto medio)",
              cfg["factor"], "FACTOR"),
             ("Horas por semana", cfg["horas_semana"], "HORAS_SEMANA"),
             ("Semanas por mes", cfg["semanas_mes"], "SEMANAS_MES"),
             ("Días laborales por semana (método SEMANAS DE 5 DÍAS)",
              cfg["dias_semana"], "DIAS_SEMANA"),
             ("Días del mes en la PILA (método PROPORCIÓN 30 DÍAS)",
              cfg["dias_mes"], "DIAS_MES"),
             ("Método de horas", METODOS[cfg["metodo"]], "METODO")]
    for i, (texto, valor, nombre) in enumerate(filas, start=3):
        p.cell(i, 1, texto)
        p.cell(i, 2, valor).font = azul
        p.cell(i, 2).fill = amarillo
        libro.defined_names[nombre] = DefinedName(
            nombre, attr_text=f"PARAMETROS!$B${i}")
    p.cell(9, 1, "Horas máximas al mes (horas por semana × semanas)").font = \
        neg
    p["B9"] = "=B4*B5"
    libro.defined_names["HORAS_MAX"] = DefinedName(
        "HORAS_MAX", attr_text="PARAMETROS!$B$9")
    for k, texto in enumerate((
            "Horas: hora completa (0,5 sube) con tope de las horas máximas.",
            "PROPORCIÓN 30 DÍAS: días pagados ÷ 30 × 168 (la PILA paga 30 "
            "días el mes completo). 9 días → 50 h; 18 días → 101 h.",
            "SEMANAS DE 5 DÍAS: días pagados ÷ 5 × 42. 9 días → 76 h; desde "
            "20 días → 168 h.",
            "Tarifa aplicada = mínima + factor × (máxima − mínima), USD por "
            "hora (hoja TARIFAS). Valor = horas × tarifa, a centavos por "
            "empleado.",
            "BU incluidas: " + ", ".join(cfg["bus"]) + "."), start=11):
        p.cell(k, 1, texto)
    v = DataValidation(type="decimal", operator="between", formula1="0",
                       formula2="1", showErrorMessage=True,
                       error="El factor va de 0 (mínima) a 1 (máxima).")
    p.add_data_validation(v)
    v.add("B3")
    v2 = DataValidation(type="list", formula1='"' + ",".join(
        METODOS.values()) + '"', showErrorMessage=True)
    p.add_data_validation(v2)
    v2.add("B8")
    p.column_dimensions["A"].width = 64
    p.column_dimensions["B"].width = 22

    # TARIFAS
    t = libro.create_sheet("TARIFAS")
    t.append(["Identificación", "Nombre", "Cargo", "Tarifa mínima USD/h",
              "Tarifa máxima USD/h", "Tarifa aplicada USD/h", "Origen"])
    for c in t[1]:
        c.font, c.fill = neg, gris
    pendientes = list(resultado["sin_tarifa"].items())
    for ced, d in list(resultado["tarifas"].items()) + [
            (c, {"nombre": n, "cargo": "", "min": None, "max": None,
                 "origen": "falta"}) for c, n in pendientes]:
        i = t.max_row + 1
        t.append([ced, d["nombre"], d["cargo"], d["min"], d["max"],
                  f'=IF(OR(D{i}="",E{i}=""),"",D{i}+FACTOR*(E{i}-D{i}))',
                  {"lista": "Resumen Tarifas",
                   "cargo": "Cargo del contrato (asignado)",
                   "falta": "SIN TARIFA: completar"}[d["origen"]]])
        t.cell(i, 1).number_format = "@"
        for col in (4, 5, 6):
            t.cell(i, col).number_format = usd
        if d["origen"] != "lista":
            for col in (4, 5):
                t.cell(i, col).fill = amarillo if d["origen"] == "falta" \
                    else PatternFill("solid", fgColor="FFDDEBF7")
    nt = t.max_row
    for col, ancho in zip("ABCDEFG", (15, 40, 40, 16, 16, 18, 30)):
        t.column_dimensions[col].width = ancho
    t.freeze_panes = "A2"

    # Meses
    resumen = []
    for m in resultado["meses"]:
        h = libro.create_sheet(m["nombre"].upper())
        h.append(["BU", "Nombre empleado", "Días pagados en el mes",
                  "Horas trabajadas mes", "Tarifa USD",
                  "Valor a facturar mes USD", "Identificación", "Observación"])
        for c in h[1]:
            c.font, c.fill = neg, gris
            c.alignment = Alignment(wrap_text=True, vertical="center")
        for x in m["filas"]:
            r = h.max_row + 1
            h.append([
                x["bu"], x["nombre"], x["dias"],
                f'=MIN(HORAS_MAX,ROUND(IF(METODO="{METODOS["semanas"]}",'
                f'C{r}/DIAS_SEMANA*HORAS_SEMANA,C{r}/DIAS_MES*HORAS_MAX),0))',
                f'=IFERROR(VLOOKUP(G{r},TARIFAS!$A$2:$F${nt},6,FALSE),"")',
                f'=IF(E{r}="","",ROUND(D{r}*E{r},2))', x["cedula"],
                x["nota"] or None])
            h.cell(r, 7).number_format = "@"
            h.cell(r, 5).number_format = usd
            h.cell(r, 6).number_format = usd
            if x["valor"] is None:
                for c in h[r][:6]:
                    c.fill = naranja
        u = h.max_row
        h.append(["TOTAL", "", f"=SUM(C2:C{u})", f"=SUM(D2:D{u})", "",
                  f"=SUM(F2:F{u})"])
        for c in h[h.max_row]:
            c.font = neg
        h.cell(h.max_row, 6).number_format = usd
        for col, ancho in zip("ABCDEFGH", (12, 40, 12, 12, 12, 18, 15, 50)):
            h.column_dimensions[col].width = ancho
        h.row_dimensions[1].height = 32
        h.freeze_panes = "A2"
        resumen.append((h.title, u + 1))

    # RESUMEN
    rs = libro.create_sheet("RESUMEN", 0)
    rs["A1"] = ("FACTURACIÓN POR HORAS BU " + ", ".join(cfg["bus"]).upper()
                + f" · {resultado['anio']}")
    rs["A1"].font = Font(bold=True, size=12)
    rs["A2"] = ('=CONCATENATE("Factor de tarifa: ",TEXT(FACTOR,"0.00"),'
                '" (0 = mínima, 1 = máxima) · método de horas: ",METODO,'
                '" · horas máximas al mes: ",HORAS_MAX)')
    rs.append([])
    rs.append(["Mes", "Empleados", "Días pagados", "Horas trabajadas",
               "Valor a facturar USD", "Empleados sin tarifa"])
    for c in rs[4]:
        c.font, c.fill = neg, gris
    for hoja, ft in resumen:
        i = rs.max_row + 1
        rs.append([hoja, f"=COUNTA('{hoja}'!B2:B{ft - 1})",
                   f"='{hoja}'!C{ft}", f"='{hoja}'!D{ft}",
                   f"='{hoja}'!F{ft}",
                   f"=COUNTIF('{hoja}'!E2:E{ft - 1},\"\")"])
        rs.cell(i, 5).number_format = usd
    fin = rs.max_row
    rs.append(["TOTAL", "", f"=SUM(C5:C{fin})", f"=SUM(D5:D{fin})",
               f"=SUM(E5:E{fin})"])
    for c in rs[rs.max_row]:
        c.font = neg
    rs.cell(rs.max_row, 5).number_format = usd
    for col, ancho in zip("ABCDEF", (14, 12, 14, 16, 22, 20)):
        rs.column_dimensions[col].width = ancho

    # OBSERVACIONES
    o = libro.create_sheet("OBSERVACIONES")
    o.append(["Mes", "Empleado", "Identificación", "Observación"])
    for c in o[1]:
        c.font, c.fill = neg, gris
    for x in resultado["observaciones"]:
        o.append(list(x))
    for col, ancho in zip("ABCD", (12, 40, 15, 100)):
        o.column_dimensions[col].width = ancho
    o.freeze_panes = "A2"
    orden = ["RESUMEN", "PARAMETROS", "TARIFAS"] + \
        [h for h, _ in resumen] + ["OBSERVACIONES"]
    libro._sheets = [libro[n] for n in orden]
    salida = io.BytesIO()
    libro.save(salida)
    return salida.getvalue()
