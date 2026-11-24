"""Lectura de extractos bancarios y libro auxiliar HELISA (sin Streamlit).

Contrato:
  leer_extracto_pdf(contenido, anio_defecto=None) -> movimientos del extracto (fecha,
      descripcion, valor con signo, saldo), banco, cuenta y periodo.
  leer_libro_helisa(contenido) -> registros del auxiliar HELISA.
  detectar_banco / detectar_cuenta / detectar_periodo -> metadatos.

Depende de: gmya.comun.numeros, gmya.comun.pdf
"""

import calendar
import datetime
import io
import re
import unicodedata
from collections import Counter
from decimal import Decimal

from gmya.comun.numeros import CENTAVO
from gmya.comun.pdf import agrupar_lineas, palabras_pagina


MESES_COMPLETOS = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5,
    "junio": 6, "julio": 7, "agosto": 8, "septiembre": 9,
    "setiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}
MESES_ABREVIADOS = {
    "ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6,
    "jul": 7, "ago": 8, "sep": 9, "sept": 9, "set": 9, "oct": 10,
    "nov": 11, "dic": 12,
}
ETIQUETA_MES = [
    "ene", "feb", "mar", "abr", "may", "jun",
    "jul", "ago", "sep", "oct", "nov", "dic",
]

ESTILO_ENCABEZADO = "1F4E78"
FORMATO_MONTO = '_-* #,##0.00_-;\\-* #,##0.00_-;_-* "-"??_-;_-@_-'

# ------------------------------------------------------------
# Reconocimiento del banco (solo para rotular el reporte).
# Se buscan frases que identifican al emisor del documento, no el
# nombre suelto, porque los extractos mencionan a otros bancos en
# las descripciones de las transferencias.
# ------------------------------------------------------------
BANCOS_CONOCIDOS = [
    ("Davivienda", r"banco\s+davivienda\s+s\.?\s?a|davivienda\.com"),
    ("Bancolombia", r"bancolombia\.com|@bancolombia|bancolombia\s+s\.?\s?a"),
    ("Banco de Bogotá", r"bancodebogota\.com|banco\s+de\s+bogot"),
    ("Bold", r"bold\.\s*compa|bold\s*c\.?f\.?|nit:?\s*901\.?522\.?349"),
    ("BBVA", r"bbva\.com\.co|banco\s+bilbao"),
    ("Banco de Occidente", r"bancodeoccidente\.com|banco\s+de\s+occidente"),
    ("AV Villas", r"avvillas\.com|banco\s+av\s+villas"),
    ("Banco Popular", r"bancopopular\.com|banco\s+popular"),
    ("Scotiabank Colpatria", r"colpatria|scotiabank"),
    ("Itaú", r"itau\.co|banco\s+ita[uú]"),
    ("Banco Agrario", r"bancoagrario\.gov|banco\s+agrario"),
    ("Banco Caja Social", r"bancocajasocial\.com|banco\s+caja\s+social"),
    ("Bancoomeva", r"bancoomeva"),
    ("Banco Falabella", r"bancofalabella"),
    ("Nequi", r"nequi\.com"),
    ("Lulo Bank", r"lulobank"),
]

# ------------------------------------------------------------
# Categorias por palabras clave CONTENIDAS en el concepto.
# El orden es la prioridad. Las palabras de hasta 4 letras se buscan
# como palabra completa (para que "ica" no coincida con "publica");
# las demas se buscan como texto contenido.
# Se usan igual para extracto y para libro: asi el mismo concepto cae
# en la misma categoria aunque el banco y el contador lo nombren distinto.
# ------------------------------------------------------------
CATEGORIAS = [
    ("gmf", "GMF / 4x1000", [
        "gmf", "gravamen", "4x1000", "4 x 1000", "4 x mil", "4 por mil",
        "impto gobierno", "impuesto gobierno", "impuesto 4",
    ]),
    ("impuestos", "Impuestos", [
        "dian", "impuesto", "impuestos", "retencion", "retefuente",
        "reteica", "rete ica", "ica", "iva", "hacienda", "u.a.e",
        "direccion de impuestos", "industria y comercio", "predial",
        "tesoreria", "timbre",
    ]),
    ("iva_bancario", "IVA de servicios bancarios", ["iva"]),
    ("comision", "Comisiones y servicios bancarios", [
        "comision", "cuota de manejo", "cuota manejo", "servicio manejo",
        "manejo portal", "servicio pago", "servicio por pago",
        "servicio transf", "cobro", "costo", "mantenimiento", "tarifa",
        "cargo servicio", "cargo por", "sobregiro", "manejo tarj",
        "c manejo", "cuota plan", "plan canal", "chequera", "comis",
        "servicio pago de nomina", "servicio pago a",
    ]),
    ("rendimientos", "Rendimientos financieros", [
        "rendimiento", "interes", "intereses",
    ]),
    ("seguridad_social", "Seguridad social y parafiscales", [
        "compensar", "compensacion", "planilla", "pila", "seguridad social",
        "eps", "arl", "pension", "colpensiones", "sena", "icbf", "sura",
        "porvenir", "proteccion", "cafam", "comfama", "comfenalco",
        "comfandi", "parafiscal", "corporacion autorre", "fonc",
    ]),
    ("nomina", "Nómina", [
        "nomina", "nomin", "salario", "sueldo", "quincena", "prima",
    ]),
    ("proveedores", "Pagos a proveedores", [
        "proveedor", "prove", "pago prov", "pago a prov", "pago de prov",
    ]),
    ("servicios_publicos", "Servicios públicos", [
        "emcali", "empresas municipales", "epm", "acueducto", "energia",
        "gas natural", "claro", "movistar", "tigo", "comunicacion celular",
        "celula",
    ]),
    ("efectivo", "Efectivo", [
        "retiro", "deposito", "consignacion", "cajero", "efectivo",
    ]),
    ("tarjeta", "Compras con tarjeta", [
        "compra", "tarjeta", "tc visa", "mastercard", "visa",
    ]),
    ("transferencias", "Transferencias", [
        "transferencia", "transf", "trf", "ach", "interbanc", "pse",
        "llave", "envio", "abono", "pago", "dcto", "descuento",
    ]),
]

