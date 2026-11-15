"""Lectura para la programacion de pagos (sin Streamlit).

Contrato:
  EMPRESAS_PROG_PAGOS -> empresas implementadas y su formato.
  leer_programacion_helisa(contenido) / leer_conceptos_helisa(contenido)
  leer_prog_anterior(contenido, nombre_archivo="") -> programacion de la semana
      anterior (se lee solo como referencia).
REGLA CONFIDENCIAL: hay filas que solo existen en la programacion anterior
y que el equipo pasa a mano; la plataforma NUNCA las resalta, marca ni
menciona en lo que genera.

Depende de: gmya.comun.texto, gmya.comun.numeros, gmya.comun.grilla, gmya.modulos.busqueda.logica
"""

import calendar
import datetime
import io
import re
from collections import OrderedDict

from gmya.comun.texto import alfanumerico, comparable, solo_nit
from gmya.comun.numeros import numero
from gmya.comun.grilla import _convertir_xls_libreoffice, leer_grilla
from gmya.modulos.busqueda.logica import listar_empresas


# ============================================================
# PROGRAMACION DE PAGOS (por empresa)
# ============================================================
# Arma la programacion de pagos ACTUAL de una empresa a partir de:
#   1. "programacion HELISA" (cuentas por pagar con saldo, tal como sale de
#      HELISA),
#   2. "conceptos HELISA" (texto capturado de cada documento),
#   3. la PROG. PAGOS ANTERIOR (la ultima que hizo la empresa).
# De la anterior se toman los textos ya revisados, las observaciones, el
# calendario de pagos (que se corre una fecha), los pagos fijos y las
# partidas que siguen pendientes aunque HELISA no las muestre con saldo.
# El libro anterior solo se lee; las hojas auxiliares (proyeccion de cobros,
# cosecha, contratistas...) se copian tal cual al libro nuevo. La hoja
# principal se arma desde cero con un formato uniforme: no se copia ningun
# color ni marca de filas del libro anterior.
MESES_PP = ["ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO", "JULIO",
            "AGOSTO", "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE"]
# Abreviaturas que se ven en las programaciones (1RA QNA DE OCTBRE...).
ABREV_MESES_PP = {"SETIEMBRE": 9, "SEPTBRE": 9, "OCTBRE": 10, "NOVBRE": 11,
                  "DICBRE": 12, "SEPT": 9}

# Empresas con la programacion implementada. La clave "claves" sirve para
# reconocer la carpeta de la empresa en 001. EMPRESAS ACTIVAS.
EMPRESAS_PROG_PAGOS = OrderedDict([
    ("NATURE", {
        "nombre": "NATURE GROWN AVOCADO FARMS SAS",
        "claves": ["NATURE GROWN", "NATURE"],
        "hoja": "PROG PAGOS CAMPO",
        "titulo_gastos": "PRESUPUESTO DE GASTOS CAMPO",
        "dia_pago": 4,                  # viernes
        "cuentas_recurrentes": ("233525",),   # honorarios mensuales
        "formato": "flujo",
    }),
    ("MEDFAM", {
        "nombre": "MEDFAM HEALTH CENTER S.A.S.",
        "claves": ["MEDFAM"],
        "formato": "cxp",              # cuentas por pagar con observaciones
    }),
    # v6.10: CAFETO SOFTWARE. Cuentas por pagar (con secciones manuales de
    # seguridad social, impuestos, pagos fijos y anticipos) y cuentas por
    # cobrar (cartera), las dos con el motor de MEDFAM.
    ("CAFETO", {
        "nombre": "CAFETO SOFTWARE S.A.S",
        "claves": ["CAFETO"],
        "formato": "cxp",
        "variantes": OrderedDict([
            ("pagar", {
                "etiqueta": "Cuentas por pagar",
                "prefijo": "CUENTAS POR PAGAR",
                "hoja": "CUENTA POR PAGAR AL {fecha:%d-%m-%Y}",
                "total": "TOTAL CUENTAS POR PAGAR AL {fecha:%d/%m/%Y}",
                "marcar_vencidas": True,
                "vencidas": {"FC": "FACTURA VENCIDA"},
                # Documentos de nomina y planilla: CAFETO los resume en
                # SEGURIDAD SOCIAL / PAGOS FIJOS, no en el listado.
                "tipos_fuera": {
                    t: ("Documento de nómina / planilla de seguridad social "
                        f"({t}): en CAFETO va resumido en SEGURIDAD SOCIAL o "
                        "PAGOS FIJOS, no en el listado de proveedores.")
                    for t in ("NMP", "LP", "LC")},
                "terceros_fuera": (
                    r"PENSION|PROMOTORA DE SALUD|\bEPS\b|SANITAS|"
                    r"CAJA DE COMPENSACION|COMPENSAR|COMFA|RIESGOS LABORALES|"
                    r"BIENESTAR FAMILIAR|APRENDIZAJE",
                    "Entidad de seguridad social: en CAFETO va resumida en "
                    "SEGURIDAD SOCIAL, no en el listado de proveedores."),
            }),
            ("cobrar", {
                "etiqueta": "Cuentas por cobrar",
                "prefijo": "CUENTAS POR COBRAR",
                "hoja": "CTAS POR COBRAR AL {fecha:%d-%m-%Y}",
                "total": "TOTAL CUENTAS POR COBRAR {fecha:%d-%m-%Y}",
                # En la cartera de CAFETO la marca de vencida es manual.
                "marcar_vencidas": False,
                "vencidas": {"FV": "FACTURA VENCIDA",
                             "FE": "FACTURA VENCIDA"},
            }),
        ]),
    }),
])

