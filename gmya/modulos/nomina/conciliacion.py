"""Conciliacion de nomina: acumulado de HELISA vs liquidacion vs contabilidad.

Contrato:
  leer_acumulado_nomina(contenido) -> {empleados, conceptos_sin_mapa,
      fechas_pago, liquidaciones}: lo PAGADO por empleado y concepto segun
      el "Acumulado de nomina" de HELISA (descuentos en positivo).
  leer_liquidacion_nomina(contenido) -> {empleados, columnas}: el Excel de
      liquidacion / nomina electronica de la firma (una fila por empleado,
      una columna por concepto, con TOTAL DEVENGOS / NETO A PAGAR).
  leer_balance_nomina(contenido) -> {empleados, cuentas, sin_concepto}: los
      DEBITOS - CREDITOS del mes por empleado y concepto del balance de
      prueba de HELISA (cuentas 51 y 61/72: gasto y costo de nomina).
  conciliar_nomina(acumulado, liquidacion=None, balance=None) -> filas por
      empleado y concepto, resumen por concepto, netos y alertas.
  excel_conciliacion_nomina(resultado, ctx) -> bytes (.xlsx).
REGLAS: tolerancia 0 (al centavo). No se asume nada: lo que no cruza se
marca. Las PRESTACIONES (cesantias, intereses, prima, vacaciones) se
comparan aparte: en la liquidacion y en la contabilidad son la PROVISION
del mes; en el acumulado de HELISA son lo PAGADO (p. ej. una liquidacion
definitiva). El archivo de nomina nunca se modifica.

Depende de: gmya.comun.texto, gmya.comun.numeros, gmya.comun.grilla
"""

import datetime
import io
import re
from collections import OrderedDict, defaultdict

from gmya.comun.texto import comparable
from gmya.comun.numeros import formato_cop, numero
from gmya.comun.grilla import leer_grilla


# ------------------------------------------------------------
# Conceptos y como se reconocen en cada documento (por nombre)
# ------------------------------------------------------------
# (clave, nombre, grupo, patrones, excluir)
#   grupo: "devengo" (se paga y es gasto), "prestacion" (provision vs
#   pago), "descuento" (se descuenta al empleado).
CONCEPTOS_NOMINA = [
    ("sueldo", "Sueldo", "devengo",
     ["SALARIO X PAGAR", "SALARIO A PAGAR", "SUELDO", "SALARIO"],
     ["BASE", "BASICO", "INTEGRAL", "AUMENTO"]),
    ("aux_transporte", "Auxilio de transporte", "devengo",
     ["AUX. TRANSP", "AUX TRANSP", "AUXILIO DE TRANSPORTE"], []),
    ("aux_conectividad", "Auxilio de conectividad", "devengo",
     ["CONECTIVIDAD"], []),
    ("horas_extras", "Horas extras y recargos", "devengo",
     ["VALOR HORAS EXTRA", "HORAS EXTRA", "RECARGO"], ["CANTIDAD"]),
    ("no_salarial", "Componente no salarial", "devengo",
     ["COMPONENTE NO SALARIAL"], []),
    ("incapacidad", "Incapacidades", "devengo",
     ["VALOR INCAPACIDAD", "INCAPACIDAD", "ENFERMEDAD GENERAL"],
     ["DIAS"]),
    ("licencia", "Licencias y permisos remunerados", "devengo",
     ["VALOR LICENCIA REMUNERADA", "LICENCIAS Y/O PERMISOS REMUNERADOS",
      "LICENCIA REMUNERADA", "PERMISOS REMUNERADOS", "INACTIVIDAD"],
     ["DIAS", "NO REMUNERADA"]),
    ("indemnizacion", "Indemnizaciones", "devengo",
     ["INDEMNIZACION"], []),
    ("dotacion", "Dotación", "devengo", ["DOTACION"], []),
    ("intereses", "Intereses sobre cesantías", "prestacion",
     ["INT. CESANTIAS", "INTERESES DE CESANTIAS",
      "INTERESES SOBRE CESANTIAS"], []),
    ("cesantias", "Cesantías", "prestacion", ["CESANTIAS"],
     ["INT", "INTERES"]),
    ("prima", "Prima de servicios", "prestacion", ["PRIMA"], []),
    ("vacaciones", "Vacaciones", "prestacion", ["VACACIONES"], []),
    ("salud", "Aporte salud", "descuento", ["APORTE SALUD", "SALUD"],
     ["BASE"]),
    ("pension", "Aporte pensión", "descuento",
     ["APORTE PENSION", "PENSION"], ["BASE", "VOLUNTARIA"]),
    ("retencion", "Retención en la fuente", "descuento",
     ["RETENCION EN LA FUENTE", "RETEFUENTE"], []),
    ("otros_descuentos", "Otros descuentos", "descuento",
     ["DESCUENTOS", "DESCUENTO"], ["TOTAL"]),
]
NOMBRE_CONCEPTO = {c[0]: c[1] for c in CONCEPTOS_NOMINA}
GRUPO_CONCEPTO = {c[0]: c[2] for c in CONCEPTOS_NOMINA}
GRUPOS = OrderedDict([("devengo", "Pagos al empleado (devengos)"),
                      ("prestacion", "Prestaciones sociales"),
                      ("descuento", "Descuentos")])


