"""Pagos de nomina con formato del banco (NATURE · FORMATOPAB).

Contrato:
  leer_planilla_nomina(contenido, nombre) -> empleados (cedula, nombre,
      valor) y total de la planilla PDF.
  leer_formato_pagos(contenido) -> filas del Excel del banco.
  cruzar_nomina(formato, planillas) -> por fila: valor nuevo (suma de todas
      las planillas), estado y similitud del nombre.
  actualizar_valores_xlsx(contenido, hoja, columna, valores, otras=None)
      -> (bytes, n): cambia SOLO las celdas indicadas a nivel XML, conserva
      formato y fuerza recalculo de formulas al abrir.
  codigo_descripcion_nomina / fecha_aplicacion_numero -> "NOM2DAQOCT",
      AAAAMMDD.
REGLA: en el Excel nunca se agregan ni se borran empleados; solo se
actualiza el valor de filas existentes. Si sobra o falta alguien, solo se
alerta (alertas_nomina).

Depende de: gmya.comun.texto, gmya.comun.numeros
"""

import datetime
import html
import io
import re
import unicodedata
import zipfile
from collections import Counter, OrderedDict

from gmya.comun.texto import comparable, _solo_digitos
from gmya.comun.numeros import formato_cop


# ============================================================
# PAGOS DE NOMINA (planillas PDF -> formato de pagos del banco)
# ============================================================
# Actualiza la columna "ValorTransaccion" del formato de pagos masivos del
# banco (FORMATOPAB, conversor de pagos) con lo que dicen las planillas de
# pago en PDF (nomina, prima, vacaciones u otros conceptos). Reglas:
#   - Cada empleado se ubica en el Excel por CEDULA y se verifica con el
#     NOMBRE (el Excel trae nombres recortados o con errores de digitacion).
#   - Si un empleado sale en varias planillas, se suman sus valores.
#   - Del Excel solo cambia el valor a pagar de filas existentes: nunca se
#     agregan ni se borran empleados ni se toca otra celda. El archivo se
#     edita directamente en su XML para conservar validaciones, listas,
#     formatos y hojas tal como vienen del banco.
#   - Quien esta en una planilla y no en el Excel, o en el Excel y no en
#     ninguna planilla, se avisa con nombre y cedula.
def _texto_nombre(texto):
    """Nombre comparable: mayusculas sin tildes, solo letras."""
    t = unicodedata.normalize("NFKD", str(texto or "").upper())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^A-Z ]", " ", t).split())


def similitud_nombres(nombre_excel, nombre_planilla):
    """0..1. Tolera nombres recortados (el formato del banco limita el
    largo), espacios de mas o de menos y letras cambiadas."""
    from difflib import SequenceMatcher
    a = _texto_nombre(nombre_excel).replace(" ", "")
    b = _texto_nombre(nombre_planilla).replace(" ", "")
    if not a or not b:
        return 0.0
    if b.startswith(a) or a.startswith(b):
        return 1.0
    completo = SequenceMatcher(None, a, b).ratio()
    recortado = SequenceMatcher(None, a, b[:len(a) + 2]).ratio()
    return round(max(completo, recortado), 3)


UMBRAL_NOMBRE_NOMINA = 0.75


def _valor_planilla(texto):
    """'1,654,800.50' -> 1654800.5 (tambien '1.654.800,50')."""
    t = str(texto).strip().replace("$", "")
    if re.fullmatch(r"[\d.]+,\d{1,2}", t):
        t = t.replace(".", "").replace(",", ".")
    else:
        t = t.replace(",", "")
    return float(t)