# Si aun no se configuro la carpeta de empresas (modulo Busqueda de
# archivos) se muestran al menos estas.
EMPRESAS_REFERENCIA = ["NATURE GROWN AVOCADO FARMS SAS",
                       "MEDFAM HEALTH CENTER S.A.S.", "CAFETO SOFTWARE S.A.S",
                       "EL VAQUERO"]

FORMATO_PESOS_PP = '_-* #,##0.00_-;\\-* #,##0.00_-;_-* "-"??_-;_-@_-'


def empresa_implementada(nombre):
    """Clave de EMPRESAS_PROG_PAGOS que corresponde al nombre, o None."""
    claro = comparable(nombre)
    for clave, datos in EMPRESAS_PROG_PAGOS.items():
        for palabra in datos["claves"]:
            if comparable(palabra) in claro:
                return clave
    return None


def empresas_para_selector(carpeta_empresas=""):
    """
    [(nombre, clave_implementada o None)] con todas las empresas del
    sistema: las subcarpetas de 001. EMPRESAS ACTIVAS (si esta configurada)
    o la lista de referencia. Siempre incluye las implementadas.
    """
    nombres = []
    if carpeta_empresas:
        try:
            nombres = [n for n, _ in listar_empresas(carpeta_empresas)]
        except Exception:
            nombres = []
    if not nombres:
        nombres = list(EMPRESAS_REFERENCIA)
    salida, vistas = [], set()
    for nombre in nombres:
        limpio = re.sub(r"^\s*\d+[\s.\-_]+", "", nombre).strip() or nombre
        clave = empresa_implementada(limpio)
        llave = clave or comparable(limpio)
        if llave in vistas:
            continue
        vistas.add(llave)
        salida.append((limpio, clave))
    for clave, datos in EMPRESAS_PROG_PAGOS.items():
        if clave not in vistas:
            salida.append((datos["nombre"], clave))
    salida.sort(key=lambda x: comparable(x[0]))
    return salida


# ------------------------------------------------------------
# Utilidades de fechas, meses y numeros
# ------------------------------------------------------------

def fecha_celda_pp(valor):
    """Fecha de una celda: date/datetime, serial de Excel o texto."""
    if isinstance(valor, datetime.datetime):
        return valor.date()
    if isinstance(valor, datetime.date):
        return valor
    if isinstance(valor, (int, float)) and 20000 < valor < 80000:
        return (datetime.date(1899, 12, 30)
                + datetime.timedelta(days=int(valor)))
    texto = str(valor or "").strip()
    for formato in ("%d/%m/%Y", "%Y/%m/%d", "%Y-%m-%d", "%d-%m-%Y",
                    "%d/%m/%y"):
        try:
            return datetime.datetime.strptime(texto[:10], formato).date()
        except ValueError:
            continue
    return None


