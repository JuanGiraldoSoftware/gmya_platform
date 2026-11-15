"""Lectura de cualquier archivo tabular a una grilla (lista de filas).

Contrato:
  leer_grilla(contenido) -> filas (listas de celdas) de la hoja activa de
      un .xlsx, .xls (BIFF, con xlrd o lector propio; si falla se convierte
      con LibreOffice), XML de Excel 2003 o PDF de HELISA (columnas
      reconstruidas por posicion). Detecta el formato por los bytes.
  tabla_desde_archivo(contenido) -> filas de la primera hoja de un Excel o
      CSV (error si llega un PDF).
Nunca escribe archivos del usuario; las conversiones van a carpetas
temporales.

Depende de: gmya.comun.texto
"""

import io
import re
import xml.etree.ElementTree as ET

from gmya.comun.cache import memo_copia
from gmya.comun.texto import comparable, decodificar


def tabla_desde_archivo(contenido):
    """Filas (listas de valores) de la primera hoja de un Excel o CSV."""
    if contenido[:4] == b"%PDF":
        raise ValueError("Se esperaba un Excel o CSV y llegó un PDF.")
    es_texto = not (contenido[:4] == b"PK\x03\x04"
                    or contenido[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
                    or contenido[:600].lstrip().startswith(b"<?xml")
                    or b"office:spreadsheet" in contenido[:2000])
    if es_texto:
        import csv
        texto = decodificar(contenido)
        muestra = texto[:5000]
        separador = max([";", ",", "\t", "|"], key=muestra.count)
        return [list(fila) for fila in csv.reader(io.StringIO(texto),
                                                  delimiter=separador)]

    if contenido[:4] == b"PK\x03\x04":
        from openpyxl import load_workbook
        libro = load_workbook(io.BytesIO(contenido), data_only=True)
        return [list(f) for f in libro.worksheets[0].iter_rows(
            values_only=True)]

    filas, _ = leer_grilla(contenido)
    tabla = []
    for fila in filas:
        valores = {}
        for celda in fila["celdas"]:
            valores[celda["col"]] = celda["valor"]
        ancho = max(valores) if valores else 0
        tabla.append([valores.get(c) for c in range(1, ancho + 1)])
    return tabla


# ------------------------------------------------------------
# Lectura de archivos HELISA (Excel 97-2003)
# ------------------------------------------------------------
# HELISA (FastReport) exporta "Excel 97-2003" como XML Spreadsheet 2003.
# Si el archivo es un .xls binario se intenta con xlrd, y si es .xlsx con
# openpyxl. Todo termina en una grilla comun: filas -> celdas con columna,
# valor, tipo, ancho combinado (span) y estilo.
NS = "urn:schemas-microsoft-com:office:spreadsheet"


SS = "{" + NS + "}"


def _estilos_xml(raiz):
    estilos = {}
    nodo = raiz.find(SS + "Styles")
    if nodo is None:
        return estilos
    for estilo in nodo.findall(SS + "Style"):
        ident = estilo.get(SS + "ID")
        datos = {}
        fuente = estilo.find(SS + "Font")
        if fuente is not None:
            datos["fuente"] = fuente.get(SS + "FontName")
            datos["tamano"] = float(fuente.get(SS + "Size") or 10)
            datos["negrita"] = fuente.get(SS + "Bold") == "1"
            datos["cursiva"] = fuente.get(SS + "Italic") == "1"
            datos["color"] = (fuente.get(SS + "Color") or "").lstrip("#")
        interior = estilo.find(SS + "Interior")
        if interior is not None and interior.get(SS + "Pattern") == "Solid":
            datos["relleno"] = (interior.get(SS + "Color") or "").lstrip("#")
        alineacion = estilo.find(SS + "Alignment")
        if alineacion is not None:
            datos["horizontal"] = (alineacion.get(SS + "Horizontal")
                                   or "").lower() or None
        estilos[ident] = datos
    return estilos


def _grilla_xml(contenido):
    raiz = ET.fromstring(contenido)
    estilos = _estilos_xml(raiz)
    hoja = raiz.find(SS + "Worksheet")
    tabla = hoja.find(SS + "Table") if hoja is not None else None
    if tabla is None:
        raise ValueError("El archivo no contiene una tabla de Excel.")

    anchos = []
    for columna in tabla.findall(SS + "Column"):
        anchos.append(float(columna.get(SS + "Width") or 0))

    filas = []
    for fila in tabla.findall(SS + "Row"):
        celdas = []
        col = 0
        for celda in fila.findall(SS + "Cell"):
            indice = celda.get(SS + "Index")
            col = int(indice) if indice else col + 1
            dato = celda.find(SS + "Data")
            valor = "".join(dato.itertext()) if dato is not None else ""
            tipo = dato.get(SS + "Type") if dato is not None else None
            if tipo == "Number":
                try:
                    valor = float(valor)
                except ValueError:
                    pass
            span = int(celda.get(SS + "MergeAcross") or 0)
            celdas.append({
                "col": col, "valor": valor, "span": span,
                "estilo": estilos.get(celda.get(SS + "StyleID"), {}),
            })
            col += span
        alto = fila.get(SS + "Height")
        filas.append({"celdas": celdas,
                      "alto": float(alto) if alto else None})
    return filas, anchos


def _grilla_tabular(valores):
    filas = []
    for fila in valores:
        celdas = [{"col": i + 1, "valor": v, "span": 0, "estilo": {}}
                  for i, v in enumerate(fila)
                  if v not in (None, "")]
        filas.append({"celdas": celdas, "alto": None})
    return filas, []


@memo_copia(6)
def leer_grilla(contenido):
    inicio = contenido[:600].lstrip()
    if inicio.startswith(b"%PDF"):
        return _grilla_pdf(contenido)
    if inicio.startswith(b"<?xml") or b"office:spreadsheet" in contenido[:2000]:
        return _grilla_xml(contenido)
    if contenido[:4] == b"PK\x03\x04":
        from openpyxl import load_workbook
        libro = load_workbook(io.BytesIO(contenido), data_only=True)
        return _grilla_tabular(libro.active.iter_rows(values_only=True))
    if contenido[:2] in (b"\x09\x00", b"\x09\x02", b"\x09\x04",
                         b"\x09\x08"):
        # Hoja BIFF suelta (sin contenedor OLE), como exportan algunos
        # informes de HELISA (p. ej. Lista de facturas por pagar).
        filas = _grilla_biff_crudo(contenido)
        if filas:
            return _grilla_tabular(filas)
        convertido = _convertir_xls_libreoffice(contenido)
        if convertido:
            from openpyxl import load_workbook
            libro = load_workbook(io.BytesIO(convertido), data_only=True)
            return _grilla_tabular(libro.active.iter_rows(values_only=True))
    if contenido[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        # Excel 97-2003 binario (BIFF): xlrd, y si no esta instalado se
        # intenta convertir con LibreOffice (si existe en el equipo).
        try:
            import xlrd
            libro = xlrd.open_workbook(file_contents=contenido)
            hoja = libro.sheet_by_index(0)
            return _grilla_tabular(hoja.row_values(i)
                                   for i in range(hoja.nrows))
        except ImportError:
            convertido = _convertir_xls_libreoffice(contenido)
            if convertido:
                from openpyxl import load_workbook
                libro = load_workbook(io.BytesIO(convertido), data_only=True)
                return _grilla_tabular(libro.active.iter_rows(
                    values_only=True))
            raise ValueError(
                "El archivo es un Excel 97-2003 binario y falta la librería "
                "xlrd (pip install xlrd). También puedes guardarlo como "
                "'Hoja de cálculo XML 2003' o .xlsx.")
    raise ValueError("Formato no reconocido. Exporta el informe de HELISA "
                     "como Excel 97-2003.")


_CONVERTIDOS = {}


def _rk_valor(rk):
    import struct
    if rk & 2:
        valor = float(rk >> 2 if not rk & 0x80000000 else
                      (rk >> 2) - (1 << 30))
    else:
        valor = struct.unpack("<d", struct.pack("<Q", (rk & 0xFFFFFFFC)
                                                << 32))[0]
    return valor / 100 if rk & 1 else valor


def _grilla_biff_crudo(contenido):
    """
    Lee una hoja BIFF2-5 sin contenedor OLE (registros sueltos de texto y
    numero). Devuelve las filas como listas de valores, o [] si no pudo.
    """
    import struct
    celdas, i, n = {}, 0, len(contenido)
    try:
        while i + 4 <= n:
            tipo, largo = struct.unpack("<HH", contenido[i:i + 4])
            datos = contenido[i + 4:i + 4 + largo]
            i += 4 + largo
            if tipo == 0x000A:                      # EOF
                break
            if len(datos) < 4:
                continue
            fila, col = struct.unpack("<HH", datos[:4])
            if tipo == 0x0004:                      # LABEL (BIFF2)
                largo_txt = datos[7]
                valor = datos[8:8 + largo_txt].decode("cp1252", "replace")
            elif tipo in (0x0204, 0x00D6):          # LABEL / RSTRING
                largo_txt = struct.unpack("<H", datos[6:8])[0]
                valor = datos[8:8 + largo_txt].decode("cp1252", "replace")
            elif tipo == 0x0003:                    # NUMBER (BIFF2)
                valor = struct.unpack("<d", datos[7:15])[0]
            elif tipo == 0x0203:                    # NUMBER
                valor = struct.unpack("<d", datos[6:14])[0]
            elif tipo == 0x0002:                    # INTEGER (BIFF2)
                valor = float(struct.unpack("<H", datos[7:9])[0])
            elif tipo == 0x027E:                    # RK
                valor = _rk_valor(struct.unpack("<I", datos[6:10])[0])
            elif tipo == 0x00BD:                    # MULRK
                cuantos = (len(datos) - 6) // 6
                for k in range(cuantos):
                    rk = struct.unpack("<I", datos[6 + 6 * k:10 + 6 * k])[0]
                    celdas[(fila, col + k)] = _rk_valor(rk)
                continue
            elif tipo in (0x0006, 0x0206, 0x0406):  # FORMULA: resultado
                inicio = 7 if tipo == 0x0006 else 6
                valor = struct.unpack("<d", datos[inicio:inicio + 8])[0]
            else:
                continue
            celdas[(fila, col)] = valor
    except (struct.error, IndexError):
        return []
    if not celdas:
        return []
    alto = max(f for f, _ in celdas) + 1
    ancho = max(c for _, c in celdas) + 1
    filas = [[None] * ancho for _ in range(alto)]
    for (f, c), v in celdas.items():
        filas[f][c] = v
    return filas


def _convertir_xls_libreoffice(contenido):
    """Convierte un .xls binario a .xlsx con LibreOffice (si existe)."""
    import hashlib
    llave = hashlib.sha1(contenido).hexdigest()
    if llave not in _CONVERTIDOS:
        _CONVERTIDOS[llave] = _convertir_xls_libreoffice_sin_cache(contenido)
    return _CONVERTIDOS[llave]


def _convertir_xls_libreoffice_sin_cache(contenido):
    import os
    import shutil
    import subprocess
    import tempfile
    programa = shutil.which("soffice") or shutil.which("libreoffice")
    if not programa:
        return None
    with tempfile.TemporaryDirectory() as carpeta:
        origen = os.path.join(carpeta, "informe.xls")
        with open(origen, "wb") as archivo:
            archivo.write(contenido)
        try:
            subprocess.run([programa, "--headless", "--convert-to", "xlsx",
                            "--outdir", carpeta, origen],
                           capture_output=True, timeout=120, check=False)
        except (OSError, subprocess.SubprocessError):
            return None
        destino = os.path.join(carpeta, "informe.xlsx")
        if os.path.exists(destino):
            with open(destino, "rb") as archivo:
                return archivo.read()
    return None


# ------------------------------------------------------------
# Informes HELISA exportados a PDF (Comprobante diario - Detalle / Resumen)
# ------------------------------------------------------------
# En el PDF de HELISA (FastReport) los textos largos de una columna se
# montan sobre la siguiente, por eso extract_text() los mezcla. Pero el
# flujo de caracteres conserva cada campo completo y seguido: se corta en
# segmentos cuando cambia la linea o el caracter salta hacia atras / deja un
# hueco, y cada segmento se asigna a la columna cuyo titulo esta mas cerca.
ETIQUETAS_PDF_HELISA = ["FECHA", "DOCUMENTO", "CUENTA", "NOMBRE DE LA CUENTA",
                        "CONCEPTO", "IDENTIDAD", "BENEFICIARIO", "PARCIALES",
                        "DEBITOS", "CREDITOS"]


COLUMNAS_VALOR_PDF = ("PARCIALES", "DEBITOS", "CREDITOS")


RE_MONTO_PDF = re.compile(r"-?\(?\d[\d,]*\.\d{2}\)?-?")


def _segmentos_pdf(caracteres):
    segmentos, actual = [], None
    for c in caracteres:
        if actual is not None and (
                abs(c["top"] - actual["top"]) > 2
                or c["x0"] < actual["x1"] - 0.6
                or c["x0"] > actual["x1"] + 1.2):
            segmentos.append(actual)
            actual = None
        if actual is None:
            actual = {"top": c["top"], "x1": c["x1"], "chars": []}
        actual["chars"].append(c)
        actual["x1"] = c["x1"]
    if actual:
        segmentos.append(actual)
    salida = []
    for s in segmentos:
        visibles = [c for c in s["chars"] if c["text"].strip()]
        if not visibles:
            continue
        texto = "".join(c["text"] for c in s["chars"])
        salida.append({"texto": texto.strip(), "crudo": texto,
                       "top": s["top"], "x0": visibles[0]["x0"],
                       "x1": visibles[-1]["x1"]})
    return salida


def _lineas_pdf(segmentos):
    lineas = []
    for s in sorted(segmentos, key=lambda s: (s["top"], s["x0"])):
        if lineas and abs(lineas[-1]["top"] - s["top"]) <= 2.5:
            lineas[-1]["segs"].append(s)
        else:
            lineas.append({"top": s["top"], "segs": [s]})
    for linea in lineas:
        linea["segs"].sort(key=lambda s: s["x0"])
        linea["texto"] = " ".join(s["texto"] for s in linea["segs"])
    return lineas


def _columnas_encabezado_pdf(palabras, top):
    """[(etiqueta, centro, x0)] de las palabras de la fila de titulos."""
    fila = sorted([p for p in palabras if abs(p["top"] - top) <= 3],
                  key=lambda p: p["x0"])
    columnas, i = [], 0
    while i < len(fila):
        hallado = None
        for etiqueta in sorted(ETIQUETAS_PDF_HELISA, key=lambda e: -len(e)):
            partes = etiqueta.split()
            grupo = fila[i:i + len(partes)]
            if [comparable(p["text"]) for p in grupo] == partes:
                hallado = (etiqueta, (grupo[0]["x0"] + grupo[-1]["x1"]) / 2,
                           grupo[0]["x0"], len(partes))
                break
        if hallado:
            columnas.append(hallado[:3])
            i += hallado[3]
        else:
            i += 1
    return columnas


def _es_encabezado_pdf(texto):
    t = comparable(texto)
    return "CUENTA" in t and ("DEBITOS" in t or "CREDITOS" in t) and (
        "FECHA" in t or "PARCIALES" in t)


def _grilla_pdf(contenido):
    """Grilla (filas, anchos) de un informe HELISA en PDF."""
    try:
        import pdfplumber
    except ImportError as error:
        raise ValueError("Para leer informes HELISA en PDF falta la librería "
                         "pdfplumber (pip install pdfplumber).") from error
    filas = []
    columnas = None             # [(etiqueta, centro, x0)]
    en_pie = False
    with pdfplumber.open(io.BytesIO(contenido)) as pdf:
        for pagina in pdf.pages:
            segmentos = _segmentos_pdf(pagina.chars)
            palabras = None
            for linea in _lineas_pdf(segmentos):
                texto = linea["texto"]
                if _es_encabezado_pdf(texto):
                    palabras = palabras or pagina.extract_words()
                    nuevas = _columnas_encabezado_pdf(palabras, linea["top"])
                    if len(nuevas) >= 3:
                        columnas = nuevas
                        filas.append({"celdas": [
                            {"col": i + 1, "valor": e, "span": 0,
                             "estilo": {"negrita": True}}
                            for i, (e, _, _) in enumerate(columnas)],
                            "alto": None})
                        continue
                if "TOTAL GENERAL" in comparable(texto):
                    en_pie = True
                if columnas is None or (en_pie and "TOTAL GENERAL" not in
                                        comparable(texto)):
                    filas.append({"celdas": [{"col": 1, "valor": texto,
                                              "span": 0, "estilo": {}}],
                                  "alto": None})
                    continue
                valores = {}
                # Textos: alineados a la izquierda -> titulo con el x0 mas
                # cercano. Valores: alineados a la derecha -> titulo de
                # valor con el centro mas cercano.
                texto_cols = [(i, x0) for i, (e, _, x0) in enumerate(columnas)
                              if e not in COLUMNAS_VALOR_PDF]
                monto_cols = [(i, c) for i, (e, c, _) in enumerate(columnas)
                              if e in COLUMNAS_VALOR_PDF]
                for s in linea["segs"]:
                    es_monto = RE_MONTO_PDF.fullmatch(s["texto"]) and monto_cols
                    if es_monto or not texto_cols:
                        centro = (s["x0"] + s["x1"]) / 2
                        i = min(monto_cols, key=lambda o: abs(o[1] - centro))[0]
                    else:
                        i = min(texto_cols,
                                key=lambda o: abs(o[1] - s["x0"]))[0]
                    # Concepto largo que se monta sobre la identidad:
                    # "CRUCE ANTICIPO ... FACT#MV496391 891904303-1".
                    m = re.match(r"^(.*[A-Za-z].*?)\s+(\d[\d.]*(?:-\d)?)$",
                                 s["texto"])
                    if not es_monto and columnas[i][0] == "IDENTIDAD" and m \
                            and i > 0:
                        previo = valores.get(i - 1)
                        valores[i - 1] = (f"{previo} {m.group(1).strip()}"
                                          if previo else m.group(1).strip())
                        valores[i] = m.group(2)
                        continue
                    if es_monto:
                        valor = s["texto"].replace(",", "")
                        negativo = valor.startswith(("-", "(")) or \
                            valor.endswith("-")
                        valor = float(valor.strip("-()"))
                        valores[i] = -valor if negativo else valor
                    elif i in valores:
                        valores[i] = f"{valores[i]} {s['texto']}"
                    else:
                        valores[i] = s["crudo"].rstrip() \
                            if columnas[i][0] == "IDENTIDAD" else s["texto"]
                filas.append({"celdas": [
                    {"col": i + 1, "valor": v, "span": 0, "estilo": {}}
                    for i, v in sorted(valores.items())], "alto": None})
    if columnas is None:
        raise ValueError("El PDF no parece un informe de HELISA (no se "
                         "encontró la fila de títulos CUENTA / DEBITOS / "
                         "CREDITOS).")
    return filas, []