def leer_planilla_nomina(contenido, nombre_archivo=""):
    """
    Planilla de pago en PDF (p. ej. 'Consignacion Periodo del ... al ...'):
    una fila por empleado con #, nombre, identificacion, valor, codigo de
    banco, banco y cuenta. Devuelve {empresa, concepto, empleados, total}.
    """
    import pdfplumber
    lineas = []
    with pdfplumber.open(io.BytesIO(contenido)) as pdf:
        for pagina in pdf.pages:
            lineas.extend((pagina.extract_text() or "").split("\n"))
    patron = re.compile(
        r"^\s*(\d{1,4})\s+(.+?)\s+(\d{5,13})\s+"
        r"(\d{1,3}(?:[.,]\d{3})*[.,]\d{2})\s+(\d{2,4})\s+(.*?)\s*"
        r"([\d-]{4,25})?\s*$")
    empleados, total, avisos = [], None, []
    empresa, concepto = "", ""
    for i, linea in enumerate(lineas):
        linea = linea.strip()
        if not linea:
            continue
        if not empresa and i < 3 and not re.match(r"^\d", linea):
            empresa = linea
        if not concepto and re.search(r"per[ií]odo|prima|vacaciones|"
                                      r"liquidaci|consignaci", linea, re.I):
            concepto = re.sub(r"\s*P[áa]gina\s+\d+.*$", "", linea).strip()
        m_total = re.match(r"^TOTAL\s+([\d.,]+)$", linea, re.I)
        if m_total:
            total = _valor_planilla(m_total.group(1))
            continue
        m = patron.match(linea)
        if not m:
            continue
        empleados.append({
            "n": int(m.group(1)), "nombre": " ".join(m.group(2).split()),
            "cedula": m.group(3), "valor": _valor_planilla(m.group(4)),
            "codigo_banco": m.group(5), "banco": m.group(6).strip(),
            "cuenta": (m.group(7) or "").strip(),
        })
    if not empleados:
        raise ValueError("No se encontraron empleados en la planilla (se "
                         "esperan filas con nombre, identificación y valor).")
    suma = round(sum(e["valor"] for e in empleados), 2)
    if total is not None and abs(suma - total) > 0.01:
        avisos.append(f"La suma de las filas ({formato_cop(suma)}) no "
                      f"coincide con el TOTAL de la planilla "
                      f"({formato_cop(total)}): puede faltar alguna fila.")
    numeros = [e["n"] for e in empleados]
    faltan = sorted(set(range(1, max(numeros) + 1)) - set(numeros))
    if faltan:
        avisos.append("No se leyeron las filas " + ", ".join(
            str(n) for n in faltan[:10]) + " de la planilla.")
    return {"archivo": nombre_archivo, "empresa": empresa,
            "concepto": concepto or nombre_archivo, "empleados": empleados,
            "total": total if total is not None else suma, "suma": suma,
            "avisos": avisos}


def leer_formato_pagos(contenido):
    """
    Formato de pagos del banco (.xlsx). Busca la fila de titulos con
    'Nit Beneficiario', 'Nombre Beneficiario' y 'ValorTransaccion' y
    devuelve las filas de empleados (hasta la primera sin identificacion).
    """
    from openpyxl import load_workbook
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        libro = load_workbook(io.BytesIO(contenido), data_only=True)
    for hoja in libro.worksheets:
        titulos = None
        for fila in hoja.iter_rows(min_row=1, max_row=min(hoja.max_row, 40)):
            mapa = {}
            for celda in fila:
                t = comparable(celda.value) if celda.value else ""
                t = t.replace(" ", "")
                if t.startswith("NITBENEFICIARIO") or \
                        t.startswith("DOCUMENTOBENEFICIARIO"):
                    mapa.setdefault("cedula", celda.column)
                elif t.startswith("NOMBREBENEFICIARIO"):
                    mapa["nombre"] = celda.column
                elif t.startswith("VALORTRANSACCI"):
                    mapa["valor"] = celda.column
                elif t.startswith("NOCUENTABENEFICIARIO") or \
                        t.startswith("NUMEROCUENTABENEFICIARIO"):
                    mapa["cuenta"] = celda.column
                elif t.startswith("FECHADEAPLICACI"):
                    mapa["fecha"] = celda.column
            if {"cedula", "nombre", "valor"} <= set(mapa):
                titulos = (fila[0].row, mapa)
                break
        if not titulos:
            continue
        fila_titulos, mapa = titulos
        empleados = []
        r = fila_titulos + 1
        while r <= hoja.max_row:
            cedula = hoja.cell(r, mapa["cedula"]).value
            if cedula in (None, ""):
                break
            valor = hoja.cell(r, mapa["valor"]).value
            empleados.append({
                "fila": r, "cedula": _solo_digitos(cedula),
                "nombre": str(hoja.cell(r, mapa["nombre"]).value or "")
                .strip(),
                "valor": float(valor) if isinstance(valor, (int, float))
                else None,
                "cuenta": str(hoja.cell(r, mapa["cuenta"]).value or "")
                .strip() if "cuenta" in mapa else "",
            })
            r += 1
        from openpyxl.utils import get_column_letter
        # Encabezado del lote: celda debajo de "DESCRIPCION DEL PAGO".
        descripcion = None
        for fila in hoja.iter_rows(min_row=1, max_row=fila_titulos):
            for celda in fila:
                t = comparable(celda.value).replace(" ", "") \
                    if celda.value else ""
                if t.startswith("DESCRIPCIONDELPAGO"):
                    abajo = hoja.cell(celda.row + 1, celda.column)
                    descripcion = {"celda": abajo.coordinate,
                                   "valor": str(abajo.value or "")}
        fecha_actual = None
        if "fecha" in mapa:
            for e in empleados:
                e["fecha"] = hoja.cell(e["fila"], mapa["fecha"]).value
            fecha_actual = next((e["fecha"] for e in empleados
                                 if e.get("fecha")), None)
        return {"hoja": hoja.title, "fila_titulos": fila_titulos,
                "columna_valor": get_column_letter(mapa["valor"]),
                "columna_fecha": (get_column_letter(mapa["fecha"])
                                  if "fecha" in mapa else None),
                "fecha_actual": fecha_actual, "descripcion": descripcion,
                "empleados": empleados}
    raise ValueError("No se encontró la tabla de beneficiarios (columnas "
                     "'Nit Beneficiario', 'Nombre Beneficiario' y "
                     "'ValorTransaccion') en el Excel.")