def sumar_mes(fecha, meses=1):
    mes = fecha.month - 1 + meses
    anio = fecha.year + mes // 12
    mes = mes % 12 + 1
    dia = min(fecha.day, calendar.monthrange(anio, mes)[1])
    return datetime.date(anio, mes, dia)


def _mes_de_palabra(palabra):
    """Numero de mes si la palabra es un mes (admite errores de digitacion
    como SEPPTIEMBRE y abreviaturas como OCTBRE)."""
    import difflib
    p = comparable(palabra)
    if p in MESES_PP:
        return MESES_PP.index(p) + 1
    if p in ABREV_MESES_PP:
        return ABREV_MESES_PP[p]
    if len(p) >= 6:
        cercano = difflib.get_close_matches(p, MESES_PP, n=1, cutoff=0.86)
        if cercano:
            return MESES_PP.index(cercano[0]) + 1
    return None


RE_PALABRA_PP = re.compile(r"[A-ZÁÉÍÓÚÑ]+", re.IGNORECASE)


def correr_meses_texto(texto, meses=1):
    """'NOMINA 1RA QNA DE OCTBRE 2026' -> 'NOMINA 1RA QNA DE NOVIEMBRE 2026'.
    Si un mes pasa de DICIEMBRE a ENERO, el año que lo sigue sube."""
    texto = str(texto or "")
    partes, ultimo, salto_anio = [], 0, False
    for m in RE_PALABRA_PP.finditer(texto):
        mes = _mes_de_palabra(m.group(0))
        if not mes:
            continue
        nuevo = (mes - 1 + meses) % 12 + 1
        if mes - 1 + meses >= 12:
            salto_anio = True
        partes.append(texto[ultimo:m.start()])
        partes.append(MESES_PP[nuevo - 1])
        ultimo = m.end()
    partes.append(texto[ultimo:])
    nuevo = "".join(partes)
    if salto_anio:
        nuevo = re.sub(r"\b(20\d\d)\b", lambda x: str(int(x.group(1)) + 1),
                       nuevo)
    return nuevo


def tiene_mes(texto):
    return any(_mes_de_palabra(m.group(0))
               for m in RE_PALABRA_PP.finditer(str(texto or "")))


def fechas_pago_sugeridas(fecha, dia_pago=4, minimo=2):
    """Dias de pago (viernes por defecto) desde la fecha hasta fin de mes;
    si quedan menos de 'minimo', se completan con los del mes siguiente."""
    dia = fecha + datetime.timedelta(days=(dia_pago - fecha.weekday()) % 7)
    fechas = []
    while dia.month == fecha.month or len(fechas) < minimo:
        fechas.append(dia)
        dia += datetime.timedelta(days=7)
    return fechas


def clave_documento(nit, numero_doc):
    return (solo_nit(nit), alfanumerico(numero_doc))


def _texto(valor):
    if valor is None:
        return ""
    if isinstance(valor, float) and valor.is_integer():
        return str(int(valor))
    return str(valor).strip()


# ------------------------------------------------------------
# Lectura de los informes de HELISA
# ------------------------------------------------------------

def _filas_valores(contenido):
    """Primera hoja de un Excel (xls, xlsx o XML 2003) como listas."""
    filas, _ = leer_grilla(contenido)
    salida = []
    for fila in filas:
        celdas = fila["celdas"]
        if not celdas:
            salida.append([])
            continue
        ancho = max(c["col"] for c in celdas)
        valores = [None] * ancho
        for c in celdas:
            valores[c["col"] - 1] = c["valor"]
        salida.append(valores)
    return salida


def _buscar_columnas(fila, etiquetas):
    """{clave: indice} buscando cada etiqueta (texto comparable) en la
    fila de titulos."""
    textos = [comparable(_texto(v)) for v in fila]
    columnas = {}
    for clave, opciones in etiquetas.items():
        for i, t in enumerate(textos):
            if t and any(t == o or t.startswith(o) for o in opciones):
                columnas[clave] = i
                break
    return columnas


