"""Pagos de nomina EMPRESA A: base de datos de nomina + planilla PDF + PDF de
vacaciones.

Contrato:
  leer_planilla_nomina_empresa_a -> netos (devengos - deducciones).
  leer_vacaciones_empresa_a -> VALOR TOTAL por liquidacion (sin repetir).
  leer_base_nomina_empresa_a -> filas del Excel y columnas a actualizar.
  cruzar_nomina_empresa_a(base, planillas, informes_vac) /
  alertas_nomina_empresa_a(cruce).
Misma REGLA que nomina/logica: nunca agregar ni borrar empleados.

Depende de: gmya.comun.texto, gmya.comun.numeros, gmya.modulos.nomina.logica
"""

import io
import re
from collections import Counter, OrderedDict

from gmya.comun.texto import comparable, _solo_digitos
from gmya.comun.numeros import formato_cop
from gmya.modulos.nomina.logica import similitud_nombres, UMBRAL_NOMBRE_NOMINA


# ------------------------------------------------------------
# Nomina EMPRESA A: "Base de datos nomina" (neto + vacaciones)
# ------------------------------------------------------------
# Llena en la base de datos de pagos de EMPRESA A (Excel con TIPO/NUMERO DE
# IDENTIFICACION, NOMBRE, APELLIDO, banco, cuenta, VALOR DEL PAGO O DE LA
# RECARGA, VACACIONES y TOTAL A PAGAR):
#   - VALOR DEL PAGO O DE LA RECARGA = NETO de la planilla de nomina (PDF
#     "Planilla de Nomina" del sistema de nomina).
#   - VACACIONES = VALOR TOTAL del informe de vacaciones (el general y/o
#     uno por empleado; se suman y se descartan liquidaciones repetidas).
# Mismas reglas que el formato del banco: cruce por cedula verificado con
# el nombre, solo se cambian esas dos columnas de filas existentes (edicion
# del XML: se conserva el formato del archivo) y se alerta quien falta en
# uno de los documentos.
_NUM_PLANILLA = r"\d{1,3}(?:,\d{3})*(?:\.\d*)?"


def _num_hib(texto):
    t = str(texto or "").strip().rstrip(".")
    return float(t.replace(",", "")) if t else 0.0


def _separar_dias_sueldo(token, otros_devengos, total):
    """'2601,234,567' -> (26, 1234567.0): los dias quedan pegados al
    sueldo en el PDF; se elige la division con la que cuadra el TOTAL."""
    opciones = []
    for corte in (2, 1):
        dias, resto = token[:corte], token[corte:]
        if not dias.isdigit() or not resto:
            continue
        if not re.fullmatch(_NUM_PLANILLA, resto):
            continue
        if len(resto) > 1 and resto[0] == "0" and not resto.startswith("0."):
            continue
        if int(dias) > 31:
            continue
        sueldo = _num_hib(resto)
        opciones.append((abs(sueldo + otros_devengos - total), int(dias),
                         sueldo))
    if not opciones:
        return None, _num_hib(token)
    _, dias, sueldo = min(opciones)
    return dias, sueldo