def concepto_de(texto, grupos=None):
    """Clave del concepto para un nombre de concepto, columna o cuenta."""
    t = comparable(texto)
    if not t:
        return None
    for clave, _, grupo, patrones, excluir in CONCEPTOS_NOMINA:
        if grupos and grupo not in grupos:
            continue
        if any(comparable(x) in t for x in excluir):
            continue
        if any(comparable(p) in t for p in patrones):
            return clave
    return None


def _cedula(valor):
    if isinstance(valor, float) and valor.is_integer():
        valor = int(valor)
    digitos = re.sub(r"\D", "", str(valor or ""))
    return digitos.lstrip("0")


def _valores(fila):
    if isinstance(fila, dict):
        celdas = fila.get("celdas") or []
        if not celdas:
            return []
        salida = [None] * max(c["col"] for c in celdas)
        for c in celdas:
            salida[c["col"] - 1] = c["valor"]
        return salida
    return list(fila)


def _filas(contenido):
    resultado = leer_grilla(contenido)
    filas = resultado[0] if isinstance(resultado, tuple) else resultado
    return [_valores(f) for f in filas]


def _texto(v):
    return "" if v is None else str(v).strip()


# ------------------------------------------------------------
# Lectura
# ------------------------------------------------------------
def leer_acumulado_nomina(contenido):
    """Acumulado de nomina de HELISA (una fila por empleado, concepto y
    centro de costo; ValorPago negativo en los descuentos)."""
    filas = _filas(contenido)
    titulo = None
    for i, fila in enumerate(filas[:15]):
        t = [comparable(_texto(v)) for v in fila]
        if "IDENTIFICACION" in t and "CONCEPTO" in t:
            titulo = i
            break
    if titulo is None:
        raise ValueError("No parece el Acumulado de nómina de HELISA (no se "
                         "encontraron las columnas IDENTIFICACION y "
                         "CONCEPTO).")
    cab = [comparable(_texto(v)) for v in filas[titulo]]

    def col(*nombres):
        for n in nombres:
            if comparable(n) in cab:
                return cab.index(comparable(n))
        return None
    c_id, c_con = col("IDENTIFICACION"), col("CONCEPTO")
    c_nom = col("NOMBRE COMPLETO", "NOMBRE")
    c_val = col("VALORPAGO", "VALOR PAGO", "VALOR")
    c_nat = col("NATURALEZA")
    c_liq = col("TIPO DE LIQUIDACION")
    c_fec = col("FECHA DE PAGO")
    if c_val is None:
        raise ValueError("El acumulado no tiene la columna ValorPago.")
    empleados = OrderedDict()
    sin_mapa = defaultdict(float)
    fechas, liquidaciones = set(), defaultdict(set)
    for fila in filas[titulo + 1:]:
        def v(i):
            return fila[i] if i is not None and i < len(fila) else None
        ced = _cedula(v(c_id))
        if not ced:
            continue
        concepto = _texto(v(c_con))
        valor = round(float(numero(v(c_val)) or 0), 2)
        naturaleza = comparable(_texto(v(c_nat)))
        es_desc = naturaleza.startswith("DESC") or valor < 0
        grupos = ("descuento",) if es_desc else ("devengo", "prestacion")
        clave = concepto_de(concepto, grupos)
        emp = empleados.setdefault(ced, {"cedula": ced,
                                         "nombre": _texto(v(c_nom)),
                                         "valores": defaultdict(float),
                                         "detalle": defaultdict(float)})
        if clave is None:
            clave = "otros_descuentos" if es_desc else None
        if clave is None:
            sin_mapa[concepto] += abs(valor)
            emp["detalle"][f"(sin concepto) {concepto}"] += abs(valor)
            continue
        emp["valores"][clave] += abs(valor)
        emp["detalle"][concepto] += abs(valor)
        f = v(c_fec)
        if hasattr(f, "date"):
            f = f.date()
        if f:
            fechas.add(f)
        if comparable(_texto(v(c_liq))).startswith("DEFINITIVA"):
            liquidaciones[ced].add(f)
    for emp in empleados.values():
        emp["valores"] = {k: round(x, 2) for k, x in emp["valores"].items()}
        emp["definitiva"] = emp["cedula"] in liquidaciones
    if not empleados:
        raise ValueError("El acumulado de nómina no trae empleados.")
    return {"empleados": empleados, "conceptos_sin_mapa": dict(sin_mapa),
            "fechas_pago": sorted(f for f in fechas
                                  if isinstance(f, datetime.date)),
            "liquidaciones": {k: sorted(x for x in v if x)
                              for k, v in liquidaciones.items()}}