def leer_programacion_helisa(contenido):
    """
    Informe 'programacion' de HELISA (cuentas por pagar). Devuelve
    {"documentos": [...], "total_saldo": x}. Cada documento: cuenta, nit,
    proveedor, tipo, numero, fecha, vence, valor, saldo, abono.
    """
    filas = _filas_valores(contenido)
    etiquetas = {"nit": ["IDENTIDAD", "NIT"], "proveedor": ["PROVEEDOR"],
                 "tipo": ["TIPO"], "numero": ["NUMERO"],
                 "fecha": ["FECHA"], "vence": ["FECHA VENC"],
                 "valor": ["VR. DOCUMENTO", "VR DOCUMENTO", "VALOR"],
                 "saldo": ["SALDO ACTUAL", "SALDO"]}
    titulo, columnas = None, {}
    for i, fila in enumerate(filas[:30]):
        columnas = _buscar_columnas(fila, etiquetas)
        if {"nit", "numero", "saldo"} <= set(columnas):
            titulo = i
            break
    if titulo is None:
        raise ValueError("No parece el informe de programación de HELISA "
                         "(faltan las columnas IDENTIDAD, NÚMERO o SALDO "
                         "ACTUAL).")
    # 'FECHA' tambien coincide con 'FECHA VENC.': se toma la exacta.
    textos = [comparable(_texto(v)) for v in filas[titulo]]
    if "FECHA" in textos:
        columnas["fecha"] = textos.index("FECHA")
    documentos = []
    for n_fila, fila in enumerate(filas[titulo + 1:], start=titulo + 2):
        def v(clave):
            i = columnas.get(clave)
            return fila[i] if i is not None and i < len(fila) else None
        num = _texto(v("numero"))
        nit = solo_nit(v("nit"))
        if not num or not nit:
            continue
        # La cuenta viene en la primera columna con un codigo de 4-10
        # digitos a la izquierda de la identidad (el titulo CUENTA de
        # HELISA queda corrido una columna).
        cuenta = ""
        for x in fila[:columnas["nit"]]:
            t = _texto(x)
            if re.fullmatch(r"\d{4,10}", t):
                cuenta = t
                break
        valor = numero(v("valor"))
        saldo = numero(v("saldo"))
        documentos.append({
            "cuenta": cuenta, "nit": nit,
            "proveedor": _texto(v("proveedor")),
            "tipo": _texto(v("tipo")), "numero": num,
            "fecha": fecha_celda_pp(v("fecha")), "vence": fecha_celda_pp(v("vence")),
            "valor": valor, "saldo": saldo,
            "abono": round(valor - saldo, 2) if saldo else valor,
            "fila": n_fila,
        })
    if not documentos:
        raise ValueError("El informe de programación no trae documentos.")
    return {"documentos": documentos, "tabla": filas,
            "total_saldo": round(sum(d["saldo"] for d in documentos), 2)}


def leer_conceptos_helisa(contenido):
    """
    Informe 'conceptos' de HELISA: (tipo, numero) -> textos capturados
    (sin repetir, en el orden del informe) y beneficiario.
    """
    filas = _filas_valores(contenido)
    etiquetas = {"tipo": ["TIPO DOC"], "numero": ["CONSECUTIVO"],
                 "fecha": ["FECHA"], "concepto": ["NOMBRE CONCEPTO"],
                 "beneficiario": ["BENEFICIARIO"],
                 "texto": ["TEXTO CAPTURA", "TEXTO"]}
    titulo = None
    for i, fila in enumerate(filas[:30]):
        columnas = _buscar_columnas(fila, etiquetas)
        if {"numero", "texto"} <= set(columnas):
            titulo = i
            break
    if titulo is None:
        raise ValueError("No parece el informe de conceptos de HELISA "
                         "(faltan las columnas Consecutivo Doc. o Texto "
                         "Captura Concepto).")
    conceptos = OrderedDict()
    for fila in filas[titulo + 1:]:
        def v(clave):
            i = columnas.get(clave)
            return fila[i] if i is not None and i < len(fila) else None
        num = _texto(v("numero"))
        if not num:
            continue
        llave = alfanumerico(num)
        dato = conceptos.setdefault(llave, {
            "numero": num, "tipo": _texto(v("tipo")),
            "beneficiario": _texto(v("beneficiario")), "textos": []})
        texto = re.sub(r"\s+", " ", _texto(v("texto"))).strip()
        if texto and comparable(texto) not in [comparable(t)
                                               for t in dato["textos"]]:
            dato["textos"].append(texto)
    return conceptos