MESES_NOMINA = ["ENE", "FEB", "MAR", "ABR", "MAY", "JUN", "JUL", "AGO",
                "SEP", "OCT", "NOV", "DIC"]
MESES_NOMINA_NOMBRE = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
                       "Julio", "Agosto", "Septiembre", "Octubre",
                       "Noviembre", "Diciembre"]


def codigo_descripcion_nomina(quincena, mes):
    """'DESCRIPCION DEL PAGO' del formato: NOM + 1ERAQ/2DAQ + mes.
    (2, 10) -> 'NOM2DAQOCT'; (1, 11) -> 'NOM1ERAQNOV'."""
    return "NOM" + ("1ERAQ" if int(quincena) == 1 else "2DAQ") + \
        MESES_NOMINA[int(mes) - 1]


def periodo_de_planillas(planillas):
    """(inicio, fin) del periodo que dicen las planillas ('Periodo del
    16/10/2026 al 30/10/2026'), o None."""
    for p in planillas:
        fechas = re.findall(r"(\d{1,2})/(\d{1,2})/(\d{4})", p["concepto"])
        if len(fechas) >= 2:
            try:
                return tuple(datetime.date(int(a), int(m), int(d))
                             for d, m, a in fechas[:2])
            except ValueError:
                continue
    return None


def fecha_aplicacion_numero(fecha):
    """date -> 20261030 (formato de la columna 'Fecha de aplicacion')."""
    return int(fecha.strftime("%Y%m%d"))