def leer_liquidacion_nomina(contenido):
    """Excel de liquidacion / nomina electronica: fila de titulos con
    CEDULA y NOMBRE (los titulos pueden ocupar dos filas), una fila por
    empleado y una fila TOTAL."""
    filas = _filas(contenido)
    titulo = None
    for i, fila in enumerate(filas[:25]):
        t = [comparable(_texto(v)) for v in fila]
        if any(x in ("CEDULA", "IDENTIFICACION", "DOCUMENTO") for x in t) \
                and any(x.startswith("NOMBRE") for x in t):
            titulo = i
            break
    if titulo is None:
        raise ValueError("No se encontró la fila de títulos (CEDULA, NOMBRE) "
                         "en la liquidación de nómina.")
    ancho = max(len(f) for f in filas[max(0, titulo - 1):titulo + 1])
    nombres = []
    for j in range(ancho):
        partes = []
        for f in filas[max(0, titulo - 1):titulo + 1]:
            v = f[j] if j < len(f) else None
            if isinstance(v, str) and v.strip():
                partes.append(v.strip())
        nombres.append(" ".join(partes))
    cab = [comparable(n) for n in nombres]
    c_ced = next(j for j, t in enumerate(cab)
                 if t.endswith(("CEDULA", "IDENTIFICACION", "DOCUMENTO")))
    c_nom = next(j for j, t in enumerate(cab) if t.startswith("NOMBRE")
                 or t.endswith("NOMBRE"))
    columnas = {}
    especiales = {}
    for j, t in enumerate(cab):
        if j in (c_ced, c_nom) or not t:
            continue
        if "TOTAL DEVENGO" in t:
            especiales["devengos"] = j
        elif "TOTAL DESCUENTO" in t:
            especiales["descuentos"] = j
        elif "NETO" in t:
            especiales["neto"] = j
    # Cada concepto toma la columna de su patron mas especifico (el primero
    # de la lista que aparezca), p. ej. SALARIO X PAGAR antes que SALARIO.
    libres = [j for j, t in enumerate(cab)
              if t and j not in (c_ced, c_nom) and j not in
              especiales.values()]
    for clave, _, _, patrones, excluir in CONCEPTOS_NOMINA:
        for patron in patrones:
            j = next((j for j in libres if comparable(patron) in cab[j]
                      and not any(comparable(x) in cab[j] for x in excluir)
                      and concepto_de(cab[j]) == clave), None)
            if j is not None:
                columnas[clave] = j
                libres.remove(j)
                break
    empleados = OrderedDict()
    for fila in filas[titulo + 1:]:
        ced = _cedula(fila[c_ced] if c_ced < len(fila) else None)
        if not ced or len(ced) < 5:
            continue
        def v(j):
            x = fila[j] if j is not None and j < len(fila) else None
            return round(float(x), 2) if isinstance(x, (int, float)) else 0.0
        empleados[ced] = {
            "cedula": ced, "nombre": _texto(fila[c_nom]) if c_nom < len(fila)
            else "",
            "valores": {k: v(j) for k, j in columnas.items() if v(j)},
            "devengos": v(especiales.get("devengos")),
            "descuentos": v(especiales.get("descuentos")),
            "neto": v(especiales.get("neto")),
            "basura": [_texto(x) for j, x in enumerate(fila)
                       if isinstance(x, str) and j not in (c_ced, c_nom)
                       and not re.search(r"\d", x) and len(x.strip()) <= 3
                       and x.strip() and x.strip().upper() != "OK"],
        }
    if not empleados:
        raise ValueError("La liquidación de nómina no trae empleados.")
    return {"empleados": empleados,
            "columnas": {k: nombres[j] for k, j in columnas.items()},
            "tiene_neto": "neto" in especiales}