def concepto_documento(conceptos, numero_doc, proveedor=""):
    """Texto capturado del documento. HELISA corta el numero en el informe
    de programacion (CCTT-1833637 vs CCTT-18336378): se acepta el prefijo
    si el beneficiario coincide."""
    llave = alfanumerico(numero_doc)
    dato = conceptos.get(llave)
    if dato is None and len(llave) >= 6:
        prov = comparable(proveedor)
        for otra, d in conceptos.items():
            if otra.startswith(llave) and (
                    not prov or comparable(d["beneficiario"]) == prov):
                dato = d
                break
    if not dato or not dato["textos"]:
        return ""
    return " / ".join(t.upper() for t in dato["textos"])


# ------------------------------------------------------------
# Lectura de la programacion anterior
# ------------------------------------------------------------

def _convertir_xls_excel(contenido):
    """Convierte .xls -> .xlsx con Microsoft Excel (solo Windows, por
    PowerShell). Trabaja sobre una copia temporal, en modo solo lectura."""
    import os
    import subprocess
    import tempfile
    if os.name != "nt":
        return None
    with tempfile.TemporaryDirectory() as carpeta:
        origen = os.path.join(carpeta, "anterior.xls")
        destino = os.path.join(carpeta, "anterior.xlsx")
        with open(origen, "wb") as archivo:
            archivo.write(contenido)
        o, d = origen.replace("'", "''"), destino.replace("'", "''")
        script = (
            "$x = New-Object -ComObject Excel.Application; "
            "$x.Visible = $false; $x.DisplayAlerts = $false; "
            f"$w = $x.Workbooks.Open('{o}', 0, $true); "
            f"$w.SaveAs('{d}', 51); $w.Close($false); $x.Quit()")
        try:
            subprocess.run(["powershell", "-NoProfile", "-NonInteractive",
                            "-ExecutionPolicy", "Bypass", "-Command", script],
                           capture_output=True, timeout=120, check=False,
                           creationflags=getattr(subprocess,
                                                 "CREATE_NO_WINDOW", 0))
        except (OSError, subprocess.SubprocessError):
            return None
        if os.path.exists(destino):
            with open(destino, "rb") as archivo:
                return archivo.read()
    return None