CATEGORIAS_BANCARIAS = ("gmf", "iva_bancario", "comision")
# Categorias especificas: permiten emparejar una partida del extracto con
# una de HELISA aunque el valor difiera (p. ej. pago DIAN registrado de
# menos). Las categorias genericas (transferencias, tarjeta, efectivo) no.
CATEGORIAS_ESPECIFICAS = (
    "impuestos", "seguridad_social", "nomina", "proveedores",
    "servicios_publicos",
)

ACCIONES_BANCARIAS = {
    "gmf": "Registrar GMF / 4x1000.",
    "iva_bancario": "Registrar IVA de servicios bancarios según soporte.",
    "comision": "Registrar gasto bancario por comisiones, sujeto a validar "
                "la cuenta contable.",
    "rendimientos": "Registrar ingreso por rendimientos financieros.",
}

PALABRAS_CABECERA = {
    "fecha", "valor", "saldo", "descripcion", "documento", "doc.", "oficina",
    "sucursal", "dcto.", "identificador", "ciudad", "clase de movimiento",
    "trans", "cod", "movimiento", "oficina/canal", "debito", "credito",
}
RE_RUIDO = re.compile(
    r"^(fin\s+estado|p[aá]gina|saldo\s+(anterior|actual|final|inicial)|"
    r"total\b|contin[uú]a|viene\b|van\b|resumen|nuevo\s+saldo|"
    r"cualquier\s+diferencia|este\s+producto|recuerde|fin\s+movimientos)",
    re.IGNORECASE,
)


# ------------------------------------------------------------
# Utilidades generales
# ------------------------------------------------------------

def texto_comparable(texto):
    texto = unicodedata.normalize("NFD", str(texto or ""))
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", texto).strip().lower()


def etiqueta_fecha(fecha):
    return f"{fecha.day:02d}-{ETIQUETA_MES[fecha.month - 1]}"


def etiqueta_dias(fechas):
    """[2 sep, 15 sep, 16 sep] -> '02, 15 y 16 sep'."""
    partes = []
    for (anio, mes) in sorted({(f.year, f.month) for f in fechas}):
        dias = sorted({f.day for f in fechas
                       if f.year == anio and f.month == mes})
        textos = [f"{d:02d}" for d in dias]
        lista = (", ".join(textos[:-1]) + " y " + textos[-1]
                 if len(textos) > 1 else textos[0])
        partes.append(f"{lista} {ETIQUETA_MES[mes - 1]}")
    return " / ".join(partes)


def ultimo_dia_mes(anio, mes):
    return calendar.monthrange(anio, mes)[1]


def crear_fecha(anio, mes, dia):
    try:
        return datetime.date(anio, mes, dia)
    except ValueError:
        return None


def descripcion_periodo(inicio, fin):
    meses = (fin.year - inicio.year) * 12 + fin.month - inicio.month + 1
    if meses == 1:
        tipo = "Mensual"
    elif meses == 3:
        tipo = "Trimestral"
    elif meses == 6:
        tipo = "Semestral"
    elif meses == 12:
        tipo = "Anual"
    else:
        tipo = f"{meses} meses"

    if meses == 1:
        rango = f"{ETIQUETA_MES[inicio.month - 1]}/{inicio.year}"
    else:
        rango = (f"{ETIQUETA_MES[inicio.month - 1]}"
                 f"–{ETIQUETA_MES[fin.month - 1]}/{fin.year}")

    return tipo, rango, meses


# ------------------------------------------------------------
# Importes: formatos 1,234.56 / 1.234,56 / signo antes, despues o $-
# ------------------------------------------------------------

RE_DINERO = re.compile(
    r"(?P<s1>[-+]?)\s*\$?\s*(?P<s2>[-+]?)(?P<n>\d[\d.,]*|[.,]\d{2})\s*"
    r"(?P<s3>[-+]?)"
)


def interpretar_dinero(texto, decimal=".", exigir_decimales=True):
    """'$ 630,309.07-' -> Decimal('-630309.07'). None si no es un importe."""
    coincidencia = RE_DINERO.fullmatch(str(texto).strip())

    if not coincidencia:
        return None

    signo = (coincidencia.group("s1") or coincidencia.group("s2")
             or coincidencia.group("s3") or "")
    cuerpo = coincidencia.group("n")
    miles = "," if decimal == "." else "."

    if re.search(r"[" + re.escape(decimal) + r"]\d{2}$", cuerpo):
        entero, decimales = cuerpo[:-3], cuerpo[-2:]
    elif exigir_decimales:
        return None
    else:
        entero, decimales = cuerpo, "00"

    if entero == "":
        entero = "0"            # '.24' (algunos bancos omiten el cero)
    if not entero.isdigit() and not re.fullmatch(
        r"\d{1,3}(?:" + re.escape(miles) + r"\d{3})*", entero
    ):
        return None

    valor = Decimal(entero.replace(miles, "") + "." + decimales)
    return -valor if signo == "-" else valor