RE_CUENTA = re.compile(r"^\s*(\d{4,10})\s+(.+?)\s*$")
RE_TERCERO = re.compile(r"\(Id\.\s*([\d.\-]+)\)", re.I)


RE_NUM_PDF = re.compile(r"-?[\d,]+\.\d{2}")


def _filas_pdf_balance(contenido):
    """Balance de prueba en PDF: cada linea de texto -> [texto, 4 valores]
    (saldo inicial, debitos, creditos, nuevo saldo)."""
    import pdfplumber
    filas = []
    with pdfplumber.open(io.BytesIO(contenido)) as pdf:
        for pagina in pdf.pages:
            for linea in (pagina.extract_text() or "").splitlines():
                nums = RE_NUM_PDF.findall(linea)
                if len(nums) < 4:
                    filas.append([linea.strip()])
                    continue
                texto = linea
                for n in nums[-4:]:
                    texto = texto.replace(n, "", 1)
                filas.append([texto.strip()] + [
                    float(n.replace(",", "")) for n in nums[-4:]])
    return filas


def leer_balance_nomina(contenido):
    """Balance de prueba de HELISA con terceros: por cada cuenta, las filas
    'nombre (Id. cedula)' con saldo inicial, debitos, creditos y saldo.
    Se toma el movimiento del mes (debitos - creditos) de las cuentas de
    gasto y costo de nomina (51, 52, 61, 72) cuyo nombre es un concepto."""
    filas = _filas_pdf_balance(contenido) if contenido[:4] == b"%PDF" \
        else _filas(contenido)
    cuenta = nombre_cuenta = None
    empleados = defaultdict(lambda: defaultdict(float))
    nombres = {}
    cuentas = defaultdict(float)
    sin_concepto = defaultdict(float)
    empresa = ""
    for fila in filas:
        textos = [(j, v) for j, v in enumerate(fila) if v not in (None, "")]
        if not textos:
            continue
        primero = _texto(textos[0][1])
        if not empresa and re.search(r"S\.?A\.?S|LTDA", primero.upper()):
            empresa = primero
        m = RE_CUENTA.match(primero)
        numeros = [v for _, v in textos if isinstance(v, (int, float))]
        if m and len(numeros) >= 4:
            cuenta, nombre_cuenta = m.group(1), m.group(2)
            continue
        t = RE_TERCERO.search(primero)
        if t and cuenta and len(numeros) >= 4:
            ced = _cedula(t.group(1))
            mov = round(float(numeros[-3]) - float(numeros[-2]), 2)
            nombres.setdefault(ced, RE_TERCERO.sub("", primero).strip())
            if not cuenta.startswith(("51", "52", "61", "72")):
                continue
            clave = concepto_de(nombre_cuenta, ("devengo", "prestacion"))
            if clave is None:
                sin_concepto[f"{cuenta} {nombre_cuenta}"] += mov
                continue
            empleados[ced][clave] += mov
            cuentas[(clave, cuenta, nombre_cuenta)] += mov
    if not cuentas and not sin_concepto:
        raise ValueError("No se encontraron cuentas de nómina (51/61) con "
                         "terceros en el balance de prueba.")
    return {"empresa": empresa,
            "empleados": {c: {k: round(x, 2) for k, x in v.items()}
                          for c, v in empleados.items()},
            "nombres": nombres,
            "cuentas": {k: round(v, 2) for k, v in cuentas.items()},
            "sin_concepto": {k: round(v, 2) for k, v in sin_concepto.items()
                             if v}}