def _xlsx_de_anterior(contenido):
    """Bytes .xlsx del libro anterior (o None si no se pudo convertir)."""
    if contenido[:4] == b"PK\x03\x04":
        return contenido
    if contenido[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        return _convertir_xls_excel(contenido) or \
            _convertir_xls_libreoffice(contenido)
    return None


RE_REF_PP = re.compile(r"\$?([A-Z]{1,3})\$?(\d+)")


def _evaluar_formula(formula, valor_de):
    """Evaluador minimo para las formulas de una programacion (=+K6,
    =+I6-K6, =+K96*70%, =SUM(I61:I64)+3000000, =SUBTOTAL(9,..)) cuando el
    libro no trae los valores calculados (archivo guardado sin abrir en
    Excel)."""
    from openpyxl.utils import column_index_from_string
    expr = formula.lstrip("=").replace("$", "")
    if "!" in expr:
        return None

    def rango(texto):
        a, b = texto.split(":")
        ma, mb = RE_REF_PP.fullmatch(a), RE_REF_PP.fullmatch(b)
        if not ma or not mb:
            return 0.0
        c1, c2 = sorted((column_index_from_string(ma.group(1)),
                         column_index_from_string(mb.group(1))))
        f1, f2 = sorted((int(ma.group(2)), int(mb.group(2))))
        return sum(numero(valor_de(f, c)) for f in range(f1, f2 + 1)
                   for c in range(c1, c2 + 1))

    expr = re.sub(r"SUBTOTAL\(\s*9\s*,", "SUM(", expr, flags=re.I)
    expr = re.sub(r"SUM\(([A-Z]+\d+:[A-Z]+\d+)\)",
                  lambda m: repr(rango(m.group(1))), expr, flags=re.I)
    expr = re.sub(r"SUM\(([^()]*)\)", r"(\1)", expr, flags=re.I)
    expr = RE_REF_PP.sub(
        lambda m: repr(numero(valor_de(
            int(m.group(2)), column_index_from_string(m.group(1))))), expr)
    expr = re.sub(r"(\d+(?:\.\d+)?)%", r"(\1/100)", expr)
    if not re.fullmatch(r"[\d\s.+\-*/()e]+", expr):
        return None
    try:
        return float(eval(expr, {"__builtins__": {}}, {}))
    except Exception:
        return None


def _hojas_openpyxl(xlsx):
    """OrderedDict nombre -> filas de valores (con formulas evaluadas si el
    libro no trae el valor calculado)."""
    from openpyxl import load_workbook
    libro_v = load_workbook(io.BytesIO(xlsx), data_only=True)
    libro_f = load_workbook(io.BytesIO(xlsx), data_only=False)
    hojas, combinadas = OrderedDict(), {}
    for hoja_v in libro_v.worksheets:
        hoja_f = libro_f[hoja_v.title]
        cache = {}

        def valor_de(f, c, hoja_v=hoja_v, hoja_f=hoja_f, cache=cache,
                     pila=None):
            if (f, c) in cache:
                return cache[(f, c)]
            v = hoja_v.cell(f, c).value
            bruto = hoja_f.cell(f, c).value
            if v is None and isinstance(bruto, str) and \
                    bruto.startswith("="):
                cache[(f, c)] = 0.0          # evita ciclos
                v = _evaluar_formula(bruto, valor_de)
            cache[(f, c)] = v
            return v

        filas = []
        for f in range(1, hoja_v.max_row + 1):
            filas.append([valor_de(f, c)
                          for c in range(1, hoja_v.max_column + 1)])
        hojas[hoja_v.title] = filas
        combinadas[hoja_v.title] = [
            (r.min_row, r.min_col, r.max_row, r.max_col)
            for r in hoja_f.merged_cells.ranges]
    return hojas, combinadas


def _hojas_xlrd(contenido):
    import xlrd
    try:
        libro = xlrd.open_workbook(file_contents=contenido,
                                   formatting_info=True)
    except Exception:
        libro = xlrd.open_workbook(file_contents=contenido)
    hojas, combinadas = OrderedDict(), {}
    for hoja in libro.sheets():
        combinadas[hoja.name] = [(r1 + 1, c1 + 1, r2, c2) for r1, r2, c1, c2
                                 in getattr(hoja, "merged_cells", [])]
        filas = []
        for f in range(hoja.nrows):
            fila = []
            for c in range(hoja.ncols):
                celda = hoja.cell(f, c)
                if celda.ctype == xlrd.XL_CELL_DATE:
                    try:
                        fila.append(xlrd.xldate.xldate_as_datetime(
                            celda.value, libro.datemode))
                        continue
                    except Exception:
                        pass
                fila.append(celda.value if celda.value != "" else None)
            filas.append(fila)
        hojas[hoja.name] = filas
    return hojas, combinadas


def abrir_libro_anterior(contenido):
    """
    {"hojas": nombre -> filas, "xlsx": bytes o None, "xls": bytes o None,
     "fuente": texto}. Lee .xlsx directo; un .xls se convierte (Excel o
    LibreOffice) y si no se puede se lee con xlrd.
    """
    xlsx = _xlsx_de_anterior(contenido)
    if xlsx:
        hojas, combinadas = _hojas_openpyxl(xlsx)
        return {"hojas": hojas, "combinadas": combinadas, "xlsx": xlsx,
                "xls": None, "fuente": "completo"}
    if contenido[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        try:
            hojas, combinadas = _hojas_xlrd(contenido)
            return {"hojas": hojas, "combinadas": combinadas, "xlsx": None,
                    "xls": contenido, "fuente": "xlrd"}
        except ImportError:
            raise ValueError(
                "La programación anterior es un Excel 97-2003 (.xls) y en "
                "este equipo no está Excel, LibreOffice ni la librería xlrd "
                "para leerlo. Ábrela en Excel y guárdala como .xlsx, o "
                "instala xlrd (pip install xlrd).")
    raise ValueError("La programación anterior debe ser un archivo de Excel "
                     "(.xls o .xlsx).")


def _hoja_principal(hojas):
    for nombre in hojas:
        if comparable(nombre).startswith("PROG"):
            return nombre
    return next(iter(hojas))


RE_PAGOS_HOJA = re.compile(r"^\s*PAGOS\s+\d")


def leer_prog_anterior(contenido, nombre_archivo=""):
    """
    Interpreta la hoja principal de la programacion anterior. Devuelve las
    facturas, anticipos y pagos fijos con su programacion por fecha.
    """
    libro = abrir_libro_anterior(contenido)
    hojas = libro["hojas"]
    nombre_hoja = _hoja_principal(hojas)
    filas = hojas[nombre_hoja]

    def celda(fila, i):
        return fila[i] if i is not None and i < len(fila) else None

    # Fila de titulos (NIT, RAZON SOCIAL, ... Saldo a Pagar).
    titulo = None
    for i, fila in enumerate(filas[:40]):
        textos = [comparable(_texto(v)) for v in fila]
        if "NIT" in textos and any(t.startswith("RAZON SOCIAL")
                                   for t in textos):
            titulo = i
            break
    if titulo is None:
        raise ValueError(f"En la hoja «{nombre_hoja}» no se encontró la fila "
                         "de títulos (NIT, RAZON SOCIAL, ...).")
    textos = [comparable(_texto(v)) for v in filas[titulo]]

    def col(*opciones):
        for i, t in enumerate(textos):
            if any(t.startswith(o) for o in opciones):
                return i
        return None

    c = {"nit": textos.index("NIT"), "razon": col("RAZON SOCIAL"),
         "numero": col("NUMERO"), "concepto": col("CONCEPTO"),
         "fecha": col("FECHA EMISION", "FECHA"), "vence": col("FECHA VENCE",
                                                               "FECHA \nVENCE"),
         "valor": col("VALOR FACTURA", "VALOR"), "abono": col("ABONOS"),
         "saldo": col("SALDO TOTAL")}
    # 'Fecha \nVence' trae salto de linea: comparable() lo vuelve espacio.
    c["vence"] = col("FECHA VENCE") if col("FECHA VENCE") is not None \
        else (c["fecha"] + 1 if c["fecha"] is not None else None)
    c["cuenta"] = c["nit"] - 1 if c["nit"] > 0 else None
    c["tipo"] = c["numero"]
    c["num"] = c["numero"] + 1 if c["numero"] is not None else None
    pagos = [i for i, t in enumerate(textos) if t.startswith("SALDO A PAGAR")]
    obs = col("OBSERVACION")
    if obs is None:
        obs = (max(pagos) + 1) if pagos else None

    # Encabezado: nombre, fecha de la programacion y fechas de pago.
    empresa, fecha_prog, titulo_gastos = "", None, ""
    for fila in filas[:titulo]:
        for v in fila:
            t = comparable(_texto(v))
            if not t:
                continue
            if not empresa and re.search(r"S\.?A\.?S|LTDA|S\.A", t):
                empresa = _texto(v)
            if t.startswith("TOTAL DISPONIBLE"):
                m = re.search(r"([A-Z]+)\s+(\d{1,2})\s+DEL?\s+(\d{4})", t)
                if m and _mes_de_palabra(m.group(1)):
                    try:
                        fecha_prog = datetime.date(
                            int(m.group(3)), _mes_de_palabra(m.group(1)),
                            int(m.group(2)))
                    except ValueError:
                        pass
            if t.startswith("PRESUPUESTO DE GASTOS"):
                titulo_gastos = _texto(v)
    fechas_pago = []
    fila_fechas = filas[titulo - 1] if titulo else []
    for i in pagos:
        t = _texto(celda(fila_fechas, i))
        m = re.search(r"(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?", t)
        fecha = None
        if m:
            anio = (fecha_prog.year if fecha_prog else
                    int(m.group(3)) if m.group(3) else
                    datetime.date.today().year)
            try:
                fecha = datetime.date(anio, int(m.group(2)), int(m.group(1)))
                if fecha_prog and fecha < fecha_prog - datetime.timedelta(60):
                    fecha = datetime.date(anio + 1, fecha.month, fecha.day)
            except ValueError:
                fecha = None
        fechas_pago.append(fecha)
    if fecha_prog is None:
        reales = [f for f in fechas_pago if f]
        fecha_prog = (min(reales) - datetime.timedelta(days=2)) if reales \
            else None
    trm = None

    facturas, anticipos, fijos = [], [], []
    grupo, padre = None, None
    for n, fila in enumerate(filas[titulo + 1:], start=titulo + 2):
        b = _texto(celda(fila, c["nit"]))
        razon = _texto(celda(fila, c["razon"]))
        cb, cr = comparable(b), comparable(razon)
        if cb.startswith("GRAN TOTAL"):
            continue
        if cb.startswith("DIFERENCIA") or cb.startswith("FLUJO"):
            for i, v in enumerate(fila):
                if comparable(_texto(v)) == "TRM" and i + 1 < len(fila):
                    trm = numero(fila[i + 1]) or trm
            continue
        if cr.startswith("TOTAL ") or cr == "TOTAL":
            padre = None
            continue
        prog = [round(numero(celda(fila, i)), 2) for i in pagos]
        base = {
            "fila": n,
            "valor": round(numero(celda(fila, c["valor"])), 2),
            "abono": round(numero(celda(fila, c["abono"])), 2),
            "saldo": round(numero(celda(fila, c["saldo"])), 2),
            "prog": prog,
            "obs": _texto(celda(fila, obs)) if obs is not None else "",
        }
        num_doc = _texto(celda(fila, c["num"]))
        if cb.startswith("PAGOS FIJOS"):
            grupo = {"bloque": b.strip(), "nombre": razon.strip(),
                     "items": []}
            fijos.append(grupo)
            padre = None
        if cb.startswith("ANTICIPO"):
            grupo, padre = None, None
            anticipos.append(dict(
                base, bloque=b.strip(), proveedor=razon,
                concepto=_texto(celda(fila, c["numero"])),
                fecha=celda(fila, c["fecha"])))
            continue
        if grupo is not None and (cb.startswith("PAGOS FIJOS") or
                                  (not b and not razon)):
            desc = _texto(celda(fila, c["numero"]))
            if not desc:
                continue
            item = dict(base, concepto=desc, fecha=celda(fila, c["fecha"]),
                        hijos=[])
            tiene_saldo = celda(fila, c["saldo"]) not in (None, "")
            if not tiene_saldo and padre is not None:
                padre["hijos"].append(item)
            else:
                grupo["items"].append(item)
                padre = item
            continue
        if num_doc and (b or razon):
            grupo, padre = None, None
            facturas.append(dict(
                base, cuenta=_texto(celda(fila, c["cuenta"])),
                nit=solo_nit(b), proveedor=razon,
                tipo=_texto(celda(fila, c["tipo"])), numero=num_doc,
                concepto=_texto(celda(fila, c["concepto"])),
                fecha=fecha_celda_pp(celda(fila, c["fecha"])),
                vence=fecha_celda_pp(celda(fila, c["vence"]))))

    numero_prog = None
    m = re.search(r"#\s*(\d+)", nombre_hoja)
    if m:
        numero_prog = int(m.group(1))
    return {
        "archivo": nombre_archivo, "hoja": nombre_hoja, "empresa": empresa,
        "fecha": fecha_prog, "fechas_pago": fechas_pago,
        "titulo_gastos": titulo_gastos, "trm": trm,
        "numero_prog": numero_prog, "facturas": facturas,
        "anticipos": anticipos, "fijos": fijos, "libro": libro,
        "hojas_auxiliares": [h for h in hojas if h != nombre_hoja
                             and not RE_PAGOS_HOJA.match(h)],
    }