def leer_planilla_nomina_empresa_a(contenido, nombre_archivo=""):
    """
    'Planilla de Nomina' (Ingreso/Pagos): por empleado cedula, nombre
    (recortado), dias, devengos, deducciones y NETO. El PDF recorta los
    decimales de las columnas angostas (1,234,567.0 en vez de .04): el
    neto se recalcula como devengos - deducciones y se compara con el
    impreso.
    """
    import pdfplumber
    lineas = []
    with pdfplumber.open(io.BytesIO(contenido)) as pdf:
        for pagina in pdf.pages:
            lineas.extend((pagina.extract_text() or "").split("\n"))
    texto = "\n".join(lineas)
    if "PLANILLA DE NOMINA" not in comparable(texto):
        raise ValueError("No parece una «Planilla de Nómina» (falta el "
                         "título).")
    m = re.search(r"Del\s+(\d{2}/\d{2}/\d{4})\s+Al\s+(\d{2}/\d{2}/\d{4})",
                  texto, re.I)
    periodo = (m.group(1), m.group(2)) if m else None
    m = re.search(r"Fecha de Pago:\s*(\d{2}/\d{2}/\d{4})", texto, re.I)
    fecha_pago = m.group(1) if m else ""
    m = re.search(r"Nomina:\s*(\S+)|NOMINA\s+(\S+)\s+Periodo", texto, re.I)
    nomina = (m.group(1) or m.group(2)) if m else ""
    patron = re.compile(
        r"^(\d{1,4})\s+(\d{5,13})\s*([A-ZÑÁÉÍÓÚÜ][A-ZÑÁÉÍÓÚÜ .]*?)\s+(\d\S*)"
        r"((?:\s+" + _NUM_PLANILLA + r"){9})\s*$")
    empleados, avisos = [], []
    for linea in lineas:
        linea = linea.strip()
        mm = patron.match(linea)
        if not mm:
            continue
        resto = [_num_hib(t) for t in mm.group(5).split()]
        salario_in, componente, otros, total = resto[0:4]
        aporte_1, aporte_2, otras_ded, retencion, neto_impreso = resto[4:9]
        dias, sueldo = _separar_dias_sueldo(
            mm.group(4), salario_in + componente + otros, total)
        devengos = round(sueldo + salario_in + componente + otros, 2)
        neto = round(devengos - aporte_1 - aporte_2 - otras_ded - retencion,
                     2)
        if abs(neto - neto_impreso) >= 1:
            avisos.append(f"{mm.group(3).strip()} ({mm.group(2)}): el NETO "
                          f"impreso ({formato_cop(neto_impreso)}) no cuadra "
                          f"con devengos − deducciones ({formato_cop(neto)});"
                          " se usa el impreso.")
            neto = neto_impreso
        empleados.append({
            "n": int(mm.group(1)), "cedula": mm.group(2),
            "nombre": " ".join(mm.group(3).split()), "dias": dias,
            "devengos": devengos, "neto": neto})
    if not empleados:
        raise ValueError("No se encontraron empleados en la planilla de "
                         "nómina.")
    numeros = [e["n"] for e in empleados]
    faltan = sorted(set(range(1, max(numeros) + 1)) - set(numeros))
    if faltan:
        avisos.append("No se leyeron las filas " + ", ".join(
            str(n) for n in faltan[:10]) + " de la planilla de nómina.")
    return {"archivo": nombre_archivo, "periodo": periodo,
            "fecha_pago": fecha_pago, "nomina": nomina,
            "empleados": empleados,
            "total_neto": round(sum(e["neto"] for e in empleados), 2),
            "avisos": avisos}


def leer_vacaciones_empresa_a(contenido, nombre_archivo=""):
    """'Informe de Vacaciones' (general o de un empleado): por liquidacion,
    identificacion, nombre, numero de liquidacion y VALOR TOTAL (no el
    sueldo)."""
    import pdfplumber
    lineas = []
    with pdfplumber.open(io.BytesIO(contenido)) as pdf:
        for pagina in pdf.pages:
            lineas.extend((pagina.extract_text() or "").split("\n"))
    texto = "\n".join(lineas)
    if "VACACIONES" not in comparable(texto):
        raise ValueError("No parece un informe de vacaciones.")
    liquidaciones, actual = [], None
    for linea in lineas:
        m = re.search(r"IDENTIFICACION\s*:\s*(\d{5,13}).*?VALOR TOTAL\s+"
                      r"([\d.,]+)", linea, re.I)
        if m:
            actual = {"cedula": m.group(1), "valor": _num_hib(m.group(2)),
                      "nombre": "", "liquidacion": "", "inicio": "",
                      "fin": ""}
            liquidaciones.append(actual)
            continue
        if actual is None:
            continue
        m = re.search(r"^NOMBRE\s+(.+?)\s+DIAS ANTICIPO", linea, re.I)
        if m:
            actual["nombre"] = " ".join(m.group(1).split())
        m = re.search(r"^LIQUIDACION\s+(\d+).*?partir de\s*:?\s*"
                      r"(\d{2}/\d{2}/\d{4})", linea, re.I)
        if m:
            actual["liquidacion"] = m.group(1)
            actual["inicio"] = m.group(2)
        m = re.search(r"Termina en\s*:?\s*(\d{2}/\d{2}/\d{4})", linea, re.I)
        if m:
            actual["fin"] = m.group(1)
    if not liquidaciones:
        raise ValueError("No se encontraron liquidaciones de vacaciones.")
    m = re.search(r"TOTAL EMPLEADOS\s+(\d+)", texto, re.I)
    avisos = []
    if m and int(m.group(1)) != len(liquidaciones):
        avisos.append(f"El informe dice {m.group(1)} empleados y se leyeron "
                      f"{len(liquidaciones)} liquidaciones.")
    return {"archivo": nombre_archivo, "liquidaciones": liquidaciones,
            "total": round(sum(l["valor"] for l in liquidaciones), 2),
            "avisos": avisos}


