"""Parametros y reglas de alerta de la conciliacion DIAN (colores, conceptos
FV/FC/DSE/NC/ND/NCV/NDV/NADSE, alertas por documento).

Depende de: gmya.comun.numeros
"""

from collections import defaultdict
from itertools import combinations

from gmya.comun.numeros import numero


# ------------------------------------------------------------
# Parametros por defecto (todos editables desde la interfaz)
# ------------------------------------------------------------
PARAMETROS_DIAN_BASE = {
    # Conceptos que se concilian. "helisa" indica el informe de HELISA
    # que se compara: "resumen" (Comprobante de diario - Resumen) o
    # "detalle" (Comprobante diario - Detalle, documento por documento).
    "conceptos": [
        {
            "clave": "FV",
            "nombre": "Facturas electrónicas de venta",
            "grupo": "Emitido",
            # v6.5: tambien las de exportacion (en HELISA son FEV igual).
            "tipos": ["Factura electrónica",
                      "Factura electrónica de contingencia",
                      "Factura electrónica de exportación"],
            "helisa": "resumen",
            "documento_helisa": "FEV - FACTURA ELECTRONICA DE VENTA",
            "cuentas_iva": ["2408"],
            # HELISA incluye el descuento comercial (530535) en el total
            # del documento; la DIAN reporta la factura ya neta.
            "ajustes": ["DESCUENTOS COMERCIALES"],
            "restar_descuentos": True,
        },
        {
            # v5.8: notas credito de ventas (devoluciones / descuentos a
            # clientes). HELISA: NCV. El IVA generado se reversa al debito.
            "clave": "NCV",
            "nombre": "Notas crédito de ventas",
            "grupo": "Emitido",
            "tipos": ["Nota de crédito electrónica"],
            "helisa": "resumen",
            "documento_helisa": "NCV - NOTA CREDITO VENTAS",
            "cuentas_iva": ["2408"],
            "naturaleza_iva": "debito",
            "ajustes": ["AJUSTE AL PESO"],
        },
        {
            # v5.8: notas debito de ventas (mayor valor a clientes). HELISA:
            # NDV. IVA generado al credito, como la factura de venta.
            "clave": "NDV",
            "nombre": "Notas débito de ventas",
            "grupo": "Emitido",
            "tipos": ["Nota de débito electrónica"],
            "helisa": "resumen",
            "documento_helisa": "NDV - NOTA DEBITO VENTAS",
            "cuentas_iva": ["2408"],
            "naturaleza_iva": "credito",
            "ajustes": ["AJUSTE AL PESO"],
        },
        {
            "clave": "DSE",
            "nombre": "Documentos soporte con no obligados",
            "grupo": "Emitido",
            "tipos": ["Documento soporte con no obligados"],
            "helisa": "resumen",
            "documento_helisa": "DSE - DOCUMENTO SOPORTE ELECTRONICO",
            "cuentas_iva": [],
            "ajustes": ["AJUSTE AL PESO"],
        },
        {
            # v5.8: notas de ajuste al documento soporte (reversan total o
            # parcialmente un DSE). HELISA: NADSE. IVA al credito.
            "clave": "NADSE",
            "nombre": "Notas de ajuste de documento soporte",
            "grupo": "Emitido",
            "tipos": ["Nota de ajuste*"],
            "helisa": "resumen",
            "documento_helisa": "NADSE - NOTA DE AJUSTE DOCUMENTO SOPORTE",
            "cuentas_iva": ["2408"],
            "naturaleza_iva": "credito",
            "ajustes": ["AJUSTE AL PESO"],
        },
        {
            "clave": "NC",
            "nombre": "Notas crédito de proveedores",
            "grupo": "Recibido",
            "tipos": ["Nota de crédito electrónica"],
            "helisa": "resumen",
            "documento_helisa": "NDC - NOTA DEBITO COMPRAS",
            "cuentas_iva": [],
            "ajustes": [],
        },
        {
            "clave": "FC",
            "nombre": "Facturas de compra",
            "grupo": "Recibido",
            # "*" al final = cualquier tipo que empiece asi (Documento
            # equivalente POS, Documento equivalente electronico ...).
            "tipos": ["Factura electrónica",
                      "Factura electrónica de contingencia",
                      "Documento equivalente*"],
            "helisa": "detalle",
            "documento_helisa": "FC - FACTURA DE COMPRA",
            "cuentas_iva": ["IVA"],
            "ajustes": [],
        },
    ],
    # Detalle de compras (FC): como se reconocen las cuentas.
    # IVA: cuentas cuyo nombre EMPIEZA por estas palabras o cuyo codigo
    # empieza por estos codigos (2408 = IVA en el PUC).
    "palabras_iva": ["IVA", "2408"],
    "palabras_excluir_iva": ["RETE", "RETEN"],
    "palabras_consumo": ["IMPUESTO AL CONSUMO", "IMPOCONSUMO"],
    "palabras_no_deducible": ["NO DEDUCIBLE"],
    # Cuentas de descuento comercial en ventas (codigo o nombre).
    # v6.9: tambien el descuento a pie de factura (DUMA: 417601 DESCUENTO A
    # PIE DE FACTURA). La DIAN reporta la factura neta; igual se compara
    # con y sin descuento y se toma el que cuadre exacto con la DIAN.
    "palabras_descuento": ["530535", "DESCUENTOS COMERCIALES",
                           "DESCUENTO A PIE DE FACTURA",
                           "DESCUENTO PIE DE FACTURA"],
    # Impuestos que la empresa asume (rete fuente, ICA... ASUMIDA): HELISA
    # los suma al total del documento pero la DIAN reporta la factura sin
    # ellos. Se buscan en el nombre de la cuenta o en el concepto.
    "palabras_asumidos": ["ASUMID"],
    # Tambien cuentas de impuestos asumidos del PUC (5315 gastos
    # extraordinarios) cuyo nombre es de un impuesto o retencion, p. ej.
    # 53152502 RETEICA COMERCIAL.
    "cuentas_asumidos": ["5315"],
    "palabras_impuesto_asumido": ["RETE", "RTE", "ICA", "IMPUEST", "IVA",
                                  "GMF"],
    # v6.4: TODAS las tolerancias en 0 por defecto: la contabilidad debe
    # cuadrar exacta, centavos incluidos. Se pueden subir en la pantalla
    # (Parametros) solo para un caso puntual.
    # Diferencias de hasta este valor entre el total HELISA y el total
    # DIAN de una misma factura se tratan como redondeo.
    "tolerancia_redondeo": 0.0,
    # Cruce por NIT y valor cuando el numero no coincide (folio mal
    # digitado): diferencia maxima aceptada.
    "tolerancia_folio": 0.0,
    # Diferencia maxima (total o IVA por concepto) para marcar CONCILIADO.
    "tolerancia_estado": 0.0,
    # Diferencia maxima de IVA por documento (DIAN vs HELISA).
    "tolerancia_iva": 0.0,
    # Forma de pago DIAN.
    "formas_pago": {"1": "CONTADO", "2": "CREDITO"},
    # Prefijos de folio de los eventos (Application response) emitidos por
    # la empresa. None = deteccion automatica.
    "prefijo_acuse_1": None,
    "prefijo_acuse_2": None,
    "prefijo_acuse_3": None,
}