def cruzar_nomina(formato, planillas):
    """
    Une las planillas por cedula (sumando conceptos) y las cruza con las
    filas del Excel. Devuelve {"filas": [...], "solo_planilla": [...]}.
    Cada fila del Excel: estado 'ok' (cedula y nombre coinciden),
    'nombre' (cedula igual, nombre distinto: revisar), 'sin_planilla'.
    """
    por_cedula = OrderedDict()
    for p in planillas:
        for e in p["empleados"]:
            d = por_cedula.setdefault(e["cedula"], {
                "cedula": e["cedula"], "nombre": e["nombre"], "valor": 0.0,
                "detalle": [], "cuentas": set(), "nombres": []})
            if e["nombre"] not in d["nombres"]:
                d["nombres"].append(e["nombre"])
            d["valor"] = round(d["valor"] + e["valor"], 2)
            d["detalle"].append((p["concepto"], e["valor"]))
            if e.get("cuenta"):
                d["cuentas"].add(e["cuenta"])
    filas, usados = [], set()
    for x in formato["empleados"]:
        d = por_cedula.get(x["cedula"])
        fila = dict(x, valor_nuevo=None, nombre_planilla="", detalle=[],
                    similitud=None, estado="sin_planilla", nota="")
        if d:
            usados.add(x["cedula"])
            # Con varias planillas, el nombre debe coincidir en todas.
            sim = min(similitud_nombres(x["nombre"], n) for n in d["nombres"])
            fila.update(valor_nuevo=d["valor"],
                        nombre_planilla=" / ".join(d["nombres"]),
                        detalle=d["detalle"], similitud=sim,
                        estado="ok" if sim >= UMBRAL_NOMBRE_NOMINA
                        else "nombre")
            cx = x.get("cuenta", "").lstrip("0")
            # La planilla puede recortar la cuenta (no cabe en la columna):
            # se acepta si una empieza por la otra.
            if cx and d["cuentas"] and not any(
                    c.lstrip("0") and (cx.startswith(c.lstrip("0")) or
                                       c.lstrip("0").startswith(cx))
                    for c in d["cuentas"]):
                fila["nota"] = (f"Cuenta distinta: planilla "
                                f"{', '.join(sorted(d['cuentas']))}, Excel "
                                f"{x['cuenta']} (no se modifica).")
        filas.append(fila)
    # Repetidos en el Excel (misma cedula en dos filas): se avisa.
    conteo = Counter(x["cedula"] for x in formato["empleados"])
    for f in filas:
        if conteo[f["cedula"]] > 1:
            f["estado"] = "repetido"
    solo_planilla = []
    for cedula, d in por_cedula.items():
        if cedula in usados:
            continue
        # ¿Esta en el Excel con otra cedula (mismo nombre)?
        parecido = max(formato["empleados"], key=lambda x: similitud_nombres(
            x["nombre"], d["nombre"]), default=None)
        sim = similitud_nombres(parecido["nombre"], d["nombre"]) \
            if parecido else 0
        solo_planilla.append(dict(
            d, parecido=parecido if sim >= 0.9 else None))
    return {"filas": filas, "solo_planilla": solo_planilla}


def alertas_nomina(cruce):
    """Lista de (texto, grave) para mostrar antes de generar."""
    alertas = []
    for d in cruce["solo_planilla"]:
        texto = (f"{d['nombre']} (C.C. {d['cedula']}) está en la planilla "
                 f"PDF por {formato_cop(d['valor'])} pero NO está en el "
                 "Excel: no se agrega; si debe pagarse, inclúyelo en el "
                 "formato del banco.")
        if d.get("parecido"):
            texto += (f" En el Excel hay un nombre parecido con otra cédula: "
                      f"{d['parecido']['nombre']} (C.C. "
                      f"{d['parecido']['cedula']}, fila "
                      f"{d['parecido']['fila']}).")
        alertas.append((texto, True))
    for f in cruce["filas"]:
        if f["estado"] == "sin_planilla":
            alertas.append((f"{f['nombre']} (C.C. {f['cedula']}, fila "
                            f"{f['fila']}) está en el Excel pero NO está en "
                            "ninguna planilla PDF: no se borra y conserva su "
                            f"valor actual ({formato_cop(f['valor'] or 0)}); "
                            "revisa si debe salir del formato o quedar en "
                            "cero.", True))
        elif f["estado"] == "nombre":
            alertas.append((f"Fila {f['fila']}: la cédula {f['cedula']} "
                            f"coincide pero el nombre no: Excel "
                            f"«{f['nombre']}», planilla "
                            f"«{f['nombre_planilla']}». No se actualiza "
                            "hasta que lo confirmes en la revisión.", True))
        elif f["estado"] == "repetido":
            alertas.append((f"La cédula {f['cedula']} ({f['nombre']}) está "
                            "repetida en el Excel: no se actualiza.", True))
    return alertas


def _celda_xml_valor(xml_celda, ref, valor):
    """Reescribe una celda <c> (numero o texto) conservando su estilo."""
    estilo = re.search(r'\ss="(\d+)"', xml_celda)
    s = f' s="{estilo.group(1)}"' if estilo else ""
    if isinstance(valor, str):
        return (f'<c r="{ref}"{s} t="inlineStr"><is><t>'
                f'{html.escape(valor, quote=False)}</t></is></c>')
    numero = repr(round(float(valor), 2))
    if numero.endswith(".0"):
        numero = numero[:-2]
    return f'<c r="{ref}"{s}><v>{numero}</v></c>'


def _col_a_numero(letras):
    n = 0
    for ch in letras:
        n = n * 26 + ord(ch) - 64
    return n