def tiene_signo_explicito(texto):
    return bool(re.search(r"[-+]", str(texto)))


def detectar_decimal(textos):
    puntos = comas = 0

    for texto in textos:
        limpio = texto.strip().strip("-+").replace("$", "")
        if not re.fullmatch(r"[\d.,]+", limpio):
            continue
        if re.search(r"\.\d{2}$", limpio):
            puntos += 1
        elif re.search(r",\d{2}$", limpio):
            comas += 1

    return "," if comas > puntos else "."


def dividir_segmentos(palabras, hueco=5.5):
    """Agrupa palabras contiguas; un hueco grande separa columnas."""
    segmentos = []

    for palabra in palabras:
        if segmentos and palabra["x0"] - segmentos[-1][-1]["x1"] <= hueco:
            segmentos[-1].append(palabra)
        else:
            segmentos.append([palabra])

    return segmentos


# ------------------------------------------------------------
# Encabezado del extracto: banco, cuenta, periodo, resumen de saldos
# ------------------------------------------------------------

def detectar_banco(texto):
    claro = texto_comparable(texto)
    mejor = None

    for nombre, patron in BANCOS_CONOCIDOS:
        coincidencias = list(re.finditer(patron, claro))
        if coincidencias:
            puntaje = (len(coincidencias), -coincidencias[0].start())
            if mejor is None or puntaje > mejor[0]:
                mejor = (puntaje, nombre)

    return mejor[1] if mejor else "Banco no reconocido"


def detectar_cuenta(texto):
    patrones = [
        r"cuenta\s+(?:de\s+)?(?:ahorros|corriente)\s*\n?\s*"
        r"(\d[\d \-]{6,22}\d)(?!\d)",
        r"n[uú]mero(?:\s+de\s+cuenta)?\s*:?\s*(\d[\d \-]{5,22}\d)",
        r"cuenta\s+n[uú]mero\s*:?\s*(\d[\d \-]{5,22}\d)",
        r"nro\.?\s*cuenta\s*:?\s*(\d[\d \-]{5,22}\d)",
        r"dep[oó]sito\s+ordinario\s*\n?\s*(\d[\d \-]{5,22}\d)",
        r"cta\.?\s*(?:no\.?)?\s*(\d[\d \-]{5,22}\d)",
    ]

    for patron in patrones:
        coincidencia = re.search(patron, texto, re.IGNORECASE)
        if coincidencia:
            digitos = re.sub(r"\D", "", coincidencia.group(1))
            if len(digitos) >= 6:
                return digitos

    return None


def detectar_tipo_cuenta(texto):
    claro = texto_comparable(texto[:3000])

    if "ahorro" in claro or "deposito ordinario" in claro:
        return "Ahorros"
    if "corriente" in claro:
        return "Corriente"

    return ""


def _fecha_texto_mes(dia, nombre_mes, anio):
    mes = MESES_COMPLETOS.get(texto_comparable(nombre_mes))
    return crear_fecha(int(anio), mes, int(dia)) if mes else None


def detectar_periodo(texto):
    """Devuelve (inicio, fin) o None. Prueba los formatos mas comunes."""
    plano = re.sub(r"\s+", " ", texto)
    nombres = "|".join(MESES_COMPLETOS)

    # DESDE: 2026/08/31 HASTA: 2026/09/30
    m = re.search(
        r"desde:?\s*(\d{4})[/\-](\d{2})[/\-](\d{2})\s*hasta:?\s*"
        r"(\d{4})[/\-](\d{2})[/\-](\d{2})", plano, re.I)
    if m:
        a = crear_fecha(int(m[1]), int(m[2]), int(m[3]))
        b = crear_fecha(int(m[4]), int(m[5]), int(m[6]))
        if a and b:
            return a, b

    # Desde 1 de septiembre de 2026 hasta 30 de septiembre de 2026
    m = re.search(
        rf"desde:?\s*(\d{{1,2}})\s+de\s+({nombres})\s+de\s+(\d{{4}})\s+"
        rf"hasta:?\s*(\d{{1,2}})\s+de\s+({nombres})\s+de\s+(\d{{4}})",
        plano, re.I)
    if m:
        a = _fecha_texto_mes(m[1], m[2], m[3])
        b = _fecha_texto_mes(m[4], m[5], m[6])
        if a and b:
            return a, b

    # Del 01/09/2026 al 30/09/2026
    m = re.search(
        r"(\d{1,2})/(\d{1,2})/(\d{4})\s*(?:al|a|-|hasta)\s*"
        r"(\d{1,2})/(\d{1,2})/(\d{4})", plano, re.I)
    if m:
        a = crear_fecha(int(m[3]), int(m[2]), int(m[1]))
        b = crear_fecha(int(m[6]), int(m[5]), int(m[4]))
        if a and b and a < b:
            return a, b

    # Enero - Marzo 2026   (extractos trimestrales)
    m = re.search(
        rf"({nombres})\s*[-–a]\s*({nombres})\s+(?:de\s+)?(\d{{4}})",
        plano, re.I)
    if m:
        m1 = MESES_COMPLETOS[texto_comparable(m[1])]
        m2 = MESES_COMPLETOS[texto_comparable(m[2])]
        anio = int(m[3])
        if m1 <= m2:
            return (datetime.date(anio, m1, 1),
                    datetime.date(anio, m2, ultimo_dia_mes(anio, m2)))

    # INFORME DEL MES: SEPTIEMBRE /2026   |   Septiembre 2026
    m = re.search(
        rf"(?:mes|per[ií]odo|periodo)\s*:?\s*({nombres})\s*(?:de|/|-)?\s*"
        rf"(\d{{4}})", plano, re.I)
    if m:
        mes = MESES_COMPLETOS[texto_comparable(m[1])]
        anio = int(m[2])
        return (datetime.date(anio, mes, 1),
                datetime.date(anio, mes, ultimo_dia_mes(anio, mes)))

    return None