TIPO_EVENTO = "Application response"

# Estilos del libro Excel de salida (tomados del formato manual de referencia)
VERDE_ENCABEZADO = "348441"
CIAN_REVISADO = "66FFFF"
AZUL_NO_DIAN = "DDEBF7"
AMARILLO = "FFFF00"
ROJO_SUAVE = "FFC7CE"
FORMATO_CONTABLE = '_-* #,##0.00_-;\\-* #,##0.00_-;_-* "-"??_-;_-@_-'

# Resaltado de alertas en los Excel de salida (v4.5). Convencion comun:
#   rojo     = falta en uno de los dos documentos (no contabilizada)
#   morado   = posible faltante deducido de un informe Resumen (v5.6: antes
#              era naranja claro y se confundia con el rojo claro)
#   amarillo = esta en los dos pero hay que revisar (valor, IVA, folio,
#              gasto no deducible, acuse)
#   azul     = esta en HELISA pero no en la DIAN
ROJO_ALERTA = "FF9B9B"
LETRA_ROJA_ALERTA = "9C0006"
MORADO_ALERTA = "C9B8F0"
AZUL_ALERTA = "9BC2E6"
AZUL_ASUMIDOS = "B7DEE8"     # fila de impuestos asumidos (simplificado)
ROJO_DIFERENCIA = "C00000"
CONVENCIONES_DIAN = [
    (ROJO_ALERTA, "Documento DIAN no contabilizado en HELISA"),
    (MORADO_ALERTA, "Posible documento no contabilizado (deducido del "
                     "informe Resumen: confirmar con el Detalle)"),
    (AMARILLO, "Está en los dos pero hay que revisar: valor, IVA, folio, "
               "gasto no deducible o acuse"),
    (AZUL_ALERTA, "Registrado en HELISA pero no está en el reporte DIAN"),
    (CIAN_REVISADO, "Conciliado (igual o con redondeo)"),
]