def actualizar_valores_xlsx(contenido, hoja, columna, valores, otras=None):
    """
    Cambia SOLO las celdas {fila: valor} de la columna indicada en la hoja
    (y las celdas sueltas de 'otras' = {"G2": "NOM2DAQOCT"}),
    editando el XML del .xlsx (el resto del archivo queda byte a byte
    igual). Marca el libro para recalcular formulas al abrir.
    """
    entrada = zipfile.ZipFile(io.BytesIO(contenido))
    libro = entrada.read("xl/workbook.xml").decode("utf-8")
    rels = entrada.read("xl/_rels/workbook.xml.rels").decode("utf-8")
    m = re.search(r'<sheet\b[^>]*name="' + re.escape(html.escape(hoja))
                  + r'"[^>]*r:id="([^"]+)"', libro)
    if not m:
        raise ValueError(f"No se encontró la hoja «{hoja}» en el Excel.")
    m_rel = re.search(r'<Relationship\b[^>]*Id="' + re.escape(m.group(1))
                      + r'"[^>]*Target="([^"]+)"', rels) or re.search(
        r'<Relationship\b[^>]*Target="([^"]+)"[^>]*Id="'
        + re.escape(m.group(1)) + '"', rels)
    destino = m_rel.group(1).lstrip("/")
    ruta_hoja = destino if destino.startswith("xl/") else "xl/" + destino
    xml = entrada.read(ruta_hoja).decode("utf-8")
    cambiadas = 0
    trabajos = [(columna, fila, valor) for fila, valor in
                sorted(valores.items())]
    for ref_otra, valor in (otras or {}).items():
        m_ref = re.match(r"^([A-Z]+)(\d+)$", ref_otra)
        trabajos.append((m_ref.group(1), int(m_ref.group(2)), valor))
    for columna, fila, valor in trabajos:
        ref = f"{columna}{fila}"
        patron = re.compile(r'<c r="' + ref + r'"(?:\s[^>]*?)?(?:/>|>.*?</c>)',
                            re.S)
        m_c = patron.search(xml)
        if m_c:
            xml = xml[:m_c.start()] + _celda_xml_valor(m_c.group(0), ref,
                                                       valor) \
                + xml[m_c.end():]
            cambiadas += 1
            continue
        # La celda no existe: se inserta en su fila en el orden de columnas.
        m_f = re.search(r'(<row r="' + str(fila) + r'"[^>]*?)(/>|>(.*?)</row>)',
                        xml, re.S)
        if not m_f:
            raise ValueError(f"No existe la fila {fila} en la hoja «{hoja}».")
        nueva = _celda_xml_valor("", ref, valor)
        if m_f.group(2) == "/>":
            reemplazo = m_f.group(1) + ">" + nueva + "</row>"
        else:
            celdas = m_f.group(3)
            pos = len(celdas)
            for m_x in re.finditer(r'<c r="([A-Z]+)\d+"', celdas):
                if _col_a_numero(m_x.group(1)) > _col_a_numero(columna):
                    pos = m_x.start()
                    break
            reemplazo = m_f.group(1) + ">" + celdas[:pos] + nueva + \
                celdas[pos:] + "</row>"
        xml = xml[:m_f.start()] + reemplazo + xml[m_f.end():]
        cambiadas += 1
    # Formulas de la hoja (p. ej. =SUM de la columna): se quita el valor
    # guardado para que Excel las recalcule al abrir con los nuevos valores.
    xml = re.sub(r'(<c\b[^>]*>)(<f\b[^>]*(?:/>|>.*?</f>))<v>[^<]*</v>',
                 r'\1\2', xml, flags=re.S)
    if "<calcPr" in libro:
        if "fullCalcOnLoad" not in libro:
            libro = libro.replace("<calcPr", '<calcPr fullCalcOnLoad="1"', 1)
    else:
        libro = libro.replace("</workbook>",
                              '<calcPr fullCalcOnLoad="1"/></workbook>')
    salida = io.BytesIO()
    with zipfile.ZipFile(salida, "w") as nuevo:
        for item in entrada.infolist():
            datos = entrada.read(item.filename)
            if item.filename == ruta_hoja:
                datos = xml.encode("utf-8")
            elif item.filename == "xl/workbook.xml":
                datos = libro.encode("utf-8")
            nuevo.writestr(item, datos, compress_type=item.compress_type)
    return salida.getvalue(), cambiadas