def _revisar_sumas_base(contenido, nombre_hoja, mapa, empleados):
    """v6.7: las sumas (SUM/SUMA) de las columnas VALOR DEL PAGO, VACACIONES
    y TOTAL A PAGAR deben cubrir TODAS las filas de empleados. Si una deja
    filas por fuera (p. ej. =SUM(I3:I52) con empleados desde la fila 2) se
    avisa; el archivo no se modifica."""
    import re as _re
    from openpyxl import load_workbook
    from openpyxl.utils import get_column_letter
    import warnings
    if not empleados:
        return []
    primera = min(e["fila"] for e in empleados)
    ultima = max(e["fila"] for e in empleados)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        hoja = load_workbook(io.BytesIO(contenido))[nombre_hoja]
    avisos = []
    nombres = {"valor": "VALOR DEL PAGO", "vacaciones": "VACACIONES",
               "total": "TOTAL A PAGAR"}
    for clave, titulo in nombres.items():
        if clave not in mapa:
            continue
        letra = get_column_letter(mapa[clave])
        for r in range(ultima + 1, min(hoja.max_row, ultima + 15) + 1):
            formula = hoja.cell(r, mapa[clave]).value
            if not isinstance(formula, str) or not formula.startswith("="):
                continue
            for desde, hasta in _re.findall(
                    rf"SUMA?\(\$?{letra}\$?(\d+):\$?{letra}\$?(\d+)\)",
                    formula.upper()):
                desde, hasta = int(desde), int(hasta)
                if desde > primera or hasta < ultima:
                    avisos.append(
                        f"La suma de {titulo} en {letra}{r} ({formula}) no "
                        f"incluye todas las filas de empleados "
                        f"({letra}{primera}:{letra}{ultima}): el total del "
                        "Excel no cuadrará con la planilla. Corrige la "
                        "fórmula en el archivo (la plataforma no la cambia).")
    return avisos


def leer_base_nomina_empresa_a(contenido):
    """Base de datos de pagos de EMPRESA A: fila de titulos con NUMERO DE
    IDENTIFICACION, NOMBRE, APELLIDO, VALOR DEL PAGO... y VACACIONES."""
    from openpyxl import load_workbook
    from openpyxl.utils import get_column_letter
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        libro = load_workbook(io.BytesIO(contenido), data_only=True)
    for hoja in libro.worksheets:
        for fila in hoja.iter_rows(min_row=1, max_row=min(hoja.max_row, 30)):
            mapa = {}
            for celda in fila:
                t = comparable(celda.value).replace(" ", "") \
                    if celda.value else ""
                if t.startswith("NUMERODEIDENTIFICACION"):
                    mapa["cedula"] = celda.column
                elif t == "NOMBRE" or t == "NOMBRES":
                    mapa["nombre"] = celda.column
                elif t.startswith("APELLIDO"):
                    mapa["apellido"] = celda.column
                elif t.startswith("VALORDELPAGO"):
                    mapa["valor"] = celda.column
                elif t.startswith("VACACIONES"):
                    mapa["vacaciones"] = celda.column
                elif t.startswith("TOTALAPAGAR"):
                    mapa["total"] = celda.column
            if {"cedula", "nombre", "valor", "vacaciones"} <= set(mapa):
                empleados = []
                r = fila[0].row + 1
                while r <= hoja.max_row:
                    cedula = _solo_digitos(hoja.cell(r, mapa["cedula"]).value)
                    if not cedula:
                        break
                    nombre = " ".join(str(hoja.cell(r, mapa["nombre"]).value
                                          or "").split())
                    if "apellido" in mapa:
                        nombre = " ".join((nombre + " " + str(hoja.cell(
                            r, mapa["apellido"]).value or "")).split())
                    valor = hoja.cell(r, mapa["valor"]).value
                    vac = hoja.cell(r, mapa["vacaciones"]).value
                    empleados.append({
                        "fila": r, "cedula": cedula, "nombre": nombre,
                        "valor": valor if isinstance(valor, (int, float))
                        else None,
                        "vacaciones": vac if isinstance(vac, (int, float))
                        else None})
                    r += 1
                return {"hoja": hoja.title, "fila_titulos": fila[0].row,
                        "col_valor": get_column_letter(mapa["valor"]),
                        "col_vacaciones": get_column_letter(
                            mapa["vacaciones"]),
                        "empleados": empleados,
                        "avisos": _revisar_sumas_base(
                            contenido, hoja.title, mapa, empleados)}
    raise ValueError("No se encontró la tabla (columnas NUMERO DE "
                     "IDENTIFICACION, NOMBRE, VALOR DEL PAGO O DE LA RECARGA "
                     "y VACACIONES) en el Excel.")