# Medio centavo: NO es una tolerancia contable. Solo absorbe el ruido de los
# calculos con decimales binarios (0,1 + 0,2 = 0,30000000000000004), para
# que "exacto al centavo" no falle por la forma en que el computador guarda
# los numeros. Cualquier diferencia de 1 centavo o mas se reporta.
RUIDO_DECIMAL = 0.005
# Diferencia de IVA aceptada por documento (DIAN vs HELISA). 0 = exacto.
TOLERANCIA_IVA_DOCUMENTO = 0.0


def dentro_de(diferencia, tolerancia=0.0):
    """True si |diferencia| <= tolerancia (exacto al centavo si es 0)."""
    return abs(float(diferencia or 0)) <= float(tolerancia or 0) \
        + RUIDO_DECIMAL


def resaltar_si_no_es_cero(hoja, rango, tolerancia=0.0, fondo=ROJO_DIFERENCIA,
                           letra="FFFFFF"):
    """
    Formato condicional: las celdas del rango cuyo valor absoluto supera la
    tolerancia se pintan (sirve para celdas con formula, cuyo valor solo se
    conoce al abrir el archivo).
    """
    from openpyxl.formatting.rule import FormulaRule
    from openpyxl.styles import Font, PatternFill
    primera = rango.split(":")[0].replace("$", "")
    regla = FormulaRule(
        formula=[f'AND(ISNUMBER({primera}),'
                 f'ABS(ROUND({primera},2))>{tolerancia})'],
        fill=PatternFill("solid", fgColor=fondo, bgColor=fondo),
        font=Font(bold=True, color=letra), stopIfTrue=False)
    hoja.conditional_formatting.add(rango, regla)


