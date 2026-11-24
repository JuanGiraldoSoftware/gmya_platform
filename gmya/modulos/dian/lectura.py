"""Lectura de documentos para la conciliacion DIAN (sin Streamlit).

Contrato:
  leer_helisa(contenido, nombre_archivo="") -> informe HELISA (resumen + detalle por
      documento) desde PDF/Excel.
  leer_reporte_dian / leer_varios_reportes_dian -> reporte de la DIAN
      (Excel descargado del portal, o varios combinados).
  expandir_archivos(lista) -> abre .zip y devuelve los archivos internos.

Depende de: gmya.comun.texto, gmya.comun.numeros, gmya.comun.fechas, gmya.comun.grilla, gmya.modulos.dian.parametros
"""

import datetime
import io
import re
from collections import Counter, OrderedDict

from gmya.comun.texto import alfanumerico, comparable, _sin_tildes, solo_nit
from gmya.comun.numeros import numero
from gmya.comun.fechas import MES_CORTO, MESES_ES
from gmya.comun.grilla import leer_grilla
from gmya.modulos.dian.parametros import dato


def contiene_palabra(nombre, palabras):
    claro = comparable(nombre)
    for palabra in palabras or []:
        p = comparable(palabra)
        if not p:
            continue
        # Hasta 4 letras: palabra completa (IVA no coincide con ACTIVA).
        # Mas largas: inicio de palabra, admite plural (DEDUCIBLE/S).
        fin = r"(?![A-Z0-9])" if len(p) <= 4 else ""
        if re.search(r"(?<![A-Z0-9])" + re.escape(p) + fin, claro):
            return True
    return False


def coincide_cuenta(codigo, nombre, palabras):
    """Codigo que empieza por un codigo de la lista, o nombre que EMPIEZA
    por una de las palabras."""
    claro = comparable(nombre)
    for palabra in palabras or []:
        p = comparable(palabra)
        if not p:
            continue
        if es_codigo(p):
            if str(codigo).strip().startswith(p):
                return True
        elif re.match(re.escape(p) + r"(?![A-Z0-9])", claro):
            return True
    return False


def es_codigo(texto):
    return bool(re.fullmatch(r"\d{2,}", str(texto).strip()))


def etiqueta_periodo(fecha):
    return f"{MES_CORTO[fecha.month - 1]} {fecha.year}"