ETIQUETAS_RESUMEN = {
    "saldo_inicial": r"(?:saldo\s+anterior|saldo\s+inicial)",
    "creditos": (r"(?:total\s+(?:\d+\s+)?abonos|m[aá]s\s+cr[eé]ditos|"
                 r"total\s+cr[eé]ditos|total\s+dep[oó]sitos)"),
    "debitos": (r"(?:total\s+(?:\d+\s+)?cargos|menos\s+d[eé]bitos|"
                r"total\s+d[eé]bitos)"),
    "saldo_final": r"(?:saldo\s+actual|nuevo\s+saldo|saldo\s+final)",
}
ETIQUETAS_EXTRAS = {
    "iva": r"total\s+iva",
    "gmf": r"total\s+4\s?x\s?1000(?:\s+gmf)?|total\s+gmf",
    "retencion": r"total\s+retenci[oó]n|retefuente",
    "intereses": (r"total\s+intereses|valor\s+intereses\s+pagados|"
                  r"valor\s+de\s+intereses\s+pagados"),
}
MONEDA_TEXTO = r"[-+]?\s*\$?\s*[-+]?\d[\d.,]*"


def leer_resumen_saldos(texto, decimal):
    datos = {}

    for clave, etiqueta in {**ETIQUETAS_RESUMEN, **ETIQUETAS_EXTRAS}.items():
        coincidencia = re.search(
            r"(?:" + etiqueta + r")\s*:?[^\d\-\$\n]{0,25}("
            + MONEDA_TEXTO + r")",
            texto, re.IGNORECASE)
        if coincidencia:
            valor = interpretar_dinero(
                coincidencia.group(1), decimal, exigir_decimales=False)
            if valor is not None:
                datos[clave] = valor

    return datos


# ------------------------------------------------------------
# Lectura generica del extracto bancario (PDF)
# ------------------------------------------------------------

RE_FECHA_BARRAS = re.compile(r"^(\d{1,2})[/\-](\d{1,2})(?:[/\-](\d{2,4}))?$")
RE_FECHA_ISO = re.compile(r"^(\d{4})[/\-](\d{1,2})[/\-](\d{1,2})$")


def leer_fecha_inicial(textos):
    """(dia, mes, anio|None, palabras_usadas) o None."""
    if not textos:
        return None

    m = RE_FECHA_ISO.match(textos[0])
    if m:
        return int(m[3]), int(m[2]), int(m[1]), 1

    m = RE_FECHA_BARRAS.match(textos[0])
    if m:
        anio = m[3]
        if anio:
            anio = int(anio) if len(anio) == 4 else 2000 + int(anio)
        return int(m[1]), int(m[2]), anio or None, 1

    # Formato "01 09 $ 630,309.07-" (dia y mes en columnas separadas) y
    # "06 08 CobroTransferencia... $1,000.00- $9,000,000.00+" (cuenta
    # corriente Davivienda: la descripcion va antes del valor).
    if (len(textos) >= 3 and re.fullmatch(r"\d{1,2}", textos[0])
            and re.fullmatch(r"\d{1,2}", textos[1])
            and (textos[2][:1] in "$-+"
                 or re.match(r"[^\W\d_]{3,}", textos[2]))):
        return int(textos[0]), int(textos[1]), None, 2

    return None


def es_linea_cabecera(texto):
    claro = texto_comparable(texto)
    aciertos = sum(1 for p in PALABRAS_CABECERA if re.search(
        r"(?<![a-z])" + re.escape(p) + r"(?![a-z])", claro))
    return aciertos >= 2


def limpiar_descripcion(texto):
    texto = re.sub(r"(?:\s-){3,}.*$", "", texto)       # "- - - FIN MOVIM..."
    texto = re.sub(r"\s*fin\s+movimientos.*$", "", texto, flags=re.I)
    return re.sub(r"\s+", " ", texto).strip()


def percentil(valores, fraccion):
    valores = sorted(valores)
    return valores[min(int(len(valores) * fraccion), len(valores) - 1)]