# ------------------------------------------------------------
# Conciliacion
# ------------------------------------------------------------
def _estado(valores):
    """valores: los que existen (None = documento no cargado)."""
    presentes = [v for v in valores if v is not None]
    if len(presentes) < 2:
        return "SOLO UNO"
    base = presentes[0]
    difs = [abs(v - base) for v in presentes[1:]]
    if all(d < 0.005 for d in difs):
        return "CUADRA"
    if all(d < 1 for d in difs):
        return "DIFERENCIA DE CENTAVOS"
    return "NO CUADRA"


def conciliar_nomina(acumulado, liquidacion=None, balance=None):
    acu = acumulado["empleados"]
    liq = (liquidacion or {}).get("empleados") or {}
    bal = (balance or {}).get("empleados") or {}
    cedulas = list(acu)
    for c in list(liq) + list(bal):
        if c not in cedulas and (c in liq or any(
                abs(x) > 0.005 for x in bal.get(c, {}).values())):
            cedulas.append(c)
    nombres = {}
    for c in cedulas:
        nombres[c] = (acu.get(c, {}).get("nombre") or
                      liq.get(c, {}).get("nombre") or
                      (balance or {}).get("nombres", {}).get(c, "")).strip()
    filas, alertas = [], []
    for c in cedulas:
        a = acu.get(c, {}).get("valores", {}) if c in acu else None
        l_ = liq.get(c, {}).get("valores", {}) if c in liq else None
        b = bal.get(c, {}) if c in bal else None
        conceptos = set(a or {}) | set(l_ or {}) | set(b or {})
        for clave in [k for k, *_ in CONCEPTOS_NOMINA if k in conceptos]:
            grupo = GRUPO_CONCEPTO[clave]
            va = None if a is None else round(a.get(clave, 0.0), 2)
            vl = None if l_ is None or liquidacion is None else \
                round(l_.get(clave, 0.0), 2)
            vb = None if balance is None or grupo == "descuento" else \
                round((b or {}).get(clave, 0.0), 2)
            if grupo == "prestacion":
                # Provision (liquidacion y contabilidad) vs pagado (HELISA).
                estado = _estado([vl, vb])
            else:
                estado = _estado([va, vl, vb])
            if not any(x for x in (va, vl, vb)):
                continue
            filas.append({"cedula": c, "nombre": nombres[c],
                          "concepto": clave,
                          "nombre_concepto": NOMBRE_CONCEPTO[clave],
                          "grupo": grupo, "acumulado": va,
                          "liquidacion": vl, "contabilidad": vb,
                          "estado": estado})
        if c not in acu:
            alertas.append(f"{nombres[c]} ({c}) está en la liquidación o en "
                           "la contabilidad pero no en el acumulado de "
                           "nómina de HELISA.")
        elif liquidacion is not None and c not in liq:
            alertas.append(f"{nombres[c]} ({c}) está en el acumulado de "
                           "HELISA pero no en la liquidación de nómina.")
    # Netos: lo realmente pagado (HELISA) vs el NETO A PAGAR del Excel.
    netos = []
    for c in cedulas:
        if c not in acu:
            continue
        v = acu[c]["valores"]
        pagado = round(sum(x for k, x in v.items()
                           if GRUPO_CONCEPTO[k] != "descuento")
                       - sum(x for k, x in v.items()
                             if GRUPO_CONCEPTO[k] == "descuento"), 2)
        neto_liq = liq.get(c, {}).get("neto") if c in liq else None
        prov = round(sum(x for k, x in (liq.get(c, {}).get("valores") or {}
                                        ).items()
                         if GRUPO_CONCEPTO[k] == "prestacion"), 2) \
            if c in liq else None
        pag_prest = round(sum(x for k, x in v.items()
                              if GRUPO_CONCEPTO[k] == "prestacion"), 2)
        explicacion = ""
        if neto_liq is not None and liquidacion and liquidacion.get(
                "tiene_neto"):
            dif = round(neto_liq - pagado, 2)
            esperado = round((prov or 0) - pag_prest, 2)
            if abs(dif) < 0.005:
                explicacion = "Coincide."
            elif abs(dif - esperado) < 1:
                explicacion = (
                    "La diferencia es la provisión de prestaciones del mes "
                    f"({formato_cop(prov or 0)}) que el Excel suma al neto"
                    + (f", menos las prestaciones pagadas en HELISA "
                       f"({formato_cop(pag_prest)})" if pag_prest else "")
                    + ": el NETO A PAGAR del Excel no es lo que se transfiere"
                    + (f" (centavos: {formato_cop(dif - esperado)})"
                       if abs(dif - esperado) >= 0.005 else "") + ".")
            else:
                explicacion = "No se explica: revisar."
        netos.append({"cedula": c, "nombre": nombres[c], "pagado": pagado,
                      "neto_liquidacion": neto_liq, "provision": prov,
                      "prestaciones_pagadas": pag_prest,
                      "definitiva": acu[c].get("definitiva", False),
                      "explicacion": explicacion})
        if acu[c].get("definitiva"):
            alertas.append(
                f"{nombres[c]} ({c}) tiene liquidación DEFINITIVA en HELISA "
                f"(prestaciones pagadas {formato_cop(pag_prest)}). En la "
                "liquidación de nómina solo aparece la provisión del mes: "
                "confirmar qué se reporta en la nómina electrónica.")
    for c in cedulas:
        basura = liq.get(c, {}).get("basura") if c in liq else None
        if basura:
            alertas.append(f"{nombres[c]} ({c}): la liquidación tiene "
                           f"texto extraño en una celda de valores "
                           f"({', '.join(repr(x) for x in basura)}).")
    if acumulado.get("conceptos_sin_mapa"):
        alertas.append("Conceptos del acumulado que no se reconocen (no se "
                       "concilian): " + ", ".join(
                           f"{k} ({formato_cop(v)})" for k, v in
                           acumulado["conceptos_sin_mapa"].items()) + ".")
    if balance and balance.get("sin_concepto"):
        alertas.append("Cuentas de nómina del balance que no se reconocen "
                       "como concepto: " + ", ".join(
                           f"{k} ({formato_cop(v)})" for k, v in
                           balance["sin_concepto"].items()) + ".")
    # Resumen por concepto.
    resumen = OrderedDict()
    for f in filas:
        r = resumen.setdefault(f["concepto"], {
            "concepto": f["concepto"], "nombre": f["nombre_concepto"],
            "grupo": f["grupo"], "acumulado": 0.0, "liquidacion": 0.0,
            "contabilidad": 0.0})
        for k in ("acumulado", "liquidacion", "contabilidad"):
            r[k] = round(r[k] + (f[k] or 0), 2)
    for r in resumen.values():
        tiene_l = liquidacion is not None
        tiene_b = balance is not None and r["grupo"] != "descuento"
        if r["grupo"] == "prestacion":
            r["estado"] = _estado([r["liquidacion"] if tiene_l else None,
                                   r["contabilidad"] if tiene_b else None])
        else:
            r["estado"] = _estado([r["acumulado"],
                                   r["liquidacion"] if tiene_l else None,
                                   r["contabilidad"] if tiene_b else None])
    malas = [f for f in filas if f["estado"] in ("NO CUADRA",
                                                 "DIFERENCIA DE CENTAVOS")]
    for f in malas:
        alertas.append(
            f"{f['nombre']} · {f['nombre_concepto']}: "
            + " / ".join(f"{e} {formato_cop(f[k])}" for e, k in (
                ("HELISA", "acumulado"), ("liquidación", "liquidacion"),
                ("contabilidad", "contabilidad"))
                if f[k] is not None and not (
                    f["grupo"] == "prestacion" and k == "acumulado"))
            + (" (diferencia de centavos: HELISA redondea al peso)"
               if f["estado"] == "DIFERENCIA DE CENTAVOS" else ""))
    orden = [k for k, *_ in CONCEPTOS_NOMINA]
    return {"filas": filas,
            "resumen": sorted(resumen.values(),
                              key=lambda r: orden.index(r["concepto"])),
            "netos": netos, "alertas": alertas,
            "tiene_liquidacion": liquidacion is not None,
            "tiene_balance": balance is not None,
            "cuadra": not malas}