def fecha_dian(texto):
    texto = str(texto or "").strip()
    for formato in ("%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.datetime.strptime(texto[:10], formato).date()
        except ValueError:
            continue
    if isinstance(texto, (datetime.date, datetime.datetime)):
        return texto if isinstance(texto, datetime.date) else texto.date()
    return None


def _fecha_elaboracion(filas):
    """'Este informe se elaboró el 19 de Octubre del año 2026' -> date."""
    for fila in reversed(filas):
        texto = _sin_tildes(_texto_fila(fila)).lower()
        m = re.search(r"elaboro el (\d{1,2}) de ([a-z]+) del? (?:ano )?"
                      r"(\d{4})", texto)
        if m and m.group(2) in MESES_ES:
            try:
                return datetime.date(int(m.group(3)), MESES_ES[m.group(2)],
                                     int(m.group(1)))
            except ValueError:
                return None
    return None


def _texto_fila(fila):
    return " ".join(str(c["valor"]).strip() for c in fila["celdas"]
                    if str(c["valor"]).strip())


def _celda(fila, col):
    for celda in fila["celdas"]:
        if celda["col"] == col:
            return celda["valor"]
    return None


def _encabezado_informe(filas):
    textos = [_texto_fila(f) for f in filas[:6]]
    empresa = textos[0] if textos else ""
    nit = ""
    for texto in textos:
        m = re.search(r"nit:?\s*([\d.,\- ]+\d)", texto, re.I)
        if m:
            nit = m.group(1).strip()
            break
    titulo = next((t for t in textos if "comprobante" in t.lower()), "")
    return empresa, nit, titulo


def _meses_solicitados(filas):
    for fila in filas:
        texto = _texto_fila(fila)
        if "MESES SOLICITADOS" in texto.upper():
            return texto.split(":", 1)[-1].strip()
    return ""


def periodo_desde_texto(texto):
    """' Septiembre de 2026' -> date(2026, 9, 1)."""
    m = re.search(r"([A-Za-zñÑ]+)\s+(?:de\s+)?(\d{4})", _sin_tildes(texto))
    if m and m.group(1).lower() in MESES_ES:
        return datetime.date(int(m.group(2)), MESES_ES[m.group(1).lower()], 1)
    return None


def nit_sin_dv(texto):
    """'900,123,456-1' -> '900123456'."""
    return re.sub(r"\D", "", str(texto).split("-")[0])


# ------------------------------------------------------------
# Comprobante de diario - Resumen (FV, DSE, NC ...)
# ------------------------------------------------------------

def leer_resumen_helisa(contenido, nombre_archivo="", grilla=None):
    filas, _ = grilla or leer_grilla(contenido)
    empresa, nit, titulo = _encabezado_informe(filas)

    columnas = None
    for indice, fila in enumerate(filas):
        etiquetas = {comparable(c["valor"]): c["col"] for c in fila["celdas"]}
        if "CUENTA" in etiquetas and ("DEBITOS" in etiquetas
                                      or "CREDITOS" in etiquetas):
            columnas = {
                "parciales": etiquetas.get("PARCIALES"),
                "debitos": etiquetas.get("DEBITOS"),
                "creditos": etiquetas.get("CREDITOS"),
                "inicio": indice + 1,
            }
            break

    if not columnas:
        raise ValueError(
            f"{nombre_archivo}: no parece un 'Comprobante de diario - "
            "Resumen' de HELISA (no se encontró la fila CUENTA / DEBITOS / "
            "CREDITOS).")

    def valores(fila):
        return (numero(_celda(fila, columnas["parciales"])),
                numero(_celda(fila, columnas["debitos"])),
                numero(_celda(fila, columnas["creditos"])))

    tipos, cuentas = [], []
    total_debitos = total_creditos = None
    fila_total_general = None

    for fila in filas[columnas["inicio"]:]:
        texto = _texto_fila(fila)
        if not texto:
            continue
        primera = str(fila["celdas"][0]["valor"]).strip() \
            if fila["celdas"] else ""
        if comparable(texto).startswith("TOTAL GENERAL") or \
                "TOTAL GENERAL" in comparable(texto):
            _, total_debitos, total_creditos = valores(fila)
            fila_total_general = fila
            continue
        m = re.match(r"^(\d{2,})\s+(.*)$", primera)
        if m:
            parcial, debito, credito = valores(fila)
            cuentas.append({"fila": fila,
                            "codigo": m.group(1), "nombre": m.group(2).strip(),
                            "parcial": parcial, "debito": debito,
                            "credito": credito})
            continue
        m = re.match(r"^([A-Z]{1,6})\s+-\s+(.+)$", primera)
        if m and not primera.upper().startswith("TOTAL"):
            tipos.append((m.group(1), m.group(2).strip()))

    if total_debitos is None:
        total_debitos = sum(c["debito"] for c in cuentas)
        total_creditos = sum(c["credito"] for c in cuentas)

    return {
        "archivo": nombre_archivo,
        "clase": "resumen",
        "empresa": empresa,
        "nit": nit,
        "titulo": titulo,
        "meses": _meses_solicitados(filas),
        "tipos": tipos,
        "cuentas": cuentas,
        "fila_total_general": fila_total_general,
        "total_debitos": round(total_debitos, 2),
        "total_creditos": round(total_creditos, 2),
    }


def valor_cuentas(resumen, palabras=None, excluir=None):
    """
    Suma las cuentas cuyo NOMBRE contiene alguna palabra o cuyo CODIGO
    empieza por alguno de los codigos indicados. Si una cuenta y su
    subcuenta coinciden, solo se toma la de mayor nivel (no se duplica).
    Devuelve (valor, cuentas usadas).
    """
    palabras = [p for p in (palabras or []) if str(p).strip()]
    codigos = [p.strip() for p in palabras if es_codigo(p)]
    textos = [p for p in palabras if not es_codigo(p)]

    coinciden = []
    for cuenta in resumen["cuentas"]:
        por_codigo = any(cuenta["codigo"].startswith(c) for c in codigos)
        por_nombre = (contiene_palabra(cuenta["nombre"], textos)
                      and not contiene_palabra(cuenta["nombre"], excluir))
        if por_codigo or por_nombre:
            coinciden.append(cuenta)

    elegidas = []
    for cuenta in sorted(coinciden, key=lambda c: len(c["codigo"])):
        if any(cuenta["codigo"].startswith(e["codigo"]) for e in elegidas):
            continue
        elegidas.append(cuenta)

    total = 0.0
    for cuenta in elegidas:
        if cuenta["debito"] or cuenta["credito"]:
            total += abs(cuenta["debito"] - cuenta["credito"])
        else:
            total += abs(cuenta["parcial"])
    return round(total, 2), elegidas


def iva_debito_resumen(resumen, codigos, iva_dian):
    """
    IVA de un informe Resumen por codigo de cuenta (2408...). En documentos
    soporte el IVA descontable (debito, p. ej. 24080212) suele cancelarse
    con un credito de IVA teorico en otra subcuenta 2408, y el neto da 0:
    se comparan el neto y la suma de los debitos de las subcuentas y se
    toma el que mas se acerca al IVA DIAN. Devuelve (valor, cuentas).
    """
    neto, elegidas = valor_cuentas(resumen, codigos)
    todas = [c for c in resumen["cuentas"]
             if any(c["codigo"].startswith(x) for x in codigos)]
    hojas = [c for c in todas if not any(
        o is not c and o["codigo"].startswith(c["codigo"])
        and len(o["codigo"]) > len(c["codigo"]) for o in todas)]
    debitos = round(sum(c["debito"] for c in hojas), 2)
    con_debito = [c for c in hojas if c["debito"]]
    if debitos and abs(debitos - iva_dian) < abs(neto - iva_dian):
        return debitos, con_debito
    return neto, elegidas


# ------------------------------------------------------------
# Comprobante diario - Detalle (FC)
# ------------------------------------------------------------

def leer_detalle_helisa(contenido, nombre_archivo="", grilla=None):
    filas, anchos = grilla or leer_grilla(contenido)
    empresa, nit, titulo = _encabezado_informe(filas)

    columnas, fila_encabezado = None, None
    for indice, fila in enumerate(filas):
        etiquetas = {comparable(c["valor"]): c["col"] for c in fila["celdas"]}
        if {"FECHA", "DOCUMENTO", "CUENTA"} <= set(etiquetas) and \
                ("DEBITOS" in etiquetas or "CREDITOS" in etiquetas):
            columnas = {
                "fecha": etiquetas["FECHA"],
                "documento": etiquetas["DOCUMENTO"],
                "cuenta": etiquetas["CUENTA"],
                "nombre": etiquetas.get("NOMBRE DE LA CUENTA"),
                "concepto": etiquetas.get("CONCEPTO"),
                "identidad": etiquetas.get("IDENTIDAD"),
                "beneficiario": etiquetas.get("BENEFICIARIO"),
                "debitos": etiquetas.get("DEBITOS"),
                "creditos": etiquetas.get("CREDITOS"),
            }
            fila_encabezado = indice
            break

    if not columnas:
        raise ValueError(
            f"{nombre_archivo}: no parece un 'Comprobante diario - Detalle' "
            "de HELISA (no se encontró la fila FECHA / DOCUMENTO / CUENTA).")

    encabezado_texto = comparable(_texto_fila(filas[fila_encabezado]))
    titulo_cmp = comparable(titulo)
    empresa_cmp = comparable(empresa)

    def es_cabecera_pagina(fila):
        texto = comparable(_texto_fila(fila))
        return (not texto or texto == encabezado_texto
                or texto == empresa_cmp or texto == titulo_cmp
                or re.fullmatch(r"PAGINA \d+ DE \d+", texto) is not None
                or texto.startswith("(NIT"))

    cuerpo, pie = [], []
    documentos = OrderedDict()
    total_general = None
    actual = None
    en_pie = False

    for fila in filas[fila_encabezado + 1:]:
        texto = comparable(_texto_fila(fila))
        if en_pie:
            if texto:
                pie.append(fila)
            continue
        if es_cabecera_pagina(fila):
            continue

        fecha = str(_celda(fila, columnas["fecha"]) or "").strip()
        documento = separar_tipo_documento(
            str(_celda(fila, columnas["documento"]) or "").strip())

        if "TOTAL GENERAL" in texto:
            total_general = fila
            en_pie = True
            continue

        if texto.startswith("TOTAL DOCUMENTO") or \
                "TOTAL DOCUMENTO" in texto:
            # En el PDF, cuando el numero del documento es solo digitos
            # (DSE 000000000285, FC 000003009100460607) queda en otra celda
            # ("TOTAL DOCUMENTO DSE" | "000000000285"): se unen las celdas
            # de texto antes de los valores para armar el documento.
            partes, en_total = [], False
            for c in sorted(fila["celdas"], key=lambda x: x["col"]):
                valor = c["valor"]
                if "TOTAL DOCUMENTO" in comparable(valor):
                    partes.append(re.sub(r"^.*?TOTAL DOCUMENTO\s*", "",
                                         str(valor), flags=re.I).strip())
                    en_total = True
                elif en_total and isinstance(valor, str) and valor.strip() \
                        and c["col"] not in (columnas["debitos"],
                                             columnas["creditos"]) \
                        and not re.fullmatch(r"-?[\d,]*\.\d{2}",
                                             valor.strip()):
                    partes.append(valor.strip())
                elif en_total and not isinstance(valor, str):
                    break
            etiqueta = " ".join(p for p in partes if p).strip()
            clave = next((d for d in documentos
                          if alfanumerico(d) == alfanumerico(etiqueta)), None)
            if clave is None and actual and alfanumerico(etiqueta) and \
                    alfanumerico(actual).startswith(alfanumerico(etiqueta)):
                # El total cierra el documento que se venia leyendo.
                clave = actual
            clave = clave or etiqueta
            doc = documentos.setdefault(clave, _documento_vacio(clave))
            doc["fila_total"] = fila
            doc["total_debito"] = numero(_celda(fila, columnas["debitos"]))
            doc["total_credito"] = numero(_celda(fila, columnas["creditos"]))
            cuerpo.append(("total", fila, clave))
            continue

        if re.fullmatch(r"\d{1,2}/\d{1,2}/\d{4}", fecha) and documento:
            if documento not in documentos:
                documentos[documento] = _documento_vacio(documento)
            doc = documentos[documento]
            identidad = str(_celda(fila, columnas["identidad"]) or "")
            movimiento = {
                "fecha": fecha,
                "cuenta": str(_celda(fila, columnas["cuenta"]) or "").strip(),
                "nombre": str(_celda(fila, columnas["nombre"]) or "").strip(),
                "concepto": str(_celda(fila, columnas["concepto"]) or ""),
                "identidad": identidad,
                "beneficiario": str(
                    _celda(fila, columnas["beneficiario"]) or "").strip(),
                "debito": numero(_celda(fila, columnas["debitos"])),
                "credito": numero(_celda(fila, columnas["creditos"])),
                "fila": fila,
            }
            doc["movimientos"].append(movimiento)
            if not doc["nit"]:
                doc["nit"] = solo_nit(identidad)
                doc["fecha"] = fecha
                doc["beneficiario"] = movimiento["beneficiario"]
            cuerpo.append(("mov", fila, documento))
            actual = documento
            continue

        # Cualquier otra fila (poco comun) se conserva tal cual.
        cuerpo.append(("otra", fila, actual))

    for doc in documentos.values():
        if doc["total_debito"] is None:
            doc["total_debito"] = round(sum(m["debito"]
                                            for m in doc["movimientos"]), 2)
            doc["total_credito"] = round(sum(m["credito"]
                                             for m in doc["movimientos"]), 2)

    total_debitos = numero(_celda(total_general, columnas["debitos"])) \
        if total_general else sum(d["total_debito"]
                                  for d in documentos.values())

    return {
        "archivo": nombre_archivo,
        "clase": "detalle",
        "empresa": empresa,
        "nit": nit,
        "titulo": titulo,
        "meses": _meses_solicitados(pie),
        "columnas": columnas,
        "anchos": anchos,
        "fila_encabezado": filas[fila_encabezado],
        "filas_titulo": filas[:fila_encabezado],
        "cuerpo": cuerpo,
        "total_general": total_general,
        "pie": pie,
        "documentos": documentos,
        "total_debitos": round(total_debitos, 2),
    }


def separar_tipo_documento(documento):
    """v6.9: algunas empresas (EMPRESA B) exportan el documento con el tipo
    pegado al numero ("FEDU185", "FEEX35"); se separa ("FEDU 185") para
    reconocer el tipo. Si ya trae espacio o no es letras + numero, queda
    igual."""
    m = re.fullmatch(r"([A-Za-z]{2,6})(\d[\w\-]*)", documento)
    return f"{m.group(1)} {m.group(2)}" if m else documento


def _documento_vacio(clave):
    return {"documento": clave, "nit": "", "fecha": "", "beneficiario": "",
            "movimientos": [], "fila_total": None,
            "total_debito": None, "total_credito": None}


def leer_helisa(contenido, nombre_archivo=""):
    """Detecta si el informe es Resumen o Detalle y lo lee."""
    grilla = leer_grilla(contenido)
    filas = grilla[0]
    cabecera = " ".join(comparable(_texto_fila(f)) for f in filas[:8])
    if "DETALLE" in cabecera or ("FECHA" in cabecera
                                 and "DOCUMENTO" in cabecera):
        informe = leer_detalle_helisa(contenido, nombre_archivo, grilla)
    else:
        informe = leer_resumen_helisa(contenido, nombre_archivo, grilla)
    informe["fecha_informe"] = _fecha_elaboracion(filas)
    informe["grilla"] = filas          # para el visor (filas originales)
    return informe


# ------------------------------------------------------------
# Reporte DIAN
# ------------------------------------------------------------

SINONIMOS_DIAN = OrderedDict([
    ("Tipo de documento", ["TIPO DE DOCUMENTO", "TIPO DOCUMENTO",
                           "TIPO DOC", "TIPO"]),
    ("CUFE/CUDE", ["CUFE/CUDE", "CUFE", "CUDE"]),
    ("Folio", ["FOLIO", "NUMERO", "NUMERO DOCUMENTO", "CONSECUTIVO",
               "NO DOCUMENTO", "NUMERO FACTURA"]),
    ("Prefijo", ["PREFIJO", "SERIE"]),
    ("Divisa", ["DIVISA", "MONEDA"]),
    ("Forma de Pago", ["FORMA DE PAGO", "FORMA PAGO"]),
    ("Medio de Pago", ["MEDIO DE PAGO", "MEDIO PAGO"]),
    ("Fecha Emisión", ["FECHA EMISION", "FECHA DE EMISION", "FECHA"]),
    ("Fecha Recepción", ["FECHA RECEPCION", "FECHA DE RECEPCION"]),
    ("NIT Emisor", ["NIT EMISOR", "NIT DEL EMISOR", "EMISOR NIT",
                    "IDENTIFICACION EMISOR"]),
    ("Nombre Emisor", ["NOMBRE EMISOR", "RAZON SOCIAL EMISOR",
                       "NOMBRE DEL EMISOR", "EMISOR"]),
    ("NIT Receptor", ["NIT RECEPTOR", "NIT DEL RECEPTOR", "RECEPTOR NIT",
                      "IDENTIFICACION RECEPTOR", "NIT ADQUIRIENTE"]),
    ("Nombre Receptor", ["NOMBRE RECEPTOR", "RAZON SOCIAL RECEPTOR",
                         "NOMBRE DEL RECEPTOR", "RECEPTOR", "ADQUIRIENTE"]),
    ("IVA", ["IVA", "VALOR IVA", "TOTAL IVA"]),
    ("INC", ["INC", "IMPUESTO AL CONSUMO", "IMPOCONSUMO", "ICO"]),
    ("Total", ["TOTAL", "VALOR TOTAL", "TOTAL DOCUMENTO", "VALOR"]),
    ("Estado", ["ESTADO"]),
    ("Grupo", ["GRUPO"]),
])
COLUMNAS_DIAN_CLAVE = ["Tipo de documento", "Folio", "Prefijo", "NIT Emisor",
                       "NIT Receptor", "Total", "Grupo"]


def archivos_de_zip(contenido):
    """
    Si el contenido es un .zip comun (como lo entrega el portal DIAN, con
    el Excel adentro) devuelve [(nombre, bytes)] de las hojas de calculo que
    trae; si no es un zip (o es un .xlsx, que tambien es zip) devuelve None.
    """
    if contenido[:4] != b"PK\x03\x04":
        return None
    import zipfile
    try:
        archivo = zipfile.ZipFile(io.BytesIO(contenido))
        nombres = archivo.namelist()
    except zipfile.BadZipFile:
        return None
    if "[Content_Types].xml" in nombres:
        return None
    return [(n.rsplit("/", 1)[-1], archivo.read(n)) for n in nombres
            if not n.startswith("__MACOSX") and not n.endswith("/")
            and n.lower().endswith((".xlsx", ".xls", ".csv", ".xml"))]


def expandir_archivos(archivos):
    """[(nombre, bytes)] con los .zip reemplazados por los archivos que
    contienen (zip.xlsx)."""
    salida = []
    for nombre, contenido in archivos:
        internos = archivos_de_zip(contenido)
        if internos is None:
            salida.append((nombre, contenido))
        else:
            salida.extend((f"{nombre} › {n}", c) for n, c in internos)
    return salida


def fecha_descarga_dian(nombre_hoja):
    """'Rp_Doc_20261001_1712' / 'Reporte_Documentos_20260302_152' -> date."""
    m = re.search(r"(20\d{2})(\d{2})(\d{2})", str(nombre_hoja or ""))
    if m:
        try:
            return datetime.date(int(m.group(1)), int(m.group(2)),
                                 int(m.group(3)))
        except ValueError:
            return None
    return None


def _hojas_como_filas(contenido):
    """[(nombre_hoja, filas, anchos)] de un .xlsx, .xls, XML 2003 o CSV
    (o de un .zip que los contenga)."""
    hojas = []
    internos = archivos_de_zip(contenido)
    if internos is not None:
        for _, interno in internos:
            hojas.extend(_hojas_como_filas(interno))
        return hojas
    if contenido[:4] == b"PK\x03\x04":
        from openpyxl import load_workbook
        libro = load_workbook(io.BytesIO(contenido), data_only=True)
        for hoja in libro.worksheets:
            anchos = {letra: dim.width for letra, dim in
                      hoja.column_dimensions.items() if dim.width}
            hojas.append((hoja.title, [list(f) for f in
                                       hoja.iter_rows(values_only=True)],
                          anchos))
        return hojas
    try:
        filas, _ = leer_grilla(contenido)
        tabla = []
        for fila in filas:
            maximo = max([c["col"] for c in fila["celdas"]] or [0])
            valores = [None] * maximo
            for c in fila["celdas"]:
                valores[c["col"] - 1] = c["valor"]
            tabla.append(valores)
        return [("DIAN", tabla, {})]
    except Exception:
        texto = contenido.decode("utf-8-sig", errors="ignore")
        import csv
        separador = ";" if texto.count(";") > texto.count(",") else ","
        return [("DIAN", [list(f) for f in csv.reader(
            io.StringIO(texto), delimiter=separador)], {})]


def _ubicar_encabezado_dian(filas):
    """(indice de fila, {columna: canonico}, aciertos) del mejor encabezado."""
    mejor = (None, {}, 0)
    for indice, fila in enumerate(filas[:15]):
        mapa, usados = {}, set()
        for col, valor in enumerate(fila):
            texto = comparable(valor)
            if not texto:
                continue
            for canonico, sinonimos in SINONIMOS_DIAN.items():
                if canonico in usados:
                    continue
                if texto in sinonimos or comparable(canonico) == texto:
                    mapa[col] = canonico
                    usados.add(canonico)
                    break
        aciertos = sum(1 for c in mapa.values() if c in COLUMNAS_DIAN_CLAVE)
        if aciertos > mejor[2]:
            mejor = (indice, mapa, aciertos)
    return mejor


def parece_reporte_dian(contenido):
    try:
        return any(_ubicar_encabezado_dian(f)[2] >= 4
                   for _, f, _ in _hojas_como_filas(contenido))
    except Exception:
        return False


def leer_reporte_dian(contenido, nombre_archivo=""):
    """
    Lee el reporte de documentos DIAN de forma tolerante: busca la fila de
    encabezados en cualquier hoja, acepta nombres de columna parecidos y,
    si faltan columnas, las crea vacias (o las deduce) y lo deja en avisos.
    """
    avisos = []
    try:
        hojas = _hojas_como_filas(contenido)
    except Exception as error:
        raise ValueError(
            "No se pudo abrir el reporte DIAN. Debe ser el Excel descargado "
            "del portal de facturación electrónica (.xlsx, .xls o .csv)."
        ) from error

    candidatos = [(nombre, filas, anchos) + _ubicar_encabezado_dian(filas)
                  for nombre, filas, anchos in hojas]
    nombre_hoja, filas, anchos, fila_enc, mapa, aciertos = max(
        candidatos, key=lambda c: c[5]) if candidatos else \
        ("DIAN", [], {}, None, {}, 0)

    if fila_enc is None or aciertos < 2:
        avisos.append(
            f"«{nombre_archivo}» no parece el reporte de documentos de la "
            "DIAN (no se reconocen sus columnas). La conciliación se hace "
            "con un reporte DIAN vacío: todo lo de HELISA quedará como NO "
            "DIAN.")
        fila_enc, mapa = None, {}
        filas = []

    if fila_enc is not None:
        originales = [str(v).strip() if v is not None else ""
                      for v in filas[fila_enc]]
        encabezados = [mapa.get(i) or originales[i] or f"Columna {i + 1}"
                       for i in range(len(originales))]
        cuerpo = filas[fila_enc + 1:]
    else:
        encabezados, cuerpo = [], []

    registros, fila_excel = [], {}
    for j, fila in enumerate(cuerpo):
        if fila is None or all(v in (None, "") for v in fila):
            continue
        fila = list(fila)[:len(encabezados)]
        registro = fila + [None] * (len(encabezados) - len(fila))
        registros.append(registro)
        fila_excel[id(registro)] = fila_enc + j + 2   # fila del archivo

    # Columnas que faltan: IVA / INC antes de Total; el resto al final.
    faltan = [c for c in SINONIMOS_DIAN if c not in encabezados and (
        c in COLUMNAS_DIAN_CLAVE or c in ("IVA", "INC", "Fecha Emisión",
                                          "Nombre Emisor",
                                          "Nombre Receptor"))]
    for columna in faltan:
        if columna in ("IVA", "INC") and "Total" in encabezados:
            posicion = encabezados.index("Total")
        else:
            posicion = len(encabezados)
        encabezados.insert(posicion, columna)
        for r in registros:
            r.insert(posicion, None)

    indice = {nombre: i for i, nombre in enumerate(encabezados)}

    def poner(columna, funcion):
        for r in registros:
            r[indice[columna]] = funcion(r)

    reales = [c for c in faltan if c in COLUMNAS_DIAN_CLAVE + ["IVA"]]
    if registros and reales:
        avisos.append(
            f"Al reporte DIAN «{nombre_archivo}» le faltan las columnas "
            f"{', '.join(reales)}; se completaron vacías o deducidas. "
            "Verifica que sea el listado completo del portal DIAN.")
    if registros and "Grupo" in faltan:
        nits = Counter()
        for r in registros:
            nits[solo_nit(r[indice["NIT Emisor"]])] += 1
            nits[solo_nit(r[indice["NIT Receptor"]])] += 1
        propio = nits.most_common(1)[0][0] if nits else ""
        poner("Grupo", lambda r: "Emitido" if solo_nit(
            r[indice["NIT Emisor"]]) == propio and propio else "Recibido")
    if registros and "Tipo de documento" in faltan:
        poner("Tipo de documento", lambda r: "Factura electrónica")
    for columna in ("IVA", "INC", "Total"):
        if columna in faltan:
            poner(columna, lambda r: 0)

    if not registros and fila_enc is not None:
        avisos.append(f"El reporte DIAN «{nombre_archivo}» no trae "
                      "documentos.")

    posicion_iva = indice.get("IVA", indice["Total"])
    columnas_valor = encabezados[posicion_iva:indice["Total"] + 1] \
        if posicion_iva <= indice["Total"] else ["Total"]

    return {
        "archivo": nombre_archivo,
        "hoja": nombre_hoja or "DIAN",
        "fecha_descarga": fecha_descarga_dian(nombre_hoja),
        "encabezados": encabezados,
        "indice": indice,
        "registros": registros,
        "anchos": anchos,
        "columnas_valor": columnas_valor,
        "avisos": avisos,
        "fila_excel": fila_excel,
    }


def _clave_registro_dian(reporte, registro):
    cufe = str(dato(reporte, registro, "CUFE/CUDE") or "").strip()
    if cufe:
        return cufe
    return tuple(comparable(dato(reporte, registro, c)) for c in (
        "Tipo de documento", "Prefijo", "Folio", "NIT Emisor", "NIT Receptor"))


def combinar_reportes_dian(reportes):
    """
    Une varios reportes DIAN (p. ej. descargas del 30-sep, 1-oct y 7-oct
    del mismo mes). Un documento repetido (mismo CUFE) se toma de la
    descarga mas reciente (fecha en el nombre de la hoja).
    """
    if len(reportes) == 1:
        return reportes[0]
    con_datos = [r for r in reportes if r["registros"]] or reportes
    orden = sorted(con_datos, key=lambda r: (r.get("fecha_descarga")
                                             or datetime.date.min))
    base = orden[-1]
    encabezados = list(base["encabezados"])
    for r in orden:
        for e in r["encabezados"]:
            if e not in encabezados:
                encabezados.append(e)
    unicos, repetidos = OrderedDict(), 0
    for r in orden:
        for registro in r["registros"]:
            fila = [dato(r, registro, e) for e in encabezados]
            clave = _clave_registro_dian(r, registro)
            if clave in unicos:
                repetidos += 1
            unicos[clave] = fila
    avisos = []
    for r in reportes:
        avisos.extend(r.get("avisos", []))
    descripcion = ", ".join(
        f"«{r['archivo']}»" + (f" (descargado el {r['fecha_descarga']:%d/%m/%Y})"
                               if r.get("fecha_descarga") else "")
        for r in orden)
    nota = (f"Se unieron {len(orden)} reportes DIAN: {descripcion}. Quedaron "
            f"{len(unicos)} documentos; {repetidos} repetidos se tomaron de "
            "la descarga más reciente.")
    ignorados = [r for r in reportes if r not in con_datos]
    for r in ignorados:
        avisos.append(f"El reporte DIAN «{r['archivo']}» no trae documentos; "
                      "se omitió.")
    indice = {nombre: i for i, nombre in enumerate(encabezados)}
    posicion_iva = indice.get("IVA", indice["Total"])
    columnas_valor = encabezados[posicion_iva:indice["Total"] + 1] \
        if posicion_iva <= indice["Total"] else ["Total"]
    return {
        "archivo": " + ".join(r["archivo"] for r in orden),
        "hoja": base["hoja"],
        "fecha_descarga": base.get("fecha_descarga"),
        "encabezados": encabezados,
        "indice": indice,
        "registros": list(unicos.values()),
        "anchos": base.get("anchos", {}),
        "columnas_valor": columnas_valor,
        "avisos": avisos,
        "nota": nota,
        "fila_excel": {},
    }


def leer_varios_reportes_dian(archivos):
    """Lee uno o varios reportes DIAN [(nombre, bytes)] (.zip incluidos) y
    los une en uno solo."""
    reportes = [leer_reporte_dian(c, n) for n, c in expandir_archivos(archivos)]
    if not reportes:
        raise ValueError("El .zip no trae ningún Excel del reporte DIAN.")
    return combinar_reportes_dian(reportes)


def tipo_coincide(tipo, tipos):
    """'Documento equivalente POS' coincide con 'Documento equivalente*'."""
    t = comparable(tipo)
    for patron in tipos or []:
        p = comparable(patron)
        if p.endswith("*"):
            if t.startswith(p[:-1].strip()):
                return True
        elif t == p:
            return True
    return False


def filtrar_dian(reporte, grupo, tipos):
    return [r for r in reporte["registros"]
            if comparable(dato(reporte, r, "Grupo")) == comparable(grupo)
            and tipo_coincide(dato(reporte, r, "Tipo de documento"), tipos)]


def periodo_dian(reporte):
    fechas = [fecha_dian(dato(reporte, r, "Fecha Emisión"))
              for r in reporte["registros"]]
    meses = Counter((f.year, f.month) for f in fechas if f)
    if not meses:
        return None
    (anio, mes), _ = meses.most_common(1)[0]
    return datetime.date(anio, mes, 1)


def _fin_de_mes(fecha):
    siguiente = (fecha.replace(day=28) + datetime.timedelta(days=4))
    return siguiente - datetime.timedelta(days=siguiente.day)


def _fecha_helisa(texto):
    try:
        return datetime.datetime.strptime(str(texto).strip()[:10],
                                          "%d/%m/%Y").date()
    except ValueError:
        return None


def detectar_periodo_dian(reporte, informes_helisa, conceptos):
    """
    Deduce el periodo conciliado sin pedirlo al usuario:
      - fechas de emision DIAN de los conceptos cargados,
      - fechas de los documentos HELISA (informes detalle),
      - 'MESES SOLICITADOS' y la fecha en que se elaboro el informe HELISA.
    Devuelve: tipo ('mes', 'corte', 'rango', 'varios_meses'), inicio, fin,
    etiqueta (para hojas: 'SEP 2026', 'AL 19 OCT', 'DEL 13 AL 19 OCT') y
    descripcion legible.
    """
    fechas = []
    for concepto in conceptos:
        if concepto["clave"] not in informes_helisa:
            continue
        for r in filtrar_dian(reporte, concepto["grupo"], concepto["tipos"]):
            f = fecha_dian(dato(reporte, r, "Fecha Emisión"))
            if f:
                fechas.append(f)
    if not fechas:
        fechas = [f for f in (fecha_dian(dato(reporte, r, "Fecha Emisión"))
                              for r in reporte["registros"]) if f]

    meses_helisa, elaboracion, fechas_helisa = set(), [], []
    for informe in informes_helisa.values():
        for doc in (informe.get("documentos") or {}).values():
            f = _fecha_helisa(doc.get("fecha"))
            if f:
                fechas_helisa.append(f)
        mes = periodo_desde_texto(informe.get("meses", ""))
        if mes:
            meses_helisa.add((mes.year, mes.month))
        if informe.get("fecha_informe"):
            elaboracion.append(informe["fecha_informe"])
    # La fecha de descarga del reporte DIAN (nombre de la hoja) tambien es
    # un corte: un reporte bajado el 02-mar cubre febrero completo aunque el
    # informe HELISA se haya sacado el 27-feb.
    if reporte.get("fecha_descarga"):
        elaboracion.append(reporte["fecha_descarga"])

    hoy = datetime.date.today()
    if not fechas and not meses_helisa:
        inicio = hoy.replace(day=1)
        fechas = [inicio]
    if fechas:
        f_min, f_max = min(fechas), max(fechas)
    else:
        (a, m) = min(meses_helisa)
        f_min = f_max = datetime.date(a, m, 1)

    meses = sorted(meses_helisa or {(f.year, f.month) for f in fechas})
    primero = datetime.date(meses[0][0], meses[0][1], 1)
    ultimo_mes = datetime.date(meses[-1][0], meses[-1][1], 1)
    fin_mes = _fin_de_mes(ultimo_mes)

    # Fecha de corte: la de elaboracion del informe HELISA si cae dentro
    # del ultimo mes; si no, la ultima fecha de emision DIAN.
    corte = None
    if elaboracion:
        e = max(elaboracion)
        corte = fin_mes if e > fin_mes else (e if e >= ultimo_mes else None)
    if corte is None:
        corte = fin_mes if f_max.day >= 28 or f_max >= fin_mes else f_max
        if f_max.month != ultimo_mes.month or f_max.year != ultimo_mes.year:
            corte = fin_mes
    mes_completo = corte >= fin_mes

    def mes_txt(f, con_anio=True):
        return f"{MES_CORTO[f.month - 1]}" + (f" {f.year}" if con_anio
                                              else "")

    if len(meses) > 1:
        tipo = "varios_meses"
        etiqueta = (f"{mes_txt(primero, primero.year != ultimo_mes.year)}-"
                    f"{mes_txt(ultimo_mes)}")
        if not mes_completo:
            etiqueta += f" AL {corte.day}"
        inicio, fin = primero, corte
        descripcion = (f"Varios meses: del {inicio:%d/%m/%Y} al "
                       f"{fin:%d/%m/%Y}")
    elif mes_completo:
        tipo = "mes"
        etiqueta = mes_txt(ultimo_mes)
        inicio, fin = ultimo_mes, fin_mes
        descripcion = f"Mes completo: {etiqueta}"
    else:
        # El inicio del rango sale de TODO el reporte DIAN (no solo de los
        # conceptos cargados) y de los documentos HELISA: si el reporte se
        # descargo por semana, todas sus fechas caen en esa semana.
        todas_dian = [f for f in (fecha_dian(dato(reporte, r, "Fecha Emisión"))
                                  for r in reporte["registros"]) if f]
        del_mes = [f for f in todas_dian + fechas + fechas_helisa
                   if (f.year, f.month) == meses[-1]]
        inicio_rango = min(del_mes) if del_mes else ultimo_mes
        if inicio_rango.day > 1 and (corte - inicio_rango).days <= 10:
            tipo = "rango"
            # En un rango corto el cierre es el ultimo documento, no la
            # fecha en que se saco el informe.
            corte = min(corte, max(del_mes))
            etiqueta = (f"DEL {inicio_rango.day} AL {corte.day} "
                        f"{mes_txt(corte, False)}")
            inicio, fin = inicio_rango, corte
            descripcion = (f"Semana / rango: del {inicio:%d/%m/%Y} al "
                           f"{fin:%d/%m/%Y}")
        else:
            tipo = "corte"
            etiqueta = f"AL {corte.day} {mes_txt(corte, False)}"
            inicio, fin = ultimo_mes, corte
            descripcion = (f"Mes en curso con corte: del {inicio:%d/%m/%Y} "
                           f"al {fin:%d/%m/%Y}")
    return {"tipo": tipo, "inicio": inicio, "fin": fin,
            "etiqueta": etiqueta, "descripcion": descripcion,
            "mes": ultimo_mes, "fecha_min": f_min, "fecha_max": f_max}


def nit_empresa_dian(reporte):
    nits = Counter()
    for r in reporte["registros"]:
        grupo = comparable(dato(reporte, r, "Grupo"))
        if grupo == "EMITIDO":
            nits[solo_nit(dato(reporte, r, "NIT Emisor"))] += 1
        elif grupo == "RECIBIDO":
            nits[solo_nit(dato(reporte, r, "NIT Receptor"))] += 1
    return nits.most_common(1)[0][0] if nits else ""