def detectar_filas_pagina(pagina, decimal):
    """Marca las lineas que son movimientos (fecha + importes)."""
    lineas = agrupar_lineas(palabras_pagina(pagina))
    filas = {}

    for indice, linea in enumerate(lineas):
        palabras = linea["palabras"]
        textos = [w["text"] for w in palabras]
        fecha = leer_fecha_inicial(textos)

        if not fecha:
            continue

        dia, mes, anio, usadas = fecha
        if not (1 <= dia <= 31 and 1 <= mes <= 12):
            continue

        resto = palabras[usadas:]
        importes = []
        otras = []

        for palabra in resto:
            valor = interpretar_dinero(palabra["text"], decimal)
            if valor is not None:
                importes.append((palabra, valor))
            else:
                otras.append(palabra)

        if not importes:
            continue

        # Descripcion: primer bloque de texto con una palabra alfabetica
        # de 3 letras o mas (los codigos e identificadores mezclan digitos).
        descripcion, siguiente_x, x_inicio = [], None, None
        segmentos = dividir_segmentos(otras)
        for posicion, segmento in enumerate(segmentos):
            if any(re.fullmatch(r"[^\W\d_]{3,}", w["text"])
                   for w in segmento):
                descripcion = [w["text"] for w in segmento]
                x_inicio = segmento[0]["x0"]
                derecha = [s[0]["x0"] for s in segmentos[posicion + 1:]]
                derecha += [p["x0"] for p, _ in importes
                            if p["x0"] > segmento[-1]["x1"]]
                siguiente_x = min(derecha) if derecha else None
                break

        filas[indice] = {
            "dia": dia, "mes": mes, "anio": anio,
            "importes": importes,
            "descripcion": descripcion,
            "x_descripcion": x_inicio,
            "x_siguiente": siguiente_x,
            "top": linea["top"],
            "texto_origen": linea["texto"],
        }

    return lineas, filas


def adjuntar_continuaciones(lineas, filas, x_desc, x_sig):
    """
    Une las lineas de texto que continuan la descripcion de un movimiento.
    Se agrupan en bloques separados por huecos verticales grandes: dentro
    de un bloque el texto pertenece a la ultima fila anterior (o a la
    primera si el texto va arriba, como en extractos centrados).
    """
    if not filas:
        return

    tops = [l["top"] for l in lineas]
    saltos = [b - a for a, b in zip(tops, tops[1:]) if b - a > 1]
    umbral = max(2.0 * percentil(saltos, 0.10), 12) if len(saltos) > 4 else 20

    bloques, actual = [], []
    for indice, linea in enumerate(lineas):
        if actual and linea["top"] - lineas[actual[-1]]["top"] > umbral:
            bloques.append(actual)
            actual = []
        actual.append(indice)
    if actual:
        bloques.append(actual)

    for bloque in bloques:
        if not any(i in filas for i in bloque):
            continue

        ultima, pendientes = None, []

        for indice in bloque:
            if indice in filas:
                ultima = filas[indice]
                for texto in pendientes:
                    ultima["descripcion"].extend(texto)
                pendientes = []
                continue

            linea = lineas[indice]
            if es_linea_cabecera(linea["texto"]) or RE_RUIDO.search(
                    linea["texto"]):
                continue

            palabras = [
                w["text"] for w in linea["palabras"]
                if (x_desc is None or w["x0"] >= x_desc - 6)
                and (x_sig is None or w["x0"] < x_sig - 2)
            ]
            if not palabras:
                continue

            if ultima is None:
                pendientes.append(palabras)
            elif len(ultima["descripcion"]) < 40:
                ultima["descripcion"].extend(palabras)


def asignar_fechas(filas, periodo, anio_defecto):
    """Completa el anio de cada fila a partir del periodo del extracto."""
    previa = None

    for fila in filas:
        if fila["anio"]:
            fecha = crear_fecha(fila["anio"], fila["mes"], fila["dia"])
        elif periodo:
            fecha = None
            for anio in sorted({periodo[0].year, periodo[1].year}):
                candidata = crear_fecha(anio, fila["mes"], fila["dia"])
                if candidata and (periodo[0] - datetime.timedelta(days=35)
                                  <= candidata
                                  <= periodo[1] + datetime.timedelta(days=35)):
                    fecha = candidata
                    break
            fecha = fecha or crear_fecha(
                periodo[1].year, fila["mes"], fila["dia"])
        else:
            anio = (previa.year if previa else anio_defecto)
            fecha = crear_fecha(anio, fila["mes"], fila["dia"])
            if fecha and previa and (previa - fecha).days > 180:
                fecha = crear_fecha(anio + 1, fila["mes"], fila["dia"])

        fila["fecha"] = fecha
        previa = fecha or previa