def alerta_documento_dian(resultado, j, factura, reporte, formas=None):
    """
    Estado de un documento del reporte DIAN frente a HELISA para pintar su
    fila en los Excel: (color, texto, es_alerta).
    """
    if resultado["modo"] != "detalle":
        posible = (resultado.get("posibles") or {}).get(j)
        if posible:
            return MORADO_ALERTA, posible, True
        return None, "", False
    doc = resultado["dian_a_helisa"].get(j)
    if doc is None:
        return ROJO_ALERTA, "NO CONTABILIZADA EN HELISA", True
    partes, alerta = [], False
    if doc["estado"] == "ok":
        partes.append(f"OK - {doc['documento']}")
    elif doc["estado"] == "redondeo":
        partes.append(f"REDONDEO ({doc['diferencia']:,.2f}) - "
                      f"{doc['documento']}")
    else:
        partes.append(f"DIFERENCIA DE VALOR: HELISA "
                      f"{doc['total_debito']:,.2f} (DIF. "
                      f"{doc['diferencia']:,.2f}) - {doc['documento']}")
        alerta = True
    if doc.get("descuento") and doc["estado"] != "diferencia":
        partes.append(f"DESCUENTO COMERCIAL {doc['descuento']:,.2f} EN "
                      "HELISA")
    if doc.get("asumido") and doc["estado"] != "diferencia":
        partes.append(f"IMPUESTOS ASUMIDOS {doc['asumido']:,.2f} EN HELISA")
    if doc.get("nivel") == 4:
        partes.append("FOLIO DIFERENTE EN HELISA: VERIFICAR NÚMERO")
        alerta = True
    if doc.get("cruce_interno"):
        partes.append(f"CRUCE DE CUENTAS {doc['cruce_interno']:,.2f} EN "
                      "HELISA (SE COMPARA EL NETO)")
    if doc.get("nit_distinto"):
        nh, nd = doc["nit_distinto"]
        partes.append(f"NIT EN HELISA {nh} VS DIAN {nd}")
        if doc.get("nit_distinto_revisar"):
            alerta = True
    if doc.get("dif_iva") is not None and not dentro_de(
            doc["dif_iva"], TOLERANCIA_IVA_DOCUMENTO):
        partes.append(f"IVA DIFERENTE: DIAN {doc['iva_dian']:,.2f} VS "
                      f"HELISA {doc['iva']:,.2f}")
        alerta = True
    if doc.get("no_deducible"):
        partes.append("GASTO NO DEDUCIBLE")
        alerta = True
    acuse = (resultado.get("acuses") or {}).get(id(factura)) or []
    if "NO" in acuse:
        faltan = [f"ACUSE {i + 1}" for i, a in enumerate(acuse) if a == "NO"]
        partes.append("SIN " + ", ".join(faltan) + " EN EL REPORTE (VER "
                      "HOJA ACUSES)")
        alerta = True
    return (AMARILLO if alerta else CIAN_REVISADO), " / ".join(partes), alerta


def posibles_no_contabilizadas(reporte, facturas, diferencia, dif_iva,
                               tolerancia=0.0, maximo=3):
    """
    Con un informe Resumen de HELISA no se sabe que factura falta. Si el
    total DIAN es mayor que el de HELISA, se buscan 1, 2 o 3 documentos
    DIAN cuya suma explique la diferencia (se prefiere la combinacion cuyo
    IVA tambien cuadre). Devuelve {indice: texto} o {}.
    """
    tolerancia = float(tolerancia or 0) + RUIDO_DECIMAL
    if diferencia is None or diferencia <= tolerancia or not facturas:
        return {}
    totales = [round(numero(dato(reporte, f, "Total")), 2) for f in facturas]
    ivas = [round(numero(dato(reporte, f, "IVA")), 2) for f in facturas]
    candidatas = []

    def agregar(indices):
        iva = sum(ivas[i] for i in indices)
        cuadra_iva = dif_iva is not None and abs(iva - dif_iva) <= tolerancia
        candidatas.append((not cuadra_iva, len(indices), tuple(indices)))

    for i, t in enumerate(totales):
        if abs(t - diferencia) <= tolerancia:
            agregar([i])
    if not candidatas and maximo >= 2:
        por_valor = defaultdict(list)
        for i, t in enumerate(totales):
            por_valor[round(t)].append(i)
        for i, t in enumerate(totales):
            for delta in (-1, 0, 1):
                for k in por_valor.get(round(diferencia - t) + delta, []):
                    if k > i and abs(t + totales[k] - diferencia) <= tolerancia:
                        agregar([i, k])
    if not candidatas and maximo >= 3 and len(totales) <= 150:
        for trio in combinations(range(len(totales)), 3):
            if abs(sum(totales[i] for i in trio) - diferencia) <= tolerancia:
                agregar(list(trio))
                if len(candidatas) > 20:
                    break
    if not candidatas:
        return {}
    candidatas.sort()
    mejores = [c for c in candidatas if c[:2] == candidatas[0][:2]][:5]
    unica = len(mejores) == 1
    salida = {}
    for _, _, indices in mejores:
        for i in indices:
            salida[i] = (
                "POSIBLE NO CONTABILIZADA EN HELISA: "
                + ("explica" if unica else "podría explicar")
                + f" la diferencia de {diferencia:,.2f} del informe Resumen"
                + ("" if unica else " (hay varias combinaciones posibles)")
                + ". Confirmar con el Comprobante diario - Detalle.")
    return salida


def dato(reporte, registro, columna, defecto=None):
    i = reporte["indice"].get(columna)
    return registro[i] if i is not None else defecto