def cruzar_nomina_empresa_a(base, planillas, informes_vac):
    """Neto por cedula (suma de planillas, sin repetir la misma fila de la
    misma nomina/periodo) y vacaciones por cedula (sin repetir la misma
    liquidacion) cruzados con las filas del Excel."""
    netos, vistos = OrderedDict(), set()
    for p in planillas:
        for e in p["empleados"]:
            clave = (p.get("periodo"), p.get("nomina"), e["cedula"],
                     e["neto"])
            if clave in vistos:
                continue
            vistos.add(clave)
            d = netos.setdefault(e["cedula"], {"nombre": e["nombre"],
                                               "neto": 0.0, "nombres": []})
            d["neto"] = round(d["neto"] + e["neto"], 2)
            if e["nombre"] not in d["nombres"]:
                d["nombres"].append(e["nombre"])
    vac, liq_vistas, repetidas = OrderedDict(), set(), 0
    for inf in informes_vac:
        for l in inf["liquidaciones"]:
            clave = (l["cedula"], l["liquidacion"] or l["inicio"], l["valor"])
            if clave in liq_vistas:
                repetidas += 1
                continue
            liq_vistas.add(clave)
            d = vac.setdefault(l["cedula"], {"nombre": l["nombre"],
                                             "valor": 0.0, "detalle": []})
            d["valor"] = round(d["valor"] + l["valor"], 2)
            d["detalle"].append(l)
    filas = []
    en_excel = set()
    conteo = Counter(x["cedula"] for x in base["empleados"])
    for x in base["empleados"]:
        en_excel.add(x["cedula"])
        n = netos.get(x["cedula"])
        v = vac.get(x["cedula"])
        nombres = (n["nombres"] if n else []) + \
            ([v["nombre"]] if v and v["nombre"] else [])
        sim = min((similitud_nombres(x["nombre"], nm) for nm in nombres),
                  default=None)
        if conteo[x["cedula"]] > 1:
            estado = "repetido"
        elif not n:
            estado = "sin_planilla"
        elif sim is not None and sim < UMBRAL_NOMBRE_NOMINA:
            estado = "nombre"
        else:
            estado = "ok"
        filas.append(dict(
            x, neto=n["neto"] if n else None,
            vac_nueva=v["valor"] if v else 0.0,
            vac_detalle=v["detalle"] if v else [],
            nombre_planilla=" / ".join(nombres), similitud=sim,
            estado=estado))
    solo_planilla = [dict(cedula=c, **d) for c, d in netos.items()
                     if c not in en_excel]
    solo_vacaciones = [dict(cedula=c, **d) for c, d in vac.items()
                       if c not in en_excel]
    vac_sin_nomina = [f for f in filas if f["vac_nueva"] and
                      f["estado"] == "sin_planilla"]
    return {"filas": filas, "solo_planilla": solo_planilla,
            "solo_vacaciones": solo_vacaciones,
            "vac_sin_nomina": vac_sin_nomina,
            "liquidaciones_repetidas": repetidas,
            "total_neto": round(sum(d["neto"] for d in netos.values()), 2),
            "total_vacaciones": round(sum(d["valor"] for d in vac.values()),
                                      2)}


def alertas_nomina_empresa_a(cruce):
    alertas = []
    for d in cruce["solo_planilla"]:
        alertas.append(f"{d['nombre']} (C.C. {d['cedula']}) está en la "
                       f"planilla de nómina PDF (neto {formato_cop(d['neto'])})"
                       " pero NO está en el Excel: no se agrega; si se le "
                       "debe pagar, inclúyelo en la base con sus datos "
                       "bancarios.")
    for d in cruce["solo_vacaciones"]:
        alertas.append(f"{d['nombre']} (C.C. {d['cedula']}) tiene vacaciones "
                       f"por {formato_cop(d['valor'])} en el PDF de "
                       "vacaciones pero NO está en el Excel: no se agrega.")
    for f in cruce["filas"]:
        if f["estado"] == "sin_planilla":
            alertas.append(f"{f['nombre']} (C.C. {f['cedula']}, fila "
                           f"{f['fila']}) está en el Excel pero NO está en "
                           "la planilla de nómina PDF: su valor del pago no "
                           "se cambia (hoy "
                           f"{formato_cop(f['valor'] or 0)}); revisa si debe "
                           "salir del archivo.")
        elif f["estado"] == "nombre":
            alertas.append(f"Fila {f['fila']}: la cédula {f['cedula']} "
                           f"coincide pero el nombre no: Excel «{f['nombre']}»"
                           f", PDF «{f['nombre_planilla']}». No se actualiza "
                           "hasta que lo confirmes en la revisión.")
        elif f["estado"] == "repetido":
            alertas.append(f"La cédula {f['cedula']} ({f['nombre']}) está "
                           "repetida en el Excel: no se actualiza.")
    return alertas