def leer_extracto_pdf(contenido, anio_defecto=None):
    try:
        import pdfplumber
    except ImportError as error:
        raise RuntimeError(
            "Falta la libreria pdfplumber. Instalala con: "
            "pip install pdfplumber"
        ) from error

    anio_defecto = anio_defecto or datetime.date.today().year

    try:
        with pdfplumber.open(io.BytesIO(contenido)) as pdf:
            texto = "\n".join(
                (p.extract_text(x_tolerance=1.5) or "") for p in pdf.pages)

            if len(texto.strip()) < 50:
                raise ValueError(
                    "El PDF no contiene texto seleccionable (parece un "
                    "escaneo). Solicita el extracto digital al banco.")

            todas = [w["text"] for p in pdf.pages for w in palabras_pagina(p)]
            decimal = detectar_decimal(todas)

            paginas = [detectar_filas_pagina(p, decimal) for p in pdf.pages]
            # Numero de pagina del PDF: permite ir directo al movimiento.
            for numero_pagina, (_, filas_pagina) in enumerate(paginas, 1):
                for fila in filas_pagina.values():
                    fila["pagina"] = numero_pagina
    except ValueError:
        raise
    except Exception as error:
        raise ValueError(
            "No se pudo leer el PDF del extracto. Verifica que sea el "
            "archivo original del banco, sin contraseña ni daños."
        ) from error

    filas_totales = [f for _, filas in paginas for f in filas.values()]
    if not filas_totales:
        raise ValueError(
            "No se encontraron movimientos en el extracto. El documento no "
            "tiene una tabla con fecha e importe por fila.")

    x_desc_lista = [round(f["x_descripcion"]) for f in filas_totales
                    if f["x_descripcion"] is not None]
    x_sig_lista = [f["x_siguiente"] for f in filas_totales
                   if f["x_siguiente"] is not None]
    x_desc = Counter(x_desc_lista).most_common(1)[0][0] if x_desc_lista \
        else None
    x_sig = sorted(x_sig_lista)[len(x_sig_lista) // 2] if x_sig_lista \
        else None

    for lineas, filas in paginas:
        adjuntar_continuaciones(lineas, filas, x_desc, x_sig)

    resumen = leer_resumen_saldos(texto, decimal)
    periodo = detectar_periodo(texto)

    if periodo and periodo[0].day == ultimo_dia_mes(
            periodo[0].year, periodo[0].month) and periodo[1] > periodo[0]:
        # "DESDE 31/08 HASTA 30/09": el 31/08 es el cierre del mes anterior.
        periodo = (periodo[0] + datetime.timedelta(days=1), periodo[1])

    filas = [f for _, filas in paginas for _, f in sorted(filas.items())]
    asignar_fechas(filas, periodo, anio_defecto)
    filas = [f for f in filas if f["fecha"]]

    # Con saldo corrido (2 importes por fila) el signo sale de la diferencia
    # entre saldos; si no, del signo impreso junto al valor.
    con_saldo = sum(1 for f in filas if len(f["importes"]) >= 2)
    saldo_corrido = con_saldo >= max(1, int(len(filas) * 0.6))

    movimientos, inconsistentes = [], 0
    anterior = resumen.get("saldo_inicial")

    for fila in filas:
        if saldo_corrido and len(fila["importes"]) >= 2:
            (_, valor_token), (_, saldo) = fila["importes"][-2:]
            if anterior is None:
                anterior = saldo - valor_token
            delta = (saldo - anterior).quantize(CENTAVO)
            if abs(delta) == abs(valor_token):
                valor = delta
            else:
                valor = valor_token
                inconsistentes += 1
            anterior = saldo
        else:
            valor, saldo = fila["importes"][0][1], None

        movimientos.append({
            "fecha": fila["fecha"],
            "descripcion": limpiar_descripcion(" ".join(
                fila["descripcion"])) or "(sin descripción)",
            "valor": valor.quantize(CENTAVO),
            "saldo": saldo,
            "pagina": fila.get("pagina"),
            "ubicacion": (f"Pág. {fila['pagina']}" if fila.get("pagina")
                          else ""),
        })

    if not periodo:
        fechas = [m["fecha"] for m in movimientos]
        periodo = (min(fechas).replace(day=1),
                   max(fechas).replace(
                       day=ultimo_dia_mes(max(fechas).year,
                                          max(fechas).month)))

    resumen.setdefault(
        "saldo_inicial",
        (movimientos[0]["saldo"] - movimientos[0]["valor"])
        if saldo_corrido and movimientos[0]["saldo"] is not None else None)
    if resumen.get("saldo_final") is None and saldo_corrido:
        resumen["saldo_final"] = movimientos[-1]["saldo"]

    for clave in ("creditos", "debitos"):
        if resumen.get(clave) is not None:
            resumen[clave] = abs(resumen[clave])

    return {
        "banco": detectar_banco(texto),
        "tipo_cuenta": detectar_tipo_cuenta(texto),
        "cuenta": detectar_cuenta(texto),
        "periodo": periodo,
        "resumen": resumen,
        "movimientos": movimientos,
        "saldo_corrido": saldo_corrido,
        "inconsistentes": inconsistentes,
        "decimal": decimal,
        "formato": "PDF",
    }


# ------------------------------------------------------------
# Lectura del informe de bancos de HELISA (PDF)
# ------------------------------------------------------------

# v6.5: el mes puede venir en letras (01/OCT/2026, Libro de Caja Bancos) o
# en numero (01/10/2026, "Libro Auxiliar" de HELISA NIIF, sin tercero).
# v6.9.2: el numero del comprobante puede terminar en letras (EMPRESA B, cuenta
# Bold: "PE 00000000058B") y la fecha puede venir pegada al tipo
# ("03/OCT/2026PE"). v6.10.1: o en guion y consecutivo ("PE
# 0000001234-1").
RE_HELISA_FILA = re.compile(
    r"^(\d{1,2})/\s*([A-Za-z]{3,4}|\d{1,2})/\s*(\d{4})\s*([A-Z]{1,5})\s+"
    r"(\d+[A-Z]{0,3}(?:-[0-9A-Z]{1,4})?)\s+(?:(\d+)\s+)?(.*?)\s*"
    r"(-?[\d,]+\.\d{2})\s+"
    r"(-?[\d,]+\.\d{2})\s+(-?[\d,]+\.\d{2})\s*$"
)
RE_HELISA_INICIO_FECHA = re.compile(
    r"^\d{1,2}/\s*([A-Za-z]{3,4}|\d{1,2})/\s*\d{4}")
RE_HELISA_SECCION = re.compile(
    r"^(.*?)\s*saldo\s+inicial(?:\s+a\s+(\d{1,2})/\s*([A-Za-z]{3,4}|\d{1,2})/"
    r"\s*(\d{4}))?\s+(-?[\d,]+\.\d{2})", re.IGNORECASE)
RE_HELISA_PERIODO = re.compile(
    r"(?:desde|\(de)\s+(\d{1,2})/\s*([A-Za-z]{3,4}|\d{1,2})/\s*(\d{4})\s+"
    r"(?:a|hasta)\s+(\d{1,2})/\s*([A-Za-z]{3,4}|\d{1,2})/\s*(\d{4})",
    re.IGNORECASE)


def _mes_abreviado(texto):
    texto = str(texto or "").strip()
    if texto.isdigit():
        return int(texto) if 1 <= int(texto) <= 12 else None
    return MESES_ABREVIADOS.get(texto_comparable(texto)[:4]) or \
        MESES_ABREVIADOS.get(texto_comparable(texto)[:3])


def es_libro_helisa(texto):
    claro = texto_comparable(texto)
    return bool(re.search(
        r"libro\s+de\s+caja\s+bancos|libro\s+auxiliar|saldo\s+inicial\s+a\s+"
        r"\d{1,2}/", claro))


def leer_libro_helisa(contenido):
    try:
        import pdfplumber
    except ImportError as error:
        raise RuntimeError(
            "Falta la libreria pdfplumber. Instalala con: "
            "pip install pdfplumber") from error

    try:
        with pdfplumber.open(io.BytesIO(contenido)) as pdf:
            lineas, paginas_linea = [], []
            for numero_pagina, pagina in enumerate(pdf.pages, start=1):
                propias = (pagina.extract_text(x_tolerance=1.5)
                           or "").splitlines()
                lineas.extend(propias)
                paginas_linea.extend([numero_pagina] * len(propias))
    except Exception as error:
        raise ValueError(
            "No se pudo leer el PDF de HELISA. Verifica que sea HELISA "
            "original, sin contraseña ni daños.") from error

    return procesar_lineas_libro(
        lineas, [f"Pág. {n}" for n in paginas_linea], paginas_linea, "PDF")


def procesar_lineas_libro(lineas, ubicaciones, paginas=None, formato="PDF"):
    """
    Interpreta las lineas de texto del informe de bancos de HELISA
    (vengan de un PDF o de las filas de un Excel convertidas a texto).
    """
    paginas = paginas or [None] * len(lineas)
    texto = "\n".join(lineas)
    if not es_libro_helisa(texto):
        raise ValueError(
            "El documento cargado como HELISA no parece el informe de "
            "bancos de HELISA (no se encontró 'Libro de Caja Bancos', "
            "'Libro Auxiliar' ni 'Saldo Inicial').")

    empresa = lineas[0].strip() if lineas else ""
    nit = re.search(r"nit:?\s*([\d.,\- ]+\d)", texto, re.IGNORECASE)

    periodo = None
    m = RE_HELISA_PERIODO.search(texto)
    if m:
        mes1, mes2 = _mes_abreviado(m[2]), _mes_abreviado(m[5])
        if mes1 and mes2:
            periodo = (crear_fecha(int(m[3]), mes1, int(m[1])),
                       crear_fecha(int(m[6]), mes2, int(m[4])))

    secciones, actual = [], None
    no_leidas = []

    for linea, numero_pagina, ubicacion in zip(lineas, paginas,
                                               ubicaciones):
        limpia = linea.strip()

        m = RE_HELISA_SECCION.match(limpia)
        if m:
            etiqueta = m[1].strip()
            digitos = re.findall(r"\d[\d\-]{4,}\d", etiqueta)
            clave = re.sub(r"\D", "", digitos[-1]) if digitos else etiqueta
            existente = next((s for s in secciones if s["clave"] == clave),
                             None)
            if existente:
                actual = existente
            else:
                mes = _mes_abreviado(m[3]) if m[3] else None
                actual = {
                    "clave": clave,
                    "etiqueta": etiqueta,
                    "cuenta": clave if digitos else "",
                    "saldo_inicial": interpretar_dinero(
                        m[5].replace(",", ""), ".", True),
                    # "Libro Auxiliar" no trae la fecha: inicio del periodo.
                    "fecha_saldo_inicial": (crear_fecha(
                        int(m[4]), mes, int(m[2])) if mes else
                        (periodo[0] if periodo else None)),
                    "movimientos": [],
                }
                secciones.append(actual)
            continue

        m = RE_HELISA_FILA.match(limpia)
        if not m and RE_HELISA_INICIO_FECHA.match(limpia) and \
                re.search(r"[\d,]+\.\d{2}\s*$", limpia):
            # v6.10.1: linea de movimiento que no se pudo interpretar: se
            # avisa (nunca se pierde en silencio).
            no_leidas.append(f"{ubicacion}: «{limpia}»")
        if m:
            mes = _mes_abreviado(m[2])
            fecha = crear_fecha(int(m[3]), mes, int(m[1])) if mes else None
            if not fecha:
                continue

            if actual is None:
                actual = {"clave": "", "etiqueta": "", "cuenta": "",
                          "saldo_inicial": None,
                          "fecha_saldo_inicial": None, "movimientos": []}
                secciones.append(actual)

            debito = Decimal(m[8].replace(",", ""))
            credito = Decimal(m[9].replace(",", ""))
            actual["movimientos"].append({
                "fecha": fecha,
                "tipo": m[4],
                "numero": m[5].lstrip("0") or "0",
                "tercero": re.sub(r"\s+", " ", m[7]).strip(),
                "debito": debito,
                "credito": credito,
                # Para el banco: el debito de HELISA es un ingreso.
                "valor": (debito - credito).quantize(CENTAVO),
                "saldo": Decimal(m[10].replace(",", "")),
                "pagina": numero_pagina,
                "ubicacion": ubicacion,
            })

    secciones = [s for s in secciones if s["movimientos"] or
                 s["saldo_inicial"] is not None]
    if not secciones:
        raise ValueError(
            "No se encontraron movimientos en HELISA. Verifica "
            "que sea el 'Libro de Caja Bancos' con la tabla de movimientos.")

    for seccion in secciones:
        movs = seccion["movimientos"]
        seccion["saldo_final"] = movs[-1]["saldo"] if movs else \
            seccion["saldo_inicial"]
        # Control interno: el saldo corrido de HELISA debe cuadrar.
        previo = seccion["saldo_inicial"]
        seccion["inconsistentes"] = 0
        for mov in movs:
            if previo is not None and abs(
                    previo + mov["valor"] - mov["saldo"]) > 0:
                seccion["inconsistentes"] += 1
            previo = mov["saldo"]

    return {
        "empresa": empresa,
        "nit": nit.group(1).strip() if nit else "",
        "periodo": periodo,
        "secciones": secciones,
        "formato": formato,
        "no_leidas": no_leidas,
    }


def elegir_seccion_libro(libro, cuenta_extracto):
    """Devuelve (seccion, aviso). Busca por coincidencia del numero de cuenta."""
    secciones = libro["secciones"]

    if cuenta_extracto:
        for seccion in secciones:
            numero_cuenta = seccion["cuenta"]
            if numero_cuenta and len(min(numero_cuenta, cuenta_extracto,
                                         key=len)) >= 6 \
                    and (numero_cuenta.endswith(cuenta_extracto)
                         or cuenta_extracto.endswith(numero_cuenta)):
                return seccion, None

    if len(secciones) == 1:
        aviso = ("No se pudo confirmar que la cuenta de HELISA "
                 f"({secciones[0]['etiqueta'] or 'sin nombre'}) corresponda "
                 f"a la del extracto ({cuenta_extracto or 'no identificada'})."
                 )
        if cuenta_extracto and secciones[0]["cuenta"]:
            aviso = (f"La cuenta de HELISA ({secciones[0]['cuenta']}) no "
                     f"coincide con la del extracto ({cuenta_extracto}).")
        return secciones[0], aviso

    nombres = ", ".join(s["etiqueta"] or "sin nombre" for s in secciones)
    raise ValueError(
        "El archivo de HELISA tiene varias cuentas y ninguna coincide con la "
        f"del extracto ({cuenta_extracto or 'no identificada'}). Cuentas "
        f"de HELISA: {nombres}.")


# ------------------------------------------------------------
# Clasificacion por palabras clave
# ------------------------------------------------------------

def _contiene(claro, palabra):
    palabra = texto_comparable(palabra)
    if len(palabra) <= 4:
        # Siglas cortas (iva, ica, dian, gmf): palabra completa.
        return re.search(
            r"(?<![a-z0-9])" + re.escape(palabra) + r"(?![a-z0-9])",
            claro) is not None
    # Resto: al inicio de palabra, admite sufijos (interes -> intereses).
    return re.search(r"(?<![a-z0-9])" + re.escape(palabra), claro) is not None


def construir_categorias(extra=None):
    """Copia de CATEGORIAS con palabras clave adicionales del usuario."""
    extra = extra or {}
    resultado = []

    for identificador, nombre, palabras in CATEGORIAS:
        adicionales = [p.strip() for p in extra.get(identificador, [])
                       if p.strip()]
        resultado.append((identificador, nombre, list(palabras) + adicionales))

    return resultado


def separar_palabras_pegadas(texto):
    """'IVAporServicios' -> 'IVA por Servicios' (extractos Davivienda que
    traen el concepto sin espacios)."""
    texto = str(texto or "")
    texto = re.sub(r"(?<=[a-záéíóúñ])(?=[A-ZÁÉÍÓÚÑ])", " ", texto)
    texto = re.sub(r"\b(IVA|GMF|ACH|PSE|ICA)(?=[a-záéíóúñ])", r"\1 ", texto)
    return texto


def clasificar_concepto(texto, valor, categorias):
    claro = texto_comparable(separar_palabras_pegadas(texto))

    for identificador, nombre, palabras in categorias:
        if identificador == "iva_bancario":
            if not _contiene(claro, "iva"):
                continue
        elif not any(_contiene(claro, p) for p in palabras):
            continue

        # "Impuestos" incluye la palabra IVA, pero un cobro de IVA del
        # banco (sin DIAN/impuesto en el concepto) es un gasto bancario.
        if identificador == "impuestos" and not any(
                _contiene(claro, p) for p in palabras if p != "iva"):
            continue

        # "Pago a proveedores/nomina" en un abono es dinero recibido.
        if identificador in ("nomina", "proveedores", "seguridad_social") \
                and valor > 0:
            continue

        # Intereses cobrados (valor negativo) son un cargo, no un ingreso.
        if identificador == "rendimientos" and valor < 0:
            return "comision", "Comisiones y servicios bancarios"

        return identificador, nombre

    return "otros", "Otros movimientos"


def es_cargo_bancario(identificador):
    return identificador in CATEGORIAS_BANCARIAS


def es_registro_bancario_libro(mov, nombre_banco):
    tercero = texto_comparable(mov["tercero"])
    return (mov["tipo"] in ("NB", "ND", "NC")
            or "banco" in tercero
            or (nombre_banco and texto_comparable(nombre_banco) in tercero))