# ------------------------------------------------------------
# Excel
# ------------------------------------------------------------
def excel_conciliacion_nomina(resultado, ctx=None):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter
    ctx = ctx or {}
    libro = Workbook()
    fino = Side(style="thin", color="000000")
    borde = Border(left=fino, right=fino, top=fino, bottom=fino)
    gris = PatternFill("solid", fgColor="C0C0C0")
    verde = PatternFill("solid", fgColor="C6EFCE")
    amarillo = PatternFill("solid", fgColor="FFEB9C")
    rojo = PatternFill("solid", fgColor="FFC7CE")
    pesos = '_-$* #,##0.00_-;"-$"* #,##0.00_-;_-$* "-"??_-;_-@_-'
    color_estado = {"CUADRA": verde, "DIFERENCIA DE CENTAVOS": amarillo,
                    "NO CUADRA": rojo}

    def encabezado(ws, titulos, fila):
        for j, t in enumerate(titulos, start=1):
            c = ws.cell(fila, j, t)
            c.font = Font(bold=True)
            c.fill = gris
            c.border = borde
            c.alignment = Alignment(horizontal="center", vertical="center",
                                    wrap_text=True)

    def titulo(ws, texto):
        ws.cell(1, 1, ctx.get("empresa") or "").font = Font(bold=True,
                                                            size=14)
        ws.cell(2, 1, texto).font = Font(bold=True, size=12)
        ws.cell(3, 1, ctx.get("periodo") or "")

    # Hoja RESUMEN
    ws = libro.active
    ws.title = "RESUMEN"
    titulo(ws, "CONCILIACIÓN DE NÓMINA · HELISA vs LIQUIDACIÓN vs "
               "CONTABILIDAD")
    fila = 5
    encabezado(ws, ["GRUPO", "CONCEPTO", "ACUMULADO HELISA (PAGADO)",
                    "LIQUIDACIÓN (EXCEL)", "CONTABILIDAD (BALANCE)",
                    "DIF. LIQUIDACIÓN − HELISA",
                    "DIF. CONTABILIDAD − LIQUIDACIÓN", "ESTADO"], fila)
    for r in resultado["resumen"]:
        fila += 1
        valores = [GRUPOS[r["grupo"]], r["nombre"], r["acumulado"],
                   r["liquidacion"] if resultado["tiene_liquidacion"]
                   else None,
                   r["contabilidad"] if resultado["tiene_balance"] and
                   r["grupo"] != "descuento" else None]
        for j, v in enumerate(valores, start=1):
            c = ws.cell(fila, j, v)
            c.border = borde
            if j >= 3:
                c.number_format = pesos
        ws.cell(fila, 6, f"=IF(D{fila}=\"\",\"\",ROUND(D{fila}-C{fila},2))"
                if r["grupo"] != "prestacion" else "PROVISIÓN vs PAGO")
        ws.cell(fila, 7, f"=IF(OR(D{fila}=\"\",E{fila}=\"\"),\"\","
                         f"ROUND(E{fila}-D{fila},2))")
        for j in (6, 7):
            ws.cell(fila, j).border = borde
            ws.cell(fila, j).number_format = pesos
        c = ws.cell(fila, 8, r["estado"])
        c.border = borde
        c.fill = color_estado.get(r["estado"], PatternFill())
    fila += 2
    ws.cell(fila, 1, "Prestaciones: en la liquidación y en la contabilidad "
                     "son la PROVISIÓN del mes; en el acumulado de HELISA es "
                     "lo PAGADO (liquidaciones definitivas). Se comparan "
                     "liquidación vs contabilidad.").font = Font(italic=True)
    for letra, ancho in zip("ABCDEFGH", (28, 34, 22, 22, 22, 22, 24, 24)):
        ws.column_dimensions[letra].width = ancho

    # Hoja POR EMPLEADO
    ws = libro.create_sheet("POR EMPLEADO")
    titulo(ws, "DETALLE POR EMPLEADO Y CONCEPTO")
    fila = 5
    encabezado(ws, ["CÉDULA", "EMPLEADO", "GRUPO", "CONCEPTO",
                    "ACUMULADO HELISA", "LIQUIDACIÓN", "CONTABILIDAD",
                    "ESTADO"], fila)
    for f in resultado["filas"]:
        fila += 1
        for j, v in enumerate([f["cedula"], f["nombre"], GRUPOS[f["grupo"]],
                               f["nombre_concepto"], f["acumulado"],
                               f["liquidacion"], f["contabilidad"],
                               f["estado"]], start=1):
            c = ws.cell(fila, j, v)
            c.border = borde
            if 5 <= j <= 7:
                c.number_format = pesos
        ws.cell(fila, 8).fill = color_estado.get(f["estado"], PatternFill())
    ws.auto_filter.ref = f"A5:H{fila}"
    ws.freeze_panes = "A6"
    for letra, ancho in zip("ABCDEFGH", (14, 34, 26, 30, 18, 18, 18, 24)):
        ws.column_dimensions[letra].width = ancho

    # Hoja NETOS
    ws = libro.create_sheet("NETOS")
    titulo(ws, "NETO PAGADO (HELISA) vs NETO A PAGAR (LIQUIDACIÓN)")
    fila = 5
    encabezado(ws, ["CÉDULA", "EMPLEADO", "NETO PAGADO SEGÚN HELISA",
                    "NETO A PAGAR EXCEL", "DIFERENCIA",
                    "PROVISIÓN EN EL EXCEL", "PRESTACIONES PAGADAS HELISA",
                    "EXPLICACIÓN"], fila)
    for n in resultado["netos"]:
        fila += 1
        for j, v in enumerate([n["cedula"], n["nombre"], n["pagado"],
                               n["neto_liquidacion"], None, n["provision"],
                               n["prestaciones_pagadas"], n["explicacion"]],
                              start=1):
            c = ws.cell(fila, j, v)
            c.border = borde
            if 3 <= j <= 7:
                c.number_format = pesos
        ws.cell(fila, 5, f"=IF(D{fila}=\"\",\"\",ROUND(D{fila}-C{fila},2))")
        ws.cell(fila, 8).alignment = Alignment(wrap_text=True)
    if resultado["netos"]:
        fila += 1
        ws.cell(fila, 2, "TOTAL").font = Font(bold=True)
        for j in (3, 4, 5, 6, 7):
            letra = get_column_letter(j)
            c = ws.cell(fila, j, f"=SUM({letra}6:{letra}{fila - 1})")
            c.font = Font(bold=True)
            c.number_format = pesos
    for letra, ancho in zip("ABCDEFGH", (14, 34, 20, 20, 16, 20, 22, 70)):
        ws.column_dimensions[letra].width = ancho

    # Hoja ALERTAS
    ws = libro.create_sheet("ALERTAS")
    titulo(ws, "ALERTAS DE REVISIÓN")
    for i, a in enumerate(resultado["alertas"] or
                          ["Sin alertas: todo cuadra."], start=5):
        c = ws.cell(i, 1, a)
        c.alignment = Alignment(wrap_text=True, vertical="top")
    ws.column_dimensions["A"].width = 140
    salida = io.BytesIO()
    libro.save(salida)
    return salida.getvalue()
